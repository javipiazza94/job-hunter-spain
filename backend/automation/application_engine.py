"""
automation/application_engine.py — Orchestrates automatic CV submissions.
Reads relevant offers, picks best contact, sends email or fills form.

Usage:
  python -m automation.application_engine --dry-run
  python -m automation.application_engine --limit 5
"""
import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import MAX_EMAILS_PER_DAY, PROFILE_PATH, CV_DIR
from database import get_conn, get_pending_offers, record_application, stats
from automation.cover_letter import generate as generate_letter
from automation.email_sender import rate_limited_send

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _load_profile() -> dict:
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


SAP_KEYWORDS = {"sap", "abap", "btp", "s/4hana", "hana", "s4", "fiori"}


def _cv_path(job_title: str | None = None, description: str | None = None) -> Path | None:
    """Return SAP CV if the offer is SAP-related, IA CV otherwise."""
    profile = _load_profile()
    text = ((job_title or "") + " " + (description or "")).lower()
    is_sap = any(kw in text for kw in SAP_KEYWORDS)
    key = "cv_sap_path" if is_sap else "cv_ia_path"
    cv_rel = profile.get(key) or profile.get("cv_path", "")
    cv = Path(__file__).parent.parent / cv_rel
    return cv if cv.exists() else None


def _emails_sent_today(conn) -> int:
    today = date.today().isoformat()
    row = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE method='email' AND sent_at LIKE ?",
        (f"{today}%",),
    ).fetchone()
    return row[0]


def _get_best_contact(conn, company_id: str) -> dict | None:
    rows = conn.execute(
        "SELECT * FROM contacts WHERE company_id=? ORDER BY type='email' DESC, verified DESC LIMIT 1",
        (company_id,),
    ).fetchall()
    return dict(rows[0]) if rows else None


def run_applications(dry_run: bool = False, limit: int | None = None) -> int:
    profile = _load_profile()
    personal = profile.get("personal", {})

    conn = get_conn()
    today_count = _emails_sent_today(conn)
    remaining = MAX_EMAILS_PER_DAY - today_count
    if remaining <= 0 and not dry_run:
        logger.warning("Daily email limit (%d) reached. Stopping.", MAX_EMAILS_PER_DAY)
        conn.close()
        return 0

    pending = get_pending_offers(conn)
    logger.info("Pending relevant offers: %d | Daily limit remaining: %d", len(pending), remaining)

    applied = 0
    for offer in pending:
        if limit and applied >= limit:
            break
        if not dry_run and applied >= remaining:
            logger.info("Daily limit reached (%d). Stopping.", MAX_EMAILS_PER_DAY)
            break

        company_name = offer["company_name"]
        job_title = offer["title"]
        contact = _get_best_contact(conn, offer["company_id"])

        if not contact:
            logger.info("SKIP (no contact): %s — %s", company_name, job_title)
            continue

        cv = _cv_path(job_title, offer.get("description"))
        if not cv and not dry_run:
            logger.warning("CV not found for offer: %s", job_title)

        cover_letter = generate_letter(
            company_name=company_name,
            job_title=job_title,
            tech_stack=offer.get("tech_stack"),
            template="tech",
        )

        if contact["type"] == "email":
            subject = f"Candidatura — {personal.get('name', '')} | Python · Data Science · SAP"
            if job_title:
                subject = f"Solicitud: {job_title} — {personal.get('name', '')}"

            logger.info("SEND email → %s: %s | %s", contact["value"], company_name, job_title)
            success = rate_limited_send(
                to=contact["value"],
                subject=subject,
                body=cover_letter,
                cv_path=cv,
                dry_run=dry_run,
            )
        elif contact["type"] == "form":
            from automation.form_filler import fill_form
            logger.info("FORM → %s: %s", company_name, contact["value"])
            success = fill_form(
                form_url=contact["value"],
                profile=profile,
                cv_path=cv,
                cover_letter=cover_letter,
                dry_run=dry_run,
            )
            if not success and not dry_run:
                record_application(conn, {
                    "company_id": offer["company_id"],
                    "job_offer_id": offer["id"],
                    "contact_id": contact["id"],
                    "method": "form",
                    "status": "needs_manual_review",
                    "notes": f"Form fill failed: {contact['value']}",
                })

        if success:
            if not dry_run:
                record_application(conn, {
                    "company_id": offer["company_id"],
                    "job_offer_id": offer["id"],
                    "contact_id": contact["id"],
                    "method": contact["type"],
                    "cover_letter_used": cover_letter,
                    "status": "sent",
                })
            applied += 1
            logger.info("  ✓ Applied (%d) — %s", applied, company_name)

    conn.close()
    logger.info("Applications this run: %d", applied)
    return applied


def main():
    parser = argparse.ArgumentParser(description="Job Hunter Spain — Application Engine")
    parser.add_argument("--dry-run", action="store_true", help="Print without sending")
    parser.add_argument("--limit", type=int, default=None, help="Max applications this run")
    args = parser.parse_args()
    run_applications(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
