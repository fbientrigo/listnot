"""QC run-status logic and per-series/campaign summaries (docs/QC_MODEL.md §6).

Run status is the most-severe outcome across all rule hits for the run. Also
provides the CV-high and accepted-run TM messages.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from pucv_aq_qc.qc.levey_jennings import MeasurementLike, lj_series
from pucv_aq_qc.qc.metrics import ControlStats, control_stats
from pucv_aq_qc.qc.westgard import (
    _ANALYTE_ES,
    DEFAULT_CONFIG,
    RuleHit,
    WestgardConfig,
    evaluate,
)
from pucv_aq_qc.schemas.enums import RunStatus, Severity

# Severity ordering for "most severe wins".
_SEVERITY_RANK = {Severity.info: 0, Severity.warning: 1, Severity.reject: 2}


def run_status_from_hits(hits: list[RuleHit]) -> RunStatus:
    """Most-severe rule outcome → run status (docs/QC_MODEL.md §6)."""
    worst = max((_SEVERITY_RANK.get(Severity(h.severity), 0) for h in hits), default=0)
    if worst >= 2:
        return RunStatus.rejected
    if worst == 1:
        return RunStatus.warning
    return RunStatus.accepted


def cv_high_message(analyte_code: str, level: str, cv_obs: float, cv_max: float) -> str:
    analyte = _ANALYTE_ES.get(analyte_code, analyte_code)
    return (
        f"⚠️ La imprecisión (CV%) de {analyte} Nivel {level} superó el límite permitido "
        f"({cv_obs:.1f}% > {cv_max:.1f}%). Revise condiciones pre-analíticas y del equipo."
    )


def accepted_message(analyte_code: str) -> str:
    analyte = _ANALYTE_ES.get(analyte_code, analyte_code)
    return (
        f"✅ Corrida aceptada: todos los controles de {analyte} dentro de límites. "
        "Puede liberar resultados."
    )


@dataclass(slots=True)
class AnalyteQCSummary:
    analyte_code: str
    control_level: str
    reagent_lot: str | None
    stats: ControlStats
    run_status: RunStatus
    hits: list[RuleHit] = field(default_factory=list)
    flag_counts: dict[str, int] = field(default_factory=dict)
    cv_exceeded: bool = False

    def as_dict(self) -> dict:
        return {
            "analyte_code": self.analyte_code,
            "control_level": self.control_level,
            "reagent_lot": self.reagent_lot,
            "n": self.stats.n,
            "mean": self.stats.mean,
            "sd": self.stats.sd,
            "cv_percent": self.stats.cv_percent,
            "run_status": self.run_status.value,
            "flags": self.flag_counts,
            "cv_exceeded": self.cv_exceeded,
        }


def summarize_series(
    measurements: list[MeasurementLike],
    config: WestgardConfig = DEFAULT_CONFIG,
    allowable_cv: float | None = None,
) -> AnalyteQCSummary:
    """Summarize one (analyte, level, lot) series: stats + rules + run status."""
    series = lj_series(measurements)
    hits = evaluate(series, config)
    values = [p.value for p in series.points if p.valid]
    stats = control_stats(values)

    cv_exceeded = False
    if allowable_cv is not None and stats.cv_percent is not None:
        cv_exceeded = stats.cv_percent > allowable_cv

    status = run_status_from_hits(hits)
    if cv_exceeded and status is RunStatus.accepted:
        status = RunStatus.warning

    return AnalyteQCSummary(
        analyte_code=series.analyte_code,
        control_level=series.control_level,
        reagent_lot=series.reagent_lot,
        stats=stats,
        run_status=status,
        hits=hits,
        flag_counts=dict(Counter(h.rule_code for h in hits)),
        cv_exceeded=cv_exceeded,
    )


def summarize_campaign(
    measurements: list[MeasurementLike],
    config: WestgardConfig = DEFAULT_CONFIG,
    allowable_cv: dict[str, float] | None = None,
) -> list[AnalyteQCSummary]:
    """Group measurements by (analyte, level, lot) and summarize each series."""
    groups: dict[tuple, list[MeasurementLike]] = defaultdict(list)
    for m in measurements:
        key = (m.analyte_code, m.control_level, getattr(m, "reagent_lot", None))
        groups[key].append(m)

    summaries: list[AnalyteQCSummary] = []
    for (analyte, _level, _lot), series_measurements in sorted(groups.items(), key=lambda kv: kv[0]):
        cv_limit = (allowable_cv or {}).get(analyte)
        summaries.append(summarize_series(series_measurements, config, cv_limit))
    return summaries
