"""
main.py — FastAPI application for Job Hunter Spain.
Exposes REST endpoints for the Next.js dashboard.

Run: uvicorn main:app --reload --port 8020
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import logging

from config import CORS_ORIGINS, API_PORT
from database import (
    get_conn, init_db, get_all_companies, get_pending_offers, stats as db_stats
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = get_conn()
    init_db(conn)
    conn.close()
    yield


app = FastAPI(title="Job Hunter Spain API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/stats")
def get_stats():
    conn = get_conn()
    result = db_stats(conn)
    conn.close()
    return result


@app.get("/api/companies")
def get_companies(sector: str | None = None, country: str | None = None):
    conn = get_conn()
    rows = get_all_companies(conn)
    conn.close()
    data = [dict(r) for r in rows]
    if sector:
        data = [c for c in data if c.get("sector") == sector]
    if country:
        data = [c for c in data if c.get("country") == country]
    return data


@app.get("/api/offers")
def get_offers(relevant_only: bool = False, source: str | None = None):
    conn = get_conn()
    query = "SELECT jo.*, c.name as company_name FROM job_offers jo JOIN companies c ON jo.company_id = c.id"
    conditions = []
    params: list = []
    if relevant_only:
        conditions.append("jo.is_relevant = 1")
    if source:
        conditions.append("jo.source = ?")
        params.append(source)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY jo.relevance_score DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/applications")
def get_applications(status: str | None = None):
    conn = get_conn()
    query = """SELECT a.*, c.name as company_name, jo.title as job_title
               FROM applications a
               LEFT JOIN companies c ON a.company_id = c.id
               LEFT JOIN job_offers jo ON a.job_offer_id = jo.id"""
    if status:
        query += " WHERE a.status = ?"
        rows = conn.execute(query, [status]).fetchall()
    else:
        rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/contacts")
def get_contacts():
    conn = get_conn()
    rows = conn.execute("""
        SELECT ct.*, c.name as company_name, c.website as company_website
        FROM contacts ct
        LEFT JOIN companies c ON c.id = ct.company_id
        ORDER BY ct.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.patch("/api/applications/{app_id}/status")
def update_application_status(app_id: str, status: str):
    valid = {"sent", "replied", "interview", "rejected", "withdrawn"}
    if status not in valid:
        raise HTTPException(400, f"Invalid status. Must be one of: {valid}")
    conn = get_conn()
    conn.execute("UPDATE applications SET status=? WHERE id=?", (status, app_id))
    conn.commit()
    conn.close()
    return {"id": app_id, "status": status}


def _run_seed():
    from scraper.seed_loader import load_seed
    load_seed()


def _run_scraper(source: str):
    import asyncio
    if source == "contacts":
        from scraper.contact_extractor import run_contact_extractor
        asyncio.run(run_contact_extractor())
        return
    if source == "tecnoempleo":
        from scraper.tecnoempleo import run_tecnoempleo
        from database import upsert_company, upsert_job_offer
        from automation.filter_engine import score_offer
        offers = asyncio.run(run_tecnoempleo(max_pages=3))
        conn = get_conn()
        for offer in offers:
            company_row = conn.execute(
                "SELECT id FROM companies WHERE name = ?", (offer.get("company_name", ""),)
            ).fetchone()
            cid = company_row["id"] if company_row else upsert_company(conn, {
                "name": offer.get("company_name", "Desconocida"), "source": "tecnoempleo"
            })
            s = score_offer(offer)
            upsert_job_offer(conn, {**offer, "company_id": cid, "is_relevant": s >= 0.55, "relevance_score": s})
        conn.close()


def _run_applications():
    from automation.application_engine import run_applications
    run_applications(dry_run=False)


@app.post("/api/scraper/run")
def trigger_scraper(source: str = "seed", background_tasks: BackgroundTasks = None):
    if source == "seed":
        background_tasks.add_task(_run_seed)
    elif source == "tecnoempleo":
        background_tasks.add_task(_run_scraper, "tecnoempleo")
    elif source == "contacts":
        background_tasks.add_task(_run_scraper, "contacts")
    else:
        raise HTTPException(400, f"Unknown source: {source}")
    return {"status": "started", "source": source}


@app.post("/api/applications/run")
def trigger_applications(background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_applications)
    return {"status": "started"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=API_PORT, reload=True)
