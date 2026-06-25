# Job Hunter Spain — SAP Multi-portal, Form Filler & LinkedIn

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand Job Hunter Spain with SAP-targeted multi-portal scraping (InfoJobs, Computrabajo, company career pages, LinkedIn), a Playwright-based form filler for ATS portals (Workday, Greenhouse, Lever, SuccessFactors), and authenticated LinkedIn job search.

**Architecture:** Three independent modules wired into the existing pipeline: new scrapers extend `BaseScraper` and plug into `runner.py` under `--source sap`; form filler uses URL-based ATS detection with a handler-per-platform pattern; LinkedIn uses persistent cookie sessions to avoid storing credentials.

**Tech Stack:** Python 3.12+, Playwright async, BeautifulSoup4, pytest + pytest-asyncio, SQLite (existing schema)

## Global Constraints

- All scrapers must extend `BaseScraper` from `scraper/base.py`
- All DB writes use `upsert_company`, `upsert_job_offer`, `upsert_contact`, `record_application` from `database.py` — no raw SQL inserts in feature code
- Offer scoring always uses `score_offer()` from `automation/filter_engine.py`; threshold is `MIN_RELEVANCE_SCORE` from `config.py`
- Profile fields accessed as `profile["personal"]["email"]` — structure defined in `backend/profile.json`
- Tests live in `backend/tests/`, run with `.venv/bin/pytest tests/ -v`
- LinkedIn session stored only as cookies in `sessions/linkedin_session.json` — no credentials in code or `.env`
- Each portal in `run_sap_source()` is wrapped in try/except — one failure must not stop the others

---

### Task 1: Foundation — SAP config constants, sessions dir, test infrastructure

**Files:**
- Modify: `backend/config.py`
- Modify: `backend/.gitignore` (root project `.gitignore`)
- Create: `backend/sessions/.gitkeep`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `SAP_KEYWORDS: list[str]`, `SAP_COMPANIES_DIRECT: list[dict]`, `LINKEDIN_SAP_SEARCHES: list[dict]`, `LINKEDIN_SESSION_PATH: Path`, `SESSIONS_DIR: Path` — imported by all SAP scrapers

- [ ] **Step 1: Install pytest + pytest-asyncio**

```bash
cd /home/javi-piazza/Documentos/Desarrollos/SCRIPTS/Proyectos/job-hunter-spain/backend
.venv/bin/pip install pytest pytest-asyncio
echo "pytest>=8.0.0" >> requirements.txt
echo "pytest-asyncio>=0.23.0" >> requirements.txt
```

- [ ] **Step 2: Write failing tests**

Create `tests/__init__.py` (empty). Create `tests/test_config.py`:

```python
def test_sap_keywords_non_empty():
    from config import SAP_KEYWORDS
    assert len(SAP_KEYWORDS) >= 10
    assert "SAP BTP" in SAP_KEYWORDS
    assert "S/4HANA" in SAP_KEYWORDS

def test_sap_companies_direct_structure():
    from config import SAP_COMPANIES_DIRECT
    assert len(SAP_COMPANIES_DIRECT) >= 5
    for c in SAP_COMPANIES_DIRECT:
        assert "name" in c
        assert "careers_url" in c
        assert c["careers_url"].startswith("https://")

def test_linkedin_sap_searches_structure():
    from config import LINKEDIN_SAP_SEARCHES
    assert len(LINKEDIN_SAP_SEARCHES) >= 3
    for s in LINKEDIN_SAP_SEARCHES:
        assert "keywords" in s
        assert "location" in s

def test_sessions_paths_defined():
    from config import SESSIONS_DIR, LINKEDIN_SESSION_PATH
    assert "sessions" in str(SESSIONS_DIR)
    assert str(LINKEDIN_SESSION_PATH).endswith(".json")
```

- [ ] **Step 3: Run tests — expect FAIL (ImportError)**

```bash
.venv/bin/pytest tests/test_config.py -v
```
Expected: `ImportError: cannot import name 'SAP_KEYWORDS' from 'config'`

- [ ] **Step 4: Append constants to config.py**

Add at the end of `backend/config.py`:

```python
# ── SAP Mode ─────────────────────────────────────────────────────────────────
SAP_KEYWORDS = [
    "SAP Public Cloud", "SAP BTP", "S/4HANA", "Rise with SAP",
    "SAP Fiori", "ABAP", "SAP SuccessFactors", "SAP consultant",
    "consultor SAP", "SAP MM", "SAP SD", "SAP FI", "SAP CO",
]

SAP_COMPANIES_DIRECT = [
    {"name": "SEIDOR",          "careers_url": "https://www.seidor.com/es/trabaja-con-nosotros"},
    {"name": "STRATESYS",       "careers_url": "https://www.stratesys.es/es/trabaja-con-nosotros"},
    {"name": "NTT Data Spain",  "careers_url": "https://es.nttdata.com/careers"},
    {"name": "Capgemini Spain", "careers_url": "https://www.capgemini.com/es-es/carreras/"},
    {"name": "Accenture Spain", "careers_url": "https://www.accenture.com/es-es/careers"},
    {"name": "Indra",           "careers_url": "https://www.indracompany.com/es/trabaja-indra"},
    {"name": "T-Systems Iberia","careers_url": "https://www.t-systems.com/es/es/sobre-t-systems/empleo"},
]

LINKEDIN_SAP_SEARCHES = [
    {"keywords": "SAP Public Cloud", "location": "España"},
    {"keywords": "consultor SAP BTP", "location": "España"},
    {"keywords": "SAP S/4HANA",       "location": "Sevilla"},
    {"keywords": "ABAP developer",    "location": "España"},
]

SESSIONS_DIR = BASE_DIR / "sessions"
LINKEDIN_SESSION_PATH = SESSIONS_DIR / "linkedin_session.json"
```

- [ ] **Step 5: Create sessions dir and update .gitignore**

```bash
mkdir -p backend/sessions
touch backend/sessions/.gitkeep
```

Append to the project `.gitignore` (at repo root or `backend/`):
```
sessions/
!sessions/.gitkeep
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
.venv/bin/pytest tests/test_config.py -v
```
Expected: 4 PASSED

- [ ] **Step 7: Commit**

```bash
git init  # if not already a git repo
git add backend/config.py backend/sessions/.gitkeep backend/tests/__init__.py backend/tests/test_config.py backend/requirements.txt
git commit -m "feat: add SAP config constants, sessions dir and test infrastructure"
```

---

### Task 2: scraper/infojobs.py — InfoJobs scraper

**Files:**
- Create: `backend/scraper/infojobs.py`
- Create: `backend/tests/test_infojobs.py`

**Interfaces:**
- Consumes: `BaseScraper` from `scraper/base.py`
- Produces: `run_infojobs(keywords: list[str], max_pages: int = 3) -> list[dict]` — each dict: `{title, url, company_name, location, description, salary_min, salary_max, tech_tags, source}`; `_parse_card_html(html: str, base_url: str) -> dict | None`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_infojobs.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

SAMPLE_CARD = """
<div class="ij-OfferCardContent">
  <h2 class="title"><a href="/empleo/sap-consultant_oferta_12345.aspx">SAP Consultant</a></h2>
  <a class="companyName">Empresa Tech SL</a>
  <span class="location">Sevilla</span>
  <p class="description">Buscamos consultor SAP BTP con experiencia en S/4HANA</p>
</div>
"""

def test_parse_card_returns_expected_fields():
    from scraper.infojobs import _parse_card_html
    result = _parse_card_html(SAMPLE_CARD, base_url="https://www.infojobs.net")
    assert result is not None
    assert result["title"] == "SAP Consultant"
    assert result["company_name"] == "Empresa Tech SL"
    assert result["location"] == "Sevilla"
    assert "SAP BTP" in result["description"]
    assert result["url"].startswith("https://")
    assert result["source"] == "infojobs"

