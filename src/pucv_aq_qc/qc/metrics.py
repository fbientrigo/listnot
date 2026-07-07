"""Control statistics: mean, sample SD, CV% (docs/QC_MODEL.md §4)."""

from __future__ import annotations

import statistics
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ControlStats:
    n: int
    mean: float
    sd: float | None  # None when n < 2
    cv_percent: float | None  # None when n < 2 or mean == 0


def control_stats(values: list[float]) -> ControlStats:
    """Compute n, mean, sample SD (n-1), and CV% over a window of QC values."""
    n = len(values)
    if n == 0:
        return ControlStats(n=0, mean=0.0, sd=None, cv_percent=None)
    mean = sum(values) / n
    if n < 2:
        return ControlStats(n=n, mean=mean, sd=None, cv_percent=None)
    sd = statistics.stdev(values)  # sample SD, n-1 denominator
    cv = None if mean == 0 else 100.0 * sd / mean
    return ControlStats(n=n, mean=mean, sd=sd, cv_percent=cv)
