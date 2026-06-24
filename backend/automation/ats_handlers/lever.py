"""
automation/ats_handlers/lever.py — Lever ATS handler.
Lever uses a clean single-page form at jobs.lever.co/{company}/{id}/apply.
Uses a single 'name' field (not split first/last).
"""
import logging
from pathlib import Path
from playwright.async_api import Page
from automation.ats_handlers.generic import _dismiss_cookies

logger = logging.getLogger(__name__)


async def fill_lever(page: Page, profile: dict, cv_path: Path, cover_letter: str) -> bool:
    await _dismiss_cookies(page)
    personal = profile.get("personal", {})
    filled = 0

    for sel, value in [
        ("input[name='name'], input[id='name']",                   personal.get("name", "")),
        ("input[name='email'], input[type='email']",               personal.get("email", "")),
        ("input[name='phone'], input[type='tel']",                 personal.get("phone", "")),
        ("input[name='urls[LinkedIn]'], input[name*='linkedin' i]", personal.get("linkedin", "")),
    ]:
        if not value:
            continue
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=1200):
                await el.fill(value)
                filled += 1
        except Exception:
            pass

    if cv_path and cv_path.exists():
        try:
            fi = page.locator("input[type='file']").first
            if await fi.is_visible(timeout=2000):
                await fi.set_input_files(str(cv_path))
                filled += 1
        except Exception as e:
            logger.debug("Lever CV: %s", e)

    try:
        ta = page.locator(
            "textarea[name='comments'], textarea[name='additional'], textarea"
        ).first
        if await ta.is_visible(timeout=1500):
            await ta.fill(cover_letter)
            filled += 1
    except Exception:
        pass

    try:
        submit = page.locator("button[type='submit'], input[type='submit']").first
        if await submit.is_visible(timeout=3000):
            await submit.click()
            logger.info("Lever: submitted")
            return True
    except Exception as e:
        logger.warning("Lever submit: %s", e)

    return filled > 0
