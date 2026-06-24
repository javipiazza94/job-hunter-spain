"""
config.py — Centralised settings for Job Hunter Spain.
All tunable parameters live here; never hardcode in other modules.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")          # backend/.env
load_dotenv(BASE_DIR.parent / ".env")   # project root .env (fallback)
DB_PATH = BASE_DIR / "job_hunter.db"
PROFILE_PATH = BASE_DIR / "profile.json"
SEEDS_PATH = BASE_DIR.parent / "seeds" / "companies_public_salary.json"
TEMPLATES_DIR = BASE_DIR / "templates"
CV_DIR = BASE_DIR / "cv"

# ── Scraping ──────────────────────────────────────────────────────────────────
DELAY_MIN = 3.0
DELAY_MAX = 8.0
MAX_RETRIES = 3

TECNOEMPLEO_BASE = "https://www.tecnoempleo.com"
TECNOEMPLEO_SEARCH_KEYWORDS = [
    "python", "fastapi", "django", "data scientist",
    "machine learning", "devops", "react", "next.js", "sap"
]
TECNOEMPLEO_LOCATIONS = ["Sevilla", "Andalucia", "remoto"]

LINKEDIN_BASE = "https://www.linkedin.com/jobs/search"
LINKEDIN_KEYWORDS = "developer OR data scientist OR devops OR SAP"
LINKEDIN_LOCATIONS = ["Sevilla, España", "Andalucía, España", "España"]

# ── Filter Engine ─────────────────────────────────────────────────────────────
MIN_RELEVANCE_SCORE = 0.55

STACK_KEYWORDS_BOOST = [
    "python", "fastapi", "django", "data science", "data scientist",
    "machine learning", "ml", "llm", "ia", "ai", "inteligencia artificial",
    "react", "next.js", "nextjs", "typescript", "javascript",
    "devops", "docker", "kubernetes", "ci/cd",
    "sap", "sap btp", "sap cloud", "abap",
    ".net", "dotnet", "c#",
    "sql", "postgresql", "sqlite", "mongodb",
    "playwright", "scraping", "automatización",
]

TITLE_KEYWORDS_BOOST = [
    "desarrollador", "developer", "data scientist", "data engineer",
    "fullstack", "full stack", "backend", "frontend",
    "devops", "sre", "platform engineer",
    "sap", "consultor", "consultant",
    "ingeniero", "engineer", "analista", "analyst",
    "ml engineer", "ai engineer", "llm", "nlp",
]

LOCATION_BOOST = ["sevilla", "remoto", "remote", "híbrido", "hibrido", "andalucia"]

NEGATIVE_KEYWORDS = [
    "+10 años", "10 years", "c++ senior", "java ee", "cobol",
    "mainframe", "pl/sql dba", "director", "cto", "ceo",
]

# ── Application Engine ────────────────────────────────────────────────────────
MAX_EMAILS_PER_DAY = 20
EMAIL_DELAY_MIN = 30    # seconds between sends
EMAIL_DELAY_MAX = 120

# ── Email ─────────────────────────────────────────────────────────────────────
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# ── API ───────────────────────────────────────────────────────────────────────
API_PORT = int(os.getenv("API_PORT", "8020"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3010").split(",")

# ── SAP Mode ─────────────────────────────────────────────────────────────────
SAP_KEYWORDS = [
    "SAP Public Cloud", "SAP BTP", "S/4HANA", "Rise with SAP",
    "SAP Fiori", "ABAP", "SAP SuccessFactors", "SAP consultant",
    "consultor SAP", "SAP MM", "SAP SD", "SAP FI", "SAP CO",
]

SAP_COMPANIES_DIRECT = [
    {"name": "SEIDOR",           "careers_url": "https://www.seidor.com/es/trabaja-con-nosotros"},
    {"name": "STRATESYS",        "careers_url": "https://www.stratesys.es/es/trabaja-con-nosotros"},
    {"name": "NTT Data Spain",   "careers_url": "https://es.nttdata.com/careers"},
    {"name": "Capgemini Spain",  "careers_url": "https://www.capgemini.com/es-es/carreras/"},
    {"name": "Accenture Spain",  "careers_url": "https://www.accenture.com/es-es/careers"},
    {"name": "Indra",            "careers_url": "https://www.indracompany.com/es/trabaja-indra"},
    {"name": "T-Systems Iberia", "careers_url": "https://www.t-systems.com/es/es/sobre-t-systems/empleo"},
]

LINKEDIN_SAP_SEARCHES = [
    {"keywords": "SAP Public Cloud", "location": "España"},
    {"keywords": "consultor SAP BTP", "location": "España"},
    {"keywords": "SAP S/4HANA",       "location": "Sevilla"},
    {"keywords": "ABAP developer",    "location": "España"},
]

SESSIONS_DIR = BASE_DIR / "sessions"
LINKEDIN_SESSION_PATH = SESSIONS_DIR / "linkedin_session.json"
