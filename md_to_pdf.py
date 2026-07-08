#!/usr/bin/env python
"""Convert a resume Markdown file to an ATS-safe one-page PDF via headless Chrome.
Usage: python md_to_pdf.py resumes/hypernet.md
"""
import sys, subprocess, tempfile, os, pathlib, re
import markdown

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

CSS = """
@page { size: letter; margin: 0.45in; }
* { box-sizing: border-box; }
body { font-family: Arial, Helvetica, sans-serif; font-size: 9pt; line-height: 1.13;
       color: #000; max-width: 100%; margin: 0; }
h1 { font-size: 25pt; font-weight: 400; margin: 0; letter-spacing: 1px; }
h1 + p { font-size: 10pt; color: #000; margin: 2px 0 5px; }
h2 { font-size: 10pt; font-weight: 400; border-bottom: 1px solid #000; padding-bottom: 2px;
     margin: 7px 0 3px; text-transform: uppercase; letter-spacing: 2px; }
/* job-title header row: bold title left, date right on same line */
h3 { font-size: 10pt; margin: 4px 0 0; display: flex; justify-content: space-between;
     align-items: baseline; gap: 12px; }
h3 .date { font-weight: 700; white-space: nowrap; }
h3 + p { margin: 0; font-style: italic; font-weight: 400; font-size: 9pt; }
ul { margin: 1px 0 2px; padding-left: 18px; }
li { margin: 0; }
p { margin: 2px 0; }
a { color: #000; text-decoration: none; }
"""

def main(md_path):
    md_path = pathlib.Path(md_path).resolve()
    html_body = markdown.markdown(md_path.read_text(encoding="utf-8"))
    # "### Title | Date" -> flex row with the date pushed right (matches resume template)
    html_body = re.sub(r"<h3>(.*?)\s*\|\s*(.*?)</h3>",
                       r'<h3><span>\1</span><span class="date">\2</span></h3>', html_body)
    html = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{html_body}</body></html>"
    tmp_html = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8")
    tmp_html.write(html); tmp_html.close()
    pdf_path = md_path.with_suffix(".pdf")
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf_path}", "file:///" + tmp_html.name.replace(os.sep, "/")],
                   check=True, capture_output=True)
    os.unlink(tmp_html.name)
    print(f"Wrote {pdf_path}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "resumes/hypernet.md")
