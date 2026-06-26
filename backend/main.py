"""
main.py — FastAPI application for Job Hunter Spain.
Exposes REST endpoints for the Next.js dashboard.

Run: uvicorn main:app --reload --port 8020
"""
import csv
import io
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import logging

from config import CORS_ORIGINS, API_PORT
from automation.filter_engine import classify_profile
from database import (
    get_conn, init_db, get_all_companies, get_pending_offers, stats as db_stats,
    get_pending_applications, get_history, record_history, get_dashboard_stats,
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


def _parse_modality(location: str | None) -> str:
    if not location:
        return "presencial"
    loc = location.lower()
    if "remoto" in loc or "remote" in loc:
        return "remoto"
    if "híbrido" in loc or "hibrido" in loc or "hybrid" in loc:
        return "hibrido"
    return "presencial"


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
    result = []
    for r in rows:
        offer = dict(r)
        profile, _ = classify_profile(offer)
        offer["cv_profile"] = profile
        offer["modality"] = _parse_modality(offer.get("location"))
        result.append(offer)
    return result


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
    contacts = conn.execute("""
        SELECT ct.*, c.name as company_name, c.website as company_website
        FROM contacts ct
        LEFT JOIN companies c ON c.id = ct.company_id
        ORDER BY ct.created_at DESC
    """).fetchall()
    offers_rows = conn.execute("""
        SELECT id, company_id, title, url, relevance_score, location
        FROM job_offers WHERE is_relevant = 1
        ORDER BY relevance_score DESC
    """).fetchall()
    conn.close()
    offers_by_company: dict = {}
    for o in offers_rows:
        cid = o["company_id"]
        if cid not in offers_by_company:
            offers_by_company[cid] = []
        offers_by_company[cid].append({
            "id": o["id"], "title": o["title"],
            "url": o["url"], "relevance_score": o["relevance_score"],
            "location": o["location"],
        })
    result = []
    for ct in contacts:
        d = dict(ct)
        d["offers"] = offers_by_company.get(ct["company_id"], [])
        result.append(d)
    return result


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
    from automation.application_engine import create_drafts
    create_drafts()


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
    return {"status": "started", "note": "Generating drafts (pending_approval). Approve from dashboard to send."}


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=API_PORT, reload=True)
