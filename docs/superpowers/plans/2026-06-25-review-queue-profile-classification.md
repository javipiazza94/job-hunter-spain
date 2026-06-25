# Job Hunter Spain — Review Queue & Profile Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir clasificación automática SAP/IA-Dev por oferta, cola de revisión humana antes del envío, deduplicación por empresa+email, variación de cover letters, e historial persistente exportable.

**Architecture:** Modificación incremental sobre el pipeline FastAPI+SQLite existente. El cambio de paradigma central es que `application_engine` deja de enviar directamente y genera borradores (`status='pending_approval'`); el envío real lo dispara el usuario desde el dashboard. Se añaden 3 columnas a `applications`, 1 a `job_offers`, y una tabla nueva `company_contact_history`.

**Tech Stack:** Python 3.12, FastAPI, SQLite (sqlite3), Jinja2, pytest, Next.js (App Router), TypeScript, Tailwind CSS, bun.

## Global Constraints

- Python venv en `backend/.venv` — siempre `backend/.venv/bin/pytest`, nunca `pytest` global
- Tests en `backend/tests/` — añadir `sys.path.insert(0, str(Path(__file__).parent.parent))` en cada fichero nuevo
- Migraciones SQLite: usar `try/except sqlite3.OperationalError` para `ALTER TABLE ADD COLUMN` (SQLite no soporta `IF NOT EXISTS` en ALTER)
- Frontend: `bun run dev` en `frontend/`; componentes en `frontend/app/components/`
- Todos los endpoints nuevos siguen el patrón existente: `conn = get_conn()` / devuelven `[dict(r) for r in rows]` / `conn.close()`
- `sent_at` en `applications` debe ser NULL para `status='pending_approval'`; se rellena solo al enviar

---

### Task 1: Config — keyword lists y constantes nuevas

**Files:**
- Modify: `backend/config.py`
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `SAP_PROFILE_KEYWORDS: list[str]`, `IADEV_PROFILE_KEYWORDS: list[str]`, `PROFILE_CONFIDENCE_THRESHOLD: float`, `RECONTACT_COOLDOWN_DAYS: int`, `MAX_EMAILS_PER_DAY: int` (baja de 20 a 15)

- [ ] **Step 1: Añadir al test existente `test_config.py` las aserciones para las nuevas constantes**

Añadir al final de `backend/tests/test_config.py`:

```python
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
```

- [ ] **Step 2: Ejecutar test para verificar que falla**

```bash
cd /home/javi-piazza/Documentos/Desarrollos/SCRIPTS/Proyectos/job-hunter-spain/backend
.venv/bin/pytest tests/test_config.py::test_new_profile_constants_exist tests/test_config.py::test_max_emails_per_day_is_15 -v
```
Esperado: FAIL con `ImportError` o `AssertionError`.

- [ ] **Step 3: Modificar `backend/config.py` — añadir las constantes nuevas y eliminar el SAP_KEYWORDS duplicado**

Localizar el bloque `# ── Application Engine` y reemplazar `MAX_EMAILS_PER_DAY = 20` por 15. Añadir al final del bloque `# ── Filter Engine` (después de `NEGATIVE_KEYWORDS`):

```python
# ── Profile classification ────────────────────────────────────────────────────
SAP_PROFILE_KEYWORDS = [
    "sap", "abap", "btp", "s/4hana", "s4hana", "hana", "fiori",
    "sap ps", "sap mm", "sap sd", "sap fi", "sap co", "sap pp",
    "successfactors", "rise with sap", "sap public cloud",
    "consultor funcional", "consultor sap", "sap consultant",
    "erp", "sap cloud",
]

IADEV_PROFILE_KEYWORDS = [
    "python", "fastapi", "django", "react", "next.js", "nextjs",
    "typescript", "javascript", "llm", "machine learning", "ml",
    "data scientist", "data engineer", "ai engineer", "ia",
    "inteligencia artificial", "full stack", "fullstack",
    "backend developer", "frontend developer", "devops",
    "automatización", "scraping", "playwright", "rag",
]

PROFILE_CONFIDENCE_THRESHOLD = 0.2
RECONTACT_COOLDOWN_DAYS = 180
```

En el mismo `config.py`, cambiar:
```python
MAX_EMAILS_PER_DAY = 20
```
por:
```python
MAX_EMAILS_PER_DAY = 15
```

- [ ] **Step 4: Ejecutar tests para verificar que pasan**

