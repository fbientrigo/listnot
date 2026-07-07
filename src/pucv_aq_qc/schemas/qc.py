"""QC measurement and flag contracts (docs/DATA_DICTIONARY.md §6-7)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from pucv_aq_qc.schemas.enums import ControlLevel, RuleCode, RunStatus, Severity


class QCMeasurementIn(BaseModel):
    """One QC control measurement (a Levey-Jennings point).

    ``z`` is derived, not stored: z = (value - target_mean) / target_sd.
    QC data carries no subject linkage at all (docs/API_CONTRACT.md §3).
    """

    model_config = ConfigDict(extra="forbid")

    campaign_id: str
    analyte_code: str
    control_level: ControlLevel
    value: float
    target_mean: float
    target_sd: float
    unit: str
    instrument_id: str | None = None
    reagent_lot: str | None = None
    measured_at: datetime


class QCFlagOut(BaseModel):
    """A rule evaluation result attached to a QC measurement."""

    model_config = ConfigDict(extra="forbid")

    id: str
    qc_measurement_id: str
    rule_code: RuleCode
    severity: Severity
    run_status: RunStatus
    message: str
    created_at: datetime
