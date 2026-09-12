"""
scraper/tecnoempleo.py — Scrapes tech job offers from Tecnoempleo.com.
Targets: /ofertas-trabajo/ with keyword + province ID filters.

Selectors verified 2026-06-24 against live site structure:
  Card: div.p-3.border.rounded.mb-3.bg-white
  Title link: h3 a.font-weight-bold
  Company: a.text-primary.link-muted
  Location: div.col-12.col-lg-3.text-gray-700
  Description: span.hidden-md-down
"""
import json
import re
import logging
from urllib.parse import urlencode
from playwright.async_api import Page
from scraper.base import BaseScraper
from automation.experience_classifier import classify_experience, classify_contract
from automation.filter_engine import score_offer
from config import (
    TECNOEMPLEO_BASE,
    TECNOEMPLEO_SEARCH_KEYWORDS,
    TECNOEMPLEO_LOCATIONS,
    DETAIL_FETCH_MIN_SCORE,
)

logger = logging.getLogger(__name__)

SALARY_PATTERN = re.compile(r"(\d[\d.,]+)\s*[€$]?\s*[-–]\s*(\d[\d.,]+)")

# Province IDs from Tecnoempleo filter sidebar (pr= parameter)
PROVINCE_IDS = {
    "sevilla": "274",
    "andalucia": None,   # no single ID — use keyword search only
    "remoto": None,      # remoto is a keyword filter, not province
}


def _parse_salary(text: str) -> tuple[int | None, int | None]:
    m = SALARY_PATTERN.search(text)
    if not m:
        return None, None
    try:
        lo = int(m.group(1).replace(".", "").replace(",", ""))
        hi = int(m.group(2).replace(".", "").replace(",", ""))
        return lo, hi
    except ValueError:
        return None, None


class TecnoempleoScraper(BaseScraper):
    def __init__(self):
        super().__init__(delay_min=3.0, delay_max=7.0)

    async def _parse_offer_card(self, card) -> dict | None:
        try:
            # URL from onclick attribute on the card div
            onclick = await card.get_attribute("onclick") or ""
            url = None
            m = re.search(r"location\.href='([^']+)'", onclick)
            if m:
                url = m.group(1)
                if not url.startswith("http"):
                    url = TECNOEMPLEO_BASE + url

            # Title and URL also available from the h3 > a link
            title_el = await card.query_selector("h3 a, h2 a")
            if not title_el:
                return None
            title = (await title_el.inner_text()).strip()
            if not url:
                href = await title_el.get_attribute("href")
                if href:
                    url = href if href.startswith("http") else TECNOEMPLEO_BASE + href

            # Company
            company_el = await card.query_selector("a.text-primary, a.link-muted")
            company_name = (await company_el.inner_text()).strip() if company_el else None

            # Location — desktop column
            loc_el = await card.query_selector(".col-12.col-lg-3.text-gray-700, .col-lg-3.text-gray-700")
            if loc_el:
                loc_text = (await loc_el.inner_text()).strip()
                # First line is date, second is location
                lines = [l.strip() for l in loc_text.splitlines() if l.strip()]
                location = lines[1] if len(lines) > 1 else lines[0] if lines else None
            else:
                # Mobile fallback
                mob_el = await card.query_selector("span.d-block.d-lg-none, .d-block.d-lg-none")
                location = (await mob_el.inner_text()).strip() if mob_el else None

            # Salary
            salary_el = await card.query_selector(".salario, .salary, [class*='salary']")
            salary_text = (await salary_el.inner_text()).strip() if salary_el else ""
            salary_min, salary_max = _parse_salary(salary_text)

            # Description
            desc_el = await card.query_selector(".hidden-md-down, span.hidden-md-down")
            description = (await desc_el.inner_text()).strip() if desc_el else None

            # Tech stack badges
            badge_els = await card.query_selector_all("span.badge")
            tech_tags = []
            for b in badge_els:
                t = (await b.inner_text()).strip()
                if t and t not in ("Nueva", "Urgente", "Destacada"):
                    tech_tags.append(t)

            return {
                "title": title,
                "url": url,
                "company_name": company_name,
                "location": location,
                "salary_min": salary_min,
                "salary_max": salary_max,
                "description": description,
                "tech_stack": ", ".join(tech_tags) if tech_tags else None,
                "source": "tecnoempleo",
            }
        except Exception as e:
            logger.debug("Card parse error: %s", e)
            return None

    async def scrape_keyword(self, keyword: str, location: str, max_pages: int = 5) -> list[dict]:
        offers = []
        pr_id = PROVINCE_IDS.get(location.lower())

        async with self as scraper:
            page = await scraper.new_page()
            for page_num in range(1, max_pages + 1):
                params: dict = {"te": keyword, "pagina": page_num}
                if pr_id:
                    params["pr"] = f",{pr_id},"
                elif location.lower() == "remoto":
                    params["te"] = f"{keyword} remoto"
                # For "andalucia" without a province ID we skip the province filter
                # so results come from all Spain — caller should deduplicate

                url = f"{TECNOEMPLEO_BASE}/ofertas-trabajo/?{urlencode(params)}"
                logger.info("Fetching page %d: %s", page_num, url)
                if not await scraper.fetch_with_retry(page, url):
                    break

                cards = await page.query_selector_all("div.p-3.border.rounded.mb-3.bg-white")
                if not cards:
                    logger.info("No offers on page %d", page_num)
                    break

                page_offers = []
                for card in cards:
                    offer = await self._parse_offer_card(card)
                    if offer:
                        page_offers.append(offer)
                        offers.append(offer)

                logger.info("  Page %d: %d offers found (total %d)", page_num, len(page_offers), len(offers))
                await scraper.random_delay()

                # Check for next page
                next_btn = await page.query_selector("a[rel='next'], a.next, [aria-label*='siguiente'], li.next a")
                if not next_btn:
                    break
        return offers


async def run_tecnoempleo(max_pages: int = 3) -> list[dict]:
    all_offers = []
    scraper = TecnoempleoScraper()
    seen_urls: set[str] = set()
    for keyword in TECNOEMPLEO_SEARCH_KEYWORDS:
        for location in TECNOEMPLEO_LOCATIONS:
            logger.info("Tecnoempleo: keyword=%s location=%s", keyword, location)
            offers = await scraper.scrape_keyword(keyword, location, max_pages)
            for o in offers:
                if o.get("url") and o["url"] not in seen_urls:
                    seen_urls.add(o["url"])
                    all_offers.append(o)
    logger.info("Tecnoempleo total: %d unique offers", len(all_offers))
    return all_offers
