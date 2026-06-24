"""
automation/ats_handlers/successfactors.py — SAP SuccessFactors ATS handler.
May embed form in iframes; multi-step flow with Next/Submit buttons.
"""
import logging
from pathlib import Path
from playwright.async_api import Page
from automation.ats_handlers.generic import _dismiss_cookies

logger = logging.getLogger(__name__)


async def fill_successfactors(page: Page, profile: dict, cv_path: Path, cover_letter: str) -> bool:
    await _dismiss_cookies(page)
    personal = profile.get("personal", {})
    name_parts = personal.get("name", "").split(" ", 1)
    filled = 0

    target = page
    for frame in page.frames:
        if "successfactors" in (frame.url or "").lower():
            target = frame  # type: ignore[assignment]
            break

    for sel, value in [
        ("input[name*='firstName' i], input[id*='firstName' i]", name_parts[0] if name_parts else ""),
        ("input[name*='lastName' i], input[id*='lastName' i]",   name_parts[1] if len(name_parts) > 1 else ""),
        ("input[type='email'], input[name*='email' i]",          personal.get("email", "")),
        ("input[type='tel'], input[name*='phone' i]",            personal.get("phone", "")),
    ]:
        if not value:
            continue
        try:
            el = target.locator(sel).first
            if await el.is_visible(timeout=1500):
                await el.fill(value)
                filled += 1
        except Exception:
            pass

    if cv_path and cv_path.exists():
        try:
            fi = target.locator("input[type='file']").first
            if await fi.is_visible(timeout=2000):
                await fi.set_input_files(str(cv_path))
                filled += 1
        except Exception as e:
            logger.debug("SuccessFactors CV: %s", e)

    try:
        ta = target.locator("textarea").first
        if await ta.is_visible(timeout=1500):
            await ta.fill(cover_letter)
            filled += 1
    except Exception:
        pass

    for btn_text in ["Next", "Siguiente", "Continue", "Submit", "Enviar"]:
        try:
            btn = target.locator(f"button:text('{btn_text}'), input[value='{btn_text}']").first
            if await btn.is_visible(timeout=1500):
                await btn.click()
                await page.wait_for_timeout(1500)
                if btn_text in ("Submit", "Enviar"):
                    logger.info("SuccessFactors: submitted")
                    return True
        except Exception:
            continue

    if filled == 0:
        logger.warning("SuccessFactors: no fields filled — needs_manual_review")
    return filled > 0
