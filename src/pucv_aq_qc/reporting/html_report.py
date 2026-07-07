"""HTML report generation (prints to PDF; no wkhtmltopdf/Chromium dependency)."""

from __future__ import annotations

import html

from pucv_aq_qc.reporting.markdown_report import render_markdown_report

_STYLE = """
body { font-family: system-ui, sans-serif; max-width: 60rem; margin: 2rem auto; padding: 0 1rem; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
th, td { border: 1px solid #ccc; padding: 4px 8px; text-align: left; font-size: 0.9rem; }
th { background: #f3f4f6; }
h1, h2 { color: #1f2937; }
.suppressed { color: #9ca3af; font-style: italic; }
""".strip()


def _md_table_to_html(lines: list[str], i: int) -> tuple[str, int]:
    """Convert a contiguous Markdown table starting at index i to HTML."""
    header = [c.strip() for c in lines[i].strip().strip("|").split("|")]
    rows_html = ["<tr>" + "".join(f"<th>{html.escape(c)}</th>" for c in header) + "</tr>"]
    j = i + 2  # skip header + separator
    while j < len(lines) and lines[j].lstrip().startswith("|"):
        cells = [c.strip() for c in lines[j].strip().strip("|").split("|")]
        rows_html.append("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in cells) + "</tr>")
        j += 1
    return "<table>" + "".join(rows_html) + "</table>", j


def render_html_report(**kwargs) -> str:
    """Render an HTML report from the same inputs as the Markdown report."""
    md = render_markdown_report(**kwargs)
    lines = md.splitlines()
    body: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("# "):
            body.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            body.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.lstrip().startswith("|"):
            table_html, i = _md_table_to_html(lines, i)
            body.append(table_html)
            continue
        elif line.startswith("- "):
            body.append(f"<p>{html.escape(line[2:])}</p>")
        elif line.strip():
            body.append(f"<p>{html.escape(line)}</p>")
        i += 1
    return (
        "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
        f"<title>Reporte QC</title><style>{_STYLE}</style></head><body>"
        + "".join(body)
        + "</body></html>"
    )
