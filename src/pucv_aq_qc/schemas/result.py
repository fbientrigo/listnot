"""AnalyteResult contract (docs/DATA_DICTIONARY.md §5)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from pucv_aq_qc.schemas.enums import ResultFlag


class AnalyteResultIn(BaseModel):
    """One measured analyte for one sample."""

    model_config = ConfigDict(extra="forbid")

    sample_id: str
    analyte_code: str
    value: float | None = None  # None -> missing value
    unit: str
    method: str | None = None
    instrument_id: str | None = None
    reagent_lot: str | None = None
    reference_low: float | None = None
    reference_high: float | None = None
    result_flags: list[ResultFlag] = Field(default_factory=list)
