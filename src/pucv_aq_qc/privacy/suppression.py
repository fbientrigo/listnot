"""Small-group suppression (docs/PRIVACY_MODEL.md §10, API_CONTRACT §4).

Any cell with ``n < min_group_size`` is suppressed (values dropped, marked
"suppressed") or coarsened (small groups merged into one "OTRAS" bucket). Default
threshold is 10; there is no exception for "trusted" users in MVP.
"""

from __future__ import annotations

from dataclasses import dataclass

from pucv_aq_qc.privacy.aggregation import GroupCell, _stats

DEFAULT_MIN_GROUP_SIZE = 10
_SUPPRESS_REASON = "n_below_min_group_size"


@dataclass(slots=True)
class SuppressionResult:
    cells: list[GroupCell]
    suppressed_count: int
    all_suppressed: bool


def suppress(cells: list[GroupCell], min_group_size: int = DEFAULT_MIN_GROUP_SIZE) -> SuppressionResult:
    """Drop the statistics of any cell below the threshold, marking it suppressed."""
    out: list[GroupCell] = []
    suppressed = 0
    for cell in cells:
        if cell.n < min_group_size:
            out.append(
                GroupCell(group=cell.group, n=cell.n, suppressed=True, reason=_SUPPRESS_REASON)
            )
            suppressed += 1
        else:
            out.append(cell)
    non_empty = [c for c in cells if c.n > 0]
    all_suppressed = bool(non_empty) and suppressed == len(non_empty)
    return SuppressionResult(cells=out, suppressed_count=suppressed, all_suppressed=all_suppressed)


def coarsen(
    observations: list[dict],
    cells: list[GroupCell],
    min_group_size: int,
    value_field: str,
    group_by: list[str],
) -> SuppressionResult:
    """Merge all below-threshold groups into a single coarsened 'OTRAS' bucket.

    The merged bucket is only emitted if it itself reaches the threshold;
    otherwise it is suppressed. Above-threshold cells pass through unchanged.
    """
    kept: list[GroupCell] = [c for c in cells if c.n >= min_group_size]
    small = [c for c in cells if c.n < min_group_size]
    suppressed_count = 0

    if small:
        small_groups = {tuple(c.group.values()) for c in small}
        merged_values = [
            obs[value_field]
            for obs in observations
            if tuple(str(obs.get(g, "")) for g in group_by) in small_groups
            and obs.get(value_field) is not None
        ]
        merged_n = sum(c.n for c in small)
        label = {group_by[0]: f"OTRAS (n<{min_group_size} combinadas)"} if group_by else {"group": "OTRAS"}
        if merged_n >= min_group_size:
            mean, sd, p50 = _stats(merged_values)
            kept.append(
                GroupCell(group=label, n=merged_n, mean=mean, sd=sd, p50=p50, coarsened=True)
            )
        else:
            kept.append(GroupCell(group=label, n=merged_n, suppressed=True, reason=_SUPPRESS_REASON))
            suppressed_count += 1

    all_suppressed = all(c.suppressed for c in kept) if kept else False
    return SuppressionResult(cells=kept, suppressed_count=suppressed_count, all_suppressed=all_suppressed)
