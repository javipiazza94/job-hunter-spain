"""
scraper/indeed.py — Scrapes job offers from Indeed Spain (es.indeed.com).
URL: /jobs?q={keyword}&l={location}&fromage=14&sort=date&start={offset}

Indeed uses PerimeterX bot protection — we use full Playwright with stealth,
slow delays, and randomised behaviour to stay under the radar.

Primary card selectors (verified 2026-06):
  Card container: div.job_seen_beacon, td.resultContent
  Title: h2.jobTitle > a > span
  Company: span[data-testid="company-name"]
  Location: div[data-testid="text-location"]
  Salary: div.salary-snippet-container, div.metadata.salary-snippet-container
  Description snippet: div.job-snippet
"""
import re
import logging
from urllib.parse import urlencode
from playwright.async_api import Page
from scraper.base import BaseScraper

logger = logging.getLogger(__name__)

INDEED_BASE = "https://es.indeed.com"

# Matches patterns like: 25.000€ - 35.000€/año, 2.500€/mes, 30.000 - 45.000 €
SALARY_PATTERN = re.compile(
    r"([\d.,]+)\s*€?\s*(?:[-–a]\s*([\d.,]+)\s*€?)?\s*(?:/?(?:año|mes|hora|year|month))?",
    re.IGNORECASE,
)


def _parse_salary_indeed(text: str) -> tuple[int | None, int | None]:
    """Parse salary from Indeed salary snippet. Returns (min, max) annual."""
    if not text:
        return None, None
    text_clean = text.strip().lower()

    m = SALARY_PATTERN.search(text_clean)
    if not m:
        return None, None

    try:
        lo = int(m.group(1).replace(".", "").replace(",", ""))
        hi = int(m.group(2).replace(".", "").replace(",", "")) if m.group(2) else None
    except (ValueError, AttributeError):
        return None, None

    # Normalise to annual if monthly
    if "mes" in text_clean or "month" in text_clean:
        lo *= 12
        if hi:
            hi *= 12
    elif "hora" in text_clean or "hour" in text_clean:
        lo *= 1760  # ~220 days * 8h
        if hi:
            hi *= 1760

    return lo, hi


class IndeedScraper(BaseScraper):
    def __init__(self):
        super().__init__(delay_min=5.0, delay_max=10.0)

    async def _parse_card(self, card) -> dict | None:
        try:
            # Title
            title_el = await card.query_selector(
                "h2.jobTitle a span, h2 a span[id^='jobTitle'], h2 a"
            )
            if not title_el:
                return None
            title = (await title_el.inner_text()).strip()

            # URL from the title link
            link_el = await card.query_selector("h2.jobTitle a, h2 a[data-jk]")
            url = None
            if link_el:
                href = await link_el.get_attribute("href")
                if href:
                    url = href if href.startswith("http") else INDEED_BASE + href

            # Company name
            company_el = await card.query_selector(
                "[data-testid='company-name'], span.companyName, span.company"
            )
            company_name = (await company_el.inner_text()).strip() if company_el else None

            # Location
            loc_el = await card.query_selector(
                "[data-testid='text-location'], div.companyLocation, div.company_location"
            )
            location = (await loc_el.inner_text()).strip() if loc_el else None

            # Salary
            salary_el = await card.query_selector(
                "div.salary-snippet-container, "
                "div.metadata.salary-snippet-container, "
                "[data-testid='attribute_snippet_testid'], "
                "div.salaryOnly"
            )
            salary_text = (await salary_el.inner_text()).strip() if salary_el else ""
            salary_min, salary_max = _parse_salary_indeed(salary_text)

            # Description snippet
            desc_el = await card.query_selector(
                "div.job-snippet, table.jobCardShelfContainer, ul[style]"
            )
            description = (await desc_el.inner_text()).strip() if desc_el else None

            return {
                "title": title,
                "url": url,
                "company_name": company_name,
                "location": location,
                "description": description,
                "salary_min": salary_min,
                "salary_max": salary_max,
                "salary_text": salary_text,
                "tech_tags": [],
                "source": "indeed",
            }
        except Exception as e:
            logger.debug("Indeed card parse error: %s", e)
            return None

    async def scrape_keyword(
        self, keyword: str, location: str = "Sevilla", max_pages: int = 3
    ) -> list[dict]:
        offers: list[dict] = []
        async with self as scraper:
            page = await scraper.new_page()
            for page_num in range(max_pages):
                params = {
                    "q": keyword,
                    "l": location,
                    "fromage": "14",     # últimos 14 días
                    "sort": "date",
                    "start": page_num * 10,
                }
                url = f"{INDEED_BASE}/jobs?{urlencode(params)}"
                logger.info("Indeed page %d: %s", page_num + 1, url)

                if not await scraper.fetch_with_retry(page, url):
                    logger.warning("Indeed: failed to fetch page %d", page_num + 1)
                    break

                # Check for CAPTCHA / block page
                content = await page.content()
                if "captcha" in content.lower() or "unusual traffic" in content.lower():
                    logger.warning("Indeed: CAPTCHA detected, stopping")
                    break

                # Parse job cards
                cards = await page.query_selector_all(
                    "div.job_seen_beacon, "
                    "div.cardOutline, "
                    "div[class*='jobsearch-ResultsList'] > div"
                )
                if not cards:
                    logger.info("Indeed: no cards on page %d", page_num + 1)
                    break

                page_offers = []
                for card in cards:
                    offer = await self._parse_card(card)
                    if offer and offer.get("url"):
                        page_offers.append(offer)
                        offers.append(offer)

                logger.info(
                    "  Indeed page %d: %d offers (total %d)",
                    page_num + 1, len(page_offers), len(offers),
                )
                await scraper.random_delay()

                # Check for next page
                next_btn = await page.query_selector(
                    "a[data-testid='pagination-page-next'], "
                    "a[aria-label='Next Page'], "
                    "a[aria-label='Siguiente']"
                )
                if not next_btn:
                    break

        return offers


async def run_indeed(
    keywords: list[str] | None = None,
    locations: list[str] | None = None,
    max_pages: int = 3,
) -> list[dict]:
    """Run Indeed scraper for all keyword + location combinations."""
    from config import TECNOEMPLEO_SEARCH_KEYWORDS, TECNOEMPLEO_LOCATIONS

    keywords = keywords or TECNOEMPLEO_SEARCH_KEYWORDS
    locations = locations or ["Sevilla", "Remoto"]

    scraper = IndeedScraper()
    seen: set[str] = set()
    all_offers: list[dict] = []

    for kw in keywords:
        for loc in locations:
            logger.info("Indeed: keyword=%s location=%s", kw, loc)
            try:
                for offer in await scraper.scrape_keyword(kw, loc, max_pages):
                    if offer.get("url") and offer["url"] not in seen:
                        seen.add(offer["url"])
                        all_offers.append(offer)
            except Exception as e:
                logger.error("Indeed keyword '%s' @ '%s' failed: %s", kw, loc, e)

    logger.info("Indeed total: %d unique offers", len(all_offers))
    return all_offers
