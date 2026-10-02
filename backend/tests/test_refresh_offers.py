import sys
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from automation import refresh_offers as ro
from database import init_db, upsert_job_offer, upsert_company, get_pending_offers


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def test_classify_response():
    assert ro.classify_response(404, "") == ro.INACTIVE
    assert ro.classify_response(410, "") == ro.INACTIVE
    assert ro.classify_response(403, "") == ro.UNKNOWN
    assert ro.classify_response(429, "") == ro.UNKNOWN
    assert ro.classify_response(200, "<h1>Esta oferta ya no está disponible</h1>") == ro.INACTIVE
    assert ro.classify_response(200, "Please solve this CAPTCHA") == ro.UNKNOWN
    assert ro.classify_response(200, "<h1>Python Developer</h1> apply now") == ro.ACTIVE


def test_migration_adds_active_columns():
    cols = {r[1] for r in _conn().execute("PRAGMA table_info(job_offers)").fetchall()}
    assert {"is_active", "last_checked_at", "inactive_reason"} <= cols


def _add(conn, url, scraped_at, relevant=1):
    cid = upsert_company(conn, {"name": "Acme", "source": "test"})
    oid = upsert_job_offer(conn, {"company_id": cid, "title": "Dev", "url": url,
                                  "is_relevant": relevant, "relevance_score": 0.8})
    conn.execute("UPDATE job_offers SET scraped_at=? WHERE id=?", (scraped_at, oid))
    conn.commit()
    return oid


def test_verify_marks_inactive_and_keeps_active(monkeypatch):
    conn = _conn()
    old = (datetime.now() - timedelta(days=2)).isoformat()
    dead = _add(conn, "https://x/dead", old)
    live = _add(conn, "https://x/live", old)
    blocked = _add(conn, "https://x/blocked", old)
    verdicts = {"https://x/dead": ro.INACTIVE, "https://x/live": ro.ACTIVE, "https://x/blocked": ro.UNKNOWN}
    monkeypatch.setattr(ro, "check_offer", lambda s, url, src: verdicts[url])
    monkeypatch.setattr(ro.time, "sleep", lambda *_: None)

    res = ro.verify_offers(conn, datetime.now().isoformat(), 100, 60, dry_run=False)

    assert (res["inactive"], res["active"], res["unknown"]) == (1, 1, 1)
    flag = lambda i: conn.execute("SELECT is_active FROM job_offers WHERE id=?", (i,)).fetchone()[0]
    assert (flag(dead), flag(live), flag(blocked)) == (0, 1, 1)
    assert dead not in {r["id"] for r in get_pending_offers(conn)}


def test_stale_unknown_is_deactivated_and_dry_run_writes_nothing(monkeypatch):
    conn = _conn()
    very_old = (datetime.now() - timedelta(days=90)).isoformat()
    oid = _add(conn, "https://x/old", very_old)
    monkeypatch.setattr(ro, "check_offer", lambda *a: ro.UNKNOWN)
    monkeypatch.setattr(ro.time, "sleep", lambda *_: None)

    ro.verify_offers(conn, datetime.now().isoformat(), 100, 60, dry_run=True)
    assert conn.execute("SELECT is_active FROM job_offers WHERE id=?", (oid,)).fetchone()[0] == 1

    res = ro.verify_offers(conn, datetime.now().isoformat(), 100, 60, dry_run=False)
    row = conn.execute("SELECT is_active, inactive_reason FROM job_offers WHERE id=?", (oid,)).fetchone()
    assert res["stale"] == 1 and row["is_active"] == 0 and row["inactive_reason"].startswith("stale")


def test_rescrape_reactivates_offer():
    conn = _conn()
    oid = _add(conn, "https://x/back", datetime.now().isoformat())
    conn.execute("UPDATE job_offers SET is_active=0, inactive_reason='closed' WHERE id=?", (oid,))
    cid = conn.execute("SELECT company_id FROM job_offers WHERE id=?", (oid,)).fetchone()[0]
    upsert_job_offer(conn, {"company_id": cid, "title": "Dev", "url": "https://x/back",
                            "is_relevant": 1, "relevance_score": 0.8})
    assert conn.execute("SELECT is_active FROM job_offers WHERE id=?", (oid,)).fetchone()[0] == 1
