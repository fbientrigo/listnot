"""SQLModel tables (docs/DATA_DICTIONARY.md, ADR-0004).

Portability rules honoured:
- string PKs generated in Python (``new_id``),
- ``list[str]`` columns stored as JSON (works on SQLite and Postgres),
- timezone-aware UTC datetimes,
- no engine-specific column types.

Privacy invariant: no table has a rut/name/phone/address column. The only
subject key persisted operationally is ``person_uid_global`` on ``Subject``
(docs/PRIVACY_MODEL.md §9). ``Campaign.name`` is a campaign label, not a person.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from pucv_aq_qc.database.ids import new_id


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Campaign(SQLModel, table=True):
    __tablename__ = "campaign"

    id: str = Field(default_factory=lambda: new_id("camp"), primary_key=True)
    name: str
    protocol_version: str
    location_label: str  # coarse comuna/región only
    start_date: date
    end_date: date | None = None
    status: str = "planned"
    synthetic: bool = True


class Subject(SQLModel, table=True):
    __tablename__ = "subject"

    id: str = Field(default_factory=lambda: new_id("subj"), primary_key=True)
    # Operational-zone-only pseudonym; never selected into an API response.
    person_uid_global: str = Field(index=True, unique=True)
    key_version: str = "v1"
    synthetic: bool = True
    created_at: datetime = Field(default_factory=_utcnow)


class StudySubject(SQLModel, table=True):
    __tablename__ = "study_subject"

    id: str = Field(default_factory=lambda: new_id("stsu"), primary_key=True)
    campaign_id: str = Field(foreign_key="campaign.id", index=True)
    subject_id: str = Field(foreign_key="subject.id", index=True)
    study_subject_uid: str = Field(index=True)
    consent_status: str = "granted"
    created_at: datetime = Field(default_factory=_utcnow)


class Sample(SQLModel, table=True):
    __tablename__ = "sample"

    id: str = Field(default_factory=lambda: new_id("samp"), primary_key=True)
    campaign_id: str = Field(foreign_key="campaign.id", index=True)
    study_subject_id: str = Field(foreign_key="study_subject.id", index=True)
    sample_uid: str
    sample_type: str
    collected_at: datetime | None = None
    preanalytical_flags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_utcnow)


class AnalyteResult(SQLModel, table=True):
    __tablename__ = "analyte_result"

    id: str = Field(default_factory=lambda: new_id("res"), primary_key=True)
    sample_id: str = Field(foreign_key="sample.id", index=True)
    analyte_code: str = Field(index=True)
    value: float | None = None
    unit: str
    method: str | None = None
    instrument_id: str | None = None
    reagent_lot: str | None = None
    reference_low: float | None = None
    reference_high: float | None = None
    result_flags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_utcnow)


class QCMeasurement(SQLModel, table=True):
    __tablename__ = "qc_measurement"

    id: str = Field(default_factory=lambda: new_id("qcm"), primary_key=True)
    campaign_id: str = Field(foreign_key="campaign.id", index=True)
    analyte_code: str = Field(index=True)
    control_level: str
    value: float
    target_mean: float
    target_sd: float
    unit: str
    instrument_id: str | None = None
    reagent_lot: str | None = None
    measured_at: datetime = Field(index=True)


class QCFlag(SQLModel, table=True):
    __tablename__ = "qc_flag"

    id: str = Field(default_factory=lambda: new_id("qcf"), primary_key=True)
    qc_measurement_id: str = Field(foreign_key="qc_measurement.id", index=True)
    rule_code: str
    severity: str
    run_status: str
    message: str
    created_at: datetime = Field(default_factory=_utcnow)


class StatisticalExport(SQLModel, table=True):
    __tablename__ = "statistical_export"

    id: str = Field(default_factory=lambda: new_id("exp"), primary_key=True)
    campaign_id: str = Field(foreign_key="campaign.id", index=True)
    export_id: str = Field(unique=True)
    export_policy: str
    min_group_size: int
    created_by: str
    created_at: datetime = Field(default_factory=_utcnow)
    output_uri: str


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"

    id: str = Field(default_factory=lambda: new_id("aud"), primary_key=True)
    event_type: str = Field(index=True)
    actor: str
    role: str
    resource_type: str | None = None
    resource_id: str | None = None
    # JSON metadata that must never contain a RUT/identifier (PRIVACY_MODEL §8).
    event_metadata: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_utcnow)


ALL_TABLES = [
    Campaign,
    Subject,
    StudySubject,
    Sample,
    AnalyteResult,
    QCMeasurement,
    QCFlag,
    StatisticalExport,
    AuditLog,
]

# Column names that must never appear on any persisted table (PRIVACY_MODEL §9).
FORBIDDEN_COLUMNS = {"rut", "phone", "address", "geolocation"}