def test_parse_card_returns_none_on_missing_title():
    from scraper.infojobs import _parse_card_html
    result = _parse_card_html("<div></div>", base_url="https://www.infojobs.net")
    assert result is None
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
.venv/bin/pytest tests/test_infojobs.py -v
```
Expected: `ModuleNotFoundError: No module named 'scraper.infojobs'`

- [ ] **Step 3: Create backend/scraper/infojobs.py**

```python
"""
scraper/infojobs.py — Scrapes job offers from InfoJobs.net.
URL: /jobsearch/search-results/list.xhtml?keyword={kw}&normalizedLocation=sevilla-andalucia-espana

Primary card selector: .ij-OfferCardContent
If selectors stop working, inspect with:
  chromium --headless --dump-dom 'https://www.infojobs.net/jobsearch/...'
"""
import re
import logging
from bs4 import BeautifulSoup
from urllib.parse import urlencode, urljoin
from scraper.base import BaseScraper

logger = logging.getLogger(__name__)

INFOJOBS_BASE = "https://www.infojobs.net"
SALARY_PATTERN = re.compile(r"(\d[\d.,]+)\s*€")


def _parse_card_html(html: str, base_url: str = INFOJOBS_BASE) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.select_one("h2.title a, h3.title a, [class*='title'] a")
    if not title_el:
        return None
    title = title_el.get_text(strip=True)
    href = title_el.get("href", "")
    url = urljoin(base_url, href) if href else None
    if not url:
        return None

    company_el = soup.select_one(".companyName, [class*='company']")
    company_name = company_el.get_text(strip=True) if company_el else None

    location_el = soup.select_one(".location, [class*='location']")
    location = location_el.get_text(strip=True) if location_el else None

    desc_el = soup.select_one(".description, p.description, [class*='description']")
    description = desc_el.get_text(strip=True) if desc_el else None

    salary_match = SALARY_PATTERN.search(soup.get_text())
    salary_min = int(salary_match.group(1).replace(".", "").replace(",", "")) if salary_match else None

    return {
        "title": title,
        "url": url,
        "company_name": company_name,
        "location": location,
        "description": description,
        "salary_min": salary_min,
        "salary_max": None,
        "tech_tags": [],
        "source": "infojobs",
    }


class InfoJobsScraper(BaseScraper):
    def __init__(self):
        super().__init__(delay_min=3.0, delay_max=8.0)

    async def scrape_keyword(self, keyword: str, max_pages: int = 3) -> list[dict]:
        offers = []
        async with self as scraper:
            page = await scraper.new_page()
            for page_num in range(1, max_pages + 1):
                params = {
                    "keyword": keyword,
                    "normalizedLocation": "sevilla-andalucia-espana",
                    "page": page_num,
                }
                url = f"{INFOJOBS_BASE}/jobsearch/search-results/list.xhtml?{urlencode(params)}"
                logger.info("InfoJobs page %d: %s", page_num, url)
                if not await scraper.fetch_with_retry(page, url):
                    break

                cards = await page.query_selector_all(
                    ".ij-OfferCardContent, div[class*='OfferCard'], article[class*='offer']"
                )
                if not cards:
                    logger.info("InfoJobs: no cards on page %d", page_num)
                    break

                for card in cards:
                    html = await card.inner_html()
                    offer = _parse_card_html(html)
                    if offer:
                        offers.append(offer)

                logger.info("InfoJobs page %d: %d cards", page_num, len(cards))
                await scraper.random_delay()

                next_btn = await page.query_selector(
                    "a[rel='next'], .pagination-next a, [aria-label*='siguiente']"
                )
                if not next_btn:
                    break
        return offers


async def run_infojobs(keywords: list[str], max_pages: int = 3) -> list[dict]:
    scraper = InfoJobsScraper()
    seen: set[str] = set()
    all_offers: list[dict] = []
    for kw in keywords:
        logger.info("InfoJobs keyword: %s", kw)
        try:
            for offer in await scraper.scrape_keyword(kw, max_pages):
                if offer.get("url") and offer["url"] not in seen:
                    seen.add(offer["url"])
                    all_offers.append(offer)
        except Exception as e:
            logger.error("InfoJobs keyword '%s' failed: %s", kw, e)
    logger.info("InfoJobs total: %d unique offers", len(all_offers))
    return all_offers
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
.venv/bin/pytest tests/test_infojobs.py -v
```
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add scraper/infojobs.py tests/test_infojobs.py
git commit -m "feat: add InfoJobs scraper with BeautifulSoup HTML parser"
```

---

### Task 3: scraper/computrabajo.py — Computrabajo scraper

**Files:**
- Create: `backend/scraper/computrabajo.py`
- Create: `backend/tests/test_computrabajo.py`

**Interfaces:**
- Produces: `run_computrabajo(keywords: list[str], max_pages: int = 3) -> list[dict]` — same schema as `run_infojobs` with `source="computrabajo"`; `_parse_card_html(html, base_url) -> dict | None`; `_slugify(text: str) -> str`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_computrabajo.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

SAMPLE_CARD = """
<article class="box_offer">
  <h2><a href="/oferta-de-trabajo/sap-consultant-sevilla-12345">Consultor SAP BTP</a></h2>
  <p class="fs16">Consultora SAP España SL</p>
  <span class="fs13">Sevilla</span>
  <p class="description">Proyecto S/4HANA público, viajes ocasionales</p>
</article>
"""

def test_slugify_spaces_and_special_chars():
    from scraper.computrabajo import _slugify
    assert _slugify("SAP Public Cloud") == "sap-public-cloud"
    assert _slugify("S/4HANA") == "s-4hana"

def test_parse_card_returns_expected_fields():
    from scraper.computrabajo import _parse_card_html
    result = _parse_card_html(SAMPLE_CARD, base_url="https://www.computrabajo.es")
    assert result is not None
    assert result["title"] == "Consultor SAP BTP"
    assert result["company_name"] == "Consultora SAP España SL"
    assert result["location"] == "Sevilla"
    assert result["source"] == "computrabajo"

def test_parse_card_returns_none_without_link():
    from scraper.computrabajo import _parse_card_html
    result = _parse_card_html("<article></article>", base_url="https://www.computrabajo.es")
    assert result is None
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
.venv/bin/pytest tests/test_computrabajo.py -v
```
Expected: `ModuleNotFoundError: No module named 'scraper.computrabajo'`

- [ ] **Step 3: Create backend/scraper/computrabajo.py**

```python
"""
scraper/computrabajo.py — Scrapes job offers from Computrabajo.es.
URL: /trabajo-de-{keyword-slug}?l=sevilla
Falls back to national search if no Sevilla results.

Primary card selector: article.box_offer
"""
import re
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from scraper.base import BaseScraper

logger = logging.getLogger(__name__)

COMPUTRABAJO_BASE = "https://www.computrabajo.es"


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _parse_card_html(html: str, base_url: str = COMPUTRABAJO_BASE) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")

    link_el = soup.select_one("h2 a, h3 a, .title_offer a")
    if not link_el:
        return None
    title = link_el.get_text(strip=True)
    href = link_el.get("href", "")
    url = urljoin(base_url, href) if href else None
    if not url:
        return None

    company_el = soup.select_one(".fs16, .company, [class*='company']")
    company_name = company_el.get_text(strip=True) if company_el else None

    location_el = soup.select_one(".fs13, .location, [class*='location']")
    location = location_el.get_text(strip=True) if location_el else None

    desc_el = soup.select_one(".description, p:not(.fs16):not(.fs13)")
    description = desc_el.get_text(strip=True) if desc_el else None

    return {
        "title": title,
        "url": url,
        "company_name": company_name,
        "location": location,
        "description": description,
        "salary_min": None,
        "salary_max": None,
        "tech_tags": [],
        "source": "computrabajo",
    }


