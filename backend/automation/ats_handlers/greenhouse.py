"""
automation/ats_handlers/greenhouse.py — Greenhouse ATS handler.
Greenhouse uses a simple single-page form at boards.greenhouse.io.
"""
import logging
from pathlib import Path
from playwright.async_api import Page
from automation.ats_handlers.generic import _dismiss_cookies, _map_field

logger = logging.getLogger(__name__)


async def fill_greenhouse(page: Page, profile: dict, cv_path: Path, cover_letter: str) -> bool:
    await _dismiss_cookies(page)
    personal = profile.get("personal", {})
    filled = 0

    for field_id, _ in [
        ("first_name", "name"), ("last_name", "name"),
        ("email", "email"), ("phone", "phone"),
    ]:
        value = _map_field(field_id, profile)
        if not value:
            continue
        for sel in [
            f"input#job_application_{field_id}",
            f"input[name='job_application[{field_id}]']",
            f"input[id*='{field_id}' i]",
        ]:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=1200):
                    await el.fill(value)
                    filled += 1
                    break
            except Exception:
                continue

    if cv_path and cv_path.exists():
        try:
            fi = page.locator("input[type='file']").first
            if await fi.is_visible(timeout=2000):
                await fi.set_input_files(str(cv_path))
                filled += 1
        except Exception as e:
            logger.debug("Greenhouse CV: %s", e)

    try:
        ta = page.locator(
            "textarea#job_application_cover_letter, textarea[name*='cover_letter'], textarea"
        ).first
        if await ta.is_visible(timeout=1500):
            await ta.fill(cover_letter)
            filled += 1
    except Exception:
        pass

    linkedin = personal.get("linkedin", "")
    if linkedin:
        try:
            li = page.locator("input[id*='linkedin' i], input[name*='linkedin' i]").first
            if await li.is_visible(timeout=1200):
                await li.fill(linkedin)
                filled += 1
        except Exception:
            pass

    try:
        submit = page.locator(
            "input[type='submit'], button[type='submit'], button:text('Submit Application')"
        ).first
        if await submit.is_visible(timeout=3000):
            await submit.click()
            logger.info("Greenhouse: submitted")
            return True
    except Exception as e:
        logger.warning("Greenhouse submit: %s", e)

    return filled > 0
