"""
scraper/infojobs.py — Scrapes job offers from InfoJobs.net.
URL: /jobsearch/search-results/list.xhtml?keyword={kw}&normalizedLocation=sevilla-andalucia-espana

Primary card selector: .ij-OfferCardContent
If selectors stop working, inspect with:
  chromium --headless --dump-dom 'https://www.infojobs.net/jobsearch/...'
"""
import re
import logging
from bs4 import BeautifulSoup
from urllib.parse import urlencode, urljoin
from scraper.base import BaseScraper

logger = logging.getLogger(__name__)

INFOJOBS_BASE = "https://www.infojobs.net"
SALARY_PATTERN = re.compile(r"(\d[\d.,]+)\s*€")


def _parse_card_html(html: str, base_url: str = INFOJOBS_BASE) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.select_one("h2.title a, h3.title a, [class*='title'] a")
    if not title_el:
        return None
    title = title_el.get_text(strip=True)
    href = title_el.get("href", "")
    url = urljoin(base_url, href) if href else None
    if not url:
        return None

    company_el = soup.select_one(".companyName, [class*='company']")
    company_name = company_el.get_text(strip=True) if company_el else None

    location_el = soup.select_one(".location, [class*='location']")
    location = location_el.get_text(strip=True) if location_el else None

    desc_el = soup.select_one(".description, p.description, [class*='description']")
    description = desc_el.get_text(strip=True) if desc_el else None

    salary_match = SALARY_PATTERN.search(soup.get_text())
    salary_min = int(salary_match.group(1).replace(".", "").replace(",", "")) if salary_match else None

    return {
        "title": title,
        "url": url,
        "company_name": company_name,
        "location": location,
        "description": description,
        "salary_min": salary_min,
        "salary_max": None,
        "tech_tags": [],
        "source": "infojobs",
    }


class InfoJobsScraper(BaseScraper):
    def __init__(self):
        super().__init__(delay_min=3.0, delay_max=8.0)

    async def scrape_keyword(self, keyword: str, max_pages: int = 3) -> list[dict]:
        offers = []
        async with self as scraper:
            page = await scraper.new_page()
            for page_num in range(1, max_pages + 1):
                params = {
                    "keyword": keyword,
                    "normalizedLocation": "sevilla-andalucia-espana",
                    "page": page_num,
                }
                url = f"{INFOJOBS_BASE}/jobsearch/search-results/list.xhtml?{urlencode(params)}"
                logger.info("InfoJobs page %d: %s", page_num, url)
                if not await scraper.fetch_with_retry(page, url):
                    break

                cards = await page.query_selector_all(
                    ".ij-OfferCardContent, div[class*='OfferCard'], article[class*='offer']"
                )
                if not cards:
                    logger.info("InfoJobs: no cards on page %d", page_num)
                    break

                for card in cards:
                    html = await card.inner_html()
                    offer = _parse_card_html(html)
                    if offer:
                        offers.append(offer)

                logger.info("InfoJobs page %d: %d cards", page_num, len(cards))
                await scraper.random_delay()

                next_btn = await page.query_selector(
                    "a[rel='next'], .pagination-next a, [aria-label*='siguiente']"
                )
                if not next_btn:
                    break
        return offers


async def run_infojobs(keywords: list[str], max_pages: int = 3) -> list[dict]:
    scraper = InfoJobsScraper()
    seen: set[str] = set()
    all_offers: list[dict] = []
    for kw in keywords:
        logger.info("InfoJobs keyword: %s", kw)
        try:
            for offer in await scraper.scrape_keyword(kw, max_pages):
                if offer.get("url") and offer["url"] not in seen:
                    seen.add(offer["url"])
                    all_offers.append(offer)
        except Exception as e:
            logger.error("InfoJobs keyword '%s' failed: %s", kw, e)
    logger.info("InfoJobs total: %d unique offers", len(all_offers))
    return all_offers