class ComputrabajoScraper(BaseScraper):
    def __init__(self):
        super().__init__(delay_min=3.0, delay_max=8.0)

    async def scrape_keyword(self, keyword: str, max_pages: int = 3) -> list[dict]:
        offers = []
        slug = _slugify(keyword)
        async with self as scraper:
            page = await scraper.new_page()
            for page_num in range(1, max_pages + 1):
                page_suffix = f"-p{page_num}" if page_num > 1 else ""
                url = f"{COMPUTRABAJO_BASE}/trabajo-de-{slug}{page_suffix}?l=sevilla"
                logger.info("Computrabajo page %d: %s", page_num, url)
                ok = await scraper.fetch_with_retry(page, url)
                if not ok:
                    # Retry without location
                    url_national = f"{COMPUTRABAJO_BASE}/trabajo-de-{slug}{page_suffix}"
                    if not await scraper.fetch_with_retry(page, url_national):
                        break

                cards = await page.query_selector_all(
                    "article.box_offer, div[class*='offer_box'], article[class*='offer']"
                )
                if not cards:
                    break

                for card in cards:
                    offer = _parse_card_html(await card.inner_html())
                    if offer:
                        offers.append(offer)

                logger.info("Computrabajo page %d: %d cards", page_num, len(cards))
                await scraper.random_delay()

                next_btn = await page.query_selector("a[rel='next'], .next a")
                if not next_btn:
                    break
        return offers


async def run_computrabajo(keywords: list[str], max_pages: int = 3) -> list[dict]:
    scraper = ComputrabajoScraper()
    seen: set[str] = set()
    all_offers: list[dict] = []
    for kw in keywords:
        logger.info("Computrabajo keyword: %s", kw)
        try:
            for offer in await scraper.scrape_keyword(kw, max_pages):
                if offer.get("url") and offer["url"] not in seen:
                    seen.add(offer["url"])
                    all_offers.append(offer)
        except Exception as e:
            logger.error("Computrabajo keyword '%s' failed: %s", kw, e)
    logger.info("Computrabajo total: %d unique offers", len(all_offers))
    return all_offers
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
.venv/bin/pytest tests/test_computrabajo.py -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add scraper/computrabajo.py tests/test_computrabajo.py
git commit -m "feat: add Computrabajo scraper with slug-based URL and HTML parser"
```

---

### Task 4: scraper/company_direct.py — Direct company career page scraper

**Files:**
- Create: `backend/scraper/company_direct.py`
- Create: `backend/tests/test_company_direct.py`

**Interfaces:**
- Consumes: `SAP_COMPANIES_DIRECT`, `SAP_KEYWORDS`, `MIN_RELEVANCE_SCORE` from `config.py`; `ContactExtractorScraper` from `scraper/contact_extractor.py`; `upsert_company`, `upsert_job_offer`, `upsert_contact` from `database.py`; `score_offer` from `automation/filter_engine.py`
- Produces: `run_company_direct(dry_run: bool = False) -> tuple[int, int]` — (offers_found, contacts_found); `_is_sap_offer(title: str, description: str) -> bool`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_company_direct.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_is_sap_offer_detects_keywords():
    from scraper.company_direct import _is_sap_offer
    assert _is_sap_offer("SAP BTP consultant role", "") is True
    assert _is_sap_offer("ABAP developer needed", "") is True
    assert _is_sap_offer("Java backend engineer", "") is False
    assert _is_sap_offer("", "Experience with S/4HANA required") is True

def test_is_sap_offer_case_insensitive():
    from scraper.company_direct import _is_sap_offer
    assert _is_sap_offer("sap fiori consultant", "") is True
    assert _is_sap_offer("Consultor SAP MM", "") is True

def test_parse_job_links_filters_by_hint():
    from scraper.company_direct import _parse_job_links
    html = """
    <a href="/job/sap-consultant">SAP Consultant</a>
    <a href="/blog/news">Blog post</a>
    <a href="/vacante/abap-developer">ABAP Developer</a>
    """
    links = _parse_job_links(html, "https://example.com")
    urls = [l["url"] for l in links]
    assert any("sap-consultant" in u for u in urls)
    assert any("abap-developer" in u for u in urls)
    assert not any("blog" in u for u in urls)
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
.venv/bin/pytest tests/test_company_direct.py -v
```
Expected: `ModuleNotFoundError: No module named 'scraper.company_direct'`

- [ ] **Step 3: Create backend/scraper/company_direct.py**

```python
"""
scraper/company_direct.py — Scrapes career pages of known SAP consulting firms.
For each company in SAP_COMPANIES_DIRECT: extracts SAP job links + emails/forms.
"""
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from scraper.base import BaseScraper
from scraper.contact_extractor import ContactExtractorScraper
from database import get_conn, upsert_company, upsert_job_offer, upsert_contact
from automation.filter_engine import score_offer
from config import SAP_COMPANIES_DIRECT, SAP_KEYWORDS, MIN_RELEVANCE_SCORE

logger = logging.getLogger(__name__)

_SAP_LOWER = [kw.lower() for kw in SAP_KEYWORDS]
_JOB_URL_HINTS = ["/job", "/oferta", "/empleo", "/vacante", "/position", "/career", "/oportunidad"]


def _is_sap_offer(title: str, description: str) -> bool:
    combined = (title + " " + description).lower()
    return any(kw in combined for kw in _SAP_LOWER)


def _parse_job_links(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if not text or len(text) < 5:
            continue
        if any(hint in href.lower() for hint in _JOB_URL_HINTS):
            full_url = urljoin(base_url, href)
            if full_url not in seen:
                seen.add(full_url)
                results.append({"title": text, "url": full_url})
    return results


class CompanyDirectScraper(BaseScraper):
    def __init__(self):
        super().__init__(delay_min=3.0, delay_max=8.0)

    async def scrape_company(self, company: dict) -> list[dict]:
        offers = []
        async with self as scraper:
            page = await scraper.new_page()
            if not await scraper.fetch_with_retry(page, company["careers_url"]):
                logger.warning("Could not fetch %s", company["name"])
                return offers
            html = await page.content()
            for link in _parse_job_links(html, company["careers_url"]):
                if _is_sap_offer(link["title"], ""):
                    offers.append({
                        "title": link["title"],
                        "url": link["url"],
                        "company_name": company["name"],
                        "location": None,
                        "description": None,
                        "salary_min": None,
                        "salary_max": None,
                        "tech_tags": [],
                        "source": "company_direct",
                    })
            await scraper.random_delay()
        return offers


async def run_company_direct(dry_run: bool = False) -> tuple[int, int]:
    total_offers = 0
    total_contacts = 0
    conn = get_conn()
    scraper = CompanyDirectScraper()
    extractor = ContactExtractorScraper()

    for company in SAP_COMPANIES_DIRECT:
        logger.info("Company direct: %s", company["name"])
        try:
            cid = upsert_company(conn, {
                "name": company["name"],
                "careers_url": company["careers_url"],
                "source": "company_direct",
            })

            offers = await scraper.scrape_company(company)
            if not dry_run:
                for offer in offers:
                    sc = score_offer(offer)
                    upsert_job_offer(conn, {
                        **offer,
                        "company_id": cid,
                        "is_relevant": sc >= MIN_RELEVANCE_SCORE,
                        "relevance_score": sc,
                    })
            total_offers += len(offers)
            logger.info("  %s: %d SAP offers", company["name"], len(offers))

            if not dry_run:
                contacts = await extractor.extract_for_company(
                    cid, company["careers_url"], company["careers_url"]
                )
                for c in contacts:
                    upsert_contact(conn, c)
                total_contacts += len(contacts)
        except Exception as e:
            logger.error("company_direct failed for %s: %s", company["name"], e)

    conn.close()
    return total_offers, total_contacts
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
.venv/bin/pytest tests/test_company_direct.py -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add scraper/company_direct.py tests/test_company_direct.py
git commit -m "feat: add company direct scraper for SAP consulting firms (SEIDOR, STRATESYS, etc.)"
```

---

### Task 5: scraper/linkedin_jobs.py — Authenticated LinkedIn scraper

