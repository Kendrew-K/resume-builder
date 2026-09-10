# Resume Markdown Format

What `md_to_pdf.py` expects, and why the layout is shaped this way. See
`example_resume.md` for a complete file you can export as-is.

## Structure

```markdown
# Your Name

email • phone • linkedin.com/in/you • github.com/you

## EDUCATION

### University Name, City, ST | May 2027
*B.S. in Your Major, GPA 3.9*

Relevant coursework: Course, Course, Course

## PROFESSIONAL EXPERIENCE

### Job Title | Jun 2025 – Present
*Company, City, ST*

- Verb-first bullet with a specific, real number.
- Another bullet.

## PROJECTS

### Project Name | 2025
*One-line framing of what it is*

- Bullet.

## SKILLS

**Languages:** Python, SQL, R
**Tools:** Power BI, Tableau, Git
```

## The conventions that matter

| Markdown | Renders as |
|---|---|
| `# Name` | Large header, letter-spaced, no rule |
| The paragraph right after `#` | Contact line, 10pt |
| `## SECTION` | Uppercase section header with a rule under it |
| `### Title \| Date` | Bold title left, date pushed right on the same line. The `\|` is what splits them |
| `*Italic line*` right after `###` | Subtitle: company, location, or degree |
| `- bullet` | Standard list item |

Two rules the parser is strict about:

1. **A list needs a blank line before it.** A `-` list placed directly under an
   italic line collapses and the bullets silently vanish from the PDF.
2. **The date separator is a literal `|` inside the `###` heading.** Without it
   the whole heading renders left-aligned with no date column.

## Why the layout is deliberately plain

The CSS in `md_to_pdf.py` is single-column with no tables, sidebars, icons,
graphics, or non-standard fonts. Those are the things that break applicant
tracking system parsers: a two-column layout in particular tends to get read in
the wrong order, interleaving your job titles with your skills. Standard section
names (Education, Experience, Skills, Projects) are used because ATS parsers
match on them.

Everything is tuned to fit one page at 9pt with 0.45in margins. If content
overflows, tighten the spacing values in the `CSS` string in `md_to_pdf.py`
before cutting real content.

## Checking the output

```bash
python md_to_pdf.py example_resume.md      # writes example_resume.pdf
```

Confirm it stayed on one page:

```bash
grep -a -o "/Count [0-9]*" example_resume.pdf     # want /Count 1
```
