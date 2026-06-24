import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_detect_ats_workday():
    from automation.ats_handlers import detect_ats
    assert detect_ats("https://accenture.wd3.myworkdayjobs.com/AccentureCareers/job/123") == "workday"

def test_detect_ats_greenhouse():
    from automation.ats_handlers import detect_ats
    assert detect_ats("https://boards.greenhouse.io/seidor/jobs/789") == "greenhouse"

def test_detect_ats_lever():
    from automation.ats_handlers import detect_ats
    assert detect_ats("https://jobs.lever.co/stratesys/123abc") == "lever"

def test_detect_ats_successfactors():
    from automation.ats_handlers import detect_ats
    assert detect_ats("https://stratesys.jobs.eu2.successfactors.eu/job/123") == "successfactors"
    assert detect_ats("https://jobs.sap.com/careers/job/123") == "successfactors"

def test_detect_ats_generic_fallback():
    from automation.ats_handlers import detect_ats
    assert detect_ats("https://www.seidor.com/trabaja/apply") == "generic"

def test_map_field_email():
    from automation.ats_handlers.generic import _map_field
    profile = {"personal": {"name": "Juan García", "email": "juan@example.com", "phone": "+34 600 000 000", "linkedin": "https://linkedin.com/in/juan"}}
    assert _map_field("email", profile) == "juan@example.com"

def test_map_field_first_and_last_name():
    from automation.ats_handlers.generic import _map_field
    profile = {"personal": {"name": "Juan García", "email": "j@e.com", "phone": "", "linkedin": ""}}
    assert _map_field("first_name", profile) == "Juan"
    assert _map_field("last_name", profile) == "García"

def test_map_field_unknown_returns_none():
    from automation.ats_handlers.generic import _map_field
    profile = {"personal": {"name": "Juan García", "email": "j@e.com", "phone": "", "linkedin": ""}}
    assert _map_field("random_unknown_field_xyz", profile) is None
