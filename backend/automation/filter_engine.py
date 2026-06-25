"""
automation/filter_engine.py — Scores job offers and classifies profile (sap/ia_dev/manual_review).
"""
import json
from config import (
    STACK_KEYWORDS_BOOST,
    TITLE_KEYWORDS_BOOST,
    LOCATION_BOOST,
    NEGATIVE_KEYWORDS,
    MIN_RELEVANCE_SCORE,
    SAP_PROFILE_KEYWORDS,
    IADEV_PROFILE_KEYWORDS,
    PROFILE_CONFIDENCE_THRESHOLD,
)


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

    score = 0.0
    max_score = 0.0

    title_hits = sum(1 for kw in TITLE_KEYWORDS_BOOST if kw.lower() in title)
    score += 0.4 * (min(title_hits, 3) / 3)
    max_score += 0.4

    stack_hits = sum(1 for kw in STACK_KEYWORDS_BOOST if kw.lower() in full_text)
    score += 0.45 * (min(stack_hits, 5) / 5)
    max_score += 0.45

    location_match = any(loc in location for loc in LOCATION_BOOST)
    if location_match:
        score += 0.15
    max_score += 0.15

    return round(min(score / max_score, 1.0), 3) if max_score > 0 else 0.0


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
