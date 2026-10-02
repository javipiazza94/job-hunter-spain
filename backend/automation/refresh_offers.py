"""
automation/refresh_offers.py — Daily offers refresh.

1. Discovery: runs the existing scrapers and reports new offers above MIN_RELEVANCE_SCORE.
2. Liveness: re-checks stored offer URLs and marks closed ones is_active=0 (never deletes).

Usage (from backend/):
  python -m automation.refresh_offers --dry-run
  python -m automation.refresh_offers
  python -m automation.refresh_offers --skip-discovery --max-checks 100

Cron (every day 15:01, machine in Europe/Madrid):
  1 15 * * * cd /ruta/a/job-hunter-spain/backend && .venv/bin/python -m automation.refresh_offers >> refresh.log 2>&1
"""
import argparse
import asyncio
import logging
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

from config import MIN_RELEVANCE_SCORE, SCRAPERAPI_KEY
from database import get_conn, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

ACTIVE, INACTIVE, UNKNOWN = "active", "inactive", "unknown"

CLOSED_MARKERS = [
    "oferta ya no está disponible", "oferta ya no esta disponible",
    "esta oferta ya no", "oferta caducada", "oferta finalizada", "oferta cerrada",
    "oferta no encontrada", "ha caducado", "ya no acepta", "ya no se aceptan",
    "no longer accepting applications", "this job has expired", "job is no longer available",
    "position has been filled", "no longer available",
]
BLOCK_MARKERS = ["captcha", "access denied", "unusual traffic", "are you a robot", "verify you are human"]
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 20
CHECK_DELAY = (1.0, 2.5)


def classify_response(status: int, body: str) -> str:
    """Conservative: only definitive signals mark an offer inactive; blocks/errors stay unknown."""
    if status in (404, 410):
        return INACTIVE
    if status != 200:
        return UNKNOWN
    text = (body or "").lower()
    if any(m in text for m in CLOSED_MARKERS):
        return INACTIVE
    if any(m in text for m in BLOCK_MARKERS) and len(text) < 20000:
        return UNKNOWN
    return ACTIVE


def check_offer(session: requests.Session, url: str, source: str | None) -> str:
    try:
        if source == "indeed":
            if not SCRAPERAPI_KEY:
                return UNKNOWN
            r = session.get(
                "http://api.scraperapi.com",
                params={"api_key": SCRAPERAPI_KEY, "url": url},
                timeout=60,
            )
        elif source == "linkedin":
            return UNKNOWN  # login wall: unreliable without a session
        else:
            r = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        return classify_response(r.status_code, r.text)
    except requests.RequestException as e:
        logger.debug("check failed for %s: %s", url, e)
        return UNKNOWN


def verify_offers(conn, run_started: str, max_checks: int, stale_days: int, dry_run: bool) -> dict:
    rows = conn.execute(
        """SELECT id, url, source, title, scraped_at FROM job_offers
           WHERE COALESCE(is_active, 1) = 1 AND url IS NOT NULL AND scraped_at < ?
           ORDER BY COALESCE(last_checked_at, '') ASC LIMIT ?""",
        (run_started, max_checks),
    ).fetchall()
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "es-ES,es;q=0.9"})
    stale_cutoff = (datetime.now() - timedelta(days=stale_days)).isoformat()
    result = {"checked": 0, "active": 0, "inactive": 0, "unknown": 0, "stale": 0}
    now = datetime.now().isoformat()

    for row in rows:
        verdict = check_offer(session, row["url"], row["source"])
        reason = None
        if verdict == UNKNOWN and row["scraped_at"] < stale_cutoff:
            verdict, reason = INACTIVE, f"stale>{stale_days}d"
            result["stale"] += 1
        elif verdict == INACTIVE:
            reason = "closed"
        result["checked"] += 1
        result[verdict] += 1
        if verdict == INACTIVE:
            logger.info("INACTIVA (%s): %s | %s", reason, row["title"], row["url"])
        if not dry_run:
            if verdict == INACTIVE:
                conn.execute(
                    "UPDATE job_offers SET is_active=0, inactive_reason=?, last_checked_at=? WHERE id=?",
                    (reason, now, row["id"]),
                )
            elif verdict == ACTIVE:
                conn.execute("UPDATE job_offers SET last_checked_at=? WHERE id=?", (now, row["id"]))
            conn.commit()
        time.sleep(random.uniform(*CHECK_DELAY))
    return result


