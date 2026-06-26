"""
scraper/manfred.py — Fetches job offers from GetManfred.com public API.

Manfred is a popular tech job platform in Spain, especially for startups.
Unlike other portals, Manfred exposes a public JSON API — no scraping needed.

API endpoint: https://www.getmanfred.com/api/v2/public/offers
Response: JSON array with title, company, location, salary, tags, url, etc.
"""
import logging
import re
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

MANFRED_API_BASE = "https://www.getmanfred.com/api/v2/public/offers"
MANFRED_WEB_BASE = "https://www.getmanfred.com"

# Headers that mimic a real browser request
_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-ES,es;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.getmanfred.com/ofertas-empleo",
}

SALARY_PATTERN = re.compile(r"(\d[\d.,]+)")


def _parse_manfred_salary(salary_data: dict | str | None) -> tuple[int | None, int | None]:
    """Extract min/max salary from Manfred's salary object."""
    if not salary_data:
        return None, None

    if isinstance(salary_data, dict):
        lo = salary_data.get("min") or salary_data.get("from")
        hi = salary_data.get("max") or salary_data.get("to")
        return (int(lo) if lo else None), (int(hi) if hi else None)

    if isinstance(salary_data, str):
        matches = SALARY_PATTERN.findall(salary_data)
        if len(matches) >= 2:
            return (
                int(matches[0].replace(".", "").replace(",", "")),
                int(matches[1].replace(".", "").replace(",", "")),
            )
        if len(matches) == 1:
            val = int(matches[0].replace(".", "").replace(",", ""))
            return val, None

    return None, None


def _parse_offer(raw: dict) -> dict | None:
    """Convert a Manfred API offer object to our internal format."""
    title = raw.get("title") or raw.get("name")
    if not title:
        return None

    # Build canonical URL
    offer_id = raw.get("id") or raw.get("slug")
    slug = raw.get("slug") or raw.get("friendlyUrl") or str(offer_id)
    url = raw.get("url") or f"{MANFRED_WEB_BASE}/ofertas-empleo/{slug}"

    # Company info
    company = raw.get("company") or {}
    company_name = (
        company.get("name")
        if isinstance(company, dict)
        else str(company) if company else None
    )

    # Location
    location_data = raw.get("location") or raw.get("locations") or {}
    if isinstance(location_data, dict):
        location = location_data.get("name") or location_data.get("city")
    elif isinstance(location_data, list):
        location = ", ".join(
            loc.get("name", "") if isinstance(loc, dict) else str(loc)
            for loc in location_data[:3]
        )
    else:
        location = str(location_data) if location_data else None

    # Remote policy
    remote = raw.get("remote") or raw.get("remotePolicy")
    if remote and location:
        if isinstance(remote, bool) and remote:
            location = f"{location} (Remoto)"
        elif isinstance(remote, str) and "full" in remote.lower():
            location = f"{location} (100% Remoto)"

    # Salary
    salary_raw = raw.get("salary") or raw.get("salaryRange")
    salary_min, salary_max = _parse_manfred_salary(salary_raw)
    salary_text = ""
    if salary_min or salary_max:
        parts = []
        if salary_min:
            parts.append(f"{salary_min:,}€".replace(",", "."))
        if salary_max:
            parts.append(f"{salary_max:,}€".replace(",", "."))
        salary_text = " - ".join(parts)

    # Tech tags
    tags_raw = raw.get("tags") or raw.get("skills") or raw.get("technologies") or []
    if isinstance(tags_raw, list):
        tech_tags = [
            (t.get("name") if isinstance(t, dict) else str(t))
            for t in tags_raw
            if t
        ]
    else:
        tech_tags = []

    # Description
    description = raw.get("description") or raw.get("summary") or raw.get("excerpt")

    # Experience level
    experience = raw.get("experienceMin") or raw.get("seniority")

    return {
        "title": title,
        "url": url,
        "company_name": company_name,
        "location": location,
        "description": description,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_text": salary_text,
        "tech_tags": tech_tags,
        "source": "manfred",
        "experience_level": _normalise_experience(experience),
    }


def _normalise_experience(exp: str | int | None) -> str | None:
    """Map Manfred seniority to our normalised levels."""
    if exp is None:
        return None
    exp_str = str(exp).lower()
    if any(j in exp_str for j in ("junior", "jr", "0", "1", "2")):
        return "junior"
    if any(m in exp_str for m in ("mid", "middle", "3", "4", "5")):
        return "mid"
    if any(s in exp_str for s in ("senior", "sr", "6", "7", "8")):
        return "senior"
    if any(l in exp_str for l in ("lead", "principal", "staff", "9", "10")):
        return "lead"
    return None


def run_manfred(max_pages: int = 5) -> list[dict]:
    """
    Fetch offers from Manfred's public API.
    Returns list of offer dicts in our standard format.
    """
    all_offers: list[dict] = []
    seen_urls: set[str] = set()

    for page in range(1, max_pages + 1):
        params: dict = {"page": page, "limit": 50}
        url = f"{MANFRED_API_BASE}?{urlencode(params)}"
        logger.info("Manfred API page %d: %s", page, url)

        try:
            resp = requests.get(url, headers=_HEADERS, timeout=15)
            if resp.status_code == 404:
                logger.info("Manfred: page %d returned 404, done", page)
                break
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error("Manfred API error on page %d: %s", page, e)
            break

        try:
            data = resp.json()
        except ValueError:
            logger.error("Manfred: invalid JSON on page %d", page)
            break

        # API might return {"data": [...]} or just [...]
        offers_list = data if isinstance(data, list) else data.get("data", data.get("offers", []))
        if not isinstance(offers_list, list):
            logger.info("Manfred: unexpected response shape on page %d", page)
            break

        if not offers_list:
            logger.info("Manfred: empty page %d, done", page)
            break

        page_count = 0
        for raw in offers_list:
            offer = _parse_offer(raw)
            if offer and offer.get("url") and offer["url"] not in seen_urls:
                seen_urls.add(offer["url"])
                all_offers.append(offer)
                page_count += 1

        logger.info("Manfred page %d: %d new offers (total %d)", page, page_count, len(all_offers))

    logger.info("Manfred total: %d unique offers", len(all_offers))
    return all_offers
