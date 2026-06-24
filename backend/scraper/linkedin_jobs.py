"""
scraper/linkedin_jobs.py — LinkedIn Jobs scraper using persistent cookie session.

First-time setup (opens Chromium for manual login):
  python -m scraper.runner --source linkedin-login

Subsequent runs load the saved session (~30 days validity).
If checkpoint/captcha detected, run stops with a clear warning.
"""
import asyncio
import json
import logging
import random
import shutil
from pathlib import Path
from urllib.parse import urlencode
from playwright.async_api import async_playwright
from scraper.base import BaseScraper, USER_AGENTS
from config import LINKEDIN_SAP_SEARCHES, LINKEDIN_SESSION_PATH

logger = logging.getLogger(__name__)

LINKEDIN_BASE = "https://www.linkedin.com"
_CHECKPOINT_HINTS = ["/checkpoint/", "/authwall", "/login?", "verify your identity"]


def save_linkedin_session(cookies: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
    logger.info("LinkedIn session saved: %s", path)


def load_linkedin_session(path: Path) -> list[dict] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _is_checkpoint(url: str, html: str) -> bool:
    url_lower = url.lower()
    html_lower = html.lower()
    return any(hint in url_lower or hint in html_lower for hint in _CHECKPOINT_HINTS)


async def run_linkedin_login() -> None:
    """Open headful Chromium — user logs in manually, then cookies are saved."""
    system_chromium = shutil.which("chromium") or shutil.which("chromium-browser")
    playwright = await async_playwright().start()
    launch_kwargs: dict = {"headless": False}
    if system_chromium:
        launch_kwargs["executable_path"] = system_chromium

    browser = await playwright.chromium.launch(**launch_kwargs)
    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        locale="es-ES",
        timezone_id="Europe/Madrid",
    )
    page = await context.new_page()
    await page.goto(f"{LINKEDIN_BASE}/login", wait_until="domcontentloaded")
    logger.info("Browser open — please log in to LinkedIn manually.")
    logger.info("Waiting for /feed (max 2 minutes)...")
    try:
        await page.wait_for_url("**/feed**", timeout=120_000)
        cookies = await context.cookies()
        save_linkedin_session(list(cookies), LINKEDIN_SESSION_PATH)
        logger.info("Login successful. Session saved.")
    except Exception:
        logger.error("Login timeout — session not saved. Try again.")
    finally:
        await browser.close()
        await playwright.stop()


class LinkedInJobsScraper(BaseScraper):
    def __init__(self):
        super().__init__(delay_min=5.0, delay_max=12.0)

    async def scrape_search(
        self, keywords: str, location: str, max_offers: int = 25
    ) -> list[dict]:
        cookies = load_linkedin_session(LINKEDIN_SESSION_PATH)
        if not cookies:
            logger.error(
                "No LinkedIn session. Run: python -m scraper.runner --source linkedin-login"
            )
            return []

        offers = []
        async with self as scraper:
            page = await scraper.new_page()
            await scraper._context.add_cookies(cookies)

            params = urlencode({
                "keywords": keywords,
                "location": location,
                "f_TPR": "r2592000",
                "position": 1,
                "pageNum": 0,
            })
            url = f"{LINKEDIN_BASE}/jobs/search?{params}"
            logger.info("LinkedIn: %s @ %s", keywords, location)

            if not await scraper.fetch_with_retry(page, url):
                return []

            html = await page.content()
            if _is_checkpoint(page.url, html):
                logger.warning(
                    "LinkedIn checkpoint — re-run: python -m scraper.runner --source linkedin-login"
                )
                return []

            cards = await page.query_selector_all(
                ".job-search-card, .jobs-search__results-list li, [class*='job-card-container']"
            )
            logger.info("LinkedIn: %d cards found", len(cards))

            for card in cards[:max_offers]:
                try:
                    title_el = await card.query_selector(
                        ".job-search-card__title, h3, [class*='title']"
                    )
                    company_el = await card.query_selector(
                        ".job-search-card__company-name, h4, [class*='company']"
                    )
                    location_el = await card.query_selector(
                        ".job-search-card__location, [class*='location']"
                    )
                    link_el = await card.query_selector("a[href*='/jobs/view/']")

                    title = (await title_el.inner_text()).strip() if title_el else None
                    if not title:
                        continue
                    company_name = (await company_el.inner_text()).strip() if company_el else None
                    location_text = (await location_el.inner_text()).strip() if location_el else None
                    href = await link_el.get_attribute("href") if link_el else None
                    offer_url = (
                        href if href and href.startswith("http")
                        else (LINKEDIN_BASE + href if href else None)
                    )
                    offers.append({
                        "title": title,
                        "url": offer_url,
                        "company_name": company_name,
                        "location": location_text,
                        "description": None,
                        "salary_min": None,
                        "salary_max": None,
                        "tech_tags": [],
                        "source": "linkedin",
                    })
                    await scraper.random_delay()
                except Exception as e:
                    logger.debug("LinkedIn card parse error: %s", e)

        logger.info("LinkedIn '%s': %d offers", keywords, len(offers))
        return offers


async def run_linkedin_jobs(max_per_search: int = 25) -> list[dict]:
    scraper = LinkedInJobsScraper()
    seen: set[str] = set()
    all_offers: list[dict] = []
    for search in LINKEDIN_SAP_SEARCHES:
        try:
            for offer in await scraper.scrape_search(
                search["keywords"], search["location"], max_per_search
            ):
                if offer.get("url") and offer["url"] not in seen:
                    seen.add(offer["url"])
                    all_offers.append(offer)
        except Exception as e:
            logger.error("LinkedIn search '%s' failed: %s", search["keywords"], e)
    logger.info("LinkedIn total: %d unique offers", len(all_offers))
    return all_offers
