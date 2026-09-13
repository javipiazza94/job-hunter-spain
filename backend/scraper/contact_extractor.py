"""
scraper/contact_extractor.py — Extracts contact emails and detects application forms
from company career pages using Playwright.
"""
import re
import logging
from urllib.parse import urlparse
from playwright.async_api import Page
from scraper.base import BaseScraper
from scraper.website_resolver import _BLACKLIST_DOMAINS
from database import get_conn, upsert_contact

logger = logging.getLogger(__name__)

# ATS domains beyond the 4 with a dedicated handler in automation/ats_handlers/ —
# these fall back to the "generic" form filler, but we still want to recognise
# them as real application portals worth registering as a 'form' contact.
_ATS_DOMAINS = [
    "myworkdayjobs.com", "workday.com", "greenhouse.io", "jobs.lever.co",
    "successfactors.eu", "successfactors.com", "jobs.sap.com", "sapsf.eu", "sapsf.com",
    "smartrecruiters.com", "personio.de", "personio.com", "bamboohr.com",
    "teamtailor.com", "recruitee.com", "jazzhr.com", "breezy.hr",
    "factorialhr.com", "jobvite.com", "icims.com", "taleo.net", "workable.com",
]
_APPLY_KEYWORDS = ["apply", "aplicar", "solicitar", "postular", "candidatura"]

EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)
CAREER_EMAIL_PREFIXES = [
    "careers", "jobs", "rrhh", "hr", "talent", "empleo",
    "recruiting", "recruitment", "people", "join",
]

CAREER_PATH_HINTS = [
    "/careers", "/jobs", "/empleo", "/trabaja-con-nosotros",
    "/trabaja", "/join-us", "/join", "/equipo", "/team",
    "/work-with-us", "/hiring", "/oferta", "/ofertas",
    "/vacantes", "/oportunidades",
]

FORM_FIELD_HINTS = ["cv", "resume", "curriculum", "carta", "cover"]


async def _find_career_page(page: Page, website: str) -> str | None:
    """Try common career URL patterns for a company website."""
    base = website.rstrip("/")
    for path in CAREER_PATH_HINTS:
        url = base + path
        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            if resp and resp.status == 200:
                return url
        except Exception:
            continue
    return None


def _extract_emails_from_text(text: str, domain: str) -> list[str]:
    emails = EMAIL_PATTERN.findall(text)
    career_emails = []
    all_emails = []
    for email in emails:
        email = email.lower()
        if any(p in email for p in CAREER_EMAIL_PREFIXES):
            career_emails.append(email)
        elif domain and domain in email:
            all_emails.append(email)
    return list(set(career_emails or all_emails))


async def _detect_application_form(page: Page) -> str | None:
    """Return current URL if the page contains a job application form."""
    try:
        inputs = await page.query_selector_all("input, textarea")
        labels = []
        for el in inputs:
            name = (await el.get_attribute("name") or "").lower()
            placeholder = (await el.get_attribute("placeholder") or "").lower()
            label = name + " " + placeholder
            labels.append(label)
        all_labels = " ".join(labels)
        if any(hint in all_labels for hint in FORM_FIELD_HINTS):
            return page.url
        # Check for file upload (CV attachment)
        file_inputs = await page.query_selector_all("input[type='file']")
        if file_inputs:
            return page.url
    except Exception as e:
        logger.debug("Form detection error: %s", e)
    return None


class ContactExtractorScraper(BaseScraper):
    def __init__(self):
        super().__init__(delay_min=2.0, delay_max=5.0)

    async def extract_for_company(
        self, company_id: str, website: str, careers_url: str | None
    ) -> list[dict]:
        """Return list of contact dicts found for a company."""
        contacts: list[dict] = []
        async with self as scraper:
            page = await scraper.new_page()
            # 1) Try the known careers_url first
            start_url = careers_url or website
            if not await scraper.fetch_with_retry(page, start_url):
                logger.warning("Could not fetch %s", start_url)
                return contacts

            content = await page.content()
            domain = urlparse(website).netloc.replace("www.", "")
            emails = _extract_emails_from_text(content, domain)
            for email in emails:
                contacts.append({
                    "company_id": company_id,
                    "type": "email",
                    "value": email,
                    "method": "extracted",
                })
                logger.info("  Email found: %s", email)

            form_url = await _detect_application_form(page)
            if form_url:
                contacts.append({
                    "company_id": company_id,
                    "type": "form",
                    "value": form_url,
                    "method": "detected",
                })
                logger.info("  Form found: %s", form_url)

            # 2) If no application form found yet, try career sub-paths — a form usually
            # lives on a dedicated /careers-style page, not the homepage, even when an
            # email was already found there. Skip only if we started from a known careers_url
            # (we already tried the actual careers page in step 1).
            has_form = any(c["type"] == "form" for c in contacts)
            if not has_form and not careers_url:
                career_url = await _find_career_page(page, website)
                if career_url:
                    content = await page.content()
                    emails = _extract_emails_from_text(content, domain)
                    existing_emails = {c["value"] for c in contacts if c["type"] == "email"}
                    for email in emails:
                        if email in existing_emails:
                            continue
                        contacts.append({
                            "company_id": company_id,
                            "type": "email",
                            "value": email,
                            "method": "guessed",
                        })
                    form_url = await _detect_application_form(page)
                    if form_url:
                        contacts.append({
                            "company_id": company_id,
                            "type": "form",
                            "value": form_url,
                            "method": "detected",
                        })

            await scraper.random_delay()
        return contacts


async def run_contact_extraction(companies: list[dict]) -> int:
    """Extract contacts for a list of company dicts (id, website, careers_url)."""
    conn = get_conn()
    total = 0
    extractor = ContactExtractorScraper()
    for company in companies:
        logger.info("Extracting contacts: %s", company["name"])
        contacts = await extractor.extract_for_company(
            company["id"], company.get("website", ""), company.get("careers_url")
        )
        for c in contacts:
            upsert_contact(conn, c)
            total += 1
    conn.close()
    return total
