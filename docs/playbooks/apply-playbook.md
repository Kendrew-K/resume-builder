# Apply playbook

Followed by Claude when the user says "run apply." Processes every posting in
`fall_2026_internships.md` scoring >= 30% fit (see `job_search/rank.py`
`FIT_THRESHOLD`) that isn't already recorded in `job_search_tracker.csv`
(any status except plain `pending` counts as already worked, so nothing is
applied to twice). Never auto-submits — every posting stops at the
browser review screen for the user to submit or skip by hand.

## Build the queue

1. Read `fall_2026_internships.md`, parse rows with `job_search.markdown_output.parse_internships_md`.
2. Read `job_search_tracker.csv` with `job_search.tracker.read_tracker`.
3. Queue = postings where `fit_score >= 0.30` AND
   `job_search.tracker.is_handled(tracker, title, company, location)` is `False`.
   (The tracker is keyed by normalized `(title, company, location)` — the
   same identity `job_search.posting.dedupe_postings` uses — not by URL, so a
   posting already recorded is recognized even if it resurfaces under a
   different URL from another source. `is_handled` covers every status in
   `job_search.tracker.HANDLED_STATUSES`: `applied` and `skipped` are final,
   and `pending-review`/`needs-manual` mean the form was already filled or
   handed off, so re-queueing them would apply a second time.)

   Run `python job_search_cli.py status` to see the whole tracker grouped by
   status before starting.
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

