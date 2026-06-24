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
