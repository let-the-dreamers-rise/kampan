"""Render docs/REPORT.md to docs/REPORT.html (images resolved relative to docs/). Print to PDF with a headless browser:

    msedge --headless --print-to-pdf=docs/REPORT.pdf --no-pdf-header-footer docs/REPORT.html

Needs the `markdown` package (dev only, not in the Lambda image).
"""
from pathlib import Path

import markdown

CSS = """
body { font-family: Georgia, 'Times New Roman', serif; max-width: 46rem; margin: 2rem auto; padding: 0 1rem;
       color: #1a1a1a; line-height: 1.5; font-size: 11pt; }
h1 { font-size: 20pt; line-height: 1.2; } h2 { font-size: 14pt; margin-top: 1.6em; } h3 { font-size: 12pt; }
table { border-collapse: collapse; margin: 0.8em 0; font-size: 9.5pt; }
th, td { border: 1px solid #bbb; padding: 3px 6px; text-align: left; vertical-align: top; }
th { background: #f0f0f0; }
img { max-width: 100%; }
code { font-family: Consolas, monospace; font-size: 9.5pt; }
@page { size: A4; margin: 16mm; }
"""


def main() -> None:
    src = Path("docs/REPORT.md")
    body = markdown.markdown(src.read_text(encoding="utf-8"), extensions=["tables"])
    html = f"<!doctype html><html><head><meta charset='utf-8'><title>Kampan report</title><style>{CSS}</style></head>" \
           f"<body>{body}</body></html>"
    Path("docs/REPORT.html").write_text(html, encoding="utf-8")
    print("wrote docs/REPORT.html")


if __name__ == "__main__":
    main()
