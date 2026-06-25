"""
automation/cover_letter.py — Generates personalised cover letters via Jinja2.
Supports variant_seed for deterministic cover letter variation per company.
"""
import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from config import PROFILE_PATH, TEMPLATES_DIR


def _load_profile() -> dict:
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def _pick_variant(variants: list[str], seed: str) -> str:
    """Return one variant deterministically based on seed."""
    return variants[hash(seed) % len(variants)]


def generate(
    company_name: str,
    job_title: str | None = None,
    tech_stack: str | None = None,
    template: str = "tech",
    variant_seed: str | None = None,
) -> str:
    """Return rendered cover letter as plain text."""
    profile = _load_profile()
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    tmpl_name = f"cover_letter_{template}.j2"
    try:
        tmpl = env.get_template(tmpl_name)
    except Exception:
        tmpl = env.get_template("cover_letter_base.j2")

    personal = profile.get("personal", {})
    seed = variant_seed or (company_name + (job_title or ""))
    variant_index = hash(seed) % 3

    return tmpl.render(
        company_name=company_name,
        job_title=job_title,
        tech_stack=tech_stack,
        name=personal.get("name", ""),
        email=personal.get("email", ""),
        phone=personal.get("phone", ""),
        linkedin=personal.get("linkedin", ""),
        portfolio=personal.get("portfolio", ""),
        experience=profile.get("experience", []),
        cover_letter_intro=profile.get("cover_letter_intro", "").format(company_name=company_name),
        cover_letter_stack=profile.get("cover_letter_stack", ""),
        cover_letter_closing=profile.get("cover_letter_closing", ""),
        variant_index=variant_index,
    )
