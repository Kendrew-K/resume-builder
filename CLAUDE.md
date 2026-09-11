# Working in this repo

Notes for a coding agent (Claude Code or similar) pointed at a fresh clone.
Everything here is plain files: Markdown in, Markdown, CSV and PDF out. There
is no server, no database and no account.

## First run

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp example_profile.md experiences.md
```

`experiences.md` is the user's own history and is gitignored. If the user
describes their background in conversation instead of editing the file, write
it into `experiences.md` yourself, following the shape of
[`example_profile.md`](example_profile.md). Only the skill terms in
`job_search/rank.py::SKILLS_VOCAB` affect scoring, so write real skills in
plain words rather than padding.

## The pipeline

```bash
python job_search_cli.py scrape    # find postings -> internships.md
python job_search_cli.py rank      # score each against experiences.md
python job_search_cli.py top -n 10 # best matches, highest fit first
python job_search_cli.py status    # applied / pending / manual
python job_search_cli.py applied <url>
python md_to_pdf.py <file>.md      # Markdown resume -> one-page PDF
```

`scrape` sweeps every keyword x location x source and polls a few hundred ATS
boards, so a full run takes tens of minutes. Narrow it while iterating:

```bash
JOB_SEARCH_KEYWORDS="Data Science Intern" JOB_SEARCH_LOCATIONS="Dallas, TX" \
  python job_search_cli.py scrape
```

Every other knob is an environment variable with a working default; the table
is in [`README.md`](README.md).

## Applying

[`docs/playbooks/apply-playbook.md`](docs/playbooks/apply-playbook.md) is the
procedure to follow when the user says "run apply". Read it in full before
starting. In short: build a queue from postings scoring >= 30% fit that the
tracker does not already know about, then per posting fetch the real posting
text, tailor a resume and cover letter, export both, and stop.

## Rules that are not negotiable

- **Never submit an application.** Every posting stops at the review screen for
  the user to submit or skip by hand. Filling a form is fine; pressing submit
  is not.
- **Never invent experience.** Everything in a generated resume has to trace
  back to `experiences.md`. If a posting wants something the user does not
  have, leave it out.
- **One page.** After every export, check
  `grep -a -o "/Count [0-9]*" <file>.pdf` reads `/Count 1`. If it does not,
  trim the least relevant bullets and export again.
- **Never commit personal data.** `experiences.md`, `resumes/`, the tracker CSV
  and the scrape caches are all gitignored for a reason. Do not add them, and
  do not paste their contents into a commit message.
- Follow [`RESUME_FORMAT.md`](RESUME_FORMAT.md) exactly for resume Markdown.
  The exporter's CSS is single-column with no tables or icons on purpose,
  because those are what break ATS parsers.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Every network call sits behind an injectable `fetch` parameter, so the suite
runs offline and finishes in under a second. Add a test with any change to
scoring, geocoding, dedupe or the Markdown round-trip.