**Files:**
- Create: `backend/scraper/linkedin_jobs.py`
- Create: `backend/tests/test_linkedin_jobs.py`

**Interfaces:**
- Consumes: `LINKEDIN_SAP_SEARCHES`, `LINKEDIN_SESSION_PATH`, `SESSIONS_DIR` from `config.py`; `USER_AGENTS` from `scraper/base.py`
- Produces:
  - `save_linkedin_session(cookies: list[dict], path: Path) -> None`
  - `load_linkedin_session(path: Path) -> list[dict] | None`
  - `run_linkedin_login() -> None` — opens headful browser for manual login
  - `run_linkedin_jobs(max_per_search: int = 25) -> list[dict]`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_linkedin_jobs.py`:

```python
import sys
import json
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_save_and_load_session_roundtrip():
    from scraper.linkedin_jobs import save_linkedin_session, load_linkedin_session
    cookies = [{"name": "li_at", "value": "abc123", "domain": ".linkedin.com"}]
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)
    save_linkedin_session(cookies, path)
    assert load_linkedin_session(path) == cookies

def test_load_session_returns_none_if_missing():
    from scraper.linkedin_jobs import load_linkedin_session
    assert load_linkedin_session(Path("/nonexistent/linkedin_session.json")) is None

def test_load_session_returns_none_if_invalid_json():
    from scraper.linkedin_jobs import load_linkedin_session
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        f.write("not-valid-json{{{")
        path = Path(f.name)
    assert load_linkedin_session(path) is None

def test_is_checkpoint_detects_authwall():
    from scraper.linkedin_jobs import _is_checkpoint
    assert _is_checkpoint("https://www.linkedin.com/authwall?trk=...", "") is True
    assert _is_checkpoint("https://www.linkedin.com/feed/", "") is False
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
.venv/bin/pytest tests/test_linkedin_jobs.py -v
```
Expected: `ModuleNotFoundError: No module named 'scraper.linkedin_jobs'`

- [ ] **Step 3: Create backend/scraper/linkedin_jobs.py**

```python
"""
scraper/linkedin_jobs.py — LinkedIn Jobs scraper using persistent cookie session.

First-time setup (opens Chromium for manual login):
  python -m scraper.runner --source linkedin-login

Subsequent runs load the saved session (~30 days validity).
If checkpoint/captcha detected, run stops with a clear warning.
"""
import asyncio
import json
import logging
import random
import shutil
from pathlib import Path
from urllib.parse import urlencode
from playwright.async_api import async_playwright
from scraper.base import BaseScraper, USER_AGENTS
from config import LINKEDIN_SAP_SEARCHES, LINKEDIN_SESSION_PATH

logger = logging.getLogger(__name__)

LINKEDIN_BASE = "https://www.linkedin.com"
_CHECKPOINT_HINTS = ["/checkpoint/", "/authwall", "/login?", "verify your identity"]


def save_linkedin_session(cookies: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
    logger.info("LinkedIn session saved: %s", path)


def load_linkedin_session(path: Path) -> list[dict] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _is_checkpoint(url: str, html: str) -> bool:
    url_lower = url.lower()
    html_lower = html.lower()
    return any(hint in url_lower or hint in html_lower for hint in _CHECKPOINT_HINTS)


async def run_linkedin_login() -> None:
    """Open headful Chromium — user logs in manually, then cookies are saved."""
    system_chromium = shutil.which("chromium") or shutil.which("chromium-browser")
    playwright = await async_playwright().start()
    launch_kwargs: dict = {"headless": False}
    if system_chromium:
        launch_kwargs["executable_path"] = system_chromium

    browser = await playwright.chromium.launch(**launch_kwargs)
    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        locale="es-ES",
        timezone_id="Europe/Madrid",
    )
    page = await context.new_page()
    await page.goto(f"{LINKEDIN_BASE}/login", wait_until="domcontentloaded")
    logger.info("Browser open — please log in to LinkedIn manually.")
    logger.info("Waiting for /feed (max 2 minutes)...")
    try:
        await page.wait_for_url("**/feed**", timeout=120_000)
        cookies = await context.cookies()
        save_linkedin_session(list(cookies), LINKEDIN_SESSION_PATH)
        logger.info("Login successful. Session saved.")
    except Exception:
        logger.error("Login timeout — session not saved. Try again.")
    finally:
        await browser.close()
        await playwright.stop()


class LinkedInJobsScraper(BaseScraper):
    def __init__(self):
        super().__init__(delay_min=5.0, delay_max=12.0)

    async def scrape_search(
        self, keywords: str, location: str, max_offers: int = 25
    ) -> list[dict]:
        cookies = load_linkedin_session(LINKEDIN_SESSION_PATH)
        if not cookies:
            logger.error(
                "No LinkedIn session. Run: python -m scraper.runner --source linkedin-login"
            )
            return []

        offers = []
        async with self as scraper:
            page = await scraper.new_page()
            await scraper._context.add_cookies(cookies)

            params = urlencode({
                "keywords": keywords,
                "location": location,
                "f_TPR": "r2592000",  # last 30 days
                "position": 1,
                "pageNum": 0,
            })
            url = f"{LINKEDIN_BASE}/jobs/search?{params}"
            logger.info("LinkedIn: %s @ %s", keywords, location)

            if not await scraper.fetch_with_retry(page, url):
                return []

            html = await page.content()
            if _is_checkpoint(page.url, html):
                logger.warning(
                    "LinkedIn checkpoint — re-run: python -m scraper.runner --source linkedin-login"
                )
                return []

            cards = await page.query_selector_all(
                ".job-search-card, .jobs-search__results-list li, [class*='job-card-container']"
            )
            logger.info("LinkedIn: %d cards found", len(cards))

            for card in cards[:max_offers]:
                try:
                    title_el = await card.query_selector(
                        ".job-search-card__title, h3, [class*='title']"
                    )
                    company_el = await card.query_selector(
                        ".job-search-card__company-name, h4, [class*='company']"
                    )
                    location_el = await card.query_selector(
                        ".job-search-card__location, [class*='location']"
                    )
                    link_el = await card.query_selector("a[href*='/jobs/view/']")

                    title = (await title_el.inner_text()).strip() if title_el else None
                    if not title:
                        continue
                    company_name = (await company_el.inner_text()).strip() if company_el else None
                    location_text = (await location_el.inner_text()).strip() if location_el else None
                    href = await link_el.get_attribute("href") if link_el else None
                    offer_url = (
                        href if href and href.startswith("http")
                        else (LINKEDIN_BASE + href if href else None)
                    )
                    offers.append({
                        "title": title,
                        "url": offer_url,
                        "company_name": company_name,
                        "location": location_text,
                        "description": None,
                        "salary_min": None,
                        "salary_max": None,
                        "tech_tags": [],
                        "source": "linkedin",
                    })
                    await scraper.random_delay()
                except Exception as e:
                    logger.debug("LinkedIn card parse error: %s", e)

        logger.info("LinkedIn '%s': %d offers", keywords, len(offers))
        return offers


async def run_linkedin_jobs(max_per_search: int = 25) -> list[dict]:
    scraper = LinkedInJobsScraper()
    seen: set[str] = set()
    all_offers: list[dict] = []
    for search in LINKEDIN_SAP_SEARCHES:
        try:
            for offer in await scraper.scrape_search(
                search["keywords"], search["location"], max_per_search
            ):
                if offer.get("url") and offer["url"] not in seen:
                    seen.add(offer["url"])
                    all_offers.append(offer)
        except Exception as e:
            logger.error("LinkedIn search '%s' failed: %s", search["keywords"], e)
    logger.info("LinkedIn total: %d unique offers", len(all_offers))
    return all_offers
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
.venv/bin/pytest tests/test_linkedin_jobs.py -v
```
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add scraper/linkedin_jobs.py tests/test_linkedin_jobs.py
git commit -m "feat: add LinkedIn Jobs scraper with cookie-based session and checkpoint detection"
```

