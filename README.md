# Resume Builder and Job Search Automation

A dependency-light Python pipeline that finds internship postings, filters them
to the ones you could actually take, scores each against your own experience
file, and tracks what you have applied to. Plus a Markdown resume builder that
exports an ATS-safe one-page PDF through headless Chrome.

Everything is plain files: Markdown in, Markdown and CSV out. No database, no
server, no account to create. The only third-party runtime dependency is
`markdown`; the rest is the standard library.

```
scrape  ->  internships.md  ->  rank  ->  internships.md (with fit scores)
                 |                                |
                 +--------- applied / status -----+
                                 |
                        job_search_tracker.csv
```

## Why it exists

Job boards are bad at three specific things, and each one is a module here:

1. **They surface jobs you cannot take.** `job_search/geocode.py` geocodes each
   posting through Nominatim and drops anything outside a radius of your home
   address, keeping remote postings only when they are US-based. "Remote" on a
   job board routinely means "Remote, Colombia".
2. **They re-list the same job from four sources.** `job_search/posting.py`
   dedupes across sources with the company's own ATS link winning, so the URL
   you get is the real apply link rather than an aggregator redirect.
3. **They rank by recency, not by you.** `job_search/rank.py` scores each
   posting as *(skills in the posting that also appear in your profile) /
   (skills in the posting)*, and hides anything under 30%.

## Setup

Requires Python 3.11+ (uses `X | None` type syntax) and, for PDF export, any
Chrome or Chromium build.

```bash
git clone https://github.com/Kendrew-K/resume-builder.git
cd resume-builder
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp example_profile.md experiences.md   # then edit with your own history
```

Configure the search with environment variables. All have defaults, so the
pipeline runs without setting any of them:

| Variable | Default | What it does |
|---|---|---|
| `JOB_SEARCH_HOME_ADDRESS` | `Dallas, TX` | Center of the commute radius |
| `JOB_SEARCH_RADIUS_MILES` | `20` | Radius around that address |
| `JOB_SEARCH_CONTACT` | unset | Your email. Nominatim's usage policy requires a contact in the User-Agent, so set this before running live |
| `JOB_SEARCH_KEYWORDS` | `Data Analyst Intern,Data Science Intern,BI Intern` | Comma-separated search terms |
| `JOB_SEARCH_LOCATIONS` | `Dallas, TX;Remote` | Semicolon-separated (locations contain commas) |
| `JOB_SEARCH_PROFILE` | `experiences.md` | Your experience file, used for scoring |
| `JOB_SEARCH_OUTPUT` | `internships.md` | Where results are written |
| `JOB_SEARCH_TRACKER` | `job_search_tracker.csv` | Application state |
| `CHROME_PATH` | autodetected | Chrome/Chromium binary for PDF export |

## Usage

```bash
python job_search_cli.py scrape          # find postings, write internships.md
python job_search_cli.py rank            # score each against your profile
python job_search_cli.py status          # what is applied / pending / manual
python job_search_cli.py applied <url>   # mark one or more as applied
```

`scrape` also caches the job descriptions it got for free from company ATS
boards, so `rank` can reuse them instead of re-fetching:

```bash
python job_search_cli.py rank --text-cache ats_text.json
```

Export a resume to PDF:

```bash
python md_to_pdf.py resumes/acme.md      # writes resumes/acme.pdf
```

The Markdown convention the exporter expects is documented in
[`RESUME_FORMAT.md`](RESUME_FORMAT.md): `### Title | Date` becomes a flex row
with the date pushed right, `##` becomes a ruled section header. The CSS is
deliberately single-column with no tables, sidebars or icons, because those are
what break ATS parsers.

[`example_resume.md`](example_resume.md) is a complete, fictional resume in that
format. Exporting it is the fastest way to check your setup works:

```bash
python md_to_pdf.py example_resume.md
grep -a -o "/Count [0-9]*" example_resume.pdf    # want /Count 1
```

## Sources, and their honest limits

| Source | How it is reached | Works headless? |
|---|---|---|
| Greenhouse, Lever, Ashby | Public JSON on each company's own board | Yes, and it is the freshest source |
| SimplifyJobs GitHub listings | Raw Markdown from the public repo | Yes. Also supplies the ATS board slugs above, so there is no hand-maintained company list |
| LinkedIn, Indeed, Glassdoor | HTML scrape of the logged-out guest endpoints | Partially. They bot-wall and rate-limit, and Indeed serves descriptions client-side and 429s on description fetches |
| ZipRecruiter | Not reachable without a session | No. The fetcher is a stub that returns nothing rather than pretending |

For the bot-walled boards there is an `ingest` path: dump postings from a
logged-in browser as `[{title, company, location, url, source}]` and merge them
in, keeping any direct-ATS URL already found for the same job.

```bash
python job_search_cli.py ingest chrome_postings.json
```

## Layout

```
job_search_cli.py          Subcommand dispatch; every run_* function is
                           dependency-injected so tests never hit the network
job_search/posting.py      Posting model, cross-source dedupe
job_search/sources.py      Job-board scrapers (one function per board)
job_search/ats.py          Greenhouse/Lever/Ashby polling, board slugs
                           derived from the GitHub listings
job_search/geocode.py      Nominatim geocoding, haversine, radius filter
job_search/rank.py         Skill-vocabulary fit scoring
job_search/tracker.py      CSV application tracker, keyed on
                           (title, company, location) so a job re-listed
                           under a new URL stays marked applied
job_search/markdown_output.py  Markdown table writer and round-trip parser
md_to_pdf.py               Markdown resume -> ATS-safe one-page PDF
docs/                      Design spec and implementation plan
tests/                     55 tests, no network
```

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Every network call is behind an injectable `fetch` parameter, so the suite runs
offline against saved fixtures and finishes in under a second.

## Notes

- `experiences.md`, `resumes/`, and the tracker CSV are gitignored. They hold
  your contact details and application history, which is why the repo ships
  `example_profile.md` instead.
- Scraping logged-out HTML endpoints is brittle by nature. When a board changes
  its markup the corresponding source returns nothing, `scrape` reports it in
  the "blocked/empty sources" line, and the rest of the pipeline still runs.
- Respect each site's terms of service and Nominatim's one-request-per-second
  policy (already enforced in `geocode.py`).
