# Job Hunter Spain

Automatización de candidaturas tech en España con cola de revisión humana. Scraping de ofertas → clasificación por perfil → borradores editables → aprobación manual → envío.

## Flujo

```
Tecnoempleo / seed
      ↓
 classify_profile()          sap | ia_dev | manual_review
      ↓
  create_drafts()            applications con status=pending_approval
      ↓
Dashboard "Pendientes"       editar carta + aprobar o rechazar
      ↓
  send_approved(id)          Gmail SMTP → company_contact_history
```

- **SAP** → `cv_sap.pdf` + plantilla `cover_letter_sap.j2`
- **IA/Dev** → `cv_ia.pdf` + plantilla `cover_letter_tech.j2`
- **manual_review** → se salta automáticamente (confianza < 0.2)
- **Cooldown** 180 días por empresa para evitar recontactos

## Stack

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.11 · FastAPI · SQLite |
| Scraping | Playwright (stealth) · BeautifulSoup |
| Frontend | Next.js 16 · Tailwind CSS · TypeScript |
| Email | Gmail SMTP (App Password) · Jinja2 |

## Requisitos previos

- Python 3.11+, Node.js 18+, [Bun](https://bun.sh/)
- Gmail con [App Password](https://myaccount.google.com/apppasswords) activada
- Playwright: `playwright install chromium`

## Instalación

```bash
git clone git@github.com:javipiazza94/job-hunter-spain.git
cd job-hunter-spain

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Frontend
cd ../frontend
bun install
```

## Configuración

Crea `backend/.env` (o `.env` en la raíz):

```env
GMAIL_USER=tu@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
```

`backend/profile.json` está en `.gitignore` (contiene datos personales como DNI y fecha de nacimiento). Cópialo desde la plantilla y edítalo con tus datos:
```bash
cp backend/profile.example.json backend/profile.json
```
Esquema completo: personal (incluye `dni_nie`, `birth_date` — usados por el handler de SuccessFactors), `availability`, `salary_expectation`, `summary`, `stack`, `languages`, `certifications`, `education`, `experience`.

Copia tus CVs:
```
backend/cv/cv_ia.pdf
backend/cv/cv_sap.pdf
```

## Arranque

```bash
# Terminal 1 — API
cd backend && .venv/bin/uvicorn main:app --reload --port 8020

# Terminal 2 — Dashboard
cd frontend && bun run dev
```

Dashboard en `http://localhost:3010`

## Uso

```bash
cd backend

# 1. Cargar empresas seed (50 empresas tech con salario público)
python -m scraper.runner --source seed

# 2. Scraping Tecnoempleo
python -m scraper.runner --source tecnoempleo --dry-run   # vista previa
python -m scraper.runner --source tecnoempleo --max-pages 3

# 3. Extraer emails y formularios
python -m scraper.runner --source contacts

# 4. Generar borradores (sin enviar nada todavía)
python -m automation.application_engine create-drafts

# 5. Revisar y aprobar desde el dashboard → tab "Pendientes"
```

El botón **"Generar borradores"** del dashboard también lanza el paso 4 y navega directo al tab Pendientes.

## Arquitectura

```
backend/
├── main.py                      FastAPI API REST (:8020)
├── config.py                    Settings y filtros
├── database.py                  SQLite schema + migraciones
├── profile.json                 Perfil del candidato
├── scraper/
│   ├── tecnoempleo.py           Scraper principal
│   ├── seed_loader.py           50 empresas con salario público
│   ├── contact_extractor.py     Extrae emails y detecta formularios
│   └── runner.py                CLI
└── automation/
    ├── filter_engine.py         Scoring relevancia + classify_profile()
    ├── application_engine.py    create_drafts() + send_approved()
    ├── cover_letter.py          Generación Jinja2 con variación
    └── email_sender.py          Gmail SMTP con rate limiting

frontend/
├── app/page.tsx                 Dashboard (tabs: Ofertas / Pendientes / Candidaturas / ...)
├── app/components/PendingCard.tsx  Tarjeta de revisión con textarea editable
└── lib/api.ts                   Cliente API tipado
```

## Tuning

`backend/config.py`:

| Variable | Default | Qué hace |
|----------|---------|----------|
| `MIN_RELEVANCE_SCORE` | `0.55` | Umbral de relevancia de oferta |
| `MAX_EMAILS_PER_DAY` | `15` | Límite diario de envíos |
| `PROFILE_CONFIDENCE_THRESHOLD` | `0.2` | Mínimo diff SAP vs IA para no ir a manual_review |
| `RECONTACT_COOLDOWN_DAYS` | `180` | Días entre contactos a la misma empresa |
| `STACK_KEYWORDS_BOOST` | lista | Keywords de tu stack para el scoring |
| `TECNOEMPLEO_SEARCH_KEYWORDS` | lista | Keywords de búsqueda en Tecnoempleo |

## Base de datos

SQLite en `backend/job_hunter.db` (gitignored).

| Tabla | Contenido |
|-------|-----------|
| `companies` | Empresas con URL, ciudad, sector |
| `job_offers` | Ofertas con score, cv_profile, descripción |
| `contacts` | Emails y formularios extraídos |
| `applications` | Borradores y enviadas (status, cover_letter_edited, approved_at) |
| `company_contact_history` | Historial de contactos para cooldown |

## Roadmap

- [ ] Scraper InfoJobs
- [ ] Scraper LinkedIn (public search)
- [ ] Form filler con Playwright (`automation/form_filler.py` — stub existe)
- [ ] Hunter.io API para más emails
- [ ] Notificaciones cuando responden (Gmail polling)
