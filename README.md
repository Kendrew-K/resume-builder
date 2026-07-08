# Resume Builder

A file-based resume system. No servers, no apps to run.

## How it works
1. **`experiences.md`** — your master file. Everything about you lives here, raw.
2. When you want a resume, tell me the **company or role**. I pull from the master
   file, pick the most relevant experiences, rewrite them to be detailed and
   professional, and generate a tailored resume in **`resumes/`**.
3. Each resume is saved as Markdown (`resumes/<company>.md`) and ALWAYS exported to PDF
   via `python md_to_pdf.py resumes/<company>.md` (headless Chrome, one-page ATS-safe layout).

## Your part
- Fill in `experiences.md` (or just paste raw info in chat — I'll file it).
- Later, name a company/role and I build the resume.

## ATS keyword-gap check (always run on every tailored resume)
After building a tailored resume, I run an inline ATS check (no app, no self-hosting):
1. Pull the key terms from the target job description (skills, tools, titles, must-have keywords).
2. Check which of those the tailored resume actually covers.
3. List the missing/weak keywords and an honest overlap estimate.
4. Suggest where to naturally add the missing ones (only if truthful for Kendrew).

Keep layout ATS-safe: single column, standard section names (Experience, Education,
Skills, Projects), no tables/sidebars/icons/graphics, standard font, one page.

## Writing rules (avoid AI-generated tells)
- No em dashes anywhere. En dashes in date ranges (2024–2025) are fine.
- No vague filler ("leveraged synergies", "passionate about driving impact").
- Verb-first bullets with real, specific metrics. Vary bullet rhythm/length.
- Never fabricate metrics; mark ventures honestly (concept/pre-launch/no revenue).

## Why not the Reactive Resume app?
It's a full self-hosted stack (Docker + Postgres + storage + headless Chrome)
just to store data and export PDFs. This does the same job with plain files.
If you ever want their visual templates, I can output Reactive Resume JSON you
import at rxresu.me — no self-hosting needed.