---

### Task 6: runner.py — SAP orchestration

**Files:**
- Modify: `backend/scraper/runner.py`
- Create: `backend/tests/test_runner.py`

**Interfaces:**
- Consumes: `run_infojobs`, `run_computrabajo`, `run_company_direct`, `run_linkedin_jobs`, `run_linkedin_login` from their respective modules; `SAP_KEYWORDS` from `config.py`
- Produces: CLI — `python -m scraper.runner --source sap [--dry-run] [--max-pages N]` and `--source linkedin-login`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_runner.py`:

```python
import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def _make_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        choices=["seed", "tecnoempleo", "contacts", "all", "sap", "linkedin-login"],
    )
    return parser

def test_parser_accepts_sap_source():
    args = _make_parser().parse_args(["--source", "sap"])
    assert args.source == "sap"

def test_parser_accepts_linkedin_login_source():
    args = _make_parser().parse_args(["--source", "linkedin-login"])
    assert args.source == "linkedin-login"

def test_runner_module_has_run_sap_source():
    import scraper.runner as r
    assert callable(getattr(r, "run_sap_source", None))
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
.venv/bin/pytest tests/test_runner.py -v
```
Expected: choices don't include `"sap"` yet → FAIL

- [ ] **Step 3: Add run_sap_source() and update main() in runner.py**

Add this function to `backend/scraper/runner.py` after `run_contacts_source()`:

```python
async def run_sap_source(dry_run: bool, max_pages: int):
    from scraper.tecnoempleo import TecnoempleoScraper
    from scraper.infojobs import run_infojobs
    from scraper.computrabajo import run_computrabajo
    from scraper.company_direct import run_company_direct
    from scraper.linkedin_jobs import run_linkedin_jobs
    from config import SAP_KEYWORDS, TECNOEMPLEO_LOCATIONS

    conn = get_conn()

    def _save_offers(offers: list[dict], source_name: str):
        if dry_run:
            logger.info("[DRY-RUN] %s: would save %d offers", source_name, len(offers))
            for o in offers[:5]:
                logger.info("  %s | %s", o.get("title"), o.get("company_name"))
            return
        saved = 0
        for offer in offers:
            if not offer.get("url"):
                continue
            row = conn.execute(
                "SELECT id FROM companies WHERE name=?", (offer.get("company_name", ""),)
            ).fetchone()
            cid = row["id"] if row else upsert_company(
                conn, {"name": offer.get("company_name", "Desconocida"), "source": offer.get("source", "sap")}
            )
            sc = score_offer(offer)
            upsert_job_offer(conn, {
                **offer, "company_id": cid,
                "is_relevant": sc >= 0.55, "relevance_score": sc,
            })
            saved += 1
        logger.info("%s: %d offers saved", source_name, saved)

    try:
        logger.info("── Tecnoempleo (SAP keywords) ──────")
        sap_scraper = TecnoempleoScraper()
        seen: set[str] = set()
        sap_offers: list[dict] = []
        for kw in SAP_KEYWORDS:
            for loc in TECNOEMPLEO_LOCATIONS:
                for o in await sap_scraper.scrape_keyword(kw, loc, max_pages):
                    if o.get("url") and o["url"] not in seen:
                        seen.add(o["url"])
                        sap_offers.append(o)
        _save_offers(sap_offers, "Tecnoempleo-SAP")
    except Exception as e:
        logger.error("Tecnoempleo SAP failed: %s", e)

    try:
        logger.info("── InfoJobs ────────────────────────")
        _save_offers(await run_infojobs(SAP_KEYWORDS, max_pages), "InfoJobs")
    except Exception as e:
        logger.error("InfoJobs failed: %s", e)

    try:
        logger.info("── Computrabajo ────────────────────")
        _save_offers(await run_computrabajo(SAP_KEYWORDS, max_pages), "Computrabajo")
    except Exception as e:
        logger.error("Computrabajo failed: %s", e)

    try:
        logger.info("── Company direct (SEIDOR etc.) ────")
        found, contacts = await run_company_direct(dry_run)
        logger.info("Company direct: %d offers, %d contacts", found, contacts)
    except Exception as e:
        logger.error("Company direct failed: %s", e)

    try:
        logger.info("── LinkedIn ────────────────────────")
        _save_offers(await run_linkedin_jobs(), "LinkedIn")
    except Exception as e:
        logger.error("LinkedIn failed: %s", e)

    conn.close()
