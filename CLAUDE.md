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
```

## Antes de enviar emails

1. Añade tu App Password de Gmail en `.env`:
   - Ve a myaccount.google.com/apppasswords
   - Crea password para "Job Hunter Spain"
   - Pon el valor en `GMAIL_APP_PASSWORD`
2. Copia tu CV a `backend/cv/cv_javi_piazza.pdf`
3. Completa los campos vacíos en `backend/profile.json` (teléfono, dirección, LinkedIn)

## Arquitectura

```
backend/
├── main.py              # FastAPI API REST
├── config.py            # Settings y filtros (EDITAR para tuning)
├── database.py          # SQLite schema + helpers
├── profile.json         # Tu perfil (nombre, email, CV, experiencia)
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
    └── application_engine.py  # Orquestador: itera y aplica

frontend/
└── app/page.tsx         # Dashboard con tabla de empresas y candidaturas
```

## Tuning del filter engine

Editar `backend/config.py`:
- `STACK_KEYWORDS_BOOST`: añadir/quitar keywords de tu stack
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
