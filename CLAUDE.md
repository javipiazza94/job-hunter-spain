# Job Hunter Spain

Sistema de automatización de candidaturas tech en España (foco Sevilla).

## Puertos

| Servicio | Puerto | Comando |
|----------|--------|---------|
| FastAPI  | 8020   | `cd backend && .venv/bin/uvicorn main:app --reload --port 8020` |
| Next.js  | 3010   | `cd frontend && bun run dev` |

## Flujo completo

```bash
# 1. Cargar seed (50 empresas del repo companies-with-public-salary)
cd backend && python -m scraper.runner --source seed

# 2. Scraping de Tecnoempleo (dry-run primero)
python -m scraper.runner --source tecnoempleo --dry-run
python -m scraper.runner --source tecnoempleo --max-pages 3

# 3. Extraer emails y formularios de webs de empresas
python -m scraper.runner --source contacts

# 4. Ver candidaturas pendientes (dry-run)
python -m automation.application_engine --dry-run

# 5. Enviar candidaturas (20 max/día, delays automáticos)
python -m automation.application_engine --limit 10

# 6. Rellenar formularios de candidatura (SuccessFactors / genérico) — nunca envía
python -m automation.application_engine fill-forms --dry-run
python -m automation.application_engine fill-forms
```

## Antes de enviar emails

1. Añade tu App Password de Gmail en `.env`:
   - Ve a myaccount.google.com/apppasswords
   - Crea password para "Job Hunter Spain"
   - Pon el valor en `GMAIL_APP_PASSWORD`
2. Copia tus CVs a `backend/cv/` (`cv_ia.pdf`, `cv_sap.pdf`, `cv_general.pdf`)
3. `cp backend/profile.example.json backend/profile.json` y completa tus datos — `profile.json` está en `.gitignore` porque incluye DNI y fecha de nacimiento (los pide SuccessFactors)

## Arquitectura

```
backend/
├── main.py              # FastAPI API REST
├── config.py            # Settings y filtros (EDITAR para tuning)
├── database.py          # SQLite schema + helpers
├── profile.json         # Tu perfil (gitignored — PII: DNI, fecha nacimiento)
├── profile.example.json # Plantilla trackeada, sin datos reales
├── scraper/
│   ├── base.py          # Playwright con stealth + rate limiting
│   ├── seed_loader.py   # Carga companies-with-public-salary
│   ├── tecnoempleo.py   # Scraper de Tecnoempleo
│   ├── contact_extractor.py  # Extrae emails y detecta formularios
│   └── runner.py        # CLI principal
└── automation/
    ├── filter_engine.py # Scoring por stack/ubicación (umbral: 0.55)
    ├── cover_letter.py  # Genera carta con Jinja2
    ├── email_sender.py  # Gmail SMTP con rate limiting
    ├── form_filler.py   # Playwright form filler — nunca hace clic en Enviar/Submit
    ├── ats_handlers/     # workday · greenhouse · lever · successfactors · generic
    └── application_engine.py  # Orquestador: create_drafts() + fill_forms() + send_approved()

frontend/
└── app/page.tsx         # Dashboard con tabla de empresas y candidaturas
```

## Tuning del filter engine

El scoring (`automation/filter_engine.py::score_offer`) pondera 5 categorías definidas en `backend/config.py` (`SCORE_WEIGHTS`, deben sumar 1.0), de mayor a menor prioridad:

| Categoría | Peso | Qué mide |
|-----------|------|----------|
| `sap_master` | 0.35 | SAP S/4HANA Public Cloud + módulos PS/MM/SD/FI del máster (`SAP_MASTER_KEYWORDS_BOOST`) |
| `previous_stack` | 0.20 | Python, C#, SQL, Git, DevOps de trabajos previos (`PREVIOUS_STACK_KEYWORDS_BOOST`) |
| `location` | 0.20 | Sevilla si es presencial, remoto si es fuera (`TARGET_CITY`) — híbrido fuera de Sevilla puntúa a medias, presencial fuera de Sevilla puntúa 0 |
| `experience` | 0.15 | Prioridad a ofertas junior/<2 años (`EXPERIENCE_PRIORITY_MAX_YEARS`), vía `experience_classifier.classify_experience` |
| `salary` | 0.10 | Salario base >= `SALARY_MIN_BASE` (22000€) |

El tamaño de empresa no se puntúa (indiferente).

Editar `backend/config.py`:
- `SAP_MASTER_KEYWORDS_BOOST` / `PREVIOUS_STACK_KEYWORDS_BOOST`: añadir/quitar keywords de stack
- `SCORE_WEIGHTS`: reponderar categorías (deben sumar 1.0)
- `TARGET_CITY`, `SALARY_MIN_BASE`, `EXPERIENCE_PRIORITY_MAX_YEARS`: ajustar umbrales
- `MIN_RELEVANCE_SCORE`: bajar a 0.45 para más resultados, subir a 0.65 para más precisión
- `MAX_EMAILS_PER_DAY`: cambiar límite diario (default: 20)
- `TECNOEMPLEO_SEARCH_KEYWORDS`: keywords para búsqueda en Tecnoempleo

## Base de datos

SQLite en `backend/job_hunter.db` (gitignored).
Tablas: `companies`, `job_offers`, `contacts`, `applications`.

## Pendiente (Fase siguiente)

- [ ] Scraper LinkedIn public search
- [ ] Form filler con Playwright (automation/form_filler.py)
- [ ] Añadir Hunter.io API para emails adicionales
- [ ] Scraper directo de webs de empresas tech sevillanas (Google Places)
