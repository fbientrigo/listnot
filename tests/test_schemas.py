"""Schema contracts + the load-bearing forbidden-field assertion.

docs/DELIVERY_PLAN.md Commit 2, docs/PRIVACY_MODEL.md §9.
"""

from datetime import UTC, date, datetime

import pytest
from pydantic import BaseModel, ValidationError

from pucv_aq_qc import schemas
from pucv_aq_qc.ingestion.contracts import RawIngestionRow
from pucv_aq_qc.schemas.campaign import CampaignIn
from pucv_aq_qc.schemas.enums import ControlLevel, SampleType
from pucv_aq_qc.schemas.qc import QCMeasurementIn
from pucv_aq_qc.schemas.result import AnalyteResultIn
from pucv_aq_qc.schemas.sample import SampleIn

# Person-identifying fields that must never appear on any operational schema.
FORBIDDEN_FIELDS = {"rut", "phone", "address", "location", "geolocation"}
# "name" is a person identifier everywhere EXCEPT on a Campaign, where it is a
# campaign label (docs/DATA_DICTIONARY.md §1 lists name only on Campaign).
CAMPAIGN_SCHEMAS = (CampaignIn, schemas.CampaignOut)

# Every operational/persisted-facing schema. (RawIngestionRow is excluded: it is
# the in-memory ingestion contract that legitimately carries a RUT.)
OPERATIONAL_SCHEMAS: list[type[BaseModel]] = [
    schemas.CampaignIn,
    schemas.CampaignOut,
    schemas.SubjectOut,
    schemas.StudySubjectOut,
    schemas.SampleIn,
    schemas.AnalyteResultIn,
    schemas.QCMeasurementIn,
    schemas.QCFlagOut,
    schemas.ExportRequest,
    schemas.ExportResult,
]


@pytest.mark.parametrize("model", OPERATIONAL_SCHEMAS)
def test_no_forbidden_field_on_operational_schemas(model):
    fields = set(model.model_fields)
    leaked = fields & FORBIDDEN_FIELDS
    assert not leaked, f"{model.__name__} exposes forbidden field(s): {leaked}"
    # "name" is allowed only on Campaign (it's a campaign label, not a person)
    if "name" in fields:
        assert model in CAMPAIGN_SCHEMAS, f"{model.__name__} exposes a person 'name'"


def test_campaign_name_is_label_not_person():
    # Campaign.name is a human label for the campaign, explicitly allowed.
    assert "name" in CampaignIn.model_fields
    assert "rut" not in CampaignIn.model_fields


def test_valid_payloads_parse():
    CampaignIn(
        name="Screening Valparaíso 2026-Q1",
        protocol_version="v1.2",
        location_label="Valparaíso",
        start_date=date(2026, 3, 1),
    )
    SampleIn(
        campaign_id="camp_1",
        study_subject_id="stsu_1",
        sample_uid="smp_1",
        sample_type=SampleType.serum,
    )
    AnalyteResultIn(sample_id="samp_1", analyte_code="glucose", value=92.0, unit="mg/dL")
    QCMeasurementIn(
        campaign_id="camp_1",
        analyte_code="glucose",
        control_level=ControlLevel.L1,
        value=95.0,
        target_mean=95.0,
        target_sd=2.0,
        unit="mg/dL",
        measured_at=datetime(2026, 3, 1, 9, tzinfo=UTC),
    )


def test_enum_validation_rejects_bad_values():
    with pytest.raises(ValidationError):
        SampleIn(
            campaign_id="camp_1",
            study_subject_id="stsu_1",
            sample_uid="smp_1",
            sample_type="cerebrospinal",  # not a valid SampleType
        )


def test_extra_fields_forbidden_on_operational_input():
    # sneaking a rut into an operational schema must be rejected
    with pytest.raises(ValidationError):
        AnalyteResultIn(
            sample_id="samp_1",
            analyte_code="glucose",
            value=92.0,
            unit="mg/dL",
            rut="12345678-5",
        )


def test_raw_ingestion_row_repr_never_shows_rut():
    row = RawIngestionRow(rut="12345678-5", analyte_code="glucose", value=92.0, unit="mg/dL")
    assert "12345678" not in repr(row)
    assert "12345678" not in str(row)
    assert "<redacted>" in repr(row)
