"""
scraper/runner.py — CLI orchestrator for all scrapers.
Usage:
  python -m scraper.runner --source seed
  python -m scraper.runner --source tecnoempleo --dry-run
  python -m scraper.runner --source contacts
  python -m scraper.runner --source all
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import get_conn, init_db, upsert_company, upsert_job_offer, stats
from scraper.seed_loader import load_seed
from automation.filter_engine import score_offer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def run_tecnoempleo_source(dry_run: bool, max_pages: int):
    from scraper.tecnoempleo import run_tecnoempleo
    offers = await run_tecnoempleo(max_pages=max_pages)
    if dry_run:
        logger.info("[DRY-RUN] Would save %d offers", len(offers))
        for o in offers[:10]:
            logger.info("  %s | %s | %s", o.get("title"), o.get("company_name"), o.get("location"))
        return

    conn = get_conn()
    saved = 0
    for offer in offers:
        # Resolve or create company
        company_row = conn.execute(
            "SELECT id FROM companies WHERE name = ?", (offer.get("company_name", ""),)
        ).fetchone()
        if not company_row:
            cid = upsert_company(conn, {
                "name": offer.get("company_name", "Desconocida"),
                "source": "tecnoempleo",
            })
        else:
            cid = company_row["id"]

        score = score_offer(offer)
        upsert_job_offer(conn, {
            **offer,
            "company_id": cid,
            "is_relevant": score >= 0.55,
            "relevance_score": score,
        })
        saved += 1
    conn.close()
    logger.info("Tecnoempleo: %d offers saved to DB", saved)


async def run_contacts_source(dry_run: bool):
    from scraper.contact_extractor import run_contact_extraction
    conn = get_conn()
    companies = [
        dict(row) for row in conn.execute(
            "SELECT id, name, website, careers_url FROM companies WHERE website IS NOT NULL"
        ).fetchall()
    ]
    conn.close()
    logger.info("Extracting contacts for %d companies...", len(companies))
    if dry_run:
        logger.info("[DRY-RUN] Would process %d companies", len(companies))
        return
    found = await run_contact_extraction(companies)
    logger.info("Contacts extraction complete: %d contacts found", found)


async def run_sap_source(dry_run: bool, max_pages: int):
    from scraper.tecnoempleo import TecnoempleoScraper
    from scraper.infojobs import run_infojobs
    from scraper.computrabajo import run_computrabajo
    from scraper.company_direct import run_company_direct
    from scraper.linkedin_jobs import run_linkedin_jobs
    from config import SAP_KEYWORDS, TECNOEMPLEO_LOCATIONS

    conn = get_conn()

    def _save_offers(offers: list[dict], source_name: str):
        if dry_run:
            logger.info("[DRY-RUN] %s: would save %d offers", source_name, len(offers))
            for o in offers[:5]:
                logger.info("  %s | %s", o.get("title"), o.get("company_name"))
            return
        saved = 0
        for offer in offers:
            if not offer.get("url"):
                continue
            company_name = offer.get("company_name") or "Desconocida"
            row = conn.execute(
                "SELECT id FROM companies WHERE name=?", (company_name,)
            ).fetchone()
            cid = row["id"] if row else upsert_company(
                conn, {"name": company_name, "source": offer.get("source", "sap")}
            )
            sc = score_offer(offer)
            upsert_job_offer(conn, {
                **offer, "company_id": cid,
                "is_relevant": sc >= 0.55, "relevance_score": sc,
            })
            saved += 1
        logger.info("%s: %d offers saved", source_name, saved)

    try:
        logger.info("── Tecnoempleo (SAP keywords) ──────")
        sap_scraper = TecnoempleoScraper()
        seen: set[str] = set()
        sap_offers: list[dict] = []
        for kw in SAP_KEYWORDS:
            for loc in TECNOEMPLEO_LOCATIONS:
                for o in await sap_scraper.scrape_keyword(kw, loc, max_pages):
                    if o.get("url") and o["url"] not in seen:
                        seen.add(o["url"])
                        sap_offers.append(o)
        _save_offers(sap_offers, "Tecnoempleo-SAP")
    except Exception as e:
        logger.error("Tecnoempleo SAP failed: %s", e)

    try:
        logger.info("── InfoJobs ────────────────────────")
        _save_offers(await run_infojobs(SAP_KEYWORDS, max_pages), "InfoJobs")
    except Exception as e:
        logger.error("InfoJobs failed: %s", e)

    try:
        logger.info("── Computrabajo ────────────────────")
        _save_offers(await run_computrabajo(SAP_KEYWORDS, max_pages), "Computrabajo")
    except Exception as e:
        logger.error("Computrabajo failed: %s", e)

    try:
        logger.info("── Company direct (SEIDOR etc.) ────")
        found, contacts = await run_company_direct(dry_run)
        logger.info("Company direct: %d offers, %d contacts", found, contacts)
    except Exception as e:
        logger.error("Company direct failed: %s", e)

    try:
        logger.info("── LinkedIn ────────────────────────")
        _save_offers(await run_linkedin_jobs(), "LinkedIn")
    except Exception as e:
        logger.error("LinkedIn failed: %s", e)

    conn.close()


def print_stats():
    conn = get_conn()
    s = stats(conn)
    conn.close()
    logger.info("── Database stats ──────────────────")
    for k, v in s.items():
        logger.info("  %-25s %d", k, v)


def main():
    parser = argparse.ArgumentParser(description="Job Hunter Spain — Scraper Runner")
    parser.add_argument(
        "--source",
        choices=["seed", "tecnoempleo", "contacts", "all", "sap", "linkedin-login"],
        default="seed",
        help="Data source to run",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print results without saving")
    parser.add_argument("--max-pages", type=int, default=3, help="Max pages per keyword")
    args = parser.parse_args()

    conn = get_conn()
    init_db(conn)
    conn.close()

    if args.source in ("seed", "all"):
        logger.info("── Seed loader ─────────────────────")
        if not args.dry_run:
            load_seed()
        else:
            logger.info("[DRY-RUN] Would load seed companies")

    if args.source in ("tecnoempleo", "all"):
        logger.info("── Tecnoempleo scraper ─────────────")
        asyncio.run(run_tecnoempleo_source(args.dry_run, args.max_pages))

    if args.source in ("contacts", "all"):
        logger.info("── Contact extractor ───────────────")
        asyncio.run(run_contacts_source(args.dry_run))

    if args.source == "sap":
        logger.info("── SAP multi-portal scraper ────────")
        asyncio.run(run_sap_source(args.dry_run, args.max_pages))

    if args.source == "linkedin-login":
        logger.info("── LinkedIn login (headful) ─────────")
        from scraper.linkedin_jobs import run_linkedin_login
        asyncio.run(run_linkedin_login())
        return

    print_stats()


if __name__ == "__main__":
    main()
