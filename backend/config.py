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
    "machine learning", "devops", "react", "next.js", "sap",
    "consultor ia", "implantacion ia"
]
TECNOEMPLEO_LOCATIONS = ["Sevilla", "Andalucia", "remoto"]

LINKEDIN_BASE = "https://www.linkedin.com/jobs/search"
LINKEDIN_KEYWORDS = "developer OR data scientist OR devops OR SAP"
LINKEDIN_LOCATIONS = ["Sevilla, España", "Andalucía, España", "España"]

# ── Indeed ────────────────────────────────────────────────────────────────────
SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY", "")

INDEED_BASE = "https://es.indeed.com"
INDEED_SEARCH_KEYWORDS = [
    "python developer", "fullstack", "data scientist",
    "machine learning", "devops", "react", "SAP consultor",
]
INDEED_LOCATIONS = ["Sevilla", "Remoto"]

# ── Manfred ───────────────────────────────────────────────────────────────────
MANFRED_API_BASE = "https://www.getmanfred.com/api/v2/public/offers"
MANFRED_MAX_PAGES = 5

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

# ── Application Engine ────────────────────────────────────────────────────────
MAX_EMAILS_PER_DAY = 15
EMAIL_DELAY_MIN = 30    # seconds between sends
EMAIL_DELAY_MAX = 120

# ── Email ─────────────────────────────────────────────────────────────────────
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# ── API ───────────────────────────────────────────────────────────────────────
API_PORT = int(os.getenv("API_PORT", "8020"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3010,http://localhost:3000").split(",")

# ── SAP Mode ─────────────────────────────────────────────────────────────────
SAP_KEYWORDS = [
    "SAP Public Cloud", "SAP BTP", "S/4HANA", "Rise with SAP",
    "SAP Fiori", "ABAP", "SAP SuccessFactors", "SAP consultant",
    "consultor SAP", "SAP MM", "SAP SD", "SAP FI", "SAP CO",
]

SAP_COMPANIES_DIRECT = [
    {"name": "SEIDOR",           "careers_url": "https://www.seidor.com/es-es/talento"},
    # STRATESYS: ERR_CERT_COMMON_NAME_INVALID — SSL roto en su lado
    {"name": "NTT Data Spain",   "careers_url": "https://careers.services.global.ntt/global/en"},
    {"name": "Capgemini Spain",  "careers_url": "https://jobs.capgemini.com/es/"},
    {"name": "Accenture Spain",  "careers_url": "https://www.accenture.com/es-es/careers"},
    {"name": "Indra",            "careers_url": "https://careers.indragroup.com/ofertas-de-empleo"},
    {"name": "T-Systems Iberia", "careers_url": "https://www.t-systems.com/es/es"},
]

LINKEDIN_SAP_SEARCHES = [
    {"keywords": "SAP Public Cloud", "location": "España"},
    {"keywords": "consultor SAP BTP", "location": "España"},
    {"keywords": "SAP S/4HANA",       "location": "Sevilla"},
    {"keywords": "SAP Public Cloud SD", "location": "España"},
    {"keywords": "SAP Public Cloud MM", "location": "España"},
    {"keywords": "SAP Public Cloud PS", "location": "España"},
    {"keywords": "SAP Public Cloud FI", "location": "España"},
]

LINKEDIN_IADEV_SEARCHES = [
    {"keywords": "python developer",     "location": "España"},
    {"keywords": "data scientist",       "location": "España"},
    {"keywords": "machine learning LLM", "location": "España"},
    {"keywords": "AI engineer fastapi",  "location": "España"},
    {"keywords": "fullstack react",      "location": "Sevilla, España"},
    {"keywords": "devops kubernetes",    "location": "España"},
]

LINKEDIN_ALL_SEARCHES = LINKEDIN_SAP_SEARCHES + LINKEDIN_IADEV_SEARCHES

SESSIONS_DIR = BASE_DIR / "sessions"
LINKEDIN_SESSION_PATH = SESSIONS_DIR / "linkedin_session.json"
