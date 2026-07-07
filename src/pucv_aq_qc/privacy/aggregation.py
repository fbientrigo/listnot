"""Group aggregation for the statistical layer (docs/API_CONTRACT.md §2).

Aggregates numeric observations into group cells (n, mean, sd, p50). It is
deliberately generic over dict-like observations so it never depends on
operational DB models and can never select a subject pseudonym into output.
Aggregation only — never row-level data.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass


@dataclass(slots=True)
class GroupCell:
    group: dict[str, str]
    n: int
    mean: float | None = None
    sd: float | None = None
    p50: float | None = None
    suppressed: bool = False
    reason: str | None = None
    coarsened: bool = False

    def as_dict(self) -> dict:
        if self.suppressed:
            return {"group": self.group, "n": self.n, "status": "suppressed", "reason": self.reason}
        out: dict = {"group": self.group, "n": self.n, "mean": self.mean, "sd": self.sd, "p50": self.p50}
        if self.coarsened:
            out["coarsened"] = True
        return out


def _stats(values: list[float]) -> tuple[float | None, float | None, float | None]:
    if not values:
        return None, None, None
    mean = round(sum(values) / len(values), 4)
    sd = round(statistics.stdev(values), 4) if len(values) >= 2 else None
    p50 = round(statistics.median(values), 4)
    return mean, sd, p50


def aggregate(
    observations: list[dict],
    group_by: list[str],
    value_field: str = "value",
) -> list[GroupCell]:
    """Aggregate ``observations`` into group cells keyed by ``group_by`` fields.

    ``n`` is the number of observations in the group (group size). Statistics are
    computed over the non-null values in the group.
    """
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for obs in observations:
        key = tuple(str(obs.get(g, "")) for g in group_by)
        groups[key].append(obs)

    cells: list[GroupCell] = []
    for key, rows in sorted(groups.items()):
        group_label = dict(zip(group_by, key, strict=True))
        values = [r[value_field] for r in rows if r.get(value_field) is not None]
        mean, sd, p50 = _stats(values)
        cells.append(GroupCell(group=group_label, n=len(rows), mean=mean, sd=sd, p50=p50))
    return cells
