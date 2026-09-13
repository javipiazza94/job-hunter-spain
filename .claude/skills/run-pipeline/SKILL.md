---
name: run-pipeline
description: "Runs the job-hunter-spain scraping-to-application pipeline end-to-end (seed load, Tecnoempleo scraping, contact extraction, application drafts/sending/form-fill), and covers one-time Gmail/CV/profile setup needed before sending. Use when asked to scrape jobs, extract contacts, or send/review job applications in this repo."
---

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
