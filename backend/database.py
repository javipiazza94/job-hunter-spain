"""
database.py — SQLite schema, connection, and UPSERT helpers for Job Hunter Spain.
"""
import sqlite3
import uuid
from datetime import datetime
from config import DB_PATH

CREATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    website         TEXT,
    careers_url     TEXT,
    sector          TEXT,
    city            TEXT,
    country         TEXT DEFAULT 'ES',
    remote_policy   TEXT,
    salary_transparent INTEGER DEFAULT 1,
    linkedin_url    TEXT,
    source          TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_companies_sector ON companies(sector);
CREATE INDEX IF NOT EXISTS idx_companies_country ON companies(country);

CREATE TABLE IF NOT EXISTS job_offers (
    id              TEXT PRIMARY KEY,
    company_id      TEXT REFERENCES companies(id),
    title           TEXT NOT NULL,
    description     TEXT,
    location        TEXT,
    salary_min      INTEGER,
    salary_max      INTEGER,
    tech_stack      TEXT,
    url             TEXT UNIQUE,
    source          TEXT,
    posted_at       TEXT,
    is_relevant     INTEGER DEFAULT 0,
    relevance_score REAL DEFAULT 0.0,
    cv_profile      TEXT DEFAULT NULL,
    scraped_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_offers_company ON job_offers(company_id);
CREATE INDEX IF NOT EXISTS idx_offers_relevant ON job_offers(is_relevant);

CREATE TABLE IF NOT EXISTS contacts (
    id              TEXT PRIMARY KEY,
    company_id      TEXT REFERENCES companies(id),
    type            TEXT NOT NULL,
    value           TEXT NOT NULL,
    method          TEXT,
    verified        INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_unique ON contacts(company_id, type, value);

CREATE TABLE IF NOT EXISTS applications (
    id                   TEXT PRIMARY KEY,
    company_id           TEXT,
    job_offer_id         TEXT,
    contact_id           TEXT,
    status               TEXT DEFAULT 'sent',
    method               TEXT,
    sent_at              TEXT,
    cover_letter_used    TEXT,
    cover_letter_edited  TEXT,
    approved_at          TEXT,
    cv_profile           TEXT,
    notes                TEXT
);
CREATE INDEX IF NOT EXISTS idx_apps_company ON applications(company_id);
CREATE INDEX IF NOT EXISTS idx_apps_status ON applications(status);

CREATE TABLE IF NOT EXISTS company_contact_history (
    id              TEXT PRIMARY KEY,
    company_name    TEXT NOT NULL,
    company_domain  TEXT,
    email_used      TEXT NOT NULL,
    profile_used    TEXT NOT NULL,
    sent_at         TEXT NOT NULL,
    outcome         TEXT DEFAULT 'sin_respuesta',
    notes           TEXT,
    application_id  TEXT
);
CREATE INDEX IF NOT EXISTS idx_history_company ON company_contact_history(company_name);
CREATE INDEX IF NOT EXISTS idx_history_email ON company_contact_history(email_used);
CREATE INDEX IF NOT EXISTS idx_history_sent ON company_contact_history(sent_at);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(CREATE_SCHEMA)
    _run_migrations(conn)
    conn.commit()


def _run_migrations(conn: sqlite3.Connection) -> None:
    _add_column(conn, "job_offers", "cv_profile", "TEXT DEFAULT NULL")
    _add_column(conn, "applications", "cover_letter_edited", "TEXT")
    _add_column(conn, "applications", "approved_at", "TEXT")
    _add_column(conn, "applications", "cv_profile", "TEXT")


def _add_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists


def _new_id() -> str:
    return str(uuid.uuid4())


def upsert_company(conn: sqlite3.Connection, data: dict) -> str:
    """Insert or update a company. Returns the id used."""
    existing = conn.execute(
        "SELECT id FROM companies WHERE name = ?", (data["name"],)
    ).fetchone()

    if existing:
        cid = existing["id"]
        conn.execute(
            """UPDATE companies SET website=COALESCE(?,website),
               careers_url=COALESCE(?,careers_url),
               sector=COALESCE(?,sector), country=COALESCE(?,country),
               linkedin_url=COALESCE(?,linkedin_url)
               WHERE id=?""",
            (data.get("website"), data.get("careers_url"),
             data.get("sector"), data.get("country"),
             data.get("linkedin_url"), cid),
        )
    else:
        cid = data.get("id") or _new_id()
        conn.execute(
            """INSERT INTO companies
               (id, name, website, careers_url, sector, city, country,
                remote_policy, salary_transparent, linkedin_url, source, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cid, data["name"], data.get("website"), data.get("careers_url"),
             data.get("sector"), data.get("city"), data.get("country", "ES"),
             data.get("remote_policy"), data.get("salary_transparent", 1),
             data.get("linkedin_url"), data["source"],
             datetime.now().isoformat()),
        )
    conn.commit()
    return cid


def upsert_job_offer(conn: sqlite3.Connection, data: dict) -> str:
    """Insert or update a job offer (unique by URL). Returns the id used."""
    existing = conn.execute(
        "SELECT id FROM job_offers WHERE url = ?", (data["url"],)
    ).fetchone()

    if existing:
        oid = existing["id"]
        conn.execute(
            """UPDATE job_offers SET title=?, description=COALESCE(?,description),
               location=COALESCE(?,location), salary_min=COALESCE(?,salary_min),
               salary_max=COALESCE(?,salary_max), tech_stack=COALESCE(?,tech_stack),
               is_relevant=?, relevance_score=?, scraped_at=?
               WHERE id=?""",
            (data["title"], data.get("description"), data.get("location"),
             data.get("salary_min"), data.get("salary_max"), data.get("tech_stack"),
             int(data.get("is_relevant", 0)), data.get("relevance_score", 0.0),
             datetime.now().isoformat(), oid),
        )
    else:
        oid = _new_id()
        conn.execute(
            """INSERT INTO job_offers
               (id, company_id, title, description, location, salary_min, salary_max,
                tech_stack, url, source, posted_at, is_relevant, relevance_score, scraped_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (oid, data["company_id"], data["title"], data.get("description"),
             data.get("location"), data.get("salary_min"), data.get("salary_max"),
             data.get("tech_stack"), data["url"], data.get("source"),
             data.get("posted_at"), int(data.get("is_relevant", 0)),
             data.get("relevance_score", 0.0), datetime.now().isoformat()),
        )
    conn.commit()
    return oid


def upsert_contact(conn: sqlite3.Connection, data: dict) -> str:
    existing = conn.execute(
        "SELECT id FROM contacts WHERE company_id=? AND type=? AND value=?",
        (data["company_id"], data["type"], data["value"]),
    ).fetchone()

    if existing:
        return existing["id"]

    cid = _new_id()
    conn.execute(
        """INSERT INTO contacts (id, company_id, type, value, method, verified, created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (cid, data["company_id"], data["type"], data["value"],
         data.get("method"), 0, datetime.now().isoformat()),
    )
    conn.commit()
    return cid


def record_application(conn: sqlite3.Connection, data: dict) -> str:
    aid = _new_id()
    status = data.get("status", "sent")
    sent_at = data.get("sent_at")
    if sent_at is None and status == "sent":
        sent_at = datetime.now().isoformat()
    conn.execute(
        """INSERT INTO applications
           (id, company_id, job_offer_id, contact_id, status, method, sent_at,
            cover_letter_used, cv_profile, notes)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (aid, data["company_id"], data.get("job_offer_id"), data.get("contact_id"),
         status, data["method"], sent_at,
         data.get("cover_letter_used"), data.get("cv_profile"), data.get("notes")),
    )
    conn.commit()
    return aid


def get_pending_offers(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT jo.*, c.name as company_name, c.website, c.careers_url
           FROM job_offers jo
           JOIN companies c ON jo.company_id = c.id
           WHERE jo.is_relevant = 1
             AND jo.id NOT IN (SELECT job_offer_id FROM applications WHERE job_offer_id IS NOT NULL)
           ORDER BY jo.relevance_score DESC""",
    ).fetchall()


def get_all_companies(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT c.*,
               COUNT(DISTINCT jo.id) as offer_count,
               COUNT(DISTINCT a.id) as application_count
           FROM companies c
           LEFT JOIN job_offers jo ON jo.company_id = c.id
           LEFT JOIN applications a ON a.company_id = c.id
           GROUP BY c.id
           ORDER BY c.name""",
    ).fetchall()


def get_pending_applications(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT a.*, c.name as company_name, jo.title as job_title,
                  ct.value as contact_value, ct.type as contact_type
           FROM applications a
           LEFT JOIN companies c ON a.company_id = c.id
           LEFT JOIN job_offers jo ON a.job_offer_id = jo.id
           LEFT JOIN contacts ct ON a.contact_id = ct.id
           WHERE a.status = 'pending_approval'
           ORDER BY a.rowid DESC""",
    ).fetchall()


def record_history(conn: sqlite3.Connection, data: dict) -> str:
    hid = _new_id()
    conn.execute(
        """INSERT INTO company_contact_history
           (id, company_name, company_domain, email_used, profile_used, sent_at, outcome, notes, application_id)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (hid, data["company_name"], data.get("company_domain", ""),
         data["email_used"], data["profile_used"],
         data.get("sent_at") or datetime.now().isoformat(),
         data.get("outcome", "sin_respuesta"), data.get("notes"),
         data.get("application_id")),
    )
    conn.commit()
    return hid


def get_history(
    conn: sqlite3.Connection,
    company: str | None = None,
    profile: str | None = None,
    outcome: str | None = None,
) -> list[sqlite3.Row]:
    query = "SELECT * FROM company_contact_history"
    conditions: list[str] = []
    params: list = []
    if company:
        conditions.append("company_name LIKE ?")
        params.append(f"%{company}%")
    if profile:
        conditions.append("profile_used = ?")
        params.append(profile)
    if outcome:
        conditions.append("outcome = ?")
        params.append(outcome)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY sent_at DESC"
    return conn.execute(query, params).fetchall()


def get_dashboard_stats(conn: sqlite3.Connection) -> dict:
    sent_this_week = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE status='sent' AND sent_at > datetime('now', '-7 days')"
    ).fetchone()[0]
    pending = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE status='pending_approval'"
    ).fetchone()[0]
    total_sent = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE status='sent'"
    ).fetchone()[0]
    responded = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE status IN ('replied','interview')"
    ).fetchone()[0]
    sap_sent = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE status='sent' AND cv_profile='sap'"
    ).fetchone()[0]
    iadev_sent = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE status='sent' AND cv_profile='ia_dev'"
    ).fetchone()[0]
    return {
        "sent_this_week": sent_this_week,
        "pending_approval": pending,
        "total_sent": total_sent,
        "response_rate": round(responded / total_sent, 2) if total_sent > 0 else 0.0,
        "sap_ratio": round(sap_sent / total_sent, 2) if total_sent > 0 else 0.0,
        "ia_dev_ratio": round(iadev_sent / total_sent, 2) if total_sent > 0 else 0.0,
    }


def stats(conn: sqlite3.Connection) -> dict:
    return {
        "companies": conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0],
        "job_offers": conn.execute("SELECT COUNT(*) FROM job_offers").fetchone()[0],
        "relevant_offers": conn.execute("SELECT COUNT(*) FROM job_offers WHERE is_relevant=1").fetchone()[0],
        "applications_sent": conn.execute("SELECT COUNT(*) FROM applications WHERE status='sent'").fetchone()[0],
        "contacts_found": conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0],
    }
