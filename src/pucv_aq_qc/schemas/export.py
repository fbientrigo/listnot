"""Export request/result contracts (docs/API_CONTRACT.md §2, DATA_DICTIONARY §8).

Exports carry only ``export_subject_uid`` as a subject identifier — never
``study_subject_uid`` or ``person_uid_global`` (docs/PRIVACY_MODEL.md §10).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ExportRequest(BaseModel):
    """Request to produce an audited aggregated export."""

    model_config = ConfigDict(extra="forbid")

    export_id: str = Field(min_length=1, description="Namespace used to derive export_subject_uid")
    group_by: list[str] = Field(default_factory=list)
    analytes: list[str] = Field(default_factory=list)


class ExportResult(BaseModel):
    """Response after an aggregated export is produced."""

    model_config = ConfigDict(extra="forbid")

    export_id: str
    min_group_size: int
    output_uri: str
    audit_id: str
    subject_id_kind: str = "export_subject_uid"
    suppressed_cells: int = 0
