"""Reproducible reports from aggregated data (Markdown / HTML).

Reports embed only aggregated, suppression-safe data — never a raw RUT or a
subject pseudonym (docs/SDD.md §4).
"""

from pucv_aq_qc.reporting.html_report import render_html_report
from pucv_aq_qc.reporting.markdown_report import render_markdown_report

__all__ = ["render_markdown_report", "render_html_report"]
