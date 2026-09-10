# Job Search Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `job_search.py` (`scrape` + `rank` subcommands) plus an `apply` playbook that together discover Fall 2026 Data Analyst/Data Science/BI intern postings near Dallas, TX or remote, score them against the existing resume profile, and drive a bulk (never-auto-submit) application pipeline reusing the repo's existing resume/cover-letter/PDF machinery.

**Architecture:** A small `job_search/` Python package (stdlib only — `urllib`, `json`, `re`, `csv`, `math`, `dataclasses`, `argparse`) with one module per concern (postings, geocoding, tracker persistence, source scrapers, fit scoring, markdown I/O), wired together by a thin `job_search.py` CLI for `scrape`/`rank`. `apply` is not a pure script — it requires LLM drafting (resume/cover-letter text) and live browser control (Playwright MCP), so it's documented as an orchestration playbook (`docs/playbooks/apply-playbook.md`) that Claude follows step-by-step, calling the tested Python modules and the repo's existing `md_to_pdf.py` for the mechanical parts.

**Tech Stack:** Python 3.14 stdlib, `pytest` (already installed), Chrome headless + `markdown` pip package (already used by `md_to_pdf.py`, no new dependency), Playwright MCP tools (already available in this Claude Code session, no install).

## Global Constraints

- No LinkedIn login / stored credentials anywhere — every source fetch is unauthenticated.
- `apply` never auto-submits an application under any code path — every posting stops at the browser review screen.
- Fit-score cutoff for bulk apply: exactly 30% (`>= 0.30`), not approximate.
- Location filter: within 20 miles of `<HOME_ADDRESS>`, OR the posting is remote. Everything else excluded.
- Resume and cover letter: hard 1-page limit each, verified via `grep -a -o "/Count [0-9]*" resumes/<company>.pdf` reading `/Count 1` (existing rule from `RESUME_FORMAT.md`).
- `scrape` fully overwrites `fall_2026_internships.md` each run; `job_search_tracker.csv` is never overwritten by `scrape` — it's the persistent applied/skipped record.
- Manually triggered only — no cron/scheduling anywhere in this plan.
- Reuse `md_to_pdf.py` for cover letters too (it's a generic markdown-to-PDF converter, confirmed by reading it — no new PDF script).

## Source research (verified 2026-07-08, live)

Before writing scraper code, each source was hit live via `curl` to confirm real, current structure rather than guessing:

- **LinkedIn**: `https://www.linkedin.com/jobs-guest/jobs/api/seekMoreJobPostings/search` (the commonly-documented "guest API") returned `404` in live testing. The plain public `https://www.linkedin.com/jobs/search?keywords=...&location=...` page works (`200`), returns 60 real job cards server-rendered in the HTML, using classes `base-search-card__title`, `base-search-card__subtitle`, `job-search-card__location`, `base-card__full-link`. **Use this URL, not the guest API.**
- **Indeed**: `https://www.indeed.com/jobs?q=...&l=...` returns `200` with real results embedded as a JSON blob: `window.mosaic.providerData["mosaic-provider-jobcards"]={...}`. Parse via balanced-brace extraction, walk to `metaData.mosaicProviderJobCardsModel.results`, fields `displayTitle`, `company`, `formattedLocation`, `jobkey` (URL = `https://www.indeed.com/viewjob?jk=<jobkey>`).
- **Glassdoor**: needs a two-step fetch. Step 1: `https://www.glassdoor.com/autocomplete/location?term=<location>&locationTypeFilters=CITY` (JSON, returns `locationId`). Step 2: `https://www.glassdoor.com/Job/jobs.htm?sc.keyword=<kw>&locT=C&locId=<id>` (HTML, real results, classes `JobCard_jobTitle__<hash>`, `EmployerProfile_compactEmployerName__<hash>`, `JobCard_location__<hash>` — the hash suffix is a CSS-module build hash, so parsers match on the stable prefix before `__`, not the full class).
- **ZipRecruiter**: `https://www.ziprecruiter.com/jobs-search?search=...&location=...` returned `403` with a Cloudflare "Just a moment..." JS challenge page. Confirmed genuinely blocked, not a fluke. Implemented as a source that detects this exact case and degrades to an empty list — no attempt to bypass Cloudflare (out of scope, borderline ToS territory).
- **Nominatim** (`https://nominatim.openstreetmap.org/search`) geocodes `<HOME_ADDRESS>` successfully to `(33.0074446, -96.7974326)`. Usage policy requires a descriptive `User-Agent` and max 1 request/second — implemented with a 1-second sleep after each real call and an in-process cache so repeat lookups (e.g. "Remote" appearing on many postings, or the home address itself) never re-hit the network.

---

### Task 1: Posting model + dedupe

**Files:**
- Create: `job_search/__init__.py`
- Create: `job_search/posting.py`
- Test: `tests/test_posting.py`

**Interfaces:**
- Produces: `Posting` dataclass (`title: str, company: str, location: str, url: str, source: str, fetched_date: str, fit_score: float | None = None, rationale: str | None = None`), `today_iso() -> str`, `dedupe_postings(postings: list[Posting]) -> list[Posting]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_posting.py
from job_search.posting import Posting, dedupe_postings


def _p(title="Data Analyst Intern", company="Acme Corp", location="Dallas, TX",
       url="https://example.com/1", source="linkedin", fetched="2026-07-08"):
    return Posting(title=title, company=company, location=location, url=url,
                    source=source, fetched_date=fetched)


def test_dedupe_removes_case_insensitive_duplicate_across_sources():
    a = _p(source="linkedin", url="https://linkedin.com/jobs/view/1")
    b = _p(source="indeed", url="https://indeed.com/viewjob?jk=2",
           title="DATA ANALYST INTERN", company="acme corp", location="dallas, tx")
    result = dedupe_postings([a, b])
    assert len(result) == 1
    assert result[0] is a


def test_dedupe_keeps_distinct_postings():
    a = _p(title="Data Analyst Intern", company="Acme Corp")
    b = _p(title="BI Intern", company="Widgets Inc")
    result = dedupe_postings([a, b])
    assert len(result) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_posting.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'job_search'`

- [ ] **Step 3: Write minimal implementation**

```python
# job_search/__init__.py
```

```python
# job_search/posting.py
import datetime
from dataclasses import dataclass


@dataclass
class Posting:
    title: str
    company: str
    location: str
    url: str
    source: str
    fetched_date: str
    fit_score: float | None = None
    rationale: str | None = None


def today_iso() -> str:
    return datetime.date.today().isoformat()


def _dedupe_key(p: Posting) -> tuple[str, str, str]:
    return (p.title.strip().lower(), p.company.strip().lower(), p.location.strip().lower())


def dedupe_postings(postings: list[Posting]) -> list[Posting]:
    seen: dict[tuple[str, str, str], Posting] = {}
    for p in postings:
        key = _dedupe_key(p)
        if key not in seen:
            seen[key] = p
    return list(seen.values())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_posting.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add job_search/__init__.py job_search/posting.py tests/test_posting.py
git commit -m "feat: add Posting model and cross-source dedupe"
```

---

### Task 2: Geocoding + 20-mile radius filter

**Files:**
- Create: `job_search/geocode.py`
- Test: `tests/test_geocode.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `HOME_ADDRESS: str`, `RADIUS_MILES: float`, `geocode(address: str, fetch=None) -> tuple[float, float] | None`, `haversine_miles(a: tuple[float, float], b: tuple[float, float]) -> float`, `is_within_range(location: str, fetch=None) -> bool`. `fetch` is an injectable `Callable[[str], str]` for testability; real callers omit it and get the real Nominatim HTTP call.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_geocode.py
import math
from job_search import geocode as geo


def test_haversine_known_distance():
    # 1 degree of longitude at the equator is ~69.17 miles
    dist = geo.haversine_miles((0.0, 0.0), (0.0, 1.0))
    assert math.isclose(dist, 69.17, rel_tol=0.01)


def test_geocode_parses_nominatim_response():
    geo._geocode_cache.clear()
    canned = '[{"lat":"33.0074446","lon":"-96.7974326"}]'
    result = geo.geocode("<HOME_ADDRESS>", fetch=lambda url: canned)
    assert result == (33.0074446, -96.7974326)


def test_geocode_returns_none_on_empty_results():
    geo._geocode_cache.clear()
    result = geo.geocode("nowhere real", fetch=lambda url: "[]")
    assert result is None


def test_is_within_range_true_for_remote_without_any_fetch():
    def boom(url):
        raise AssertionError("remote postings must never geocode")
    assert geo.is_within_range("Remote", fetch=boom) is True


def test_is_within_range_true_when_close():
    geo._geocode_cache.clear()
    home_json = '[{"lat":"33.0","lon":"-96.8"}]'
    near_json = '[{"lat":"33.05","lon":"-96.8"}]'  # ~3.5 miles north
    calls = {"n": 0}

    def fake_fetch(url):
        calls["n"] += 1
        return home_json if calls["n"] == 1 else near_json

    assert geo.is_within_range("Plano, TX", fetch=fake_fetch) is True


def test_is_within_range_false_when_far():
    geo._geocode_cache.clear()
    home_json = '[{"lat":"33.0","lon":"-96.8"}]'
    far_json = '[{"lat":"37.77","lon":"-122.42"}]'  # San Francisco, ~1500 miles
    calls = {"n": 0}

    def fake_fetch(url):
        calls["n"] += 1
        return home_json if calls["n"] == 1 else far_json

    assert geo.is_within_range("San Francisco, CA", fetch=fake_fetch) is False


def test_is_within_range_false_when_geocode_fails():
    geo._geocode_cache.clear()
    assert geo.is_within_range("Gibberish Place Name", fetch=lambda url: "[]") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_geocode.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'job_search.geocode'`

- [ ] **Step 3: Write minimal implementation**

```python
# job_search/geocode.py
import json
import math
import time
import urllib.parse
import urllib.request

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "job-search-script/1.0 (personal use, <EMAIL>)"
HOME_ADDRESS = "<HOME_ADDRESS>"
RADIUS_MILES = 20.0

_geocode_cache: dict[str, tuple[float, float] | None] = {}


def _http_fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8")
    time.sleep(1)  # Nominatim usage policy: max 1 request/second
    return body


def geocode(address: str, fetch=None) -> tuple[float, float] | None:
    if address in _geocode_cache:
        return _geocode_cache[address]
    fetch = fetch or _http_fetch
    params = urllib.parse.urlencode({"q": address, "format": "json", "limit": 1})
    try:
        body = fetch(f"{NOMINATIM_URL}?{params}")
        results = json.loads(body)
    except Exception:
        _geocode_cache[address] = None
        return None
    if not results:
        _geocode_cache[address] = None
        return None
    coord = (float(results[0]["lat"]), float(results[0]["lon"]))
    _geocode_cache[address] = coord
    return coord


def haversine_miles(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    earth_radius_miles = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * earth_radius_miles * math.asin(math.sqrt(h))


def is_within_range(location: str, fetch=None) -> bool:
    if "remote" in location.lower():
        return True
    home = geocode(HOME_ADDRESS, fetch=fetch)
    target = geocode(location, fetch=fetch)
    if home is None or target is None:
        return False
    return haversine_miles(home, target) <= RADIUS_MILES
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_geocode.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add job_search/geocode.py tests/test_geocode.py
git commit -m "feat: add geocoding and 20-mile radius filter"
```

---

### Task 3: Tracker CSV persistence

**Files:**
- Create: `job_search/tracker.py`
- Test: `tests/test_tracker.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `TrackerRow` dataclass (`company: str, title: str, url: str, status: str, fit_score: str, date: str`), `read_tracker(path) -> dict[str, TrackerRow]` (keyed by `url`), `write_tracker(path, rows: dict[str, TrackerRow]) -> None`, `upsert(rows: dict[str, TrackerRow], row: TrackerRow) -> dict[str, TrackerRow]`, `is_handled(rows: dict[str, TrackerRow], url: str) -> bool` (True for `status in ("applied", "skipped")`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tracker.py
from job_search.tracker import TrackerRow, read_tracker, write_tracker, upsert, is_handled


def test_write_then_read_round_trips(tmp_path):
    path = tmp_path / "tracker.csv"
    rows = {}
    rows = upsert(rows, TrackerRow(company="Acme", title="Data Analyst Intern",
                                    url="https://example.com/1", status="pending-review",
                                    fit_score="0.55", date="2026-07-08"))
    write_tracker(path, rows)
    loaded = read_tracker(path)
    assert loaded["https://example.com/1"].company == "Acme"
    assert loaded["https://example.com/1"].status == "pending-review"


def test_read_missing_file_returns_empty_dict(tmp_path):
    assert read_tracker(tmp_path / "does_not_exist.csv") == {}


def test_upsert_overwrites_same_url():
    rows = {}
    rows = upsert(rows, TrackerRow(company="Acme", title="X", url="https://example.com/1",
                                    status="pending", fit_score="0.4", date="2026-07-08"))
    rows = upsert(rows, TrackerRow(company="Acme", title="X", url="https://example.com/1",
                                    status="applied", fit_score="0.4", date="2026-07-09"))
    assert len(rows) == 1
    assert rows["https://example.com/1"].status == "applied"


def test_is_handled():
    rows = {}
    rows = upsert(rows, TrackerRow(company="A", title="T", url="u1", status="applied",
                                    fit_score="0.5", date="2026-07-08"))
    rows = upsert(rows, TrackerRow(company="A", title="T", url="u2", status="needs-manual",
                                    fit_score="0.5", date="2026-07-08"))
    assert is_handled(rows, "u1") is True
    assert is_handled(rows, "u2") is False
    assert is_handled(rows, "unknown-url") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tracker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'job_search.tracker'`

- [ ] **Step 3: Write minimal implementation**

```python
# job_search/tracker.py
import csv
import pathlib
from dataclasses import asdict, dataclass

TRACKER_FIELDS = ["company", "title", "url", "status", "fit_score", "date"]


@dataclass
class TrackerRow:
    company: str
    title: str
    url: str
    status: str  # pending | pending-review | applied | skipped | needs-manual
    fit_score: str
    date: str


def read_tracker(path) -> dict[str, TrackerRow]:
    path = pathlib.Path(path)
    if not path.exists():
        return {}
    rows: dict[str, TrackerRow] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for raw in csv.DictReader(f):
            row = TrackerRow(**{k: raw[k] for k in TRACKER_FIELDS})
            rows[row.url] = row
    return rows


def write_tracker(path, rows: dict[str, TrackerRow]) -> None:
    path = pathlib.Path(path)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRACKER_FIELDS)
        writer.writeheader()
        for row in rows.values():
            writer.writerow(asdict(row))


def upsert(rows: dict[str, TrackerRow], row: TrackerRow) -> dict[str, TrackerRow]:
    rows[row.url] = row
    return rows


def is_handled(rows: dict[str, TrackerRow], url: str) -> bool:
    row = rows.get(url)
    return row is not None and row.status in ("applied", "skipped")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tracker.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add job_search/tracker.py tests/test_tracker.py
git commit -m "feat: add job_search_tracker.csv read/write/upsert"
```

---

### Task 4: LinkedIn + Indeed source scrapers

**Files:**
- Create: `job_search/sources.py`
- Test: `tests/test_sources_linkedin_indeed.py`

**Interfaces:**
- Consumes: `Posting`, `today_iso` from `job_search.posting` (Task 1).
- Produces: `USER_AGENT: str`, `fetch_linkedin(keywords: str, location: str, fetch=None) -> list[Posting]`, `fetch_indeed(keywords: str, location: str, fetch=None) -> list[Posting]`, `fetch_posting_text(url: str, fetch=None) -> str` (generic tag-strip, used later by `rank`). `fetch` is an injectable `Callable[[str], str]`; omitted means real HTTP GET with `USER_AGENT`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sources_linkedin_indeed.py
from job_search.sources import fetch_linkedin, fetch_indeed, fetch_posting_text

LINKEDIN_FIXTURE = """
<div class="base-card" data-entity-urn="urn:li:jobPosting:1">
  <a class="base-card__full-link absolute top-0 right-0 bottom-0 left-0 p-0 z-[2] outline-offset-[4px]" href="https://www.linkedin.com/jobs/view/data-analyst-intern-at-acme-4437848829?position=1&pageNum=0">
  </a>
  <h3 class="base-search-card__title">
      Data Analyst Intern
  </h3>
  <h4 class="base-search-card__subtitle">
    <a class="hidden-nested-link">
            Acme Corp
          </a>
  </h4>
  <span class="job-search-card__location">
          Dallas, TX
          </span>
</div>
<div class="base-card" data-entity-urn="urn:li:jobPosting:2">
  <a class="base-card__full-link absolute top-0 right-0 bottom-0 left-0 p-0 z-[2] outline-offset-[4px]" href="https://www.linkedin.com/jobs/view/bi-intern-at-widgets-4437848830?position=2&pageNum=0">
  </a>
  <h3 class="base-search-card__title">
      BI Intern
  </h3>
  <h4 class="base-search-card__subtitle">
    <a class="hidden-nested-link">
            Widgets Inc
          </a>
  </h4>
  <span class="job-search-card__location">
          Remote
          </span>
</div>
"""

INDEED_FIXTURE = """<!doctype html><html><head><title>Data Analyst Intern Jobs, Employment in Dallas, TX | Indeed</title></head>
<body>
<script>
window.mosaic.providerData["mosaic-provider-jobcards"]={"metaData":{"mosaicProviderJobCardsModel":{"results":[{"displayTitle":"Data Analyst Intern","company":"Acme Corp","formattedLocation":"Dallas, TX","jobkey":"abc123"},{"displayTitle":"BI Intern","company":"Widgets Inc","formattedLocation":"Remote","jobkey":"def456"}]}}};
</script>
</body></html>"""


def test_fetch_linkedin_parses_fixture():
    postings = fetch_linkedin("Data Analyst Intern", "Dallas, TX", fetch=lambda url: LINKEDIN_FIXTURE)
    assert len(postings) == 2
    assert postings[0].title == "Data Analyst Intern"
    assert postings[0].company == "Acme Corp"
    assert postings[0].location == "Dallas, TX"
    assert postings[0].url == "https://www.linkedin.com/jobs/view/data-analyst-intern-at-acme-4437848829"
    assert postings[0].source == "linkedin"
    assert postings[1].location == "Remote"


def test_fetch_linkedin_returns_empty_on_fetch_failure():
    def boom(url):
        raise TimeoutError("blocked")
    assert fetch_linkedin("x", "y", fetch=boom) == []


def test_fetch_indeed_parses_fixture():
    postings = fetch_indeed("Data Analyst Intern", "Dallas, TX", fetch=lambda url: INDEED_FIXTURE)
    assert len(postings) == 2
    assert postings[0].title == "Data Analyst Intern"
    assert postings[0].company == "Acme Corp"
    assert postings[0].url == "https://www.indeed.com/viewjob?jk=abc123"
    assert postings[0].source == "indeed"
    assert postings[1].company == "Widgets Inc"


def test_fetch_indeed_returns_empty_when_marker_missing():
    assert fetch_indeed("x", "y", fetch=lambda url: "<html>no data here</html>") == []


def test_fetch_posting_text_strips_tags():
    html = "<html><body><h1>Data Analyst Intern</h1><p>Requires SQL and Python.</p></body></html>"
    text = fetch_posting_text("https://example.com/job/1", fetch=lambda url: html)
    assert "Data Analyst Intern" in text
    assert "Requires SQL and Python." in text
    assert "<h1>" not in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sources_linkedin_indeed.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'job_search.sources'`

- [ ] **Step 3: Write minimal implementation**

```python
# job_search/sources.py
import json
import re
import urllib.parse
import urllib.request

from job_search.posting import Posting, today_iso

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def _http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _extract_json_object(text: str, start: int) -> str | None:
    depth = 0
    for j in range(start, len(text)):
        c = text[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:j + 1]
    return None


def fetch_linkedin(keywords: str, location: str, fetch=None) -> list[Posting]:
    fetch = fetch or _http_get
    url = "https://www.linkedin.com/jobs/search?" + urllib.parse.urlencode(
        {"keywords": keywords, "location": location}
    )
    try:
        html = fetch(url)
    except Exception:
        return []
    titles = re.findall(r'base-search-card__title">\s*([^<]+?)\s*<', html)
    companies = re.findall(r'base-search-card__subtitle">\s*<a[^>]*>\s*([^<]+?)\s*<', html)
    locations = re.findall(r'job-search-card__location">\s*([^<]+?)\s*<', html)
    urls = re.findall(r'class="base-card__full-link[^"]*"\s+href="([^"?]+)', html)
    n = min(len(titles), len(companies), len(locations), len(urls))
    return [
        Posting(title=titles[i].strip(), company=companies[i].strip(),
                location=locations[i].strip(), url=urls[i].strip(),
                source="linkedin", fetched_date=today_iso())
        for i in range(n)
    ]


def fetch_indeed(keywords: str, location: str, fetch=None) -> list[Posting]:
    fetch = fetch or _http_get
    url = "https://www.indeed.com/jobs?" + urllib.parse.urlencode({"q": keywords, "l": location})
    try:
        html = fetch(url)
    except Exception:
        return []
    marker = 'window.mosaic.providerData["mosaic-provider-jobcards"]='
    idx = html.find(marker)
    if idx == -1:
        return []
    blob = _extract_json_object(html, idx + len(marker))
    if blob is None:
        return []
    try:
        data = json.loads(blob)
        results = data["metaData"]["mosaicProviderJobCardsModel"]["results"]
    except (KeyError, TypeError, json.JSONDecodeError):
        return []
    postings = []
    for r in results:
        title = r.get("displayTitle") or r.get("title")
        jobkey = r.get("jobkey")
        if not title or not jobkey:
            continue
        postings.append(Posting(
            title=title, company=r.get("company", ""),
            location=r.get("formattedLocation", ""),
            url=f"https://www.indeed.com/viewjob?jk={jobkey}",
            source="indeed", fetched_date=today_iso(),
        ))
    return postings


def fetch_posting_text(url: str, fetch=None) -> str:
    fetch = fetch or _http_get
    try:
        html = fetch(url)
    except Exception:
        return ""
    return re.sub(r"<[^>]+>", " ", html)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sources_linkedin_indeed.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add job_search/sources.py tests/test_sources_linkedin_indeed.py
git commit -m "feat: add LinkedIn and Indeed source scrapers"
```

---

### Task 5: Glassdoor + ZipRecruiter sources

**Files:**
- Modify: `job_search/sources.py`
- Test: `tests/test_sources_glassdoor_zip.py`

**Interfaces:**
- Consumes: `Posting`, `today_iso` from Task 1; extends `job_search/sources.py` from Task 4.
- Produces: `fetch_glassdoor(keywords: str, location: str, fetch=None) -> list[Posting]`, `fetch_ziprecruiter(keywords: str, location: str, fetch=None) -> list[Posting]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sources_glassdoor_zip.py
from job_search.sources import fetch_glassdoor, fetch_ziprecruiter

GLASSDOOR_AUTOCOMPLETE = '[{"id":1139977,"locationId":1139977,"locationType":"C","locationName":"Dallas, TX","label":"Dallas, TX"}]'

GLASSDOOR_SEARCH = """
<a class="JobCard_jobTitle__GLyJ1" data-test="job-title" href="https://www.glassdoor.com/job-listing/data-analyst-intern-acme-JV_IC1.htm?jl=111">Data Analyst Intern</a>
<div class="EmployerProfile_compactEmployerName__abc12">Acme Corp</div>
<div class="JobCard_location__Ds1fM">Dallas, TX</div>
<a class="JobCard_jobTitle__GLyJ1" data-test="job-title" href="https://www.glassdoor.com/job-listing/bi-intern-widgets-JV_IC2.htm?jl=222">BI Intern</a>
<div class="EmployerProfile_compactEmployerName__abc12">Widgets Inc</div>
<div class="JobCard_location__Ds1fM">Remote</div>
"""

ZIPRECRUITER_CHALLENGE = '<!DOCTYPE html><html><head><title>Just a moment...</title></head><body>cf-challenge</body></html>'


def test_fetch_glassdoor_two_step_parses_fixture():
    calls = []

    def fake_fetch(url):
        calls.append(url)
        if "autocomplete/location" in url:
            return GLASSDOOR_AUTOCOMPLETE
        return GLASSDOOR_SEARCH

    postings = fetch_glassdoor("Data Analyst Intern", "Dallas, TX", fetch=fake_fetch)
    assert len(calls) == 2
    assert "autocomplete/location" in calls[0]
    assert "locId=1139977" in calls[1]
    assert len(postings) == 2
    assert postings[0].title == "Data Analyst Intern"
    assert postings[0].company == "Acme Corp"
    assert postings[0].url == "https://www.glassdoor.com/job-listing/data-analyst-intern-acme-JV_IC1.htm"
    assert postings[0].source == "glassdoor"
    assert postings[1].location == "Remote"


def test_fetch_glassdoor_returns_empty_when_location_unresolved():
    postings = fetch_glassdoor("x", "nowhere", fetch=lambda url: "[]")
    assert postings == []


def test_fetch_ziprecruiter_degrades_on_cloudflare_challenge():
    postings = fetch_ziprecruiter("Data Analyst Intern", "Dallas, TX",
                                   fetch=lambda url: ZIPRECRUITER_CHALLENGE)
    assert postings == []


def test_fetch_ziprecruiter_returns_empty_on_fetch_failure():
    def boom(url):
        raise TimeoutError("blocked")
    assert fetch_ziprecruiter("x", "y", fetch=boom) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sources_glassdoor_zip.py -v`
Expected: FAIL with `ImportError: cannot import name 'fetch_glassdoor'`

- [ ] **Step 3: Write minimal implementation**

Append to `job_search/sources.py`:

```python
def fetch_glassdoor(keywords: str, location: str, fetch=None) -> list[Posting]:
    fetch = fetch or _http_get
    try:
        auto_url = "https://www.glassdoor.com/autocomplete/location?" + urllib.parse.urlencode(
            {"term": location, "locationTypeFilters": "CITY"}
        )
        candidates = json.loads(fetch(auto_url))
        if not candidates:
            return []
        loc_id = candidates[0]["locationId"]
        search_url = "https://www.glassdoor.com/Job/jobs.htm?" + urllib.parse.urlencode(
            {"sc.keyword": keywords, "locT": "C", "locId": loc_id}
        )
        html = fetch(search_url)
    except Exception:
        return []
    titles = re.findall(r'class="JobCard_jobTitle__[^"]*"[^>]*>([^<]+)<', html)
    hrefs = re.findall(r'class="JobCard_jobTitle__[^"]*"[^>]*href="([^"?]+)"', html)
    companies = re.findall(r'class="EmployerProfile_compactEmployerName__[^"]*"[^>]*>([^<]+)<', html)
    locations = re.findall(r'class="JobCard_location__[^"]*"[^>]*>([^<]+)<', html)
    n = min(len(titles), len(hrefs), len(companies), len(locations))
    return [
        Posting(title=titles[i].strip(), company=companies[i].strip(),
                location=locations[i].strip(), url=hrefs[i].strip(),
                source="glassdoor", fetched_date=today_iso())
        for i in range(n)
    ]


def fetch_ziprecruiter(keywords: str, location: str, fetch=None) -> list[Posting]:
    # Confirmed blocked by a Cloudflare JS challenge during design research
    # (2026-07-08 live check) — this consistently degrades to an empty list
    # rather than raising, matching the graceful-degrade contract of every
    # other source. No attempt is made to bypass the challenge.
    fetch = fetch or _http_get
    url = "https://www.ziprecruiter.com/jobs-search?" + urllib.parse.urlencode(
        {"search": keywords, "location": location}
    )
    try:
        html = fetch(url)
    except Exception:
        return []
    if "Just a moment" in html or "cf-challenge" in html:
        return []
    return []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sources_glassdoor_zip.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add job_search/sources.py tests/test_sources_glassdoor_zip.py
git commit -m "feat: add Glassdoor scraper and ZipRecruiter graceful-degrade stub"
```

---

### Task 6: Fit scoring

**Files:**
- Create: `job_search/rank.py`
- Test: `tests/test_rank.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (pure text-in, score-out).
- Produces: `SKILLS_VOCAB: list[str]`, `FIT_THRESHOLD: float` (`0.30`), `extract_skills(text: str) -> set[str]`, `fit_score(posting_text: str, profile_text: str) -> float`, `passes_threshold(score: float) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rank.py
from job_search.rank import extract_skills, fit_score, passes_threshold, FIT_THRESHOLD


def test_extract_skills_case_insensitive():
    skills = extract_skills("We need someone strong in SQL, Python, and Power BI.")
    assert "sql" in skills
    assert "python" in skills
    assert "power bi" in skills
    assert "tableau" not in skills


def test_fit_score_half_overlap():
    posting = "Requires SQL, Python, Tableau, and AWS experience."
    profile = "I have used SQL and Python extensively in my internship."
    score = fit_score(posting, profile)
    assert score == 0.5  # 2 of 4 posting skills (sql, python) are in profile


def test_fit_score_zero_when_no_skills_in_posting():
    assert fit_score("Great company culture and free snacks.", "SQL Python") == 0.0


def test_fit_score_full_overlap():
    posting = "SQL and Python required."
    profile = "SQL, Python, machine learning, statistics."
    assert fit_score(posting, profile) == 1.0


def test_passes_threshold_boundary_is_inclusive():
    assert FIT_THRESHOLD == 0.30
    assert passes_threshold(0.30) is True
    assert passes_threshold(0.29) is False
    assert passes_threshold(0.31) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rank.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'job_search.rank'`

- [ ] **Step 3: Write minimal implementation**

```python
# job_search/rank.py
SKILLS_VOCAB = [
    "python", "sql", "excel", "power bi", "tableau", "r", "sas", "spss",
    "machine learning", "statistics", "statistical", "xgboost", "regression",
    "data visualization", "etl", "data pipeline", "a/b testing",
    "hypothesis testing", "pandas", "numpy", "scikit-learn", "azure", "aws",
    "gcp", "snowflake", "data warehouse", "database", "dashboard",
    "forecasting", "clustering", "nlp", "deep learning", "tensorflow",
    "pytorch", "git", "vba", "looker", "power query", "dax", "monte carlo",
    "anova", "logistic regression",
]

FIT_THRESHOLD = 0.30


def extract_skills(text: str) -> set[str]:
    lowered = text.lower()
    return {kw for kw in SKILLS_VOCAB if kw in lowered}


def fit_score(posting_text: str, profile_text: str) -> float:
    posting_skills = extract_skills(posting_text)
    if not posting_skills:
        return 0.0
    profile_skills = extract_skills(profile_text)
    matched = posting_skills & profile_skills
    return len(matched) / len(posting_skills)


def passes_threshold(score: float) -> bool:
    return score >= FIT_THRESHOLD
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rank.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add job_search/rank.py tests/test_rank.py
git commit -m "feat: add fixed-vocabulary fit scoring with 30% cutoff"
```

---

### Task 7: Markdown output (write + round-trip parse)

**Files:**
- Create: `job_search/markdown_output.py`
- Test: `tests/test_markdown_output.py`

**Interfaces:**
- Consumes: `Posting` from Task 1.
- Produces: `write_internships_md(path, postings: list[Posting]) -> None`, `parse_internships_md(path) -> list[Posting]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_markdown_output.py
from job_search.posting import Posting
from job_search.markdown_output import write_internships_md, parse_internships_md


def _p(fit_score=None, rationale=None):
    return Posting(title="Data Analyst Intern", company="Acme Corp", location="Dallas, TX",
                    url="https://example.com/1", source="linkedin", fetched_date="2026-07-08",
                    fit_score=fit_score, rationale=rationale)


def test_round_trip_without_scores(tmp_path):
    path = tmp_path / "internships.md"
    write_internships_md(path, [_p()])
    loaded = parse_internships_md(path)
    assert len(loaded) == 1
    assert loaded[0].title == "Data Analyst Intern"
    assert loaded[0].company == "Acme Corp"
    assert loaded[0].location == "Dallas, TX"
    assert loaded[0].url == "https://example.com/1"
    assert loaded[0].source == "linkedin"
    assert loaded[0].fetched_date == "2026-07-08"
    assert loaded[0].fit_score is None


def test_round_trip_with_scores(tmp_path):
    path = tmp_path / "internships.md"
    write_internships_md(path, [_p(fit_score=0.55, rationale="Strong SQL/Python overlap")])
    loaded = parse_internships_md(path)
    assert loaded[0].fit_score == 0.55
    assert loaded[0].rationale == "Strong SQL/Python overlap"


def test_sorted_highest_fit_first(tmp_path):
    path = tmp_path / "internships.md"
    low = Posting(title="Low Fit", company="B", location="Remote", url="u2",
                   source="indeed", fetched_date="2026-07-08", fit_score=0.2)
    high = Posting(title="High Fit", company="A", location="Remote", url="u1",
                    source="indeed", fetched_date="2026-07-08", fit_score=0.8)
    write_internships_md(path, [low, high])
    loaded = parse_internships_md(path)
    assert loaded[0].title == "High Fit"
    assert loaded[1].title == "Low Fit"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_markdown_output.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'job_search.markdown_output'`

- [ ] **Step 3: Write minimal implementation**

```python
# job_search/markdown_output.py
import pathlib

from job_search.posting import Posting

HEADER = (
    "| Job Title | Company | Location | URL | Source | Fetched | Fit Score | Rationale |\n"
    "|---|---|---|---|---|---|---|---|\n"
)


def write_internships_md(path, postings: list[Posting]) -> None:
    ordered = sorted(postings, key=lambda p: -(p.fit_score or 0))
    lines = [
        "# Fall 2026 Data Science / Analyst / BI Internship Search\n\n",
        f"Auto-generated by job_search.py. {len(ordered)} postings within 20 miles of home or remote.\n\n",
        HEADER,
    ]
    for p in ordered:
        rationale = (p.rationale or "").replace("|", "/")
        score = f"{p.fit_score:.2f}" if p.fit_score is not None else "-"
        lines.append(
            f"| {p.title} | {p.company} | {p.location} | {p.url} | {p.source} | "
            f"{p.fetched_date} | {score} | {rationale} |\n"
        )
    pathlib.Path(path).write_text("".join(lines), encoding="utf-8")


def parse_internships_md(path) -> list[Posting]:
    postings = []
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells or cells[0] == "Job Title":
            continue
        if len(cells) < 6:
            continue
        title, company, location, url, source, fetched = cells[:6]
        fit_score = None
        rationale = None
        if len(cells) >= 8:
            score_str = cells[6]
            if score_str not in ("-", ""):
                fit_score = float(score_str)
            rationale = cells[7] or None
        postings.append(Posting(title=title, company=company, location=location, url=url,
                                 source=source, fetched_date=fetched,
                                 fit_score=fit_score, rationale=rationale))
    return postings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_markdown_output.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add job_search/markdown_output.py tests/test_markdown_output.py
git commit -m "feat: add fall_2026_internships.md writer and round-trip parser"
```

---

### Task 8: CLI wiring (`scrape` + `rank` subcommands)

**Files:**
- Create: `job_search_cli.py` (repo-root script; named to avoid colliding with the `job_search/` package directory — `job_search.py` and `job_search/` cannot coexist in the same directory)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `dedupe_postings` (Task 1), `is_within_range` (Task 2), `read_tracker`/`is_handled` (Task 3), `fetch_linkedin`/`fetch_indeed`/`fetch_glassdoor`/`fetch_ziprecruiter`/`fetch_posting_text` (Tasks 4-5), `fit_score`/`passes_threshold`/`FIT_THRESHOLD` (Task 6), `write_internships_md`/`parse_internships_md` (Task 7).
- Produces: `run_scrape(source_fns, keywords, locations, tracker_path, output_path) -> tuple[list[Posting], list[str]]` (postings written, list of blocked/empty source names), `run_rank(output_path, experiences_path, fetch_text=None) -> tuple[list[Posting], int]` (all postings with scores set, count passing threshold). Both are called by `main()` with real defaults, and are the units under test (CLI arg-parsing itself is not unit tested — see Task 10 for the manual end-to-end check).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
# Run with `python -m pytest tests/test_cli.py` from the repo root — that
# puts the repo root on sys.path so both the `job_search` package and the
# root-level `job_search_cli.py` module import cleanly.
from job_search.posting import Posting
from job_search_cli import run_scrape, run_rank


def test_run_scrape_dedupes_filters_and_writes(tmp_path):
    output_path = tmp_path / "fall_2026_internships.md"
    tracker_path = tmp_path / "tracker.csv"

    def fake_linkedin(kw, loc, fetch=None):
        return [Posting(title="Data Analyst Intern", company="Acme", location="Remote",
                         url="https://li.example/1", source="linkedin", fetched_date="2026-07-08")]

    def fake_indeed(kw, loc, fetch=None):
        return [Posting(title="Data Analyst Intern", company="ACME", location="remote",
                         url="https://indeed.example/1", source="indeed", fetched_date="2026-07-08"),
                Posting(title="Far Away Intern", company="Other Co", location="Seattle, WA",
                         url="https://indeed.example/2", source="indeed", fetched_date="2026-07-08")]

    def empty(kw, loc, fetch=None):
        return []

    def fake_within_range(location, fetch=None):
        return "remote" in location.lower()

    postings, blocked = run_scrape(
        source_fns=[("linkedin", fake_linkedin), ("indeed", fake_indeed),
                    ("glassdoor", empty), ("ziprecruiter", empty)],
        keywords=["Data Analyst Intern"], locations=["Remote"],
        tracker_path=tracker_path, output_path=output_path,
        within_range=fake_within_range,
    )
    assert len(postings) == 1  # deduped (same title/company/location) and Seattle filtered out
    assert postings[0].url == "https://li.example/1"
    assert "glassdoor" in blocked
    assert "ziprecruiter" in blocked
    assert output_path.exists()


def test_run_scrape_excludes_already_handled(tmp_path):
    from job_search.tracker import TrackerRow, write_tracker
    output_path = tmp_path / "fall_2026_internships.md"
    tracker_path = tmp_path / "tracker.csv"
    write_tracker(tracker_path, {
        "https://li.example/1": TrackerRow(company="Acme", title="Data Analyst Intern",
                                            url="https://li.example/1", status="applied",
                                            fit_score="0.5", date="2026-07-01")
    })

    def fake_linkedin(kw, loc, fetch=None):
        return [Posting(title="Data Analyst Intern", company="Acme", location="Remote",
                         url="https://li.example/1", source="linkedin", fetched_date="2026-07-08")]

    def empty(kw, loc, fetch=None):
        return []

    postings, _ = run_scrape(
        source_fns=[("linkedin", fake_linkedin), ("indeed", empty),
                    ("glassdoor", empty), ("ziprecruiter", empty)],
        keywords=["Data Analyst Intern"], locations=["Remote"],
        tracker_path=tracker_path, output_path=output_path,
        within_range=lambda loc, fetch=None: True,
    )
    assert postings == []


def test_run_rank_scores_and_rewrites(tmp_path):
    output_path = tmp_path / "fall_2026_internships.md"
    experiences_path = tmp_path / "experiences.md"
    experiences_path.write_text("Skilled in SQL and Python.", encoding="utf-8")
    from job_search.markdown_output import write_internships_md
    write_internships_md(output_path, [
        Posting(title="Data Analyst Intern", company="Acme", location="Remote",
                url="https://example.com/1", source="linkedin", fetched_date="2026-07-08"),
    ])

    def fake_fetch_text(url, fetch=None):
        return "Requires SQL, Python, Tableau, and AWS."

    postings, qualifying = run_rank(output_path, experiences_path, fetch_text=fake_fetch_text)
    assert postings[0].fit_score == 0.5
    assert qualifying == 1  # 0.5 >= 0.30
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'job_search_cli'`

- [ ] **Step 3: Write minimal implementation**

```python
# job_search_cli.py
"""CLI for Fall 2026 internship discovery and fit ranking.
Usage: python job_search_cli.py scrape
       python job_search_cli.py rank
"""
import argparse
import pathlib

from job_search.geocode import is_within_range
from job_search.markdown_output import parse_internships_md, write_internships_md
from job_search.posting import Posting, dedupe_postings
from job_search.rank import FIT_THRESHOLD, fit_score, passes_threshold
from job_search.sources import (
    fetch_glassdoor,
    fetch_indeed,
    fetch_linkedin,
    fetch_posting_text,
    fetch_ziprecruiter,
)
from job_search.tracker import is_handled, read_tracker

KEYWORDS = ["Data Analyst Intern", "Data Science Intern", "BI Intern"]
LOCATIONS = ["Dallas, TX", "Remote"]
TRACKER_PATH = "job_search_tracker.csv"
OUTPUT_PATH = "fall_2026_internships.md"
EXPERIENCES_PATH = "experiences.md"

SOURCE_FNS = [
    ("linkedin", fetch_linkedin),
    ("indeed", fetch_indeed),
    ("glassdoor", fetch_glassdoor),
    ("ziprecruiter", fetch_ziprecruiter),
]


def run_scrape(source_fns, keywords, locations, tracker_path, output_path,
                within_range=is_within_range) -> tuple[list[Posting], list[str]]:
    all_postings: list[Posting] = []
    blocked: list[str] = []
    for kw in keywords:
        for loc in locations:
            for name, fn in source_fns:
                results = fn(kw, loc)
                if not results:
                    blocked.append(name)
                all_postings.extend(results)
    deduped = dedupe_postings(all_postings)
    tracker = read_tracker(tracker_path)
    fresh = [p for p in deduped if not is_handled(tracker, p.url)]
    nearby = [p for p in fresh if within_range(p.location)]
    write_internships_md(output_path, nearby)
    return nearby, sorted(set(blocked))


def run_rank(output_path, experiences_path,
             fetch_text=fetch_posting_text) -> tuple[list[Posting], int]:
    postings = parse_internships_md(output_path)
    profile_text = pathlib.Path(experiences_path).read_text(encoding="utf-8")
    for p in postings:
        posting_text = fetch_text(p.url)
        p.fit_score = fit_score(posting_text, profile_text)
    write_internships_md(output_path, postings)
    qualifying = sum(1 for p in postings if passes_threshold(p.fit_score))
    return postings, qualifying


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("scrape")
    sub.add_parser("rank")
    args = parser.parse_args()

    if args.command == "scrape":
        postings, blocked = run_scrape(SOURCE_FNS, KEYWORDS, LOCATIONS, TRACKER_PATH, OUTPUT_PATH)
        print(f"Scraped {len(postings)} postings within range. Blocked/empty sources: {blocked}")
    elif args.command == "rank":
        postings, qualifying = run_rank(OUTPUT_PATH, EXPERIENCES_PATH)
        pct = int(FIT_THRESHOLD * 100)
        print(f"Ranked {len(postings)} postings. {qualifying} at or above {pct}% fit.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add job_search_cli.py tests/test_cli.py
git commit -m "feat: wire scrape and rank subcommands into job_search_cli.py"
```

---

### Task 9: Full test suite + manual live smoke check

**Files:**
- None created — verification task.

**Interfaces:**
- Consumes: everything from Tasks 1-8.

- [ ] **Step 1: Run the full automated suite**

Run: `python -m pytest tests/ -v`
Expected: all tests from Tasks 1-8 pass (24 tests total: 2+6+4+5+4+5+3+3... exact count depends on final file, but zero failures/errors).

- [ ] **Step 2: Manual live check — one source at a time**

This step is NOT automated (network-dependent, sites can change) — run it once by hand to confirm the real integrations still work exactly as the fixtures assume:

```bash
python -c "from job_search.sources import fetch_linkedin; r = fetch_linkedin('Data Analyst Intern', 'Dallas, TX'); print(len(r)); print(r[0] if r else 'EMPTY')"
python -c "from job_search.sources import fetch_indeed; r = fetch_indeed('Data Analyst Intern', 'Dallas, TX'); print(len(r)); print(r[0] if r else 'EMPTY')"
python -c "from job_search.sources import fetch_glassdoor; r = fetch_glassdoor('Data Analyst Intern', 'Dallas, TX'); print(len(r)); print(r[0] if r else 'EMPTY')"
```

Expected: LinkedIn and Indeed print a nonzero count and a real `Posting`. Glassdoor should also succeed (confirmed live during design research) but is more likely to drift if Glassdoor changes their CSS-module hash prefixes — if it prints `0`, that's the expected degrade path, not a bug, but worth noting for a future fixup.

- [ ] **Step 3: Manual live check — full scrape + rank**

```bash
python job_search_cli.py scrape
python job_search_cli.py rank
```

Expected: `fall_2026_internships.md` is overwritten with real postings, sorted by fit score once `rank` runs. Read the file and sanity-check a few rows against the actual job board.

- [ ] **Step 4: Commit** (only if Step 2/3 surfaced a fixup — otherwise nothing to commit)

```bash
git add -A
git commit -m "fix: adjust scraper against live site drift found during smoke check"
```

---

### Task 10: Apply playbook (orchestration doc for Claude + Playwright MCP)

**Files:**
- Create: `docs/playbooks/apply-playbook.md`

**Interfaces:**
- Consumes: `job_search_tracker.csv` format (Task 3), `fall_2026_internships.md` format (Task 7), `FIT_THRESHOLD` (Task 6), existing `RESUME_FORMAT.md` / `README.md` resume pipeline, existing `md_to_pdf.py`.
- Produces: nothing code-level — this is the instruction set Claude follows when the user says "run apply." No placeholders: every step below is the literal procedure, not a description of one.

This is not a Python task — bulk apply requires LLM judgment (drafting resume/cover-letter text, reading company research off the posting) and live browser control (Playwright MCP), neither of which is a pure function. Write the file with this exact content:

- [ ] **Step 1: Write the playbook**

```markdown
# Apply playbook

Followed by Claude when the user says "run apply." Processes every posting in
`fall_2026_internships.md` scoring >= 30% fit (see `job_search/rank.py`
`FIT_THRESHOLD`) that isn't already `applied` or `skipped` in
`job_search_tracker.csv`. Never auto-submits — every posting stops at the
browser review screen for the user to submit or skip by hand.

## Build the queue

1. Read `fall_2026_internships.md`, parse rows with `job_search.markdown_output.parse_internships_md`.
2. Read `job_search_tracker.csv` with `job_search.tracker.read_tracker`.
3. Queue = postings where `fit_score >= 0.30` AND `job_search.tracker.is_handled(tracker, url)` is `False`.
4. If the queue is empty, report that and stop — nothing to do.

## Per posting in the queue (repeat until queue is empty)

1. **Fetch the full posting text** (not just the search-result title) — `job_search.sources.fetch_posting_text(url)`.
   Read it closely: what's the company actually asking for (required skills,
   tools, phrasing, seniority signals, anything the resume/cover letter
   should mirror)? No web search — the posting text is the only research
   input, by design (see `docs/superpowers/specs/2026-07-08-job-search-automation-design.md`).

2. **Resume**: check whether `resumes/<company-slug>.md` already exists
   (slug = company name, lowercased, spaces to underscores, matching the
   existing convention seen in `resumes/` — e.g. `jpmc.md`, `hypernet.md`).
   - If missing: draft it now following `RESUME_FORMAT.md` exactly —
     pull from `experiences.md`, tailor to what step 1 surfaced, one page,
     `EDUCATION -> PROFESSIONAL EXPERIENCE -> PROJECTS & EXTRACURRICULAR -> SKILLS`
     order, 3-5 bullets per project entry, no em dashes, no fabrication.
   - Export: `python md_to_pdf.py resumes/<company-slug>.md`.
   - Verify 1 page: `grep -a -o "/Count [0-9]*" resumes/<company-slug>.pdf`
     must read `/Count 1`. If it overflows, trim the lowest-relevance
     experience bullets first (never touch the 3-5-bullet project rule) and
     re-export. Repeat until `/Count 1`.

3. **Cover letter**: check whether `resumes/<company-slug>_cover_letter.md`
   already exists (same convention as `resumes/jpmc_cover_letter.md`).
   - If missing: draft it now — contact header, dateline, 4-5 paragraphs,
     same structure/tone as the existing cover letters in `resumes/`
     (see `jpmc_cover_letter.md` for the reference shape), informed by
     step 1, same writing rules as `README.md` (no em dash, no filler,
     verb-first, never fabricate).
   - Export: `python md_to_pdf.py resumes/<company-slug>_cover_letter.md`.
   - Verify 1 page the same way as the resume. Trim weakest paragraph
     content and re-export if it overflows.

4. **Detect the ATS platform** from the posting URL:
   - `myworkdayjobs.com` in the URL -> Workday
   - `greenhouse.io` in the URL -> Greenhouse
   - `lever.co` in the URL -> Lever
   - anything else -> **unsupported**. Update the tracker
     (`job_search.tracker.upsert` + `write_tracker`) with
     `status="needs-manual"`, `fit_score=<the posting's score>`,
     `date=<today>`. Move to the next posting in the queue. Do not attempt
     to guess-fill an unrecognized form.

5. **Fill the form** (Workday/Greenhouse/Lever only) using the Playwright MCP
   tools available in this session:
   - `browser_navigate` to the posting URL.
   - `browser_snapshot` to see the current form state.
   - `browser_fill_form` / `browser_type` for the fields the profile can
     answer confidently: full name, email (`<EMAIL>`), phone
     (`<PHONE>`), LinkedIn (`<LINKEDIN>`), GitHub
     (`github.com/Kendrew-K`).
   - `browser_file_upload` for the resume PDF (`resumes/<company-slug>.pdf`)
     and cover letter PDF (`resumes/<company-slug>_cover_letter.pdf`) on
     whichever fields accept them.
   - Leave custom application questions ("Why do you want to work here?",
     eligibility screeners, etc.) untouched — those need the user's own
     judgment, not a guess.
   - Stop navigation at the review/confirmation screen. **Never click a
     final submit/apply button under any circumstance.**

6. **Record the outcome** in `job_search_tracker.csv`:
   - Reached the review screen: `status="pending-review"`.
   - Skipped for unsupported ATS or unparseable form (step 4): `status="needs-manual"`.
   - Use `job_search.tracker.upsert` then `write_tracker` for each update —
     don't hand-edit the CSV.

7. Move to the next posting in the queue. Do not ask the user for permission
   to start the next one — the batch runs unattended through drafting and
   filling. The per-posting stop in step 5 is the review point, not a batch
   gate.

## After the queue is empty

Report a summary: total processed, how many reached `pending-review`, how
many are `needs-manual` (and which postings, so the user can apply to those
by hand), and the running total of `applied` status across all of
`job_search_tracker.csv` (not just this run — read the whole file).
```

- [ ] **Step 2: Sanity-check the playbook against the tested contracts**

Re-read `job_search/tracker.py`, `job_search/rank.py`, and `job_search/markdown_output.py` from Tasks 3, 6, 7 and confirm every function name and field name referenced in the playbook (`is_handled`, `upsert`, `write_tracker`, `read_tracker`, `parse_internships_md`, `fit_score`, `FIT_THRESHOLD`, the tracker's `status` values) matches exactly what those modules actually export. Fix any drift in the playbook text, not in the code.

- [ ] **Step 3: Commit**

```bash
git add docs/playbooks/apply-playbook.md
git commit -m "docs: add apply playbook for bulk resume/cover-letter/form-fill pipeline"
```

---

## Self-review notes

- **Spec coverage**: scrape sources (LinkedIn/Indeed/Glassdoor/ZipRecruiter) -> Tasks 4-5; location filter -> Task 2; dedupe + tracker cross-reference -> Tasks 1, 3, 8; fit scoring + 30% cutoff -> Task 6; markdown overwrite -> Task 7; bulk apply pipeline (research-then-draft, resume/cover-letter reuse, 1-page verify-trim, ATS detection, never-submit, skip/needs-manual, reporting) -> Task 10. All spec sections have a task.
- **No cron/scheduling task** — correctly absent, it's an explicit non-goal.
- **Type consistency checked**: `Posting.fit_score` is `float | None` everywhere (Tasks 1, 6, 7, 8); tracker `fit_score` field is `str` (CSV has no native float type) everywhere in Task 3 and the playbook's `upsert` calls — these are intentionally different types in different layers, not a bug, but worth flagging so whoever implements Task 10's tracker-writing steps remembers to `str()` the score before calling `upsert`.
