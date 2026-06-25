import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_classify_profile_sap_offer():
    from automation.filter_engine import classify_profile
    offer = {
        "title": "Consultor SAP PS Senior",
        "description": "Proyecto de implantación SAP S/4HANA. ABAP, SAP BTP, SAP Fiori.",
    }
    profile, confidence = classify_profile(offer)
    assert profile == "sap"
    assert confidence >= 0.2


def test_classify_profile_iadev_offer():
    from automation.filter_engine import classify_profile
    offer = {
        "title": "Python Developer / AI Engineer",
        "description": "Desarrollamos con FastAPI, LLM, RAG, Python, Next.js y scraping Playwright.",
    }
    profile, confidence = classify_profile(offer)
    assert profile == "ia_dev"
    assert confidence >= 0.2


def test_classify_profile_ambiguous_returns_manual_review():
    from automation.filter_engine import classify_profile
    offer = {
        "title": "Consultor tecnológico",
        "description": "Trabajamos con varios ERPs y también con Python.",
    }
    profile, _ = classify_profile(offer)
    assert profile in ("manual_review", "sap", "ia_dev")


def test_classify_profile_empty_offer_returns_manual_review():
    from automation.filter_engine import classify_profile
    profile, confidence = classify_profile({"title": None, "description": None})
    assert profile == "manual_review"
    assert confidence == 0.0


def test_filter_offers_includes_cv_profile():
    from automation.filter_engine import filter_offers
    offers = [
        {"title": "SAP Consultant", "description": "SAP S/4HANA ABAP BTP", "location": "Sevilla"},
        {"title": "Python Dev", "description": "Python FastAPI LLM React", "location": "remoto"},
    ]
    result = filter_offers(offers)
    for r in result:
        assert "cv_profile" in r
        assert r["cv_profile"] in ("sap", "ia_dev", "manual_review")
