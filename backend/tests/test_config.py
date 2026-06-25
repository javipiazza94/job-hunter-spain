def test_sap_keywords_non_empty():
    from config import SAP_KEYWORDS
    assert len(SAP_KEYWORDS) >= 10
    assert "SAP BTP" in SAP_KEYWORDS
    assert "S/4HANA" in SAP_KEYWORDS

def test_sap_companies_direct_structure():
    from config import SAP_COMPANIES_DIRECT
    assert len(SAP_COMPANIES_DIRECT) >= 5
    for c in SAP_COMPANIES_DIRECT:
        assert "name" in c
        assert "careers_url" in c
        assert c["careers_url"].startswith("https://")

def test_linkedin_sap_searches_structure():
    from config import LINKEDIN_SAP_SEARCHES
    assert len(LINKEDIN_SAP_SEARCHES) >= 3
    for s in LINKEDIN_SAP_SEARCHES:
        assert "keywords" in s
        assert "location" in s

def test_sessions_paths_defined():
    from config import SESSIONS_DIR, LINKEDIN_SESSION_PATH
    assert "sessions" in str(SESSIONS_DIR)
    assert str(LINKEDIN_SESSION_PATH).endswith(".json")

def test_new_profile_constants_exist():
    from config import (
        SAP_PROFILE_KEYWORDS,
        IADEV_PROFILE_KEYWORDS,
        PROFILE_CONFIDENCE_THRESHOLD,
        RECONTACT_COOLDOWN_DAYS,
    )
    assert isinstance(SAP_PROFILE_KEYWORDS, list)
    assert len(SAP_PROFILE_KEYWORDS) >= 10
    assert isinstance(IADEV_PROFILE_KEYWORDS, list)
    assert len(IADEV_PROFILE_KEYWORDS) >= 10
    assert 0.0 < PROFILE_CONFIDENCE_THRESHOLD < 1.0
    assert RECONTACT_COOLDOWN_DAYS > 0

def test_max_emails_per_day_is_15():
    from config import MAX_EMAILS_PER_DAY
    assert MAX_EMAILS_PER_DAY == 15
