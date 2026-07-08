# Job search automation: Brainstorm / Discovery Notes
Date: 2026-07-08 · Goal: stress-test the scrape/rank/apply design (docs/specs/2026-07-08-job-search-automation-design.md) before writing implementation plan.

## Summary / key decisions (final)
- **Scrape**: no login/credentials anywhere. Sources: LinkedIn jobs-guest, Indeed, Glassdoor, ZipRecruiter — all public/unauthenticated, parallel fetch, each source independently allowed to fail/degrade (Indeed/Glassdoor likely to block, that's expected not fatal).
- **Output**: fully overwrites `fall_2026_internships.md` each scrape run (old "Recheck plan" section explicitly OK to lose).
- **Rank**: fit% = (posting's required+preferred skills matched in experiences.md) / (total required+preferred skills found in posting), unweighted. Hard cutoff at exactly 30%.
- **Location filter**: within 20 miles of <HOME_ADDRESS>, OR fully remote. Relocation-required postings excluded entirely from this round.
- **Apply pipeline** (per posting, >=30% fit only): (1) parse posting text closely for what's being asked (no web search), (2) auto-draft tailored resume via existing README.md pipeline if missing, (3) auto-draft cover letter via a NEW pipeline (same writing rules, 1-page hard limit, same verify-and-trim-if-overflow approach as the resume CSS/PDF flow), (4) export both to PDF, (5) Playwright opens the form, fills known fields + uploads both PDFs, (6) stops at review screen — never auto-submits.
- **Bulk mode**: apply runs unattended across the whole >=30%-fit queue — no per-posting permission needed to start drafting/filling, but each one still stops at its own review screen before submit. Manually triggered only, never scheduled/cron (user needs to be free to sit through review screens).
- **Failure handling**: unsupported ATS or unparseable form -> skip, log to a "needs manual apply" list, continue the queue. Running applied-count tracked and reported.
- **Persistence**: new file, NOT overwritten by scrape (e.g. `job_search_tracker.csv`) — company/title/url -> status (applied/skipped/needs-manual/pending), fit_score, date. Scrape cross-references it so re-runs don't reprocess already-applied postings.

## Q&A log

### Q1 — LinkedIn discovery method
- Asked: is the public unauthenticated `jobs-guest` endpoint (urllib fetch) actually going to work, given prior boards all 403'd/stale-cached?
- Captured: user has used Playwright before with LinkedIn and it worked *logged in* with credentials. This overturns the design's core assumption — scrape should NOT be an unauthenticated `urllib` call to the public guest endpoint. It should be Playwright driving a real logged-in LinkedIn session.
- Flags: credential storage method (env var vs other) -> next question. LinkedIn ToS risk on automated logged-in scraping (account flag/ban risk) -> needs explicit user acknowledgment, not silently absorbed into design.

### Q2 — ban risk acceptance
- Asked: accept LinkedIn ToS/ban risk from logged-in automated scraping, or cap volume/frequency to reduce it?
- Captured: user does NOT want to risk account ban. Wants "mass search" instead. **Reverses Q1** — no login/credentials at all. Back to unauthenticated approach, but framed as "mass search" not single-source guest-endpoint call — needs clarification on what sources/breadth this covers.
- Flags: what exactly "mass search" means (breadth of sources? aggregator sites? multiple public endpoints in parallel?) -> next question.

### Q3 — mass search breadth
- Asked: confirm "mass search" = LinkedIn public jobs-guest (no login) + Indeed public search + Glassdoor/ZipRecruiter public search, parallel per run, each source allowed to independently fail/degrade.
- Captured: confirmed. Scrape source list locked: LinkedIn (guest), Indeed, Glassdoor, ZipRecruiter — all unauthenticated, no credentials anywhere in this system.

## Summary / key decisions
- No login/credentials anywhere (Q1 reversed by Q2). Pure unauthenticated public-endpoint scraping.
- Sources: LinkedIn jobs-guest, Indeed, Glassdoor, ZipRecruiter — public search pages, parallel fetch, per-source graceful degrade on block.

### Q4 — resume file for apply step
- Asked: does apply require the tailored resume to already exist, or fall back to generic?
- Captured: neither — apply should auto-generate the company-tailored resume on the spot, mid-application, if it doesn't exist yet. **Scope shift from earlier session decision** ("I already have creating resume and cover letter myself" was said when deciding to skip the ai-job-search repo's LaTeX drafting machinery). Reconciled: this doesn't reopen that — it means reusing the EXISTING chat-driven pipeline already documented in README.md (pull from experiences.md, tailor, output resumes/<company>.md, PDF via md_to_pdf.py, inline ATS check), just auto-triggered by `apply` instead of the user asking for it by name each time. Not building new resume-drafting logic.
- Flags: does the same auto-trigger apply to cover letters too? -> next question.

### Q5 — cover letter auto-trigger
- Asked: does apply also auto-draft cover letter on the spot, same as resume?
- Captured: yes. New pipeline needed — repo currently has no cover-letter process (README.md only documents the resume pipeline). Mirrors resume pattern: pull from experiences.md + job posting text, write cover letter, export PDF, same writing rules (no em dash, no filler, verb-first, honest/no fabrication) already established in README.md.
- Flags: storage/naming convention (mirror resumes/<company>.md -> cover_letters/<company>.md?) -> next question.

## Summary / key decisions
- No login/credentials anywhere. Sources: LinkedIn jobs-guest, Indeed, Glassdoor, ZipRecruiter, unauthenticated, parallel, per-source graceful degrade.
- `apply <url>` now does MORE than form-fill: on the spot, it (1) auto-drafts tailored resume via existing README.md pipeline if missing, (2) auto-drafts a NEW cover letter pipeline (same rules, doesn't exist yet, needs building), (3) exports both to PDF, (4) THEN opens Playwright, fills form fields + uploads both PDFs, (5) stops at review screen, never submits.

### Q6 — reviewer-agent critique step
- Asked: full two-pass drafter-reviewer (draft, then second agent critiques/revises), or single-pass since user reviews at the browser confirmation screen anyway?
- Captured: wants company research done FIRST, before drafting — so the draft itself is informed by what the company's looking for, not a separate post-hoc critique pass. This reads as single-pass but research-informed: research company -> draft resume+cover letter using that research + experiences.md + posting text -> export PDFs -> fill form. Not a two-agent drafter/reviewer split.
- Flags: confirm this reading (research-then-draft, not draft-then-critique) -> next question. Also: what counts as "company research" (web search for mission/values/recent news? just re-reading the posting closely? both?) -> next question.

### Q7 — what "research" means
- Asked: confirm research-then-draft ordering, and how deep should company research go (web search vs just posting text)?
- Captured: no web search needed. "Research" = read the job description closely, extract what the company's actually looking for (required skills, tools, phrasing, priorities) from the posting text itself. Simpler than the reference repo's reviewer-agent web-research step.
- Flags: none, resolved.

## Summary / key decisions
- `apply <url>` pipeline: (1) parse posting text closely to extract what's being asked for, (2) draft tailored resume via existing README.md pipeline if missing, (3) draft cover letter (new pipeline, same writing rules), informed by (1), (4) export both to PDF, (5) Playwright opens form, fills fields + uploads both PDFs, (6) stops at review screen, never submits. Single-pass, no web search, no second reviewer agent.

### Q8 — cover letter storage
- Asked: mirror resumes/<company>.md -> cover_letters/<company>.md, PDF export via extended/new script?
- Captured: yes, confirmed.

### Q9 — rank threshold
- Asked: cut low-fit postings below a score threshold, or show everything ranked?
- Captured: answer didn't address threshold — user said "apply to every job that i can apply to." Reads as a DIFFERENT scope change: apply should run in bulk across all (qualifying?) postings automatically, not be manually triggered one URL at a time by the user picking from the ranked list. Needs disambiguation before locking in -> next question.

### Q10 — bulk-apply threshold + loop behavior
- Asked: fit threshold for bulk apply, and does it loop unattended or wait between jobs?
- Captured: threshold set — apply to any posting scoring 30% fit or above. Loop-behavior part still unconfirmed -> next question.

## Summary / key decisions
- `rank` fit threshold: 30%. Anything scoring below 30% is excluded from bulk apply (still shown in the ranked list, just not auto-applied to).
- `apply` now has a bulk mode: run the full draft-research-fill pipeline across every qualifying (>=30% fit) posting, not just one URL at a time.

### Q11 — loop confirmation behavior
- Asked: unattended loop, or pause between postings?
- Captured: unattended for draft+fill stage (no permission needed to start each posting). Per posting: after filling all info, stop at that posting's review screen (existing never-auto-submit rule) — that stop is per-application, not a gate blocking the batch from continuing. Resolves cleanly with earlier "never auto-submit" rule: batch just runs the queue, each stop is that job's final review point, script keeps moving through the queue.

## Summary / key decisions
- Bulk apply = queue of all >=30%-fit postings, processed unattended (draft+research+fill each without asking to start), each one stops at its own browser review screen before submit (never auto-submits), then continues to the next queued posting.

### Q12 — applied tracking across overwrites
- Asked: persist "applied/skipped" status across scrape overwrites so re-runs don't reprocess the same posting?
- Captured: yes, confirmed. Needs a persistent state file SEPARATE from fall_2026_internships.md (which gets fully overwritten each scrape) — a dedupe key (company+title+url or similar) that survives across runs, marks status (applied/skipped/pending), and bulk-apply queue excludes anything already marked applied.

## Summary / key decisions
- New persistent file needed: applied-status log, NOT overwritten by scrape (unlike fall_2026_internships.md). Tracks company/title/url -> status. Scrape cross-references against it; bulk apply skips anything already applied.

### Q13 — mid-batch failure handling
- Asked: skip unsupported-ATS postings and continue, or halt batch?
- Captured: skip and continue, confirmed. Plus two additions: (1) unsupported/failed postings get logged separately as "needs manual apply" so nothing silently falls through the cracks, (2) running total count of how many jobs were successfully applied to in the batch (or overall) needs to be tracked and reported.

## Summary / key decisions
- Batch apply failure mode: skip, log to a "needs manual apply" list, continue queue. Track and report applied-count (total, and probably per-run).

### Q14 — Recheck plan section fate
- Asked: preserve the "Recheck plan" section before overwrite, or fine to lose?
- Captured: fine to lose, doesn't matter to user.

### Q15 — trigger cadence
- Asked: manual trigger only, or scheduled/cron?
- Captured: manual only. User needs to be free/available to sit through the review-screen stops, so it's not something that should run unattended on a timer.

## Summary / key decisions
- Manual trigger only. No cron/scheduling.

### Q16 — remaining open items
- Asked: page limits, fit-threshold precision, location scope.
- Captured: (1) resume AND cover letter each must be exactly 1 page, hard rule. (2) 30% fit is a literal on-the-dot cutoff, not approximate. (3) location must be close to Dallas, TX or remote — relocation-required postings are out of scope for this Fall application round.
- Flags: mechanism for enforcing 1-page (verify-and-trim loop vs trust the CSS?) -> next question. Exact formula for the 30% fit score (numerator/denominator) -> next question. Exact radius/definition of "close to Dallas" -> next question.

## Summary / key decisions
- Resume + cover letter: hard 1-page limit each.
- Fit threshold: exactly 30%, literal cutoff for bulk-apply inclusion.
- Location scope: DFW-area or remote only. Relocation-required postings excluded from this round.

### Q17 — 1-page enforcement mechanism
- Asked: verify PDF page count and trim-loop if overflow, or trust CSS sizing?
- Captured: yes, verify-and-trim loop confirmed. Reuse existing resume CSS approach for new cover letter script too.

### Q18 — fit-score formula
- Asked: (required+preferred skills matched) / (total required+preferred skills in posting) = fit%, unweighted, 30%+ threshold. Confirm or weight required higher than preferred?
- Captured: confirmed as-is, no extra weighting needed.

### Q19 — Dallas radius
- Asked: DFW metroplex broadly, or a specific radius?
- Captured: 20 miles, specific radius, not the loose DFW-metro definition.
- Flags: 20 miles from WHERE exactly (downtown Dallas? UTD Richardson campus? current home address?) -> next question.

## Summary / key decisions
- Location filter: within 20 miles of an anchor point (TBD which one), or remote. Not DFW-metro-broadly, not all-Texas.

### Q20 — radius anchor point
- Asked: downtown Dallas, UTD campus, or home address?
- Captured: home address — <HOME_ADDRESS>. Geocode this once, use as the 20-mile radius center for all location filtering.

## Summary / key decisions
- Location filter anchor: <HOME_ADDRESS> (home address), 20-mile radius, or fully remote. Everything else excluded from this Fall 2026 round.

## Open flags (pending input)
- Exact file/format for the applied-status log — implementation-level decision, not a design branch requiring further user input. Will lock in plan: persistent CSV (job_search_tracker.csv), columns: company, title, url, status (applied/skipped/needs-manual/pending), fit_score, date. Not asking further.