def run_discovery(dry_run: bool, max_pages: int) -> None:
    from scraper import runner

    steps = [
        ("Tecnoempleo", lambda: asyncio.run(runner.run_tecnoempleo_source(dry_run, max_pages))),
        ("Manfred", lambda: runner.run_manfred_source(dry_run)),
        ("SAP multi-portal", lambda: asyncio.run(runner.run_sap_source(dry_run, max_pages))),
    ]
    if SCRAPERAPI_KEY:
        steps.insert(1, ("Indeed", lambda: asyncio.run(runner.run_indeed_source(dry_run, max_pages))))
    for name, step in steps:
        try:
            logger.info("── Discovery: %s ──", name)
            step()
        except Exception as e:
            logger.error("%s failed: %s", name, e)


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh offers: discover new + deactivate closed")
    parser.add_argument("--dry-run", action="store_true", help="No DB writes; scrapers only log")
    parser.add_argument("--skip-discovery", action="store_true")
    parser.add_argument("--skip-verify", action="store_true")
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--max-checks", type=int, default=300, help="Max URLs to re-check per run")
    parser.add_argument("--stale-days", type=int, default=60,
                        help="Unverifiable offers not seen in this many days are marked inactive")
    args = parser.parse_args()

    conn = get_conn()
    init_db(conn)
    run_started = datetime.now().isoformat()
    before_ids = {r["id"] for r in conn.execute("SELECT id FROM job_offers").fetchall()}
    conn.close()

    if not args.skip_discovery:
        run_discovery(args.dry_run, args.max_pages)

    conn = get_conn()
    new_offers = [
        r for r in conn.execute(
            """SELECT jo.id, jo.title, jo.url, jo.source, jo.relevance_score, c.name AS company
               FROM job_offers jo LEFT JOIN companies c ON c.id = jo.company_id
               WHERE jo.relevance_score >= ? AND COALESCE(jo.is_active, 1) = 1
               ORDER BY jo.relevance_score DESC""",
            (MIN_RELEVANCE_SCORE,),
        ).fetchall()
        if r["id"] not in before_ids
    ]

    verify = {"checked": 0, "active": 0, "inactive": 0, "unknown": 0, "stale": 0}
    if not args.skip_verify:
        logger.info("── Verifying stored offers ──")
        verify = verify_offers(conn, run_started, args.max_checks, args.stale_days, args.dry_run)
    totals = conn.execute(
        "SELECT COUNT(*) total, COALESCE(SUM(COALESCE(is_active,1)=1),0) active FROM job_offers"
    ).fetchone()
    conn.close()

    logger.info("══ RESUMEN %s ══", "(DRY-RUN)" if args.dry_run else "")
    logger.info("Nuevas ofertas atractivas (score >= %.2f): %d", MIN_RELEVANCE_SCORE, len(new_offers))
    for o in new_offers[:20]:
        logger.info("  + %.2f | %s | %s | %s", o["relevance_score"], o["title"], o["company"], o["url"])
    logger.info(
        "Verificadas: %d | activas: %d | marcadas inactivas: %d (stale: %d) | sin verificar: %d",
        verify["checked"], verify["active"], verify["inactive"], verify["stale"], verify["unknown"],
    )
    logger.info("DB: %s ofertas totales, %s activas", totals["total"], totals["active"])


if __name__ == "__main__":
    main()
