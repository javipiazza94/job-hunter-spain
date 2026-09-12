"""
scraper/website_resolver.py — Resuelve la web oficial de una empresa por nombre,
vía búsqueda en Bing (sin JS, sin API key).

Desbloquea contact_extractor.py: las empresas descubiertas por scraping de
portales (Tecnoempleo, Manfred, LinkedIn, InfoJobs) solo tienen la URL del
listado en el portal, no su web real, así que nunca se les puede extraer
contacto sin esto.

Nota: se probó primero con DuckDuckGo HTML (html.duckduckgo.com) pero un
burst de ~10 peticiones en pruebas bastó para que empezara a devolver
HTTP 202 (bloqueo/rate-limit) de forma persistente. Bing tolera mejor un
volumen bajo de peticiones espaciadas; aun así hay que respetar el delay
entre empresas para no repetir el problema.
"""
import logging
import random
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from config import MAX_RETRIES
from database import get_conn, upsert_company
from scraper.base import USER_AGENTS

logger = logging.getLogger(__name__)

BING_SEARCH_URL = "https://www.bing.com/search"

_BLACKLIST_DOMAINS = {
    "tecnoempleo.com", "indeed.com", "es.indeed.com", "indeed.es",
    "infojobs.net", "linkedin.com", "computrabajo.es", "getmanfred.com",
    "glassdoor.com", "glassdoor.es", "facebook.com", "instagram.com",
    "twitter.com", "x.com", "wikipedia.org", "google.com", "youtube.com",
    "infoempleo.com", "monster.es", "jooble.org", "talent.com",
    "duckduckgo.com", "bing.com",
}


def _domain_allowed(url: str) -> bool:
    netloc = urlparse(url).netloc.lower().replace("www.", "")
    if not netloc or "." not in netloc:
        return False
    return not any(netloc == b or netloc.endswith("." + b) for b in _BLACKLIST_DOMAINS)


def resolve_website(company_name: str) -> str | None:
    """Busca la web oficial de una empresa. Devuelve None si no hay match limpio."""
    query = f"{company_name} sitio oficial"
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    }

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(
                BING_SEARCH_URL, params={"q": query, "setlang": "es"},
                headers=headers, timeout=15,
            )
            if resp.status_code == 200:
                break
            logger.warning("Bing HTTP %s for %r (attempt %d)", resp.status_code, company_name, attempt + 1)
        except requests.RequestException as e:
            logger.warning("Bing error for %r (attempt %d): %s", company_name, attempt + 1, e)
        if attempt < MAX_RETRIES - 1:
            time.sleep((2 ** attempt) * random.uniform(3, 6))
    else:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    for h2 in soup.select("li.b_algo h2"):
        a = h2.find("a", href=True)
        if not a:
            continue
        url = a["href"]
        if _domain_allowed(url):
            parsed = urlparse(url)
            return f"{parsed.scheme}://{parsed.netloc}"
    return None


def resolve_missing_websites(limit: int | None = None, dry_run: bool = False) -> dict:
    """
    Resuelve website para empresas con oferta relevante y sin website conocido.
    Devuelve {"resolved": n, "not_found": n}.
    """
    conn = get_conn()
    rows = conn.execute(
        """SELECT DISTINCT c.id, c.name, MAX(jo.relevance_score) as best_score
           FROM companies c
           JOIN job_offers jo ON jo.company_id = c.id
           WHERE jo.is_relevant = 1
             AND (c.website IS NULL OR c.website = '')
             AND c.name != 'Desconocida'
           GROUP BY c.id
           ORDER BY best_score DESC"""
    ).fetchall()
    conn.close()

    companies = [dict(r) for r in rows]
    if limit:
        companies = companies[:limit]

    results = {"resolved": 0, "not_found": 0}
    conn = get_conn()
    for company in companies:
        name = company["name"]
        url = resolve_website(name)
        if url:
            logger.info("RESOLVED: %s -> %s", name, url)
            results["resolved"] += 1
            if not dry_run:
                upsert_company(conn, {"name": name, "website": url})
        else:
            logger.info("NOT FOUND: %s", name)
            results["not_found"] += 1
        time.sleep(random.uniform(6.0, 12.0))
    conn.close()

    logger.info("Website resolver summary: %s", results)
    return results
