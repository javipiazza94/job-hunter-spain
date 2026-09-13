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
# Pesos de scoring (deben sumar 1.0). Prioridad: 1) SAP del máster, 2) stack de
# experiencia previa, 3) ubicación, 4) nivel de experiencia, 5) salario base.
MIN_RELEVANCE_SCORE = 0.55

SCORE_WEIGHTS = {
    "sap_master": 0.35,      # SAP S/4HANA Public Cloud + módulos PS/MM/SD/FI (máster) — mayor peso
    "previous_stack": 0.20,  # Python, C#, SQL, Git, metodología DevOps (trabajos previos)
    "location": 0.20,        # Sevilla si presencial, remoto si es fuera de Sevilla
    "experience": 0.15,      # prioridad a ofertas de menos de 2 años de experiencia
    "salary": 0.10,          # salario base >= SALARY_MIN_BASE
}

# Máster SAP S/4HANA Public Cloud — módulos PS, MM, SD, FI (mayor peso del scoring)
SAP_MASTER_KEYWORDS_BOOST = [
    "sap", "s/4hana", "s4hana", "sap s/4hana", "hana",
    "sap public cloud", "rise with sap", "sap btp", "sap fiori", "abap",
    "sap ps", "project system",
    "sap mm", "materials management",
    "sap sd", "sales & distribution", "sales and distribution",
    "sap fi", "financial accounting",
    "successfactors", "consultor sap", "sap consultant", "consultor funcional",
]

# Stack de experiencia previa (AIDEA Legal / AQR Systems): Python, C#, SQL, Git, DevOps
PREVIOUS_STACK_KEYWORDS_BOOST = [
    "python", "c#", ".net", "dotnet",
    "sql", "postgresql", "sqlite", "mysql",
    "git", "github", "gitlab",
    "devops", "ci/cd", "docker",
]

# Ubicación: presencial solo vale si es en Sevilla; fuera de Sevilla solo vale si es remoto
TARGET_CITY = "sevilla"
LOCATION_BOOST = ["sevilla", "remoto", "remote", "híbrido", "hibrido", "andalucia"]  # legacy, usado como fallback

# Nivel de experiencia: prioridad a ofertas de menos de 2 años
EXPERIENCE_PRIORITY_MAX_YEARS = 2

# Salario base mínimo deseado
SALARY_MIN_BASE = 22000

# Umbral de score (calculado con los datos del listado) a partir del cual se
# pide la ficha completa de la oferta (descripción, tech stack, experiencia, etc.)
DETAIL_FETCH_MIN_SCORE = 0.30

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
MAX_EMAILS_PER_DAY = 20  # TEMP: subido de 15 a 20 solo el 2026-09-13 para desbloquear la cola de hoy (5 pendientes). Revertir a 15 mañana.
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
