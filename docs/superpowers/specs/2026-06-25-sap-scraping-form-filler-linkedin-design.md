# Job Hunter Spain — SAP Scraping, Form Filler & LinkedIn Scraper

**Date:** 2026-06-25  
**Scope:** Three new components to expand the job hunting pipeline

---

## 1. Overview

Extends the existing pipeline with:

1. **SAP Multi-portal Scraper** — scrapes SAP-specific offers from Tecnoempleo, InfoJobs, Computrabajo, direct company career pages (SEIDOR, STRATESYS, etc.) and LinkedIn.
2. **Form Filler** — Playwright automation to submit applications via web forms; handles both simple contact forms and complex ATS portals (Workday, Greenhouse, Lever, SAP SuccessFactors).
3. **LinkedIn Jobs Scraper** — authenticated session (cookie-based), searches SAP roles across Spain.

---

## 2. Architecture

### New files

```
backend/
├── scraper/
│   ├── infojobs.py
│   ├── computrabajo.py
│   ├── company_direct.py
│   └── linkedin_jobs.py
├── automation/
│   ├── form_filler.py
│   └── ats_handlers/
│       ├── __init__.py
│       ├── generic.py
│       ├── workday.py
│       ├── greenhouse.py
│       ├── lever.py
│       └── successfactors.py
└── sessions/
    └── linkedin_session.json   # gitignored
```

### Modified files

- `config.py` — add `SAP_KEYWORDS`, `SAP_COMPANIES_DIRECT`
- `scraper/runner.py` — add `--source sap`, `--source linkedin-login`
- `automation/application_engine.py` — connect form_filler for `contact.type == "form"`
- `.gitignore` — add `sessions/`

---

## 3. SAP Multi-portal Scraper

### config.py additions

```python
SAP_KEYWORDS = [
    "SAP Public Cloud", "SAP BTP", "S/4HANA", "Rise with SAP",
    "SAP Fiori", "ABAP", "SAP SuccessFactors", "SAP consultant",
    "consultor SAP", "SAP MM", "SAP SD", "SAP FI", "SAP CO",
]

SAP_COMPANIES_DIRECT = [
    {"name": "SEIDOR",        "careers_url": "https://www.seidor.com/es/trabaja-con-nosotros"},
    {"name": "STRATESYS",     "careers_url": "https://www.stratesys.es/es/trabaja-con-nosotros"},
    {"name": "NTT Data Spain","careers_url": "https://es.nttdata.com/careers"},
    {"name": "Capgemini Spain","careers_url": "https://www.capgemini.com/es-es/carreras/"},
    {"name": "Accenture Spain","careers_url": "https://www.accenture.com/es-es/careers"},
    {"name": "Indra",          "careers_url": "https://www.indracompany.com/es/trabaja-indra"},
    {"name": "T-Systems Iberia","careers_url": "https://www.t-systems.com/es/es/sobre-t-systems/empleo"},
]
```

### scraper/infojobs.py

- Extends `BaseScraper`
- URL pattern: `https://www.infojobs.net/jobsearch/search-results/list.xhtml?keyword={kw}&normalizedJobArea=&normalizedLocation=sevilla-andalucia-espana`
- Selectors to be verified on first run against live site
- Extracts: title, company, location, description, URL, salary range
- Deduplicates by URL before DB insert

### scraper/computrabajo.py

- Extends `BaseScraper`
- URL pattern: `https://www.computrabajo.es/trabajo-de-{keyword-slugified}?l=sevilla`
- Falls back to national search if no Sevilla results
- Same output schema as TecnoempleoScraper

### scraper/company_direct.py

- Iterates `SAP_COMPANIES_DIRECT` from config
- For each company: visits `careers_url`, extracts job listings matching SAP keywords
- Also runs `ContactExtractorScraper.extract_for_company()` to get emails/forms
- Upserts company + contacts + job_offers into DB

### runner.py — new sources

```bash
python -m scraper.runner --source sap              # all SAP portals
python -m scraper.runner --source sap --dry-run    # preview without saving
python -m scraper.runner --source linkedin-login   # one-time session setup
```

`--source sap` runs in sequence: Tecnoempleo (SAP_KEYWORDS) → InfoJobs → Computrabajo → company_direct → linkedin_jobs.

---

## 4. Form Filler

### automation/form_filler.py

Entry point called by `application_engine.py`:

```python
async def fill_form(
    form_url: str,
    profile: dict,
    cv_path: Path,
    cover_letter: str,
    dry_run: bool = False,
) -> bool
```

**ATS detection by URL:**

