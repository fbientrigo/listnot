"""Markdown report generation from aggregated QC + statistics."""

from __future__ import annotations

from datetime import UTC, datetime


def _fmt(value: float | None, digits: int = 2) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def render_markdown_report(
    *,
    campaign_name: str,
    campaign_id: str,
    counts: dict[str, int],
    qc_summary: list[dict],
    stats: dict,
) -> str:
    """Render a reproducible Markdown report. Aggregated data only."""
    lines: list[str] = []
    lines.append(f"# Reporte QC — {campaign_name}")
    lines.append("")
    lines.append(f"- **Campaña:** `{campaign_id}`")
    lines.append(f"- **Generado:** {datetime.now(UTC).isoformat(timespec='seconds')}")
    lines.append("- **Datos:** sintéticos · **RUT persistido:** false")
    lines.append("")
    lines.append("## Conteos")
    lines.append("")
    for key, value in counts.items():
        lines.append(f"- {key}: {value}")
    lines.append("")

    lines.append("## Control de calidad (por analito / nivel / lote)")
    lines.append("")
    lines.append("| Analito | Nivel | Lote | n | Media | DE | CV% | Estado | Flags |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for row in qc_summary:
        flags = ", ".join(f"{k}×{v}" for k, v in row.get("flags", {}).items()) or "—"
        lines.append(
            f"| {row['analyte_code']} | {row['control_level']} | {row.get('reagent_lot') or '—'} "
            f"| {row['n']} | {_fmt(row['mean'])} | {_fmt(row['sd'])} | {_fmt(row['cv_percent'])} "
            f"| {row['run_status']} | {flags} |"
        )
    lines.append("")

    lines.append(f"## Estadísticas agregadas (min_group_size = {stats.get('min_group_size')})")
    lines.append("")
    lines.append(f"Agrupado por: `{', '.join(stats.get('group_by', []))}`")
    lines.append("")
    lines.append("| Grupo | Analito | n | Media | DE | p50 | Estado |")
    lines.append("|---|---|---|---|---|---|---|")
    for g in stats.get("groups", []):
        group_label = ", ".join(f"{k}={v}" for k, v in g.get("group", {}).items())
        if g.get("status") == "suppressed":
            lines.append(f"| {group_label} | {g['analyte_code']} | {g['n']} | — | — | — | suprimido |")
        else:
            lines.append(
                f"| {group_label} | {g['analyte_code']} | {g['n']} | {_fmt(g.get('mean'))} "
                f"| {_fmt(g.get('sd'))} | {_fmt(g.get('p50'))} | ok |"
            )
    lines.append("")
    lines.append(
        f"_Celdas suprimidas por grupo pequeño: {stats.get('suppressed_group_count', 0)}._"
    )
    lines.append("")
    return "\n".join(lines)
