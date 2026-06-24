"""
automation/ats_handlers/generic.py — Generic form filler via label/name/placeholder detection.
"""
import logging
from pathlib import Path
from playwright.async_api import Page

logger = logging.getLogger(__name__)

_FIELD_HINTS: dict[str, tuple[str, ...]] = {
    "first_name":   ("first_name", "nombre", "firstname"),
    "last_name":    ("last_name", "apellido", "apellidos", "surname", "lastname"),
    "email":        ("email", "correo", "e-mail"),
    "phone":        ("phone", "teléfono", "telefono", "móvil", "movil", "tel"),
    "linkedin":     ("linkedin",),
    "cover_letter": ("cover_letter", "carta", "motivac", "message", "mensaje", "presentation"),
}


def _map_field(field_hint: str, profile: dict) -> str | None:
    hint = field_hint.lower()
    personal = profile.get("personal", {})
    name_parts = personal.get("name", "").split(" ", 1)
    for canonical, hints in _FIELD_HINTS.items():
        if any(h in hint for h in hints):
            if canonical == "first_name":
                return name_parts[0] if name_parts else ""
            if canonical == "last_name":
                return name_parts[1] if len(name_parts) > 1 else ""
            if canonical == "email":
                return personal.get("email", "")
            if canonical == "phone":
                return personal.get("phone", "")
            if canonical == "linkedin":
                return personal.get("linkedin", "")
            if canonical == "cover_letter":
                return None  # injected by caller
    return None


async def _dismiss_cookies(page: Page) -> None:
    for sel in [
        "button[id*='accept']", "button[class*='accept']",
        "#onetrust-accept-btn-handler", ".cc-btn.cc-allow",
        "button:text('Aceptar')", "button:text('Accept all')",
    ]:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=800):
                await btn.click()
                return
        except Exception:
            continue


async def fill_generic(
    page: Page,
    profile: dict,
    cv_path: Path,
    cover_letter: str,
) -> bool:
    await _dismiss_cookies(page)
    filled = 0
    inputs = await page.query_selector_all(
        "input:not([type='hidden']):not([type='submit']):not([type='button']), textarea"
    )
    for inp in inputs:
        try:
            input_type = (await inp.get_attribute("type") or "text").lower()
            if input_type == "file":
                if cv_path and cv_path.exists():
                    await inp.set_input_files(str(cv_path))
                    filled += 1
                continue
            name = (await inp.get_attribute("name") or "").lower()
            placeholder = (await inp.get_attribute("placeholder") or "").lower()
            aria = (await inp.get_attribute("aria-label") or "").lower()
            hint = name or placeholder or aria
            if not hint:
                continue
            if any(h in hint for h in ("cover_letter", "carta", "motivac", "message", "mensaje")):
                await inp.fill(cover_letter)
                filled += 1
                continue
            value = _map_field(hint, profile)
            if value:
                await inp.fill(value)
                filled += 1
        except Exception as e:
            logger.debug("Field fill error: %s", e)
    logger.info("Generic form: %d fields filled", filled)
    return filled > 0
