"""
automation/filter_engine.py — Scores job offers and classifies profile (sap/ia_dev/manual_review).

Scoring por categorías (pesos en config.SCORE_WEIGHTS), de mayor a menor prioridad:
1. sap_master     — SAP S/4HANA Public Cloud + módulos PS/MM/SD/FI del máster
2. previous_stack — Python, C#, SQL, Git, metodología DevOps (experiencia previa)
3. location       — Sevilla si es presencial, remoto si es fuera de Sevilla
4. experience     — prioridad a ofertas de menos de EXPERIENCE_PRIORITY_MAX_YEARS años
5. salary         — salario base >= SALARY_MIN_BASE
"""
from automation.experience_classifier import classify_experience
from config import (
    SAP_MASTER_KEYWORDS_BOOST,
    PREVIOUS_STACK_KEYWORDS_BOOST,
    NEGATIVE_KEYWORDS,
    MIN_RELEVANCE_SCORE,
    SCORE_WEIGHTS,
    TARGET_CITY,
    EXPERIENCE_PRIORITY_MAX_YEARS,
    SALARY_MIN_BASE,
    SAP_PROFILE_KEYWORDS,
    IADEV_PROFILE_KEYWORDS,
    PROFILE_CONFIDENCE_THRESHOLD,
)


def _location_score(location: str) -> float:
    """Sevilla presencial vale igual que remoto; presencial fuera de Sevilla no vale."""
    if not location:
        return 0.5  # ubicación desconocida — no penalizar del todo
    loc = location.lower()
    if "remoto" in loc or "remote" in loc:
        return 1.0
    if TARGET_CITY in loc:
        return 1.0
    if "híbrido" in loc or "hibrido" in loc or "hybrid" in loc:
        return 0.5  # híbrido sin confirmar que sea en Sevilla
    return 0.0  # presencial fuera de Sevilla


def _experience_score(title: str, description: str) -> float:
    """Prioriza ofertas junior (< EXPERIENCE_PRIORITY_MAX_YEARS años)."""
    level = classify_experience(title, description)
    if level == "junior":
        return 1.0
    if level == "mid":
        return 0.5
    if level in ("senior", "lead"):
        return 0.0
    return 0.5  # nivel no especificado — no penalizar del todo


def _salary_score(offer: dict) -> float:
    """Salario base >= SALARY_MIN_BASE."""
    salary_min = offer.get("salary_min")
    salary_max = offer.get("salary_max")
    if salary_min:
        return 1.0 if salary_min >= SALARY_MIN_BASE else 0.0
    if salary_max:
        return 0.5 if salary_max >= SALARY_MIN_BASE else 0.0
    return 0.5  # salario no publicado — no penalizar del todo


def score_offer(offer: dict) -> float:
    """Calculate relevance score for a job offer dict."""
    title = (offer.get("title") or "").lower()
    description = (offer.get("description") or "").lower()
    location = (offer.get("location") or "").lower()
    tech_stack_raw = offer.get("tech_stack") or ""
    if isinstance(tech_stack_raw, list):
        tech_stack = " ".join(tech_stack_raw).lower()
    else:
        tech_stack = tech_stack_raw.lower()

    full_text = f"{title} {description} {tech_stack}"

    for neg in NEGATIVE_KEYWORDS:
        if neg.lower() in full_text:
            return 0.0

    sap_hits = sum(1 for kw in SAP_MASTER_KEYWORDS_BOOST if kw.lower() in full_text)
    sap_score = min(sap_hits, 5) / 5

    prev_hits = sum(1 for kw in PREVIOUS_STACK_KEYWORDS_BOOST if kw.lower() in full_text)
    prev_score = min(prev_hits, 5) / 5

    loc_score = _location_score(location)
    exp_score = _experience_score(title, description)
    sal_score = _salary_score(offer)

    score = (
        SCORE_WEIGHTS["sap_master"] * sap_score
        + SCORE_WEIGHTS["previous_stack"] * prev_score
        + SCORE_WEIGHTS["location"] * loc_score
        + SCORE_WEIGHTS["experience"] * exp_score
        + SCORE_WEIGHTS["salary"] * sal_score
    )

    return round(min(score, 1.0), 3)


def classify_profile(offer: dict) -> tuple[str, float]:
    """
    Classify offer as 'sap', 'ia_dev', or 'manual_review'.
    Returns (profile, confidence) where confidence is the score difference.
    """
    title = (offer.get("title") or "").lower()
    description = (offer.get("description") or "").lower()
    full_text = f"{title} {description}"

    sap_hits = sum(1 for kw in SAP_PROFILE_KEYWORDS if kw in full_text)
    iadev_hits = sum(1 for kw in IADEV_PROFILE_KEYWORDS if kw in full_text)

    if sap_hits == 0 and iadev_hits == 0:
        return ("manual_review", 0.0)

    # Clear winner: one side has hits, other has none — classify directly
    if sap_hits > 0 and iadev_hits == 0:
        return ("sap", sap_hits / len(SAP_PROFILE_KEYWORDS))
    if iadev_hits > 0 and sap_hits == 0:
        return ("ia_dev", iadev_hits / len(IADEV_PROFILE_KEYWORDS))

    # Both have hits — use threshold to resolve ambiguity
    sap_score = sap_hits / len(SAP_PROFILE_KEYWORDS)
    iadev_score = iadev_hits / len(IADEV_PROFILE_KEYWORDS)
    diff = abs(sap_score - iadev_score)

    if diff < PROFILE_CONFIDENCE_THRESHOLD:
        return ("manual_review", diff)

    return ("sap", diff) if sap_score > iadev_score else ("ia_dev", diff)


def filter_offers(offers: list[dict]) -> list[dict]:
    """Add relevance_score, is_relevant, and cv_profile to each offer dict."""
    result = []
    for offer in offers:
        s = score_offer(offer)
        profile, _ = classify_profile(offer)
        result.append({
            **offer,
            "relevance_score": s,
            "is_relevant": s >= MIN_RELEVANCE_SCORE,
            "cv_profile": profile,
        })
    return sorted(result, key=lambda x: x["relevance_score"], reverse=True)
