"""
automation/application_engine.py — Orchestrates CV submissions in two stages:
  1. create_drafts() — generates pending_approval applications (no email sent)
  2. send_approved(id) — approves and sends a single pending application
"""
import logging
from datetime import date, datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import MAX_EMAILS_PER_DAY, PROFILE_PATH, RECONTACT_COOLDOWN_DAYS
from database import (
    get_conn,
    get_pending_offers,
    record_application,
    record_history,
)
from automation.cover_letter import generate as generate_letter
from automation.email_sender import send_email
from automation.filter_engine import classify_profile
from automation.form_filler import fill_form

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

import json as _json


def _load_profile() -> dict:
    return _json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def _get_best_contact(conn, company_id: str) -> dict | None:
    rows = conn.execute(
        "SELECT * FROM contacts WHERE company_id=? ORDER BY type='email' DESC, verified DESC LIMIT 1",
        (company_id,),
    ).fetchall()
    return dict(rows[0]) if rows else None


def _emails_sent_today(conn) -> int:
    today = date.today().isoformat()
    row = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE method='email' AND status='sent' AND sent_at LIKE ?",
        (f"{today}%",),
    ).fetchone()
    return row[0]


def _is_recently_contacted(conn, company_id: str, contact_value: str) -> bool:
    row = conn.execute(
        """SELECT 1 FROM applications a
           JOIN contacts ct ON a.contact_id = ct.id
           WHERE a.company_id = ? AND ct.value = ?
             AND a.status NOT IN ('rejected_manual', 'pending_approval')
             AND a.sent_at > datetime('now', ?)
           LIMIT 1""",
        (company_id, contact_value, f"-{RECONTACT_COOLDOWN_DAYS} days"),
    ).fetchone()
    return row is not None


def _cv_path_from_profile(cv_profile: str, profile: dict) -> Path | None:
    key = "cv_sap_path" if cv_profile == "sap" else "cv_ia_path"
    cv_rel = profile.get(key) or profile.get("cv_path", "")
    cv = Path(__file__).parent.parent / cv_rel
    return cv if cv.exists() else None


def create_drafts(limit: int | None = None) -> dict:
    """
    Generate pending_approval application drafts without sending any email.
    Returns a summary dict with counts.
    """
    conn = get_conn()
    pending = get_pending_offers(conn)
    results = {
        "drafts_created": 0,
        "skipped_manual_review": 0,
        "skipped_duplicate": 0,
        "skipped_no_contact": 0,
    }

    for offer in pending:
        if limit and results["drafts_created"] >= limit:
            break

        offer = dict(offer)
        cv_profile, _confidence = classify_profile(offer)

        if cv_profile == "manual_review":
            results["skipped_manual_review"] += 1
            logger.info("SKIP manual_review: %s", offer.get("title"))
            continue

        contact = _get_best_contact(conn, offer["company_id"])
        if not contact:
            results["skipped_no_contact"] += 1
            logger.info("SKIP no_contact: %s", offer.get("company_name"))
            continue

        if contact.get("type") != "email":
            results["skipped_no_contact"] += 1
            logger.info("SKIP non-email contact (%s): %s", contact.get("type"), offer.get("company_name"))
            continue

        if _is_recently_contacted(conn, offer["company_id"], contact["value"]):
            results["skipped_duplicate"] += 1
            logger.info("SKIP duplicate: %s", offer.get("company_name"))
            continue

        template = "sap" if cv_profile == "sap" else "tech"
        cover_letter = generate_letter(
            company_name=offer["company_name"],
            job_title=offer["title"],
            tech_stack=offer.get("tech_stack"),
            template=template,
            variant_seed=offer["company_name"] + (offer.get("title") or ""),
        )

        # record_application commits internally
        record_application(conn, {
            "company_id": offer["company_id"],
            "job_offer_id": offer["id"],
            "contact_id": contact["id"],
            "method": contact["type"],
            "status": "pending_approval",
            "cover_letter_used": cover_letter,
            "cv_profile": cv_profile,
        })
        results["drafts_created"] += 1
        logger.info("DRAFT created: %s — %s", offer.get("company_name"), offer.get("title"))

    conn.close()
    logger.info("Drafts summary: %s", results)
    return results


