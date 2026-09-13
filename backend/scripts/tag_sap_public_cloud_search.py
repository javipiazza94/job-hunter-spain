"""
scripts/tag_sap_public_cloud_search.py — one-off backfill.

Tags the job_offers already saved by the 2026-09-13 "SAP S/4HANA Cloud Public Edition,
Tier 1/2/3 companies" search (see conversation) with sap_tier / sap_module / open_to_junior,
so the frontend can show them in their own "SAP Public Cloud" tab.

Run once: python -m scripts.tag_sap_public_cloud_search
"""
import json
import logging
from pathlib import Path

from database import get_conn, init_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATA_FILE = Path(__file__).parent / "_sap_tags_data.json"


def main():
    rows = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    conn = get_conn()
    init_db(conn)

    tagged, missing = 0, []
    for row in rows:
        cur = conn.execute(
            "UPDATE job_offers SET sap_tier = ?, sap_module = ?, open_to_junior = ? WHERE url = ?",
            (row["sap_tier"], row["sap_module"], row["open_to_junior"], row["url"]),
        )
        if cur.rowcount == 0:
            missing.append(f"{row['empresa']} — {row['titulo']}")
        else:
            tagged += 1
    conn.commit()
    conn.close()

    logger.info("Tagged %d/%d ofertas", tagged, len(rows))
    if missing:
        logger.warning("No encontradas en job_offers (no se tagearon, no se inventó nada):")
        for m in missing:
            logger.warning("  - %s", m)


if __name__ == "__main__":
    main()
