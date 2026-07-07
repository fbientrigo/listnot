"""Export policy enforcement (docs/PRIVACY_MODEL.md §10, API_CONTRACT §2,§4).

Aggregated-only exports with small-group suppression. The only subject
identifier permitted in an export is ``export_subject_uid`` (per-export
namespaced); ``study_subject_uid`` / ``person_uid_global`` must never appear.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from pucv_aq_qc.identity import hmac_id
from pucv_aq_qc.privacy.aggregation import aggregate
from pucv_aq_qc.privacy.suppression import DEFAULT_MIN_GROUP_SIZE, suppress

DEFAULT_POLICY_NAME = "aggregated-min-group-v1"


@dataclass(slots=True)
class ExportResultData:
    policy_name: str
    min_group_size: int
    rows: list[dict] = field(default_factory=list)
    suppressed_cells: int = 0
    all_suppressed: bool = False


def namespace_subject_uids(study_uids: list[str], export_id: str, secret: bytes) -> list[str]:
    """Derive per-export ``euid_…`` values (defense in depth for any future
    per-subject export path). Blocks cross-export linkage."""
    return [hmac_id.export_subject_uid(s, export_id, secret) for s in study_uids]


def build_aggregated_export(
    observations: list[dict],
    *,
    group_by: list[str],
    analytes: list[str],
    min_group_size: int = DEFAULT_MIN_GROUP_SIZE,
    value_field: str = "value",
    analyte_field: str = "analyte_code",
    policy_name: str = DEFAULT_POLICY_NAME,
) -> ExportResultData:
    """Aggregate per (group, analyte), apply suppression, and return safe rows."""
    rows: list[dict] = []
    suppressed_total = 0
    any_visible = False

    for analyte in analytes:
        obs_a = [o for o in observations if o.get(analyte_field) == analyte]
        cells = aggregate(obs_a, group_by, value_field)
        result = suppress(cells, min_group_size)
        suppressed_total += result.suppressed_count
        for cell in result.cells:
            row = {**cell.group, "analyte_code": analyte, "n": cell.n}
            if cell.suppressed:
                row.update({"mean": None, "sd": None, "p50": None, "status": "suppressed"})
            else:
                any_visible = True
                row.update({"mean": cell.mean, "sd": cell.sd, "p50": cell.p50, "status": "ok"})
            rows.append(row)

    return ExportResultData(
        policy_name=policy_name,
        min_group_size=min_group_size,
        rows=rows,
        suppressed_cells=suppressed_total,
        all_suppressed=bool(rows) and not any_visible,
    )


def rows_to_csv(rows: list[dict], group_by: list[str]) -> str:
    """Serialize export rows to CSV. Columns are group fields + stats + status."""
    columns = [*group_by, "analyte_code", "n", "mean", "sd", "p50", "status"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()