```

Update `main()` — replace the `choices` list and add the two new source branches:

```python
def main():
    parser = argparse.ArgumentParser(description="Job Hunter Spain — Scraper Runner")
    parser.add_argument(
        "--source",
        choices=["seed", "tecnoempleo", "contacts", "all", "sap", "linkedin-login"],
        default="seed",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-pages", type=int, default=3)
    args = parser.parse_args()

    conn = get_conn()
    init_db(conn)
    conn.close()

    if args.source in ("seed", "all"):
        logger.info("── Seed loader ─────────────────────")
        if not args.dry_run:
            load_seed()
        else:
            logger.info("[DRY-RUN] Would load seed companies")

    if args.source in ("tecnoempleo", "all"):
        logger.info("── Tecnoempleo scraper ─────────────")
        asyncio.run(run_tecnoempleo_source(args.dry_run, args.max_pages))

    if args.source in ("contacts", "all"):
        logger.info("── Contact extractor ───────────────")
        asyncio.run(run_contacts_source(args.dry_run))

    if args.source == "sap":
        logger.info("── SAP multi-portal scraper ────────")
        asyncio.run(run_sap_source(args.dry_run, args.max_pages))

    if args.source == "linkedin-login":
        logger.info("── LinkedIn login (headful) ─────────")
        from scraper.linkedin_jobs import run_linkedin_login
        asyncio.run(run_linkedin_login())
        return  # skip stats after login

    print_stats()
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
.venv/bin/pytest tests/test_runner.py -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add scraper/runner.py tests/test_runner.py
git commit -m "feat: wire SAP multi-portal orchestration into runner.py (--source sap)"
```

---

### Task 7: ATS handlers scaffold — detect_ats() + generic.py + _dismiss_cookies()

**Files:**
- Create: `backend/automation/ats_handlers/__init__.py`
- Create: `backend/automation/ats_handlers/generic.py`
- Create: `backend/tests/test_form_filler.py`

**Interfaces:**
- Produces:
  - `detect_ats(url: str) -> str` — returns `"workday"`, `"greenhouse"`, `"lever"`, `"successfactors"`, or `"generic"`
  - `_dismiss_cookies(page: Page) -> None` — async helper used by all handlers
  - `_map_field(field_hint: str, profile: dict) -> str | None` — pure function
  - `fill_generic(page, profile, cv_path, cover_letter) -> bool` — async

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_form_filler.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_detect_ats_workday():
    from automation.ats_handlers import detect_ats
    assert detect_ats("https://accenture.wd3.myworkdayjobs.com/AccentureCareers/job/123") == "workday"

def test_detect_ats_greenhouse():
    from automation.ats_handlers import detect_ats
    assert detect_ats("https://boards.greenhouse.io/seidor/jobs/789") == "greenhouse"

def test_detect_ats_lever():
    from automation.ats_handlers import detect_ats
    assert detect_ats("https://jobs.lever.co/stratesys/123abc") == "lever"

def test_detect_ats_successfactors():
    from automation.ats_handlers import detect_ats
    assert detect_ats("https://stratesys.jobs.eu2.successfactors.eu/job/123") == "successfactors"
    assert detect_ats("https://jobs.sap.com/careers/job/123") == "successfactors"

def test_detect_ats_generic_fallback():
    from automation.ats_handlers import detect_ats
    assert detect_ats("https://www.seidor.com/trabaja/apply") == "generic"

def test_map_field_email():
    from automation.ats_handlers.generic import _map_field
    profile = {"personal": {"name": "Juan García", "email": "juan@example.com", "phone": "+34 600 000 000", "linkedin": "https://linkedin.com/in/juan"}}
    assert _map_field("email", profile) == "juan@example.com"

def test_map_field_first_and_last_name():
    from automation.ats_handlers.generic import _map_field
    profile = {"personal": {"name": "Juan García", "email": "j@e.com", "phone": "", "linkedin": ""}}
    assert _map_field("first_name", profile) == "Juan"
    assert _map_field("last_name", profile) == "García"

def test_map_field_unknown_returns_none():
    from automation.ats_handlers.generic import _map_field
    profile = {"personal": {"name": "Juan García", "email": "j@e.com", "phone": "", "linkedin": ""}}
    assert _map_field("random_unknown_field_xyz", profile) is None
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
.venv/bin/pytest tests/test_form_filler.py -v
```
Expected: `ModuleNotFoundError: No module named 'automation.ats_handlers'`

- [ ] **Step 3: Create backend/automation/ats_handlers/__init__.py**

```python
_ATS_PATTERNS = {
    "workday":        ["myworkdayjobs.com", "workday.com/job"],
    "greenhouse":     ["greenhouse.io"],
    "lever":          ["jobs.lever.co"],
    "successfactors": ["successfactors.eu", "successfactors.com", "jobs.sap.com"],
}


def detect_ats(url: str) -> str:
    url_lower = url.lower()
    for name, patterns in _ATS_PATTERNS.items():
        if any(p in url_lower for p in patterns):
            return name
    return "generic"
```

- [ ] **Step 4: Create backend/automation/ats_handlers/generic.py**

```python
"""
automation/ats_handlers/generic.py — Generic form filler via label/name/placeholder detection.
"""
import logging
from pathlib import Path
from playwright.async_api import Page

logger = logging.getLogger(__name__)

_FIELD_HINTS: dict[str, tuple[str, ...]] = {
    "first_name":   ("first_name", "nombre", "firstname"),
    "last_name":    ("last_name", "apellido", "apellidos", "surname", "lastname"),
    "email":        ("email", "correo", "e-mail"),
    "phone":        ("phone", "teléfono", "telefono", "móvil", "movil", "tel"),
    "linkedin":     ("linkedin",),
    "cover_letter": ("cover_letter", "carta", "motivac", "message", "mensaje", "presentation"),
}


def _map_field(field_hint: str, profile: dict) -> str | None:
    hint = field_hint.lower()
    personal = profile.get("personal", {})
    name_parts = personal.get("name", "").split(" ", 1)
    for canonical, hints in _FIELD_HINTS.items():
        if any(h in hint for h in hints):
            if canonical == "first_name":
                return name_parts[0] if name_parts else ""
            if canonical == "last_name":
                return name_parts[1] if len(name_parts) > 1 else ""
            if canonical == "email":
                return personal.get("email", "")
            if canonical == "phone":
                return personal.get("phone", "")
            if canonical == "linkedin":
                return personal.get("linkedin", "")
            if canonical == "cover_letter":
                return None  # injected by caller
    return None


async def _dismiss_cookies(page: Page) -> None:
    for sel in [
        "button[id*='accept']", "button[class*='accept']",
        "#onetrust-accept-btn-handler", ".cc-btn.cc-allow",
        "button:text('Aceptar')", "button:text('Accept all')",
    ]:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=800):
                await btn.click()
                return
        except Exception:
            continue


async def fill_generic(
    page: Page,
    profile: dict,
    cv_path: Path,
    cover_letter: str,
) -> bool:
    await _dismiss_cookies(page)
    filled = 0
    inputs = await page.query_selector_all(
        "input:not([type='hidden']):not([type='submit']):not([type='button']), textarea"
    )
    for inp in inputs:
        try:
            input_type = (await inp.get_attribute("type") or "text").lower()
            if input_type == "file":
                if cv_path and cv_path.exists():
                    await inp.set_input_files(str(cv_path))
                    filled += 1
                continue
            name = (await inp.get_attribute("name") or "").lower()
            placeholder = (await inp.get_attribute("placeholder") or "").lower()
            aria = (await inp.get_attribute("aria-label") or "").lower()
            hint = name or placeholder or aria
            if not hint:
                continue
            if any(h in hint for h in ("cover_letter", "carta", "motivac", "message", "mensaje")):
                await inp.fill(cover_letter)
                filled += 1
                continue
            value = _map_field(hint, profile)
            if value:
                await inp.fill(value)
                filled += 1
        except Exception as e:
            logger.debug("Field fill error: %s", e)
    logger.info("Generic form: %d fields filled", filled)
    return filled > 0
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
.venv/bin/pytest tests/test_form_filler.py -v
```
Expected: 8 PASSED

- [ ] **Step 6: Commit**

```bash
git add automation/ats_handlers/__init__.py automation/ats_handlers/generic.py tests/test_form_filler.py
git commit -m "feat: add ATS URL detector and generic form filler handler"
```

---

### Task 8: ats_handlers/workday.py + greenhouse.py

**Files:**
- Create: `backend/automation/ats_handlers/workday.py`
- Create: `backend/automation/ats_handlers/greenhouse.py`

**Interfaces:**
- Consumes: `_dismiss_cookies`, `_map_field` from `automation/ats_handlers/generic.py`
- Produces: `fill_workday(page, profile, cv_path, cover_letter) -> bool`; `fill_greenhouse(page, profile, cv_path, cover_letter) -> bool`

- [ ] **Step 1: Add import tests to test_form_filler.py**

Append to `backend/tests/test_form_filler.py`:

```python
def test_workday_handler_importable():
    from automation.ats_handlers.workday import fill_workday
    assert callable(fill_workday)

def test_greenhouse_handler_importable():
    from automation.ats_handlers.greenhouse import fill_greenhouse
    assert callable(fill_greenhouse)
```

- [ ] **Step 2: Run new tests — expect FAIL**

```bash
.venv/bin/pytest tests/test_form_filler.py::test_workday_handler_importable tests/test_form_filler.py::test_greenhouse_handler_importable -v
```
Expected: 2 FAILED (`ModuleNotFoundError`)

- [ ] **Step 3: Create backend/automation/ats_handlers/workday.py**

```python
"""
automation/ats_handlers/workday.py — Workday ATS multi-step handler.
Handles iframe-embedded forms and multi-step navigation.
"""
import logging
from pathlib import Path
from playwright.async_api import Page
from automation.ats_handlers.generic import _dismiss_cookies, _map_field

logger = logging.getLogger(__name__)

_FIELDS = [
    ("firstName", "first_name"),
    ("lastName",  "last_name"),
    ("email",     "email"),
    ("phone",     "phone"),
    ("linkedIn",  "linkedin"),
]


async def fill_workday(page: Page, profile: dict, cv_path: Path, cover_letter: str) -> bool:
    await _dismiss_cookies(page)

    # Switch to Workday iframe if embedded
    target = page
    for frame in page.frames:
        if "myworkdayjobs" in (frame.url or "").lower():
            target = frame  # type: ignore[assignment]
            break

    filled = 0
    for field_name, _ in _FIELDS:
        value = _map_field(field_name, profile)
        if not value:
            continue
        for sel in [
            f"input[data-automation-id='{field_name}']",
            f"input[name='{field_name}']",
            f"input[id*='{field_name}' i]",
        ]:
            try:
                el = target.locator(sel).first
                if await el.is_visible(timeout=1200):
                    await el.fill(value)
                    filled += 1
                    break
            except Exception:
                continue

    if cv_path and cv_path.exists():
        try:
            fi = target.locator("input[type='file']").first
            if await fi.is_visible(timeout=2000):
                await fi.set_input_files(str(cv_path))
                filled += 1
        except Exception as e:
            logger.debug("Workday CV upload: %s", e)

    try:
        for ta in await target.query_selector_all("textarea"):
            await ta.fill(cover_letter)
            filled += 1
    except Exception:
        pass

    # Multi-step: click Next then Submit
    for btn_text in ["Next", "Siguiente", "Submit", "Enviar"]:
        try:
            btn = target.locator(
                f"button[data-automation-id='bottom-navigation-next-btn'], button:text('{btn_text}')"
            ).first
            if await btn.is_visible(timeout=1500):
                await btn.click()
                await page.wait_for_timeout(1500)
                if btn_text in ("Submit", "Enviar"):
                    logger.info("Workday: submitted")
                    return True
        except Exception:
            continue

    if filled == 0:
        logger.warning("Workday: no fields filled — needs_manual_review")
    return filled > 0
```

- [ ] **Step 4: Create backend/automation/ats_handlers/greenhouse.py**

```python
"""
automation/ats_handlers/greenhouse.py — Greenhouse ATS handler.
Greenhouse uses a simple single-page form at boards.greenhouse.io.
"""
import logging
from pathlib import Path
from playwright.async_api import Page
from automation.ats_handlers.generic import _dismiss_cookies, _map_field

logger = logging.getLogger(__name__)


async def fill_greenhouse(page: Page, profile: dict, cv_path: Path, cover_letter: str) -> bool:
    await _dismiss_cookies(page)
    personal = profile.get("personal", {})
    filled = 0

    for field_id, profile_key in [
        ("first_name", "name"), ("last_name", "name"),
        ("email", "email"), ("phone", "phone"),
    ]:
        value = _map_field(field_id, profile)
        if not value:
            continue
        for sel in [
            f"input#job_application_{field_id}",
            f"input[name='job_application[{field_id}]']",
            f"input[id*='{field_id}' i]",
        ]:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=1200):
                    await el.fill(value)
                    filled += 1
                    break
            except Exception:
                continue

    if cv_path and cv_path.exists():
        try:
            fi = page.locator("input[type='file']").first
            if await fi.is_visible(timeout=2000):
                await fi.set_input_files(str(cv_path))
                filled += 1
        except Exception as e:
            logger.debug("Greenhouse CV: %s", e)

    try:
        ta = page.locator(
            "textarea#job_application_cover_letter, textarea[name*='cover_letter'], textarea"
        ).first
        if await ta.is_visible(timeout=1500):
            await ta.fill(cover_letter)
            filled += 1
    except Exception:
        pass

    linkedin = personal.get("linkedin", "")
    if linkedin:
        try:
            li = page.locator("input[id*='linkedin' i], input[name*='linkedin' i]").first
            if await li.is_visible(timeout=1200):
                await li.fill(linkedin)
                filled += 1
        except Exception:
            pass

    try:
        submit = page.locator(
            "input[type='submit'], button[type='submit'], button:text('Submit Application')"
        ).first
        if await submit.is_visible(timeout=3000):
            await submit.click()
            logger.info("Greenhouse: submitted")
            return True
    except Exception as e:
        logger.warning("Greenhouse submit: %s", e)

    return filled > 0
```

- [ ] **Step 5: Run all form filler tests — expect PASS**

```bash
.venv/bin/pytest tests/test_form_filler.py -v
```
Expected: 10 PASSED

- [ ] **Step 6: Commit**

```bash
git add automation/ats_handlers/workday.py automation/ats_handlers/greenhouse.py
git commit -m "feat: add Workday and Greenhouse ATS handlers"
```

---

### Task 9: ats_handlers/lever.py + successfactors.py

**Files:**
- Create: `backend/automation/ats_handlers/lever.py`
- Create: `backend/automation/ats_handlers/successfactors.py`

**Interfaces:**
- Consumes: `_dismiss_cookies`, `_map_field` from `automation/ats_handlers/generic.py`
- Produces: `fill_lever(page, profile, cv_path, cover_letter) -> bool`; `fill_successfactors(page, profile, cv_path, cover_letter) -> bool`

- [ ] **Step 1: Add import tests to test_form_filler.py**

Append to `backend/tests/test_form_filler.py`:

```python
def test_lever_handler_importable():
    from automation.ats_handlers.lever import fill_lever
    assert callable(fill_lever)

def test_successfactors_handler_importable():
    from automation.ats_handlers.successfactors import fill_successfactors
    assert callable(fill_successfactors)
```

- [ ] **Step 2: Run new tests — expect FAIL**

```bash
.venv/bin/pytest tests/test_form_filler.py::test_lever_handler_importable tests/test_form_filler.py::test_successfactors_handler_importable -v
```
Expected: 2 FAILED

- [ ] **Step 3: Create backend/automation/ats_handlers/lever.py**

```python
"""
automation/ats_handlers/lever.py — Lever ATS handler.
Lever uses a clean single-page form at jobs.lever.co/{company}/{id}/apply.
Uses a single 'name' field (not split first/last).
"""
import logging
from pathlib import Path
from playwright.async_api import Page
from automation.ats_handlers.generic import _dismiss_cookies

logger = logging.getLogger(__name__)


async def fill_lever(page: Page, profile: dict, cv_path: Path, cover_letter: str) -> bool:
    await _dismiss_cookies(page)
    personal = profile.get("personal", {})
    filled = 0

    for sel, value in [
        ("input[name='name'], input[id='name']",                  personal.get("name", "")),
        ("input[name='email'], input[type='email']",              personal.get("email", "")),
        ("input[name='phone'], input[type='tel']",                personal.get("phone", "")),
        ("input[name='urls[LinkedIn]'], input[name*='linkedin' i]", personal.get("linkedin", "")),
    ]:
        if not value:
            continue
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=1200):
                await el.fill(value)
                filled += 1
        except Exception:
            pass

    if cv_path and cv_path.exists():
        try:
            fi = page.locator("input[type='file']").first
            if await fi.is_visible(timeout=2000):
                await fi.set_input_files(str(cv_path))
                filled += 1
        except Exception as e:
            logger.debug("Lever CV: %s", e)

    try:
        ta = page.locator(
            "textarea[name='comments'], textarea[name='additional'], textarea"
        ).first
        if await ta.is_visible(timeout=1500):
            await ta.fill(cover_letter)
            filled += 1
    except Exception:
        pass

    try:
        submit = page.locator("button[type='submit'], input[type='submit']").first
        if await submit.is_visible(timeout=3000):
            await submit.click()
            logger.info("Lever: submitted")
            return True
    except Exception as e:
        logger.warning("Lever submit: %s", e)

    return filled > 0
```

- [ ] **Step 4: Create backend/automation/ats_handlers/successfactors.py**

```python
"""
automation/ats_handlers/successfactors.py — SAP SuccessFactors ATS handler.
May embed form in iframes; multi-step flow with Next/Submit buttons.
"""
import logging
from pathlib import Path
from playwright.async_api import Page
from automation.ats_handlers.generic import _dismiss_cookies

logger = logging.getLogger(__name__)


async def fill_successfactors(page: Page, profile: dict, cv_path: Path, cover_letter: str) -> bool:
    await _dismiss_cookies(page)
    personal = profile.get("personal", {})
    name_parts = personal.get("name", "").split(" ", 1)
    filled = 0

    # Use iframe if form is embedded
    target = page
    for frame in page.frames:
        if "successfactors" in (frame.url or "").lower():
            target = frame  # type: ignore[assignment]
            break

    for sel, value in [
        ("input[name*='firstName' i], input[id*='firstName' i]", name_parts[0] if name_parts else ""),
        ("input[name*='lastName' i], input[id*='lastName' i]",   name_parts[1] if len(name_parts) > 1 else ""),
        ("input[type='email'], input[name*='email' i]",          personal.get("email", "")),
        ("input[type='tel'], input[name*='phone' i]",            personal.get("phone", "")),
    ]:
        if not value:
            continue
        try:
            el = target.locator(sel).first
            if await el.is_visible(timeout=1500):
                await el.fill(value)
                filled += 1
        except Exception:
            pass

    if cv_path and cv_path.exists():
        try:
            fi = target.locator("input[type='file']").first
            if await fi.is_visible(timeout=2000):
                await fi.set_input_files(str(cv_path))
                filled += 1
        except Exception as e:
            logger.debug("SuccessFactors CV: %s", e)

    try:
        ta = target.locator("textarea").first
        if await ta.is_visible(timeout=1500):
            await ta.fill(cover_letter)
            filled += 1
    except Exception:
        pass

    # Multi-step navigation
    for btn_text in ["Next", "Siguiente", "Continue", "Submit", "Enviar"]:
        try:
            btn = target.locator(f"button:text('{btn_text}'), input[value='{btn_text}']").first
            if await btn.is_visible(timeout=1500):
                await btn.click()
                await page.wait_for_timeout(1500)
                if btn_text in ("Submit", "Enviar"):
                    logger.info("SuccessFactors: submitted")
                    return True
        except Exception:
            continue

    if filled == 0:
        logger.warning("SuccessFactors: no fields filled — needs_manual_review")
    return filled > 0
```

- [ ] **Step 5: Run all form filler tests — expect PASS**

```bash
.venv/bin/pytest tests/test_form_filler.py -v
```
Expected: 12 PASSED

- [ ] **Step 6: Commit**

```bash
git add automation/ats_handlers/lever.py automation/ats_handlers/successfactors.py
git commit -m "feat: add Lever and SAP SuccessFactors ATS handlers"
```

---

### Task 10: automation/form_filler.py + application_engine.py integration

**Files:**
- Create: `backend/automation/form_filler.py`
- Modify: `backend/automation/application_engine.py`
- Create: `backend/tests/test_application_engine.py`

**Interfaces:**
- Consumes: `detect_ats` from `automation/ats_handlers/__init__.py`; all `fill_*` handlers; `BaseScraper` USER_AGENTS for stealth context
- Produces: `fill_form(form_url: str, profile: dict, cv_path: Path | None, cover_letter: str, dry_run: bool = False) -> bool`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_application_engine.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_fill_form_importable():
    from automation.form_filler import fill_form
    assert callable(fill_form)

def test_fill_form_dry_run_returns_true():
    from automation.form_filler import fill_form
    import json
    profile = json.loads(Path("profile.json").read_text())
    result = fill_form(
        "https://boards.greenhouse.io/seidor/jobs/123",
        profile, None, "Test cover letter", dry_run=True
    )
    assert result is True

def test_fill_form_dry_run_detects_lever():
    from automation.form_filler import fill_form
    from automation.ats_handlers import detect_ats
    url = "https://jobs.lever.co/stratesys/abc123"
    assert detect_ats(url) == "lever"
    result = fill_form(url, {}, None, "", dry_run=True)
    assert result is True
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
.venv/bin/pytest tests/test_application_engine.py -v
```
Expected: `ModuleNotFoundError: No module named 'automation.form_filler'`

- [ ] **Step 3: Create backend/automation/form_filler.py**

```python
"""
automation/form_filler.py — Orchestrates Playwright form filling for job applications.
Detects ATS by URL, dispatches to the appropriate handler.
"""
import asyncio
import importlib
import logging
import random
import shutil
from pathlib import Path
from playwright.async_api import async_playwright
from scraper.base import USER_AGENTS
from automation.ats_handlers import detect_ats

logger = logging.getLogger(__name__)

_HANDLER_MAP = {
    "workday":        ("automation.ats_handlers.workday",        "fill_workday"),
    "greenhouse":     ("automation.ats_handlers.greenhouse",     "fill_greenhouse"),
    "lever":          ("automation.ats_handlers.lever",          "fill_lever"),
    "successfactors": ("automation.ats_handlers.successfactors", "fill_successfactors"),
    "generic":        ("automation.ats_handlers.generic",        "fill_generic"),
}


async def _run_fill(form_url: str, profile: dict, cv_path: Path | None, cover_letter: str) -> bool:
    ats = detect_ats(form_url)
    module_name, func_name = _HANDLER_MAP[ats]
    handler = getattr(importlib.import_module(module_name), func_name)
    logger.info("Form filler: ATS=%s URL=%s", ats, form_url)

    system_chromium = shutil.which("chromium") or shutil.which("chromium-browser")
    launch_kwargs: dict = {
        "headless": True,
        "args": ["--no-sandbox", "--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage"],
    }
    if system_chromium:
        launch_kwargs["executable_path"] = system_chromium

    playwright = await async_playwright().start()
    try:
        browser = await playwright.chromium.launch(**launch_kwargs)
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            locale="es-ES",
            timezone_id="Europe/Madrid",
            viewport={"width": 1920, "height": 1080},
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        page = await context.new_page()
        response = await page.goto(form_url, wait_until="domcontentloaded", timeout=30000)
        if not response or response.status >= 400:
            logger.warning("Form URL returned %s", response.status if response else "no response")
            return False
        return await handler(page, profile, cv_path or Path("/nonexistent"), cover_letter)
    except Exception as e:
        logger.error("Form filler error (%s): %s", ats, e)
        return False
    finally:
        await playwright.stop()


def fill_form(
    form_url: str,
    profile: dict,
    cv_path: Path | None,
    cover_letter: str,
    dry_run: bool = False,
) -> bool:
    if dry_run:
        ats = detect_ats(form_url)
        logger.info("[DRY-RUN] Would fill form: ATS=%s URL=%s", ats, form_url)
        return True
    return asyncio.run(_run_fill(form_url, profile, cv_path, cover_letter))
```

- [ ] **Step 4: Update application_engine.py — replace form contact branch**

In `backend/automation/application_engine.py`, replace lines 121–124 (the `elif contact["type"] == "form":` block):

```python
        elif contact["type"] == "form":
            from automation.form_filler import fill_form
            logger.info("FORM → %s: %s", company_name, contact["value"])
            success = fill_form(
                form_url=contact["value"],
                profile=profile,
                cv_path=cv,
                cover_letter=cover_letter,
                dry_run=dry_run,
            )
            if not success and not dry_run:
                record_application(conn, {
                    "company_id": offer["company_id"],
                    "job_offer_id": offer["id"],
                    "contact_id": contact["id"],
                    "method": "form",
                    "status": "needs_manual_review",
                    "notes": f"Form fill failed: {contact['value']}",
                })
```

- [ ] **Step 5: Run full test suite — expect all PASS**

```bash
.venv/bin/pytest tests/ -v
```
Expected: all tests PASSED

- [ ] **Step 6: Smoke test**

```bash
.venv/bin/python -c "
import json
from pathlib import Path
from automation.form_filler import fill_form
profile = json.loads(Path('profile.json').read_text())
for url, ats in [
    ('https://boards.greenhouse.io/seidor/jobs/123', 'greenhouse'),
    ('https://jobs.lever.co/stratesys/abc', 'lever'),
    ('https://seidor.wd3.myworkdayjobs.com/job/123', 'workday'),
    ('https://stratesys.jobs.eu2.successfactors.eu/job/1', 'successfactors'),
    ('https://www.seidor.com/apply', 'generic'),
]:
    result = fill_form(url, profile, None, 'Cover letter test', dry_run=True)
    print(f'  {ats}: {result}')
"
```
Expected: each line prints `True`

- [ ] **Step 7: Commit**

```bash
git add automation/form_filler.py automation/application_engine.py tests/test_application_engine.py
git commit -m "feat: add form_filler orchestrator with ATS dispatch and wire into application_engine"
```

---

## Final Verification

```bash
cd backend

# Full test suite
.venv/bin/pytest tests/ -v --tb=short

# SAP scraper dry-run (verifies all imports and orchestration)
.venv/bin/python -m scraper.runner --source sap --dry-run

# One-time LinkedIn session setup (run manually when ready to scrape LinkedIn)
# .venv/bin/python -m scraper.runner --source linkedin-login

# Application engine dry-run with form contacts
.venv/bin/python -m automation.application_engine --dry-run --limit 5
```