| URL pattern | Handler |
|---|---|
| `myworkdayjobs.com`, `workday.com` | `workday.py` |
| `greenhouse.io`, `boards.greenhouse.io` | `greenhouse.py` |
| `jobs.lever.co` | `lever.py` |
| `successfactors.eu`, `sap.com/careers` | `successfactors.py` |
| anything else | `generic.py` |

### ats_handlers/generic.py

Scans all `<input>`, `<textarea>`, `<select>` elements. Maps by `name`, `placeholder`, `aria-label`, and associated `<label>` text to profile fields:

| Field hint | Maps to |
|---|---|
| `first_name`, `nombre`, `name` | `personal.name` (first word) |
| `last_name`, `apellido` | `personal.name` (remaining words) |
| `email`, `correo` | `personal.email` |
| `phone`, `teléfono`, `móvil` | `personal.phone` |
| `linkedin` | `personal.linkedin` |
| `cover_letter`, `carta`, `motivación` | generated cover letter text |
| `input[type=file]` | attaches CV PDF |

Cookie banner dismissal runs before any interaction (`_dismiss_cookies(page)`): clicks first visible button matching `[id*=accept]`, `[class*=accept]`, `[id*=cookie]`.

### ats_handlers/workday.py, greenhouse.py, lever.py, successfactors.py

Each handles the multi-step flow of its ATS:
1. Fill personal data fields (step 1)
2. Upload CV file (step 2)
3. Answer additional questions with generic profile text (step 3)
4. Click final Submit button

Workday and SuccessFactors use iframe navigation; handlers switch context accordingly.

If a required field cannot be mapped, the handler logs a warning and marks the application as `"needs_manual_review"` in the DB instead of failing silently.

### application_engine.py change

```python
elif contact["type"] == "form":
    success = await fill_form(
        contact["value"], profile, cv, cover_letter, dry_run=dry_run
    )
```

---

## 5. LinkedIn Jobs Scraper

### Session management

```bash
python -m scraper.runner --source linkedin-login
```

Opens Chromium in headful mode. User navigates to linkedin.com and logs in manually. Script waits until URL contains `/feed`, then saves cookies to `sessions/linkedin_session.json`. Session valid ~30 days.

Subsequent runs load cookies from file before going headless.

### scraper/linkedin_jobs.py

Searches defined in config:

```python
LINKEDIN_SAP_SEARCHES = [
    {"keywords": "SAP Public Cloud", "location": "España"},
    {"keywords": "consultor SAP BTP", "location": "España"},
    {"keywords": "SAP S/4HANA",      "location": "Sevilla"},
    {"keywords": "ABAP developer",   "location": "España"},
]
```

Per search:
- Loads `/jobs/search?keywords={kw}&location={loc}&f_TPR=r2592000` (last 30 days)
- Collects up to 25 job cards
- Opens each offer to extract full description
- Stores: title, company, location, description, url, date_posted, `source="linkedin"`

**Anti-detection measures:**
- Delays 5–12s between pages (more conservative than other scrapers)
- Max 25 offers per search per run
- If captcha/checkpoint page detected → stops run, logs warning: `"LinkedIn checkpoint detected — re-run linkedin-login"`
- Does not store LinkedIn credentials anywhere; session only via cookies

### .gitignore addition

```
sessions/
```

---

## 6. Data flow

```
runner --source sap
  ├── TecnoempleoScraper (SAP_KEYWORDS)
  ├── InfoJobsScraper (SAP_KEYWORDS)
  ├── ComputrabajoScraper (SAP_KEYWORDS)
  ├── CompanyDirectScraper (SAP_COMPANIES_DIRECT)
  │     └── ContactExtractorScraper (emails + forms)
  └── LinkedInJobsScraper (LINKEDIN_SAP_SEARCHES)
        └── loads sessions/linkedin_session.json

All results → filter_engine (MIN_RELEVANCE_SCORE=0.55) → job_offers table

application_engine
  ├── contact.type == "email"  → email_sender.py
  └── contact.type == "form"   → form_filler.py
        ├── detect ATS
        └── ats_handlers/{generic,workday,greenhouse,lever,successfactors}.py
```

---

## 7. Error handling

- Each scraper fails independently — one portal failing does not stop others
- Form filler: unknown required fields → status `"needs_manual_review"` (not silent failure)
- LinkedIn checkpoint → hard stop with clear log message
- All scrapers inherit `BaseScraper.fetch_with_retry` (3 attempts, exponential backoff)

---

## 8. Out of scope

- Hunter.io API integration (separate task)
- Automatic LinkedIn login (credential-based) — cookie session only
- Form filling for captcha-protected forms
- CV generation or customization per offer
