"""
automation/ats_handlers/workday.py — Workday ATS multi-step handler.
Handles iframe-embedded forms and multi-step navigation.
"""
import logging
from pathlib import Path
from playwright.async_api import Page
from automation.ats_handlers.generic import _dismiss_cookies, _map_field

logger = logging.getLogger(__name__)

_FIELDS = [
    ("firstName", "first_name"),
    ("lastName",  "last_name"),
    ("email",     "email"),
    ("phone",     "phone"),
    ("linkedIn",  "linkedin"),
]


async def fill_workday(page: Page, profile: dict, cv_path: Path, cover_letter: str) -> bool:
    await _dismiss_cookies(page)

    target = page
    for frame in page.frames:
        if "myworkdayjobs" in (frame.url or "").lower():
            target = frame  # type: ignore[assignment]
            break

    filled = 0
    for field_name, _ in _FIELDS:
        value = _map_field(field_name, profile)
        if not value:
            continue
        for sel in [
            f"input[data-automation-id='{field_name}']",
            f"input[name='{field_name}']",
            f"input[id*='{field_name}' i]",
        ]:
            try:
                el = target.locator(sel).first
                if await el.is_visible(timeout=1200):
                    await el.fill(value)
                    filled += 1
                    break
            except Exception:
                continue

    if cv_path and cv_path.exists():
        try:
            fi = target.locator("input[type='file']").first
            if await fi.is_visible(timeout=2000):
                await fi.set_input_files(str(cv_path))
                filled += 1
        except Exception as e:
            logger.debug("Workday CV upload: %s", e)

    try:
        for ta in await target.query_selector_all("textarea"):
            await ta.fill(cover_letter)
            filled += 1
    except Exception:
        pass

    for btn_text in ["Next", "Siguiente", "Submit", "Enviar"]:
        try:
            btn = target.locator(
                f"button[data-automation-id='bottom-navigation-next-btn'], button:text('{btn_text}')"
            ).first
            if await btn.is_visible(timeout=1500):
                await btn.click()
                await page.wait_for_timeout(1500)
                if btn_text in ("Submit", "Enviar"):
                    logger.info("Workday: submitted")
                    return True
        except Exception:
            continue

    if filled == 0:
        logger.warning("Workday: no fields filled — needs_manual_review")
    return filled > 0
