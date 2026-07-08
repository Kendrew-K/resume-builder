# Apply playbook

Followed by Claude when the user says "run apply." Processes every posting in
`fall_2026_internships.md` scoring >= 30% fit (see `job_search/rank.py`
`FIT_THRESHOLD`) that isn't already `applied` or `skipped` in
`job_search_tracker.csv`. Never auto-submits — every posting stops at the
browser review screen for the user to submit or skip by hand.

## Build the queue

1. Read `fall_2026_internships.md`, parse rows with `job_search.markdown_output.parse_internships_md`.
2. Read `job_search_tracker.csv` with `job_search.tracker.read_tracker`.
3. Queue = postings where `fit_score >= 0.30` AND
   `job_search.tracker.is_handled(tracker, title, company, location)` is `False`.
   (The tracker is keyed by normalized `(title, company, location)` — the
   same identity `job_search.posting.dedupe_postings` uses — not by URL, so a
   posting already marked `applied`/`skipped` is recognized even if it
   resurfaces under a different URL from another source.)
4. If the queue is empty, report that and stop — nothing to do.

## Per posting in the queue (repeat until queue is empty)

1. **Fetch the full posting text** (not just the search-result title) — `job_search.sources.fetch_posting_text(url)`.
   Read it closely: what's the company actually asking for (required skills,
   tools, phrasing, seniority signals, anything the resume/cover letter
   should mirror)? No web search — the posting text is the only research
   input, by design (see `docs/specs/2026-07-08-job-search-automation-design.md`).

2. **Resume**: check whether `resumes/<company-slug>.md` already exists
   (slug = company name, lowercased, spaces to underscores, matching the
   existing convention seen in `resumes/` — e.g. `jpmc.md`, `hypernet.md`).
   - If missing: draft it now following `RESUME_GUIDELINES.md` exactly —
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
     (`job_search.tracker.upsert` + `write_tracker`) with a `TrackerRow`
     carrying `company=<posting's company>`, `title=<posting's title>`,
     `location=<posting's location>`, `url=<posting's url>`,
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
     don't hand-edit the CSV. Every `TrackerRow` needs all seven fields:
     `company`, `title`, `location`, `url`, `status`, `fit_score`, `date` —
     `location` must match the posting's location exactly (same string used
     to build the queue), since `upsert`/`is_handled` key on normalized
     `(title, company, location)`, not on `url`.

7. Move to the next posting in the queue. Do not ask the user for permission
   to start the next one — the batch runs unattended through drafting and
   filling. The per-posting stop in step 5 is the review point, not a batch
   gate.

## After the queue is empty

Report a summary: total processed, how many reached `pending-review`, how
many are `needs-manual` (and which postings, so the user can apply to those
by hand), and the running total of `applied` status across all of
`job_search_tracker.csv` (not just this run — read the whole file).
