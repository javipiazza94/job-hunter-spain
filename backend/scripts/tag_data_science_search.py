"""
scripts/tag_data_science_search.py — one-off backfill.

Tags the job_offers from the 2026-09-13 "Data Science / IA, Tier 1/2/3 companies"
search (see conversation) with ds_tier / ds_category / open_to_junior, so the
frontend can show them in their own "Data Science / IA" tab.

The Navantia offer was found via direct WebFetch on the official portal (not by
any scraper), so it doesn't exist in job_offers yet — this script inserts it
first (company + offer), the same way the scrapers do, then tags everything.

Run once: python -m scripts.tag_data_science_search
"""
import logging

from database import get_conn, init_db, upsert_company, upsert_job_offer

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

NAVANTIA_OFFER = {
    "company": {
        "name": "Navantia",
        "website": "https://www.navantia.es",
        "careers_url": "https://empleo.navantia.es",
        "sector": "Defensa/Naval",
        "country": "ES",
        "source": "manual_websearch",
    },
    "offer": {
        "title": "3499 - Ingeniero/a Junior para Inteligencia Artificial",
        "location": "San Fernando (Cádiz)",
        "salary_min": 29644,
        "salary_max": 35203,
        "salary_text": "29.644,47 € - 35.202,91 € (nivel D4-D3, convenio colectivo)",
        "description": (
            "Implementacion de iniciativas estrategicas de IA, desarrollo de metodologias, "
            "integracion de tecnologias de IA en productos Navantia, gestion de proyectos "
            "Big Data/ML/LLM/Computer Vision, vigilancia en ciberseguridad, colaboracion I+D "
            "con universidades y empresas. Contrato indefinido. Plazo de solicitud: "
            "15 de septiembre de 2026, 12:00h. Certificaciones valoradas: ISO/IEC 42001, "
            "TensorFlow Developer, Azure Data Scientist, Google Cloud Professional ML Engineer."
        ),
        "url": "https://empleo.navantia.es/job/SF-San-Fernando-3499-Ingenieroa-Junior-para-Inteligencia-Artificial-CA/1362912455/",
        "source": "manual_websearch",
    },
}

# (url, ds_tier, ds_category, open_to_junior)
TAGS = [
    (NAVANTIA_OFFER["offer"]["url"], 1, "Data Scientist / ML Engineer", 1),
    ("https://www.tecnoempleo.com/senior-data-engineer-sap-bi-airbus/sap-bw-hana/rf-99831edf12cdf30f7f4e", 1, "Data Engineer / ETL", 0),
    ("https://www.tecnoempleo.com/ingeniero-ia-generativa-deloitte/python-tensorflow/rf-22ab1a67f2405372fd4d", 2, "LLM/RAG/GenAI", 0),
    ("https://www.tecnoempleo.com/consultor-ai-especializado-generative-ai-deloitte/openai-machine-learning/rf-f8881e9892f5a3624f4c", 2, "LLM/RAG/GenAI", 0),
    ("https://www.tecnoempleo.com/consultor-ai-especializado-a-deloitte/inteligencia-artificial-generative-a/rf-d2ee100802e6e3fb5740", 2, "LLM/RAG/GenAI", 0),
    ("https://www.tecnoempleo.com/desarrollador-senior-ia-generativa-accenture/inteligencia-artificial-machi/rf-fab816afa26413d3fa4d", 2, "LLM/RAG/GenAI", 0),
    ("https://www.tecnoempleo.com/agentic-commerce-ai-lead-consumer-goods-accenture/generative-ai-agentic-ai/rf-9ccb16143247336eae4b", 2, "LLM/RAG/GenAI", 0),
    ("https://www.tecnoempleo.com/manager-generative-ai-llm-agentic-ai-accenture/azure-openai/rf-8c5e1e204276f34d5c43", 2, "LLM/RAG/GenAI", 0),
    ("https://www.tecnoempleo.com/data-ai-architect-agentic-commerce-accenture/inteligencia-artificial-machi/rf-a34d130ce2c4c38a9f48", 2, "Data Scientist / ML Engineer", 0),
    ("https://www.tecnoempleo.com/threat-intel-data-scientist-cyber-deloitte/python-sql/rf-27991b3b5247b3003b48", 2, "Data Scientist / ML Engineer", 0),
    ("https://www.tecnoempleo.com/cloud-ai-platform-architect-m-f-d-t-systems/ia-generativa-arquitectura-clo/rf-bc4a1c7ad24563680644", 3, "LLM/RAG/GenAI", 0),
]


def main():
    conn = get_conn()
    init_db(conn)

    existing = conn.execute(
        "SELECT id FROM job_offers WHERE url = ?", (NAVANTIA_OFFER["offer"]["url"],)
    ).fetchone()
    if not existing:
        cid = upsert_company(conn, NAVANTIA_OFFER["company"])
        upsert_job_offer(conn, {**NAVANTIA_OFFER["offer"], "company_id": cid, "is_relevant": 1, "relevance_score": 0.9})
        logger.info("Navantia offer inserted (no existia en job_offers)")
    else:
        logger.info("Navantia offer ya existia en job_offers")

    tagged, missing = 0, []
    for url, ds_tier, ds_category, open_to_junior in TAGS:
        cur = conn.execute(
            "UPDATE job_offers SET ds_tier = ?, ds_category = ?, open_to_junior = ? WHERE url = ?",
            (ds_tier, ds_category, open_to_junior, url),
        )
        if cur.rowcount == 0:
            missing.append(url)
        else:
            tagged += 1
    conn.commit()
    conn.close()

    logger.info("Tagged %d/%d ofertas", tagged, len(TAGS))
    if missing:
        logger.warning("No encontradas en job_offers (no se tagearon, no se inventó nada):")
        for m in missing:
            logger.warning("  - %s", m)


if __name__ == "__main__":
    main()
