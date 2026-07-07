"""QC engine: Levey-Jennings, metrics (mean/SD/CV), Westgard rules, run status.

Consumes QC measurements and emits rule hits + a run status with TM-readable
Spanish messages (docs/QC_MODEL.md). The engine describes analytical
performance; it makes no clinical decisions.
"""

from pucv_aq_qc.qc.levey_jennings import LJPoint, LJSeries, lj_series
from pucv_aq_qc.qc.metrics import ControlStats, control_stats
from pucv_aq_qc.qc.summary import (
    AnalyteQCSummary,
    run_status_from_hits,
    summarize_campaign,
    summarize_series,
)
from pucv_aq_qc.qc.westgard import RuleHit, WestgardConfig, evaluate

__all__ = [
    "LJPoint",
    "LJSeries",
    "lj_series",
    "ControlStats",
    "control_stats",
    "RuleHit",
    "WestgardConfig",
    "evaluate",
    "AnalyteQCSummary",
    "run_status_from_hits",
    "summarize_series",
    "summarize_campaign",
]
