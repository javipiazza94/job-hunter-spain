# Job Hunter Spain

Sistema de automatización de candidaturas tech en España (foco Sevilla).

## Puertos

| Servicio | Puerto | Comando |
|----------|--------|---------|
| FastAPI  | 8020   | `cd backend && .venv/bin/uvicorn main:app --reload --port 8020` |
| Next.js  | 3010   | `cd frontend && bun run dev` |

Flujo de scraping/candidaturas y setup de Gmail/CVs → skill `run-pipeline` (`.claude/skills/run-pipeline/SKILL.md`).

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

### Ficha completa (Tecnoempleo)

`scraper/tecnoempleo.py` primero scrapea los listados (título/ubicación/salario/descripción corta) y calcula un score preliminar. Para las ofertas que superen `DETAIL_FETCH_MIN_SCORE` (0.30 por defecto), pide además la ficha completa de la oferta (`TecnoempleoScraper.fetch_offer_detail`), que aporta:
- Descripción completa (vía JSON-LD `JobPosting`, con fallback a `div[itemprop="description"]`)
- `tech_stack` real (tags de la ficha, no solo texto libre)
- `experience_level` y `contract_type` normalizados desde el sidebar "Experiencia"/"Tipo contrato" (reutiliza `automation.experience_classifier`)
- `posted_date` (JSON-LD `datePosted`)
- Salario si el JSON-LD trae `baseSalary` (raro en Tecnoempleo)

Solo se pide ficha completa a las candidatas (no a todas) para no machacar el sitio con una petición extra por oferta. Subir `DETAIL_FETCH_MIN_SCORE` en `config.py` para ser más selectivo (menos peticiones, más rápido); bajarlo para enriquecer más ofertas a costa de más tiempo/peticiones.

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
