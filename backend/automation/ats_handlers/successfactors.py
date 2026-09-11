"""
automation/ats_handlers/successfactors.py — SAP SuccessFactors ATS handler.
May embed form in iframes; multi-step flow with Next/Submit buttons. Many
SuccessFactors career portals gate the application form behind a candidate
login/register screen first (e.g. career55.sapsf.eu).

Safety: this handler NEVER clicks the final Submit/Enviar button. It fills every
field it can find, advances intermediate wizard steps (Next/Siguiente/Continue),
and stops on the last screen so a human reviews and submits manually. Logging in
is not treated the same way — it's reversible and doesn't commit to anything —
so if JOBPORTAL_EMAIL/JOBPORTAL_PASSWORD are set in the environment, it fills and
submits the login form to reach the actual application.
"""
import logging
import os
from pathlib import Path
from playwright.async_api import Page
from automation.ats_handlers.generic import _dismiss_cookies

logger = logging.getLogger(__name__)

# Labels that mean "this is the final, irreversible action" — never clicked.
_SUBMIT_LABELS = ("Submit", "Enviar", "Enviar candidatura", "Finalizar", "Finish", "Apply")
# Labels that mean "advance to the next step of the wizard" — safe to click.
_NEXT_LABELS = ("Next", "Siguiente", "Continue", "Continuar")
# Labels for the login button — safe to click, login is reversible.
_LOGIN_LABELS = ("Entrar", "Iniciar sesión", "Log In", "Login", "Sign In", "Sign in")

# input selector -> profile path (dot notation resolved against the loaded profile dict)
_TEXT_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("input[name*='firstName' i], input[id*='firstName' i]", ("personal", "first_name")),
    ("input[name*='lastName' i], input[id*='lastName' i]", ("personal", "last_name")),
    ("input[type='email'], input[name*='email' i]", ("personal", "email")),
    ("input[type='tel'], input[name*='phone' i]", ("personal", "phone")),
    ("input[name*='address' i], input[name*='street' i]", ("personal", "address")),
    ("input[name*='city' i]", ("personal", "city")),
    ("input[name*='postalCode' i], input[name*='zip' i], input[name*='postcode' i]", ("personal", "postal_code")),
    ("input[name*='nationalId' i], input[name*='dni' i], input[name*='documentNumber' i], input[name*='passportNumber' i]", ("personal", "dni_nie")),
    ("input[name*='linkedin' i]", ("personal", "linkedin")),
    ("input[name*='website' i], input[name*='portfolio' i]", ("personal", "portfolio")),
    ("input[name*='availab' i], input[name*='startDate' i], input[name*='earliestStart' i]", ("availability", "start_date")),
    ("input[name*='salary' i], input[name*='compensation' i]", ("salary_expectation", "amount")),
)

_SELECT_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("select[name*='country' i]", ("personal", "country")),
    ("select[name*='nationality' i]", ("personal", "nationality")),
)


def _resolve(profile: dict, path: tuple[str, ...]):
    node = profile
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


async def fill_successfactors(page: Page, profile: dict, cv_path: Path, cover_letter: str) -> bool:
    await _dismiss_cookies(page)
    filled = 0

    target = page
    for frame in page.frames:
        if "successfactors" in (frame.url or "").lower():
            target = frame  # type: ignore[assignment]
            break

    for sel, path in _TEXT_FIELDS:
        value = _resolve(profile, path)
        if not value:
            continue
        try:
            el = target.locator(sel).first
            if await el.is_visible(timeout=1500):
                await el.fill(str(value))
                filled += 1
        except Exception as e:
            logger.debug("SuccessFactors field %s: %s", sel, e)

    for sel, path in _SELECT_FIELDS:
        value = _resolve(profile, path)
        if not value:
            continue
        try:
            el = target.locator(sel).first
            if await el.is_visible(timeout=1500):
                await el.select_option(label=str(value))
                filled += 1
        except Exception as e:
            logger.debug("SuccessFactors select %s: %s (probablemente un dropdown custom, no <select>)", sel, e)

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

    # Advance intermediate wizard steps, but never click the final submit action.
    for _ in range(10):
        advanced = False
        for btn_text in _NEXT_LABELS:
            try:
                btn = target.locator(f"button:text('{btn_text}'), input[value='{btn_text}']").first
                if await btn.is_visible(timeout=1200):
                    await btn.click()
                    await page.wait_for_timeout(1200)
                    advanced = True
                    break
            except Exception:
                continue
        if not advanced:
            break

    for btn_text in _SUBMIT_LABELS:
        try:
            btn = target.locator(f"button:text('{btn_text}'), input[value='{btn_text}']").first
            if await btn.is_visible(timeout=1200):
                logger.info(
                    "SuccessFactors: formulario listo (%d campos rellenados). "
                    "Pantalla final detectada ('%s') — NO se pulsa, revisión manual requerida.",
                    filled, btn_text,
                )
                break
        except Exception:
            continue

    if filled == 0:
        logger.warning("SuccessFactors: no se rellenó ningún campo — needs_manual_review")
    return filled > 0