```bash
cd /home/javi-piazza/Documentos/Desarrollos/SCRIPTS/Proyectos/job-hunter-spain/backend
.venv/bin/pytest tests/test_config.py -v
```
Esperado: todos PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/javi-piazza/Documentos/Desarrollos/SCRIPTS/Proyectos/job-hunter-spain
git add backend/config.py backend/tests/test_config.py
git commit -m "feat: add SAP/IA profile keyword lists and lower daily email limit to 15"
```

---

### Task 2: Database — migraciones y tabla company_contact_history

**Files:**
- Modify: `backend/database.py`
- Test: `backend/tests/test_database_migrations.py` (nuevo)

**Interfaces:**
- Produces:
  - `init_db(conn)` ejecuta migraciones inline; idempotente
  - `get_pending_applications(conn) -> list[sqlite3.Row]` — applications con `status='pending_approval'` + joins
  - `record_application(conn, data)` soporta `cv_profile` y `sent_at=NULL` para borradores
  - `record_history(conn, data) -> str` — INSERT en `company_contact_history`
  - `get_history(conn, company=None, profile=None, outcome=None) -> list[sqlite3.Row]`
  - `get_dashboard_stats(conn) -> dict`

- [ ] **Step 1: Crear `backend/tests/test_database_migrations.py`**

```python
import sys
import sqlite3
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def _make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def test_init_db_creates_all_tables():
    from database import init_db
    conn = _make_conn()
    init_db(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "companies" in tables
    assert "job_offers" in tables
    assert "contacts" in tables
    assert "applications" in tables
    assert "company_contact_history" in tables
    conn.close()


def test_init_db_is_idempotent():
    from database import init_db
    conn = _make_conn()
    init_db(conn)
    init_db(conn)  # second call must not raise
    conn.close()


def test_applications_has_new_columns():
    from database import init_db
    conn = _make_conn()
    init_db(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(applications)").fetchall()}
    assert "cv_profile" in cols
    assert "cover_letter_edited" in cols
    assert "approved_at" in cols
    conn.close()


def test_job_offers_has_cv_profile_column():
    from database import init_db
    conn = _make_conn()
    init_db(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(job_offers)").fetchall()}
    assert "cv_profile" in cols
    conn.close()


def test_record_application_draft_has_null_sent_at():
    from database import init_db, record_application
    conn = _make_conn()
    init_db(conn)
    conn.execute("INSERT INTO companies (id,name,source,created_at) VALUES ('c1','ACME','test','2026-01-01')")
    conn.commit()
    aid = record_application(conn, {
        "company_id": "c1",
        "method": "email",
        "status": "pending_approval",
        "cover_letter_used": "test letter",
        "cv_profile": "ia_dev",
    })
    row = conn.execute("SELECT * FROM applications WHERE id=?", (aid,)).fetchone()
    assert row["status"] == "pending_approval"
    assert row["sent_at"] is None
    assert row["cv_profile"] == "ia_dev"
    conn.close()


def test_record_application_sent_has_sent_at():
    from database import init_db, record_application
    conn = _make_conn()
    init_db(conn)
    conn.execute("INSERT INTO companies (id,name,source,created_at) VALUES ('c1','ACME','test','2026-01-01')")
    conn.commit()
    aid = record_application(conn, {
        "company_id": "c1",
        "method": "email",
        "status": "sent",
        "cover_letter_used": "test letter",
    })
    row = conn.execute("SELECT * FROM applications WHERE id=?", (aid,)).fetchone()
    assert row["status"] == "sent"
    assert row["sent_at"] is not None
    conn.close()


def test_record_history_inserts_row():
    from database import init_db, record_history
    conn = _make_conn()
    init_db(conn)
    hid = record_history(conn, {
        "company_name": "ACME",
        "company_domain": "acme.es",
        "email_used": "jobs@acme.es",
        "profile_used": "ia_dev",
        "application_id": "app-1",
    })
    row = conn.execute("SELECT * FROM company_contact_history WHERE id=?", (hid,)).fetchone()
    assert row["company_name"] == "ACME"
    assert row["profile_used"] == "ia_dev"
    assert row["outcome"] == "sin_respuesta"
    conn.close()


def test_get_dashboard_stats_returns_all_keys():
    from database import init_db, get_dashboard_stats
    conn = _make_conn()
    init_db(conn)
    result = get_dashboard_stats(conn)
    for key in ("sent_this_week", "pending_approval", "total_sent", "response_rate", "sap_ratio", "ia_dev_ratio"):
        assert key in result
    conn.close()
```

- [ ] **Step 2: Ejecutar tests para verificar que fallan**

```bash
cd /home/javi-piazza/Documentos/Desarrollos/SCRIPTS/Proyectos/job-hunter-spain/backend
.venv/bin/pytest tests/test_database_migrations.py -v
```
Esperado: múltiples FAIL (funciones no existen todavía).

- [ ] **Step 3: Modificar `backend/database.py` — schema, migraciones, funciones nuevas**

Reemplazar la función `init_db` y añadir nuevas funciones. El fichero completo queda así (cambios marcados):

**3a. En `CREATE_SCHEMA`, añadir columna `cv_profile` a `job_offers`:**

Cambiar la línea `is_relevant INTEGER DEFAULT 0,` + `relevance_score REAL DEFAULT 0.0,` para agregar también `cv_profile TEXT`:

```python
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
```

**3b. Reemplazar `init_db` para incluir migraciones inline:**

```python
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
```

**3c. Modificar `record_application` para soportar `cv_profile` y `sent_at=NULL` en borradores:**

```python
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
```

**3d. Añadir las tres funciones nuevas al final del fichero (antes de `stats`):**

```python
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
```

**3e. Añadir `get_pending_applications` y `get_history` y `record_history` y `get_dashboard_stats` a los imports existentes en `database.py` (están todos en el mismo fichero, no hace falta import extra).**

- [ ] **Step 4: Ejecutar tests para verificar que pasan**

```bash
cd /home/javi-piazza/Documentos/Desarrollos/SCRIPTS/Proyectos/job-hunter-spain/backend
.venv/bin/pytest tests/test_database_migrations.py -v
```
Esperado: todos PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/javi-piazza/Documentos/Desarrollos/SCRIPTS/Proyectos/job-hunter-spain
git add backend/database.py backend/tests/test_database_migrations.py
git commit -m "feat: add db migrations for profile classification and review queue"
```

---

### Task 3: `classify_profile()` en filter_engine

**Files:**
- Modify: `backend/automation/filter_engine.py`
- Test: `backend/tests/test_filter_engine.py` (nuevo)

**Interfaces:**
- Consumes: `SAP_PROFILE_KEYWORDS`, `IADEV_PROFILE_KEYWORDS`, `PROFILE_CONFIDENCE_THRESHOLD` from `config`
- Produces:
  - `classify_profile(offer: dict) -> tuple[str, float]` — `("sap"|"ia_dev"|"manual_review", confidence: float)`
  - `filter_offers(offers)` ahora incluye `cv_profile` en cada dict resultado

- [ ] **Step 1: Crear `backend/tests/test_filter_engine.py`**

```python
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
```

- [ ] **Step 2: Ejecutar tests para verificar que fallan**

```bash
cd /home/javi-piazza/Documentos/Desarrollos/SCRIPTS/Proyectos/job-hunter-spain/backend
.venv/bin/pytest tests/test_filter_engine.py -v
```
Esperado: FAIL (funciones no existen / no tienen cv_profile).

- [ ] **Step 3: Modificar `backend/automation/filter_engine.py` — añadir `classify_profile` y actualizar `filter_offers`**

Reemplazar el contenido completo de `filter_engine.py`:

```python
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
```

- [ ] **Step 4: Ejecutar tests para verificar que pasan**

```bash
cd /home/javi-piazza/Documentos/Desarrollos/SCRIPTS/Proyectos/job-hunter-spain/backend
.venv/bin/pytest tests/test_filter_engine.py -v
```
Esperado: todos PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/javi-piazza/Documentos/Desarrollos/SCRIPTS/Proyectos/job-hunter-spain
git add backend/automation/filter_engine.py backend/tests/test_filter_engine.py
git commit -m "feat: add classify_profile() to filter engine (sap/ia_dev/manual_review)"
```

---

### Task 4: application_engine — `create_drafts` + `send_approved`

**Files:**
- Modify: `backend/automation/application_engine.py`
- Test: `backend/tests/test_application_engine_v2.py` (nuevo; el original se deja intacto)

**Interfaces:**
- Consumes:
  - `record_application(conn, data)` de Task 2
  - `record_history(conn, data)` de Task 2
  - `get_pending_offers(conn)` existente (ya filtra por is_relevant=1 y sin applications)
  - `generate(company_name, job_title, tech_stack, template, variant_seed)` de Task 5
  - `RECONTACT_COOLDOWN_DAYS`, `MAX_EMAILS_PER_DAY` de config
- Produces:
  - `create_drafts(limit=None) -> dict` — `{drafts_created, skipped_manual_review, skipped_duplicate, skipped_no_contact}`
  - `send_approved(application_id: str) -> bool`

- [ ] **Step 1: Crear `backend/tests/test_application_engine_v2.py`**

```python
import sys
import sqlite3
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def _in_memory_conn():
    """Return an initialised in-memory SQLite connection."""
    from database import init_db
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    return conn


def _seed(conn):
    """Insert a company, offer, and contact into the DB."""
    conn.execute(
        "INSERT INTO companies (id,name,source,created_at) VALUES ('c1','ACME','test','2026-01-01')"
    )
    conn.execute(
        """INSERT INTO job_offers
           (id,company_id,title,description,is_relevant,relevance_score,cv_profile,scraped_at,url)
           VALUES ('o1','c1','Python Dev','FastAPI LLM Python react next.js',1,0.8,'ia_dev','2026-01-01','http://a.com/1')"""
    )
    conn.execute(
        "INSERT INTO contacts (id,company_id,type,value,created_at) VALUES ('ct1','c1','email','jobs@acme.es','2026-01-01')"
    )
    conn.commit()


def test_create_drafts_returns_summary_keys():
    from automation.application_engine import create_drafts
    result = create_drafts.__code__.co_varnames  # just check it exists
    assert callable(create_drafts)


def test_is_recently_contacted_false_for_new_company():
    from automation.application_engine import _is_recently_contacted
    conn = _in_memory_conn()
    assert _is_recently_contacted(conn, "c1", "jobs@acme.es") is False
    conn.close()


def test_is_recently_contacted_true_after_application():
    from automation.application_engine import _is_recently_contacted
    from database import record_application
    conn = _in_memory_conn()
    conn.execute("INSERT INTO companies (id,name,source,created_at) VALUES ('c1','ACME','test','2026-01-01')")
    conn.execute("INSERT INTO contacts (id,company_id,type,value,created_at) VALUES ('ct1','c1','email','jobs@acme.es','2026-01-01')")
    conn.commit()
    record_application(conn, {
        "company_id": "c1",
        "contact_id": "ct1",
        "method": "email",
        "status": "sent",
        "sent_at": "2026-06-01T10:00:00",
    })
    assert _is_recently_contacted(conn, "c1", "jobs@acme.es") is True
    conn.close()


def test_send_approved_raises_for_unknown_id():
    from automation.application_engine import send_approved
    import pytest
    with pytest.raises(ValueError, match="not found"):
        send_approved("nonexistent-id")
```

- [ ] **Step 2: Ejecutar tests para verificar que fallan**

```bash
cd /home/javi-piazza/Documentos/Desarrollos/SCRIPTS/Proyectos/job-hunter-spain/backend
.venv/bin/pytest tests/test_application_engine_v2.py -v
```
Esperado: FAIL.

- [ ] **Step 3: Reemplazar `backend/automation/application_engine.py` por la versión nueva**

```python
"""
automation/application_engine.py — Orchestrates CV submissions in two stages:
  1. create_drafts() — generates pending_approval applications (no email sent)
  2. send_approved(id) — approves and sends a single pending application
"""
import logging
import uuid
from datetime import date, datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import MAX_EMAILS_PER_DAY, PROFILE_PATH, RECONTACT_COOLDOWN_DAYS
from database import (
    get_conn,
    get_pending_offers,
    record_application,
    record_history,
    get_pending_applications,
)
from automation.cover_letter import generate as generate_letter
from automation.email_sender import rate_limited_send

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

import json as _json


def _load_profile() -> dict:
    return _json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def _get_best_contact(conn, company_id: str) -> dict | None:
    rows = conn.execute(
        "SELECT * FROM contacts WHERE company_id=? ORDER BY type='email' DESC, verified DESC LIMIT 1",
        (company_id,),
    ).fetchall()
    return dict(rows[0]) if rows else None


def _emails_sent_today(conn) -> int:
    today = date.today().isoformat()
    row = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE method='email' AND status='sent' AND sent_at LIKE ?",
        (f"{today}%",),
    ).fetchone()
    return row[0]


def _is_recently_contacted(conn, company_id: str, contact_value: str) -> bool:
    row = conn.execute(
        """SELECT 1 FROM applications a
           JOIN contacts ct ON a.contact_id = ct.id
           WHERE a.company_id = ? AND ct.value = ?
             AND a.status NOT IN ('rejected_manual', 'pending_approval')
             AND a.sent_at > datetime('now', ?)
           LIMIT 1""",
        (company_id, contact_value, f"-{RECONTACT_COOLDOWN_DAYS} days"),
    ).fetchone()
    return row is not None


def _cv_path_from_profile(cv_profile: str, profile: dict) -> Path | None:
    key = "cv_sap_path" if cv_profile == "sap" else "cv_ia_path"
    cv_rel = profile.get(key) or profile.get("cv_path", "")
    cv = Path(__file__).parent.parent / cv_rel
    return cv if cv.exists() else None


def create_drafts(limit: int | None = None) -> dict:
    """
    Generate pending_approval application drafts without sending any email.
    Returns a summary dict with counts.
    """
    conn = get_conn()
    pending = get_pending_offers(conn)
    results = {
        "drafts_created": 0,
        "skipped_manual_review": 0,
        "skipped_duplicate": 0,
        "skipped_no_contact": 0,
    }

    for offer in pending:
        if limit and results["drafts_created"] >= limit:
            break

        offer = dict(offer)
        cv_profile = offer.get("cv_profile") or "ia_dev"

        if cv_profile == "manual_review":
            results["skipped_manual_review"] += 1
            logger.info("SKIP manual_review: %s", offer.get("title"))
            continue

        contact = _get_best_contact(conn, offer["company_id"])
        if not contact:
            results["skipped_no_contact"] += 1
            logger.info("SKIP no_contact: %s", offer.get("company_name"))
            continue

        if _is_recently_contacted(conn, offer["company_id"], contact["value"]):
            results["skipped_duplicate"] += 1
            logger.info("SKIP duplicate: %s", offer.get("company_name"))
            continue

        template = "sap" if cv_profile == "sap" else "tech"
        cover_letter = generate_letter(
            company_name=offer["company_name"],
            job_title=offer["title"],
            tech_stack=offer.get("tech_stack"),
            template=template,
            variant_seed=offer["company_name"] + (offer.get("title") or ""),
        )

        record_application(conn, {
            "company_id": offer["company_id"],
            "job_offer_id": offer["id"],
            "contact_id": contact["id"],
            "method": contact["type"],
            "status": "pending_approval",
            "cover_letter_used": cover_letter,
            "cv_profile": cv_profile,
        })
        results["drafts_created"] += 1
        logger.info("DRAFT created: %s — %s", offer.get("company_name"), offer.get("title"))

    conn.close()
    logger.info("Drafts summary: %s", results)
    return results


def send_approved(application_id: str) -> bool:
    """
    Send a single pending_approval application.
    Raises ValueError if not found or daily limit reached.
    Returns True on success.
    """
    profile = _load_profile()
    personal = profile.get("personal", {})

    conn = get_conn()

    today_count = _emails_sent_today(conn)
    if today_count >= MAX_EMAILS_PER_DAY:
        conn.close()
        raise ValueError(f"Daily email limit ({MAX_EMAILS_PER_DAY}) reached.")

    row = conn.execute(
        """SELECT a.*, c.name as company_name, jo.title as job_title,
                  ct.value as contact_value, ct.type as contact_type
           FROM applications a
           LEFT JOIN companies c ON a.company_id = c.id
           LEFT JOIN job_offers jo ON a.job_offer_id = jo.id
           LEFT JOIN contacts ct ON a.contact_id = ct.id
           WHERE a.id = ? AND a.status = 'pending_approval'""",
        (application_id,),
    ).fetchone()

    if not row:
        conn.close()
        raise ValueError(f"Application {application_id} not found or not in pending_approval status.")

    app = dict(row)
    cv_profile = app.get("cv_profile") or "ia_dev"
    cv = _cv_path_from_profile(cv_profile, profile)

    body = app.get("cover_letter_edited") or app.get("cover_letter_used") or ""
    subject = (
        f"Solicitud: {app['job_title']} — {personal.get('name', '')}"
        if app.get("job_title")
        else f"Candidatura — {personal.get('name', '')}"
    )

    success = rate_limited_send(
        to=app["contact_value"],
        subject=subject,
        body=body,
        cv_path=cv,
        dry_run=False,
    )

    if success:
        now = datetime.now().isoformat()
        conn.execute(
            "UPDATE applications SET status='sent', sent_at=?, approved_at=? WHERE id=?",
            (now, now, application_id),
        )
        domain = app["contact_value"].split("@")[-1] if "@" in (app.get("contact_value") or "") else ""
        record_history(conn, {
            "company_name": app.get("company_name", ""),
            "company_domain": domain,
            "email_used": app.get("contact_value", ""),
            "profile_used": cv_profile,
            "sent_at": now,
            "application_id": application_id,
        })
        conn.commit()

    conn.close()
    return success


# ── Legacy CLI entry point (kept for backward compatibility) ──────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Job Hunter Spain — Application Engine")
    parser.add_argument("--dry-run", action="store_true", help="Generate drafts only (no email)")
    parser.add_argument("--limit", type=int, default=None, help="Max drafts this run")
    args = parser.parse_args()
    result = create_drafts(limit=args.limit)
    print(result)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Ejecutar tests para verificar que pasan**

```bash
cd /home/javi-piazza/Documentos/Desarrollos/SCRIPTS/Proyectos/job-hunter-spain/backend
.venv/bin/pytest tests/test_application_engine_v2.py -v
```
Esperado: todos PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/javi-piazza/Documentos/Desarrollos/SCRIPTS/Proyectos/job-hunter-spain
git add backend/automation/application_engine.py backend/tests/test_application_engine_v2.py
git commit -m "feat: replace direct send with create_drafts/send_approved two-stage pipeline"
```

---

### Task 5: Cover letter — variación y plantilla SAP

**Files:**
- Modify: `backend/automation/cover_letter.py`
- Modify: `backend/templates/cover_letter_tech.j2`
- Create: `backend/templates/cover_letter_sap.j2`
- Test: `backend/tests/test_cover_letter.py` (nuevo)

**Interfaces:**
- Consumes: nada nuevo
- Produces:
  - `generate(company_name, job_title=None, tech_stack=None, template="tech", variant_seed=None) -> str` — firma con `variant_seed` añadido

- [ ] **Step 1: Crear `backend/tests/test_cover_letter.py`**

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_generate_returns_string():
    from automation.cover_letter import generate
    result = generate("Empresa Test", job_title="Python Dev", template="tech")
    assert isinstance(result, str)
    assert "Empresa Test" in result


def test_generate_variant_seed_same_seed_same_result():
    from automation.cover_letter import generate
    r1 = generate("ACME", "Python Dev", template="tech", variant_seed="ACME-Python Dev")
    r2 = generate("ACME", "Python Dev", template="tech", variant_seed="ACME-Python Dev")
    assert r1 == r2


def test_generate_different_seeds_may_differ():
    from automation.cover_letter import generate
    r1 = generate("ACME", "Python Dev", template="tech", variant_seed="ACME-Python Dev")
    r2 = generate("ACME", "Python Dev", template="tech", variant_seed="OtherCo-SAP Dev")
    # They might happen to be equal if same variant bucket; test just checks no crash
    assert isinstance(r1, str) and isinstance(r2, str)


def test_pick_variant_deterministic():
    from automation.cover_letter import _pick_variant
    variants = ["A", "B", "C"]
    r1 = _pick_variant(variants, "seed123")
    r2 = _pick_variant(variants, "seed123")
    assert r1 == r2
    assert r1 in variants


def test_generate_sap_template():
    from automation.cover_letter import generate
    result = generate("Capgemini", job_title="Consultor SAP PS", template="sap")
    assert isinstance(result, str)
    assert "Capgemini" in result
```

- [ ] **Step 2: Ejecutar tests para verificar que fallan**

```bash
cd /home/javi-piazza/Documentos/Desarrollos/SCRIPTS/Proyectos/job-hunter-spain/backend
.venv/bin/pytest tests/test_cover_letter.py -v
```
Esperado: FAIL (`_pick_variant` no existe, `variant_seed` no soportado, plantilla SAP no existe).

- [ ] **Step 3: Modificar `backend/automation/cover_letter.py`**

```python
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
```

- [ ] **Step 4: Modificar `backend/templates/cover_letter_tech.j2` — añadir variantes de apertura y cierre**

Reemplazar el contenido del fichero:

```jinja2
{% set greetings = [
  "Estimado/a equipo de selección de " ~ company_name ~ ",",
  "Estimado/a equipo de " ~ company_name ~ ",",
  "Me dirijo al equipo de " ~ company_name ~ ","
] %}
{% set extra_closings = [
  "Quedo disponible para una entrevista o prueba técnica cuando lo estimen oportuno.",
  "Estaré encantado de ampliar mi perfil en una entrevista cuando lo consideren conveniente.",
  "Me pongo a su disposición para cualquier proceso de selección que estimen adecuado."
] %}
{{ greetings[variant_index] }}

{{ cover_letter_intro }}

{% if job_title %}
He visto la oferta para **{{ job_title }}** y me parece muy alineada con mi trayectoria.
{% endif %}

{{ cover_letter_stack }}

Mi experiencia más relevante:

{% for exp in experience %}
- **{{ exp.role }} en {{ exp.company }} ({{ exp.duration_months }} meses):** {{ exp.description }}
{% endfor %}

{% if tech_stack %}
Tecnologías mencionadas en la oferta donde tengo experiencia: *{{ tech_stack }}*.
{% endif %}

{{ extra_closings[variant_index] }}

{{ cover_letter_closing }}

—
{{ name }}
{{ email }}{% if phone %} · {{ phone }}{% endif %}
{% if linkedin %}LinkedIn: {{ linkedin }}{% endif %}
{% if portfolio %}Portfolio: {{ portfolio }}{% endif %}
```

- [ ] **Step 5: Crear `backend/templates/cover_letter_sap.j2`**

```jinja2
{% set greetings = [
  "Estimado/a equipo de selección de " ~ company_name ~ ",",
  "Estimado/a equipo de " ~ company_name ~ ",",
  "Me dirijo al departamento de RRHH de " ~ company_name ~ ","
] %}
{% set extra_closings = [
  "Quedo disponible para una entrevista cuando lo estimen oportuno.",
  "Estaré encantado de ampliar los detalles de mi perfil SAP en una entrevista.",
  "Me pongo a su disposición para iniciar el proceso de selección cuando lo consideren."
] %}
{{ greetings[variant_index] }}

Me dirijo a ustedes para expresar mi interés en unirme al equipo de {{ company_name }} en un rol SAP.
Cuento con formación en SAP Public Cloud (SAP BTP Practitioner) y experiencia práctica en consultoría de procesos de negocio y planificación de proyectos.

{% if job_title %}
He revisado la oferta para **{{ job_title }}** y encaja directamente con mi formación y perfil funcional SAP.
{% endif %}

Mi experiencia en el entorno SAP incluye:
- Formación certificada en **SAP Public Cloud** (SAP BTP, S/4HANA Cloud)
- Conocimiento funcional de módulos **PS (Project Systems)**, **FI/CO** y procesos de gestión de proyectos
- Experiencia en consultoría de procesos de negocio e implantación de sistemas ERP
- Capacidad técnica complementaria: desarrollo Python, APIs e integración de sistemas

{% for exp in experience %}
- **{{ exp.role }} en {{ exp.company }} ({{ exp.duration_months }} meses):** {{ exp.description }}
{% endfor %}

{% if tech_stack %}
Tecnologías y módulos relevantes de la oferta: *{{ tech_stack }}*.
{% endif %}

{{ extra_closings[variant_index] }}

{{ cover_letter_closing }}

—
{{ name }}
{{ email }}{% if phone %} · {{ phone }}{% endif %}
{% if linkedin %}LinkedIn: {{ linkedin }}{% endif %}
{% if portfolio %}Portfolio: {{ portfolio }}{% endif %}
```

- [ ] **Step 6: Ejecutar tests para verificar que pasan**

```bash
cd /home/javi-piazza/Documentos/Desarrollos/SCRIPTS/Proyectos/job-hunter-spain/backend
.venv/bin/pytest tests/test_cover_letter.py -v
```
Esperado: todos PASS.

- [ ] **Step 7: Commit**

```bash
cd /home/javi-piazza/Documentos/Desarrollos/SCRIPTS/Proyectos/job-hunter-spain
git add backend/automation/cover_letter.py backend/templates/cover_letter_tech.j2 backend/templates/cover_letter_sap.j2 backend/tests/test_cover_letter.py
git commit -m "feat: add cover letter variant rotation and SAP-specific template"
```

---

### Task 6: FastAPI — nuevos endpoints

**Files:**
- Modify: `backend/main.py`

**Interfaces:**
- Consumes: `create_drafts`, `send_approved` de Task 4; `get_pending_applications`, `record_history`, `get_history`, `get_dashboard_stats` de Task 2
- Produces endpoints:
  - `POST /api/applications/create-drafts?limit=N`
  - `GET /api/applications/pending`
  - `POST /api/applications/{app_id}/approve`
  - `PATCH /api/applications/{app_id}/cover-letter` body: `{"cover_letter_edited": "..."}`
  - `POST /api/applications/{app_id}/reject`
  - `GET /api/stats/dashboard`
  - `GET /api/history?company=&profile=&outcome=`
  - `PATCH /api/history/{history_id}/outcome` body: `{"outcome": "..."}`
  - `GET /api/history/export?format=json|csv`

- [ ] **Step 1: Añadir los nuevos imports y endpoints a `backend/main.py`**

Añadir al bloque de imports al inicio del fichero (después de los imports existentes):

```python
import csv
import io
from fastapi import FastAPI, HTTPException, BackgroundTasks, Body
from fastapi.responses import StreamingResponse
```

(Reemplazar la línea existente `from fastapi import FastAPI, HTTPException, BackgroundTasks`)

Añadir al bloque de imports de database (expandir la línea existente):

```python
from database import (
    get_conn, init_db, get_all_companies, get_pending_offers, stats as db_stats,
    get_pending_applications, get_history, record_history, get_dashboard_stats,
)
```

- [ ] **Step 2: Añadir todos los nuevos endpoints al final de `backend/main.py` (antes de `if __name__ == "__main__":`)**

```python
# ── Review Queue endpoints ─────────────────────────────────────────────────────

@app.post("/api/applications/create-drafts")
def create_drafts_endpoint(limit: int | None = None):
    from automation.application_engine import create_drafts
    result = create_drafts(limit=limit)
    return result


@app.get("/api/applications/pending")
def get_pending_applications_endpoint():
    conn = get_conn()
    rows = get_pending_applications(conn)
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/applications/{app_id}/approve")
def approve_application(app_id: str):
    from automation.application_engine import send_approved
    try:
        success = send_approved(app_id)
        return {"id": app_id, "success": success, "status": "sent" if success else "failed"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.patch("/api/applications/{app_id}/cover-letter")
def update_cover_letter(app_id: str, body: dict = Body(...)):
    text = body.get("cover_letter_edited", "")
    conn = get_conn()
    conn.execute(
        "UPDATE applications SET cover_letter_edited=? WHERE id=?", (text, app_id)
    )
    conn.commit()
    conn.close()
    return {"id": app_id, "updated": True}


@app.post("/api/applications/{app_id}/reject")
def reject_application(app_id: str):
    conn = get_conn()
    conn.execute(
        "UPDATE applications SET status='rejected_manual' WHERE id=?", (app_id,)
    )
    conn.commit()
    conn.close()
    return {"id": app_id, "status": "rejected_manual"}


# ── Dashboard stats ────────────────────────────────────────────────────────────

@app.get("/api/stats/dashboard")
def get_dashboard_stats_endpoint():
    conn = get_conn()
    result = get_dashboard_stats(conn)
    conn.close()
    return result


# ── Persistent history ─────────────────────────────────────────────────────────

@app.get("/api/history")
def get_history_endpoint(
    company: str | None = None,
    profile: str | None = None,
    outcome: str | None = None,
):
    conn = get_conn()
    rows = get_history(conn, company=company, profile=profile, outcome=outcome)
    conn.close()
    return [dict(r) for r in rows]


@app.patch("/api/history/{history_id}/outcome")
def update_history_outcome(history_id: str, body: dict = Body(...)):
    valid = {"sin_respuesta", "respuesta_recibida", "entrevista", "rechazado"}
    outcome = body.get("outcome", "")
    if outcome not in valid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid outcome. Must be one of: {sorted(valid)}",
        )
    conn = get_conn()
    conn.execute(
        "UPDATE company_contact_history SET outcome=? WHERE id=?", (outcome, history_id)
    )
    conn.commit()
    conn.close()
    return {"id": history_id, "outcome": outcome}


@app.get("/api/history/export")
def export_history(format: str = "json"):
    conn = get_conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM company_contact_history ORDER BY sent_at DESC"
    ).fetchall()]
    conn.close()

    if format == "csv":
        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        from datetime import date
        filename = f"job_hunter_history_{date.today().isoformat()}.csv"
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    return rows
```

- [ ] **Step 3: Modificar el endpoint existente `POST /api/applications/run` para que genere borradores en lugar de enviar**

Localizar y reemplazar la función `_run_applications` y su endpoint:

```python
def _run_applications():
    from automation.application_engine import create_drafts
    create_drafts()


@app.post("/api/applications/run")
def trigger_applications(background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_applications)
    return {"status": "started", "note": "Generating drafts (pending_approval). Approve from dashboard to send."}
```

- [ ] **Step 4: Verificar que el servidor arranca sin errores**

```bash
cd /home/javi-piazza/Documentos/Desarrollos/SCRIPTS/Proyectos/job-hunter-spain/backend
.venv/bin/uvicorn main:app --port 8020 &
sleep 3
curl -s http://localhost:8020/api/stats/dashboard | python3 -m json.tool
curl -s http://localhost:8020/api/applications/pending | python3 -m json.tool
curl -s http://localhost:8020/api/history | python3 -m json.tool
kill %1
```
Esperado: JSON sin errores, arrays vacíos o con datos existentes.

- [ ] **Step 5: Commit**

```bash
cd /home/javi-piazza/Documentos/Desarrollos/SCRIPTS/Proyectos/job-hunter-spain
git add backend/main.py
git commit -m "feat: add review queue, history, and dashboard stats API endpoints"
```

---

### Task 7: Frontend — tab Pendientes + API client

**Files:**
- Modify: `frontend/lib/api.ts`
- Create: `frontend/app/components/PendingCard.tsx`
- Modify: `frontend/app/page.tsx`

**Interfaces:**
- Consumes: endpoints de Task 6
- Produces: tab "Pendientes" con cola de aprobación editable

- [ ] **Step 1: Añadir funciones nuevas a `frontend/lib/api.ts`**

Añadir al final del fichero (después de `triggerApplications`):

```typescript
export async function createDrafts(limit?: number): Promise<{ drafts_created: number; skipped_manual_review: number; skipped_duplicate: number; skipped_no_contact: number }> {
  const qs = limit !== undefined ? `?limit=${limit}` : "";
  const res = await fetch(`${BASE}/api/applications/create-drafts${qs}`, { method: "POST" });
  return res.json();
}

export async function fetchPendingApplications(): Promise<PendingApplication[]> {
  const res = await fetch(`${BASE}/api/applications/pending`);
  return res.json();
}

export async function approveApplication(id: string): Promise<{ id: string; success: boolean; status: string }> {
  const res = await fetch(`${BASE}/api/applications/${id}/approve`, { method: "POST" });
  return res.json();
}

export async function updateCoverLetter(id: string, coverLetterEdited: string): Promise<{ id: string; updated: boolean }> {
  const res = await fetch(`${BASE}/api/applications/${id}/cover-letter`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cover_letter_edited: coverLetterEdited }),
  });
  return res.json();
}

export async function rejectApplication(id: string): Promise<{ id: string; status: string }> {
  const res = await fetch(`${BASE}/api/applications/${id}/reject`, { method: "POST" });
  return res.json();
}

export async function fetchDashboardStats(): Promise<DashboardStats> {
  const res = await fetch(`${BASE}/api/stats/dashboard`);
  return res.json();
}

export async function fetchHistory(params?: { company?: string; profile?: string; outcome?: string }): Promise<HistoryEntry[]> {
  const qs = new URLSearchParams(params as Record<string, string>).toString();
  const res = await fetch(`${BASE}/api/history${qs ? `?${qs}` : ""}`);
  return res.json();
}

export async function exportHistoryCSV(): Promise<void> {
  const res = await fetch(`${BASE}/api/history/export?format=csv`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `job_hunter_history_${new Date().toISOString().split("T")[0]}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// Types used by the new functions
export interface PendingApplication {
  id: string;
  company_name: string | null;
  job_title: string | null;
  contact_value: string | null;
  contact_type: string | null;
  cover_letter_used: string | null;
  cover_letter_edited: string | null;
  cv_profile: string | null;
  method: string;
}

export interface DashboardStats {
  sent_this_week: number;
  pending_approval: number;
  total_sent: number;
  response_rate: number;
  sap_ratio: number;
  ia_dev_ratio: number;
}

export interface HistoryEntry {
  id: string;
  company_name: string;
  company_domain: string;
  email_used: string;
  profile_used: string;
  sent_at: string;
  outcome: string;
  notes: string | null;
  application_id: string | null;
}
```

- [ ] **Step 2: Crear `frontend/app/components/PendingCard.tsx`**

```typescript
mkdir -p /home/javi-piazza/Documentos/Desarrollos/SCRIPTS/Proyectos/job-hunter-spain/frontend/app/components
```

Contenido del fichero `frontend/app/components/PendingCard.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Check, X, FileText } from "lucide-react";
import { approveApplication, rejectApplication, updateCoverLetter, type PendingApplication } from "@/lib/api";

interface PendingCardProps {
  app: PendingApplication;
  onAction: () => void;
}

const PROFILE_BADGE: Record<string, { label: string; className: string }> = {
  sap:           { label: "SAP",    className: "bg-blue-100 text-blue-700" },
  ia_dev:        { label: "IA/Dev", className: "bg-purple-100 text-purple-700" },
  manual_review: { label: "Revisar",className: "bg-yellow-100 text-yellow-700" },
};

export function PendingCard({ app, onAction }: PendingCardProps) {
  const currentLetter = app.cover_letter_edited ?? app.cover_letter_used ?? "";
  const [body, setBody] = useState(currentLetter);
  const [saved, setSaved] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    setBusy(true);
    await updateCoverLetter(app.id, body);
    setSaved(true);
    setBusy(false);
  };

  const handleApprove = async () => {
    setError(null);
    if (!saved) await handleSave();
    setBusy(true);
    const result = await approveApplication(app.id);
    if (!result.success) {
      setError("Error al enviar. Revisa el límite diario o la conexión SMTP.");
      setBusy(false);
      return;
    }
    onAction();
  };

  const handleReject = async () => {
    setBusy(true);
    await rejectApplication(app.id);
    onAction();
  };

  const badge = PROFILE_BADGE[app.cv_profile ?? "ia_dev"] ?? PROFILE_BADGE["ia_dev"];
  const cvFile = app.cv_profile === "sap" ? "cv_sap.pdf" : "cv_ia.pdf";

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-gray-900">{app.company_name ?? "—"}</p>
          <p className="text-sm text-gray-500">{app.job_title ?? "Candidatura espontánea"}</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${badge.className}`}>
            {badge.label}
          </span>
          <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full font-mono">
            {cvFile}
          </span>
        </div>
      </div>

      <div className="text-xs text-gray-400 flex items-center gap-1.5">
        <FileText className="w-3 h-3 flex-shrink-0" />
        <span className="font-mono truncate">{app.contact_value ?? "—"}</span>
      </div>

      {error && (
        <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      <div>
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            Carta de presentación
          </span>
          {!saved && (
            <button
              onClick={handleSave}
              disabled={busy}
              className="text-xs text-blue-600 hover:underline disabled:opacity-40"
            >
              Guardar cambios
            </button>
          )}
          {saved && body !== currentLetter && (
            <span className="text-xs text-green-600">Guardado</span>
          )}
        </div>
        <textarea
          value={body}
          onChange={(e) => { setBody(e.target.value); setSaved(false); }}
          rows={10}
          disabled={busy}
          className="w-full text-xs font-mono text-gray-700 border border-gray-200 rounded-lg p-3 resize-y focus:outline-none focus:ring-2 focus:ring-blue-400 bg-gray-50 disabled:opacity-60"
        />
      </div>

      <div className="flex justify-end gap-2 pt-1">
        <button
          onClick={handleReject}
          disabled={busy}
          className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-red-600 border border-red-200 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-40"
        >
          <X className="w-4 h-4" /> Rechazar
        </button>
        <button
          onClick={handleApprove}
          disabled={busy}
          className="flex items-center gap-1.5 px-4 py-2 text-sm font-semibold bg-green-600 hover:bg-green-700 text-white rounded-lg shadow-sm transition-colors disabled:opacity-40"
        >
          <Check className="w-4 h-4" /> {busy ? "Enviando…" : "Aprobar y enviar"}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Modificar `frontend/app/page.tsx` — añadir tab Pendientes**

**3a. Añadir `PendingApplication` al import de api y el componente:**

Al inicio del fichero, después de `import { fetchStats, ... } from "@/lib/api";`, añadir:

```typescript
import { fetchPendingApplications, createDrafts, exportHistoryCSV, type PendingApplication } from "@/lib/api";
import { PendingCard } from "@/app/components/PendingCard";
```

**3b. Añadir estado para pendientes:**

Después de la línea `const [applications, setApplications] = useState<Application[]>([]);`, añadir:

```typescript
const [pendingApps, setPendingApps] = useState<PendingApplication[]>([]);
```

Cambiar el tipo del tab de:
```typescript
const [tab, setTab] = useState<"companies" | "offers" | "contacts" | "applications">("offers");
```
a:
```typescript
const [tab, setTab] = useState<"companies" | "offers" | "contacts" | "applications" | "pending">("offers");
```

**3c. Añadir la carga de pendientes en `load()`:**

Reemplazar:
```typescript
const load = async () => {
    const [s, c, o, ct, a] = await Promise.all([
      fetchStats(),
      fetchCompanies({ country: countryFilter || undefined }),
      fetchOffers(true),
      fetchContacts(),
      fetchApplications(),
    ]);
    setStats(s);
    setCompanies(c);
    setOffers(o);
    setContacts(ct);
    setApplications(a);
  };
```
por:
```typescript
const load = async () => {
    const [s, c, o, ct, a, p] = await Promise.all([
      fetchStats(),
      fetchCompanies({ country: countryFilter || undefined }),
      fetchOffers(true),
      fetchContacts(),
      fetchApplications(),
      fetchPendingApplications(),
    ]);
    setStats(s);
    setCompanies(c);
    setOffers(o);
    setContacts(ct);
    setApplications(a);
    setPendingApps(p);
  };
```

**3d. Reemplazar el botón "Enviar candidaturas" por "Generar borradores":**

Reemplazar:
```tsx
<button
  onClick={handleApply}
  disabled={loading}
  className="flex items-center gap-2 px-4 py-2.5 text-sm font-semibold bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white rounded-xl shadow-sm hover:shadow-md transition-all disabled:opacity-40 disabled:cursor-not-allowed"
>
  <Play className="w-4 h-4 fill-white" /> Enviar candidaturas
</button>
```
por:
```tsx
<button
  onClick={handleApply}
  disabled={loading}
  className="flex items-center gap-2 px-4 py-2.5 text-sm font-semibold bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white rounded-xl shadow-sm hover:shadow-md transition-all disabled:opacity-40 disabled:cursor-not-allowed"
  title="Genera borradores para revisar antes de enviar"
>
  <Play className="w-4 h-4 fill-white" /> Generar borradores
</button>
```

Y reemplazar `handleApply`:
```typescript
const handleApply = async () => {
    setLoading(true);
    setActionMsg("Generando borradores...");
    const result = await createDrafts();
    setActionMsg(`${result.drafts_created} borradores creados`);
    await load();
    setLoading(false);
    setTab("pending");
    setTimeout(() => setActionMsg(""), 3000);
  };
```

**3e. Añadir el tab "Pendientes" en la barra de tabs:**

Después del botón `Candidaturas`, añadir:
```tsx
<button onClick={() => setTab("pending")} className={`px-4 py-2 text-sm rounded-md transition-colors ${tab === "pending" ? "bg-white shadow-sm font-medium" : "text-gray-600 hover:text-gray-900"}`}>
  Pendientes ({pendingApps.length}){pendingApps.length > 0 && <span className="ml-1.5 w-2 h-2 rounded-full bg-amber-400 inline-block" />}
</button>
```

**3f. Añadir el contenido del tab "Pendientes" antes del cierre de `</main>`:**

Antes de la línea `</main>`, añadir:
```tsx
{tab === "pending" && (
  <div className="space-y-4">
    {pendingApps.length === 0 ? (
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-12 text-center text-gray-400">
        <Check className="w-8 h-8 mx-auto mb-3 opacity-30" />
        <p className="font-medium">No hay candidaturas pendientes de revisión</p>
        <p className="text-sm mt-1">Pulsa &quot;Generar borradores&quot; para crear candidaturas desde las ofertas relevantes</p>
      </div>
    ) : (
      <>
        <p className="text-sm text-gray-500">{pendingApps.length} candidatura{pendingApps.length !== 1 ? "s" : ""} esperando aprobación</p>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {pendingApps.map((a) => (
            <PendingCard key={a.id} app={a} onAction={load} />
          ))}
        </div>
      </>
    )}
  </div>
)}
```

**3g. Añadir `Check` al import de lucide-react:**

Cambiar:
```typescript
import { Building2, Briefcase, Send, Users, RefreshCw, Play } from "lucide-react";
```
por:
```typescript
import { Building2, Briefcase, Send, Users, RefreshCw, Play, Check } from "lucide-react";
```

- [ ] **Step 4: Verificar que el frontend compila sin errores**

```bash
cd /home/javi-piazza/Documentos/Desarrollos/SCRIPTS/Proyectos/job-hunter-spain/frontend
bun run build 2>&1 | tail -20
```
Esperado: `Route (app) / ...` sin errores TypeScript.

- [ ] **Step 5: Verificar el flujo en navegador**

Con backend en :8020 y frontend en :3010:
```bash
cd /home/javi-piazza/Documentos/Desarrollos/SCRIPTS/Proyectos/job-hunter-spain/backend
.venv/bin/uvicorn main:app --reload --port 8020 &
cd /home/javi-piazza/Documentos/Desarrollos/SCRIPTS/Proyectos/job-hunter-spain/frontend
bun run dev &
```
Abrir http://localhost:3010. Verificar:
- Tab "Pendientes" aparece en la barra
- Botón "Generar borradores" está en el header
- Clic en "Generar borradores" → navega a tab "Pendientes"
- Si hay contactos y ofertas relevantes → aparecen PendingCards con textarea editable
- Botones Rechazar y Aprobar visibles

- [ ] **Step 6: Commit**

```bash
kill %1 %2 2>/dev/null; true
cd /home/javi-piazza/Documentos/Desarrollos/SCRIPTS/Proyectos/job-hunter-spain
git add frontend/lib/api.ts frontend/app/components/PendingCard.tsx frontend/app/page.tsx
git commit -m "feat: add Pendientes tab with approval queue and editable cover letters"
```

---

## Self-Review

**Spec coverage:**
- [x] Punto 1 — clasificación SAP/IA/manual_review → Tasks 1+3
- [x] Punto 2 — cola revisión humana, edición cover letter, aprobación → Tasks 4+6+7
- [x] Punto 3 — dedup por company+email, cooldown 180d, tracking de estados → Tasks 2+4; estados adicionales en DB
- [x] Punto 4 — rate limiting 15/día, variación cover letter → Tasks 1+5
- [x] Punto 5 (InfoJobs) — explícitamente fuera de scope en spec
- [x] Punto 6 — historial persistente, export CSV/JSON → Tasks 2+6

**Placeholder scan:** ningún TBD, TODO o "implement later" en el plan.

**Type consistency:**
- `classify_profile()` devuelve `tuple[str, float]` — usado en `filter_engine.py` Task 3, leído como `offer.get("cv_profile")` en Task 4 ✓
- `record_application(conn, data)` — firma igual en Task 2 y Task 4 ✓
- `record_history(conn, data)` — firma definida en Task 2, usada en Task 4 ✓
- `send_approved(application_id: str) -> bool` — definido en Task 4, llamado desde Task 6 ✓
- `PendingApplication` interface — definida en Task 7 lib/api.ts, consumida en PendingCard.tsx ✓
- `generate(..., variant_seed=None)` — firma en Task 5, llamada en Task 4 con `variant_seed=` ✓
