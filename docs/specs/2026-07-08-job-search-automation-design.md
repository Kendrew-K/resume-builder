# Job search automation — design

Supersedes the earlier version of this doc (manual per-URL apply, no auto-drafting). Rewritten after grill session: `brainstorms/2026-07-08-job-search-automation-grill.md`.

## Purpose
Automate job discovery, fit ranking, and bulk application (draft + form-fill, human-reviewed before submit) for Fall 2026 Data Analyst/Data Science/BI intern search, DFW-area or remote.

## Non-goals
- No LinkedIn login / stored credentials anywhere — public/unauthenticated sources only, accepted trade-off for zero ban risk.
- No auto-submission of applications — every posting stops at the browser review screen. Hard rule, no code path bypasses it.
- No web-search-based "company research" — fit and framing come from the posting text itself.
- No two-agent drafter/reviewer split — single pass, research(-the-posting)-then-draft.
- No Bun/Node/LaTeX toolchain — Python stdlib + existing Chrome/`markdown`-based PDF pipeline, matching `md_to_pdf.py` precedent.
- No scheduling/cron — manually triggered only.
- No new cover-letter pipeline — **correction after codebase check**: `resumes/<company>_cover_letter.md` + PDF already exist (e.g. `jpmc_cover_letter.md`), built via the same `md_to_pdf.py` (it's a generic markdown-to-PDF converter, not resume-specific). Reuse as-is, same naming convention, same folder. No `cover_letters/` folder, no new script.

## Architecture
Single script `job_search.py`, three subcommands:

```
python job_search.py scrape   # discover postings, overwrite fall_2026_internships.md
python job_search.py rank     # score postings against experiences.md, apply 30% cutoff
python job_search.py apply    # bulk pipeline over every posting scoring >=30% fit
```

Plus a persistent tracker file that survives `scrape` overwrites. Cover letters reuse the existing `md_to_pdf.py` — no new PDF script needed.

### `scrape`
- Sources, all public/unauthenticated, fetched in parallel via `urllib.request` with a browser-like User-Agent: LinkedIn `jobs-guest` search, Indeed public search, Glassdoor public search, ZipRecruiter public search.
- Query: `Data Analyst Intern` / `Data Science Intern` / `BI Intern`, Dallas-Fort Worth + Remote.
- Each source wrapped in its own try/except — a block/403 on one source degrades that source only (reported as "blocked, skipped"), never crashes the run.
- Dedupe by normalized (company, title, location) across sources.
- Cross-reference against `job_search_tracker.csv` (see Persistence below) — postings already marked `applied` or `skipped` are excluded from the fresh output, not re-surfaced.
- Location filter applied here: geocode each posting's location, keep only postings within 20 miles of <HOME_ADDRESS>, or explicitly remote. Relocation-required postings dropped, not just deprioritized.
- Output: **overwrites** `fall_2026_internships.md` entirely with a fresh table (Job Title, Company, Location, URL, Source, Fetched date). No "recheck plan" carryover — that framing is retired.

### `rank`
- Reads postings in `fall_2026_internships.md` + `experiences.md`.
- Per posting: extract required+preferred skills/tools/qualifications from the posting text, count how many are genuinely supported by `experiences.md`, divide by total required+preferred items found = fit%. Unweighted (required and preferred count equally).
- Hard cutoff: exactly 30%. Below 30% stays visible in the ranked list (for your own manual reference) but is excluded from the `apply` bulk queue.
- Appends `Fit score` + one-line rationale per row, sorted highest first.

### `apply` (bulk mode)
Builds a queue: every posting in `fall_2026_internships.md` scoring >=30% fit AND not already `applied`/`skipped` in `job_search_tracker.csv`. Processes the queue unattended — no per-posting go-ahead needed to start drafting — but each posting individually stops before submission. For each posting in the queue:

1. **Parse posting text** closely — extract what's actually being asked for (required skills, tools, phrasing, priorities). No web search.
2. **Resume**: if `resumes/<company>.md` doesn't exist yet, draft it now via the existing pipeline described in `README.md`/`RESUME_GUIDELINES.md` (pull from `experiences.md`, tailor to the posting, informed by step 1). Export to PDF via `python md_to_pdf.py resumes/<company>.md`. Verify PDF is exactly 1 page (`grep -a -o "/Count [0-9]*" resumes/<company>.pdf` must read `/Count 1`, per existing `RESUME_GUIDELINES.md` rule); if it overflows, trim lowest-relevance content and re-export, looping until it fits.
3. **Cover letter**: if `resumes/<company>_cover_letter.md` doesn't exist yet, draft it now — same existing pattern already used for `jpmc_cover_letter.md` etc (contact header, dateline, 4-5 paragraphs, informed by step 1 + `experiences.md`, same writing rules as `README.md`: no em dash, no filler, verb-first, honest/no fabrication). Export via the SAME `md_to_pdf.py resumes/<company>_cover_letter.md` (no new script — it's already a generic markdown-to-PDF converter). Same 1-page verify-and-trim loop.
4. **Detect ATS platform** by URL/DOM pattern: `myworkdayjobs.com` → Workday, `greenhouse.io` → Greenhouse, `lever.co` → Lever. Unsupported platform or unparseable form → log to `job_search_tracker.csv` as `needs-manual`, skip to next posting in queue, continue (never halts the batch).
5. **Claude in Chrome** (the browser extension driving the user's own logged-in Chrome; replaced Playwright MCP): open the posting, fill known fields from `experiences.md`/`Profile.pdf` contact info (name, email, phone), upload both PDFs. Stop at the review/confirmation screen. Never click submit.
6. **Record**: update `job_search_tracker.csv` — status `pending-review` for anything that reached the review screen (you decide submit/skip manually in the browser), `needs-manual` for anything skipped due to ATS/form issues.
7. **Report**: at the end of the batch, print/return a summary — total processed, how many reached review screen, how many needs-manual, running applied-count.

## Persistence — `job_search_tracker.csv`
New file, never overwritten by `scrape`. Columns: `company`, `title`, `url`, `status` (`pending` / `pending-review` / `applied` / `skipped` / `needs-manual`), `fit_score`, `date`. `scrape` reads it to exclude already-handled postings from fresh output; `apply` reads/writes it to build the queue and record outcomes.

## Data flow
```
experiences.md ──┐
                  ├─> rank (fit scoring, 30% cutoff) ─> fall_2026_internships.md (sorted, scored)
scrape ──────────>│    (cross-referenced against job_search_tracker.csv, location-filtered)
                  
fall_2026_internships.md (>=30% fit rows) ─> apply (bulk queue)
  ├─> draft resume (if missing) ─> md_to_pdf.py ─> PDF (1-page verified)
  ├─> draft cover letter (if missing) ─> md_to_pdf.py ─> PDF (1-page verified)
  ├─> Claude in Chrome: fill form, upload both, stop at review
  └─> job_search_tracker.csv updated (pending-review / needs-manual)
```

## Error handling
- Any scrape source blocked/rate-limited: reported explicitly per-source, never silently treated as "zero postings found = clean result."
- `apply` never auto-submits under any code path — hard rule, not a default.
- Unsupported ATS or malformed form: skip + log `needs-manual`, continue batch — one bad posting never halts the run.
- PDF page-count verification failure after trim attempts: flag for manual review rather than shipping a >1-page document.

## Testing
- `scrape`: run against known-live search URLs per source, verify parsing/dedupe/location-filter correctness; verify a deliberately-blocked source degrades without crashing the run.
- `rank`: fixture of 3-4 postings with known skill overlap, verify fit% math and the exact-30% cutoff boundary.
- `apply`: dry run against one Workday and one Greenhouse posting — verify resume+cover-letter draft/export/1-page-trim, verify the Claude in Chrome fill stops at review without submitting, verify an unsupported-ATS posting logs `needs-manual` and the batch continues to the next item.