def fill_forms(limit: int | None = None, dry_run: bool = False) -> dict:
    """
    Fill (never submit) application forms for pending offers whose best contact
    is a detected form URL (not an email). Opens a real, visible browser window
    per offer and pauses for manual review/submit before moving to the next one.
    """
    conn = get_conn()
    pending = get_pending_offers(conn)
    profile = _load_profile()
    results = {
        "forms_filled": 0,
        "needs_manual_review": 0,
        "skipped_manual_review": 0,
        "skipped_no_form": 0,
        "skipped_duplicate": 0,
    }

    for offer in pending:
        if limit and results["forms_filled"] >= limit:
            break

        offer = dict(offer)
        cv_profile, _confidence = classify_profile(offer)

        if cv_profile == "manual_review":
            results["skipped_manual_review"] += 1
            logger.info("SKIP manual_review: %s", offer.get("title"))
            continue

        contact = _get_best_contact(conn, offer["company_id"])
        if not contact or contact.get("type") != "form":
            results["skipped_no_form"] += 1
            continue

        if _is_recently_contacted(conn, offer["company_id"], contact["value"]):
            results["skipped_duplicate"] += 1
            logger.info("SKIP duplicate: %s", offer.get("company_name"))
            continue

        template = "sap" if cv_profile == "sap" else "tech"
        cover_letter = generate_letter(
            company_name=offer["company_name"],
            job_title=offer["title"],
            tech_stack=offer.get("tech_stack"),
            template=template,
            variant_seed=offer["company_name"] + (offer.get("title") or ""),
        )
        cv = _cv_path_from_profile(cv_profile, profile)
        form_url = contact["value"]

        logger.info("Filling form: %s — %s (%s)", offer.get("company_name"), offer.get("title"), form_url)
        ok = fill_form(
            form_url, profile, cv, cover_letter,
            dry_run=dry_run, headless=False, pause_for_review=not dry_run,
        )

        if not dry_run:
            status = "form_filled_pending_review" if ok else "needs_manual_review"
            record_application(conn, {
                "company_id": offer["company_id"],
                "job_offer_id": offer["id"],
                "contact_id": contact["id"],
                "method": "form",
                "status": status,
                "cover_letter_used": cover_letter,
                "cv_profile": cv_profile,
                "notes": form_url,
            })

        if ok:
            results["forms_filled"] += 1
        else:
            results["needs_manual_review"] += 1
            logger.warning("Form needs manual review: %s — %s", offer.get("company_name"), form_url)

    conn.close()
    logger.info("Fill-forms summary: %s", results)
    return results


def send_approved(application_id: str) -> bool:
    """
    Send a single pending_approval application.
    Raises ValueError if not found or daily limit reached.
    Returns True on success.
    """
    conn = get_conn()

    today_count = _emails_sent_today(conn)
    if today_count >= MAX_EMAILS_PER_DAY:
        conn.close()
        raise ValueError(f"Daily email limit ({MAX_EMAILS_PER_DAY}) reached.")

    row = conn.execute(
        """SELECT a.*, c.name as company_name, jo.title as job_title,
                  ct.value as contact_value, ct.type as contact_type
           FROM applications a
           LEFT JOIN companies c ON a.company_id = c.id
           LEFT JOIN job_offers jo ON a.job_offer_id = jo.id
           LEFT JOIN contacts ct ON a.contact_id = ct.id
           WHERE a.id = ? AND a.status = 'pending_approval'""",
        (application_id,),
    ).fetchone()

    if not row:
        conn.close()
        raise ValueError(f"Application {application_id} not found or not in pending_approval status.")

    profile = _load_profile()
    personal = profile.get("personal", {})

    app = dict(row)
    cv_profile = app.get("cv_profile") or "ia_dev"
    cv = _cv_path_from_profile(cv_profile, profile)

    body = app.get("cover_letter_edited") or app.get("cover_letter_used") or ""
    subject = (
        f"Solicitud: {app['job_title']} — {personal.get('name', '')}"
        if app.get("job_title")
        else f"Candidatura — {personal.get('name', '')}"
    )

    success = send_email(
        to=app["contact_value"],
        subject=subject,
        body=body,
        cv_path=cv,
        dry_run=False,
    )

    if success:
        now = datetime.now().isoformat()
        conn.execute(
            "UPDATE applications SET status='sent', sent_at=?, approved_at=? WHERE id=?",
            (now, now, application_id),
        )
        domain = app["contact_value"].split("@")[-1] if "@" in (app.get("contact_value") or "") else ""
        record_history(conn, {
            "company_name": app.get("company_name", ""),
            "company_domain": domain,
            "email_used": app.get("contact_value", ""),
            "profile_used": cv_profile,
            "sent_at": now,
            "application_id": application_id,
        })
        conn.commit()

    conn.close()
    return success


# ── Legacy CLI entry point (kept for backward compatibility) ──────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Job Hunter Spain — Application Engine")
    parser.add_argument(
        "command", nargs="?", default="create-drafts",
        choices=["create-drafts", "fill-forms"],
        help="create-drafts: email drafts (default). fill-forms: fill (never submit) SuccessFactors/generic application forms.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no writes / no browser action")
    parser.add_argument("--limit", type=int, default=None, help="Max items this run")
    args = parser.parse_args()
    if args.command == "fill-forms":
        result = fill_forms(limit=args.limit, dry_run=args.dry_run)
    else:
        result = create_drafts(limit=args.limit)
    print(result)


if __name__ == "__main__":
    main()