4. **Navigate to the real application URL, then detect the ATS platform.**
   Browser control for steps 4 and 5 is the **Claude in Chrome** extension,
   driving the user's own already-open, already-logged-in Chrome — not
   Playwright. If no Chrome tools are present in the session, stop the whole
   run and tell the user to restart Claude Code with Claude in Chrome enabled
   (`claude --chrome`, or the "Claude in Chrome enabled by default" toggle in
   `/config`) with the Claude extension pinned and connected in Chrome. Do not
   silently fall back to Playwright.

   The scraped `url` is the aggregator's search-result/listing page
   (linkedin.com/jobs/view/..., glassdoor.com/job-listing/...,
   indeed.com/viewjob?..., etc) — it is NEVER the company's actual
   application form. The real Workday/Greenhouse/Lever link only appears
   after clicking "Apply" on that aggregator page, one navigation hop
   deeper. Detecting the ATS from the scraped `url` directly will never
   match anything and every posting will wrongly fall through to
   `needs-manual`. Instead:
   - Navigate to the posting's scraped `url`.
   - If the page is an authwall / login-required gate (e.g. LinkedIn's
     `linkedin.com/authwall?...` redirect) or a "job not found / expired"
     placeholder page (e.g. Glassdoor's "Job is OOO"): stop for this
     posting. Update the tracker with `status="needs-manual"` (reason:
     unreachable without login, or listing expired) and move on. **Never
     ask the user for a password or attempt to submit login credentials
     through the form** — if login is required, this playbook does not
     authenticate on the user's behalf. (The browser runs on the user's
     own logged-in Chrome profile, so an authwall here means the session
     really is signed out — don't try to sign in.)
   - Otherwise, read the page and look for an "Apply" / "Apply now" /
     "Easy Apply" link or button. Click through it (following any
     intermediate redirect) until the URL stabilizes on either an external
     company careers page or a LinkedIn/aggregator-native "Easy Apply"
     modal.
   - Now check the STABILIZED URL for the ATS platform:
     - `myworkdayjobs.com` in the URL -> Workday
     - `greenhouse.io` in the URL -> Greenhouse
     - `lever.co` in the URL -> Lever
     - a same-site "Easy Apply" modal (no navigation to an external ATS) ->
       **unsupported for now** — this playbook does not yet drive
       aggregator-native apply modals, only external Workday/Greenhouse/Lever
       forms.
     - anything else -> **unsupported**.
   - For any unsupported case: update the tracker
     (`job_search.tracker.upsert` + `write_tracker`) with a `TrackerRow`
     carrying `company=<posting's company>`, `title=<posting's title>`,
     `location=<posting's location>`, `url=<posting's url>`,
     `status="needs-manual"`, `fit_score=<the posting's score>`,
     `date=<today>`. Move to the next posting in the queue. Do not attempt
     to guess-fill an unrecognized form.

5. **Fill the form** (Workday/Greenhouse/Lever only) using the same Claude in
   Chrome tools from step 4 (read the actual tool names off the session's tool
   list — don't guess them):
   - Already navigated to the real application URL in step 4 — continue
     from there.
   - Read the page to see the current form state.
   - Type/fill the fields the profile can answer confidently: full name,
     email (`<EMAIL>`), phone (`<PHONE>`), LinkedIn
     (`<LINKEDIN>`), GitHub (`github.com/Kendrew-K`).
   - Upload the resume PDF (`resumes/<company-slug>.pdf`) and cover letter
     PDF (`resumes/<company-slug>_cover_letter.pdf`) on whichever fields
     accept them. A file picker opened by the extension is an OS-level dialog
     the browser tools cannot drive: if there is no upload tool that takes a
     path, do NOT click the upload button. Fill everything else first, then
     print the two absolute PDF paths and ask the user to drag them onto the
     upload fields themselves before they review. Keep going with the rest of
     the form either way — a missing upload is not a reason to abandon the
     posting.
   - If the ATS has a "My Experience" section with Work Experience/Education/
     Languages/Skills entries (Workday does), fill those in too from
     `experiences.md`: both paid roles AND relevant club/leadership
     activities (Business Leadership Community, National Model United
     Nations, Bellevue Indonesian Club, etc.) when the activity is relevant
     to the posting (leadership, event/budget management, cross-functional
     collaboration). Don't add every club reflexively, only ones that
     strengthen the fit for that specific role.
   - If Workday exposes a separate "Extracurricular Activities" subsection
     (distinct from Work Experience), put the relevant club/leadership
     entries there too.
   - Fill the Skills field, don't leave it blank. If the autocomplete
     doesn't filter on typed text, try selecting an option against the
     underlying listbox, or click into the unfiltered list and pick the
     closest matching skill from `experiences.md`'s Technical Skills list
     (Python, SQL, Java, Machine Learning, Power BI, etc.) rather than
     skipping it.
   - Answer repeated screener questions (sponsorship, background check, remote
     willingness, skill yes/no) from `application_answers.md`, which records
     Kendrew's confirmed answers. Never guess one that is not in that file, and
     never invert an answer to fit a differently-worded question — confirm instead.
   - Draft the open-text company questions ("Why do you want to work here?",
     "Why this role?") from the posting text and `experiences.md`, then tell the
     user they are drafts to edit in his own voice before submitting. Leave the
     items listed under "Always leave for Kendrew" in `application_answers.md`
     (course credit, salary, dates, consent checkboxes, EEO) untouched.
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
   - `status="applied"` is never set here — only the user pressing submit makes
     a posting applied. After they submit, they (or Claude at their request)
     run `python job_search_cli.py applied <url> [<url> ...]`, which flips
     those rows to `applied`. That works even though the posting has by then
     dropped out of `fall_2026_internships.md` — `applied` falls back to
     matching the tracker row by URL.

7. **Ping the user.** Send a `PushNotification` the moment a posting needs his
   hands: reached the review screen and waits on submit, or hit an item from
   "Always leave for Kendrew", a required upload, or an answer not in
   `application_answers.md`. One line, under 200 chars, lead with the company
   and what he must do — e.g. `Hone Health SWE intern: review screen ready,
   needs your submit`. The tool self-suppresses when he is watching the
   terminal, so send it every time rather than guessing whether he stepped away.

8. Move to the next posting in the queue. Do not ask the user for permission
   to start the next one — the batch runs unattended through drafting and
   filling. The per-posting stop in step 5 is the review point, not a batch
   gate.

## After the queue is empty

Send one final `PushNotification` with the run totals, then report a summary: total processed, how many reached `pending-review`, how
many are `needs-manual` (and which postings, so the user can apply to those
by hand), and the running total of `applied` status across all of
`job_search_tracker.csv` (not just this run — read the whole file).

## Microsoft careers gotchas (learned 2026-09-06)

- Uploading a resume **re-parses it and overwrites the Contact Information
  section**. If the resume has no street address on it, Microsoft blanks
  Address / Country / State / City / Zip. Re-upload late in the process and you
  must refill contact afterwards. Fill contact AFTER the resume, never before.
- Field-level "Error: X cannot be left blank" messages go stale: the value is
  present and saved but the error label persists. Reloading the apply URL
  (`apply.careers.microsoft.com/careers/apply?pid=...`) clears them. Drafts are
  saved server-side, so reloading loses nothing.
- Microsoft carries EEO answers, disability, and the background/integrity
  questions across applications automatically once one application has them.
  Work authorization and job-specific questions do NOT carry over; refill per
  application.
- Microsoft asks US applicants to redact graduation and attendance dates.
  `resumes/microsoft_swe.md` has the education date removed for this reason.
  It is a request, not a disqualifier, and the screener questions capture
  eligibility separately.
- To check whether a req was actually submitted, open
  `apply.careers.microsoft.com/careers/job?pid=...`. A submitted one shows
  "You have already applied for this position"; a draft still shows "Apply now".
