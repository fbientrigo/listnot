"""Database models + session (docs/DELIVERY_PLAN.md Commit 3, ADR-0004)."""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import inspect
from sqlmodel import select

from pucv_aq_qc.database import models
from pucv_aq_qc.database.init_db import init_db
from pucv_aq_qc.database.models import (
    ALL_TABLES,
    FORBIDDEN_COLUMNS,
    Campaign,
    QCMeasurement,
    Sample,
    Subject,
)
from pucv_aq_qc.database.session import get_engine, session_scope


@pytest.fixture()
def db_url(tmp_path):
    url = f"sqlite:///{tmp_path}/test.db"
    init_db(url)
    return url


def test_init_db_creates_all_tables(db_url):
    inspector = inspect(get_engine(db_url))
    tables = set(inspector.get_table_names())
    expected = {t.__tablename__ for t in ALL_TABLES}
    assert expected <= tables


def test_no_forbidden_columns_on_any_table(db_url):
    inspector = inspect(get_engine(db_url))
    for table in ALL_TABLES:
        cols = {c["name"] for c in inspector.get_columns(table.__tablename__)}
        leaked = cols & FORBIDDEN_COLUMNS
        assert not leaked, f"{table.__tablename__} has forbidden column(s): {leaked}"
        # a person 'name' column is forbidden everywhere except campaign
        if "name" in cols:
            assert table is Campaign


def test_round_trip_insert_select(db_url):
    with session_scope(db_url) as s:
        camp = Campaign(
            name="Demo campaign",
            protocol_version="v1",
            location_label="Valparaíso",
            start_date=date(2026, 3, 1),
        )
        s.add(camp)
        s.flush()
        camp_id = camp.id

    with session_scope(db_url) as s:
        got = s.get(Campaign, camp_id)
        assert got is not None
        assert got.id.startswith("camp_")
        assert got.location_label == "Valparaíso"


def test_json_list_column_round_trips(db_url):
    with session_scope(db_url) as s:
        camp = Campaign(
            name="c", protocol_version="v1", location_label="X", start_date=date(2026, 1, 1)
        )
        s.add(camp)
        s.flush()
        subj = Subject(person_uid_global="puid_ABC", key_version="v1")
        s.add(subj)
        s.flush()
        # a sample with preanalytical flags stored as JSON
        from pucv_aq_qc.database.models import StudySubject

        stsu = StudySubject(campaign_id=camp.id, subject_id=subj.id, study_subject_uid="suid_X")
        s.add(stsu)
        s.flush()
        samp = Sample(
            campaign_id=camp.id,
            study_subject_id=stsu.id,
            sample_uid="smp_1",
            sample_type="serum",
            preanalytical_flags=["hemolysis_suspected", "wrong_tube"],
        )
        s.add(samp)
        s.flush()
        samp_id = samp.id

    with session_scope(db_url) as s:
        got = s.get(Sample, samp_id)
        assert got.preanalytical_flags == ["hemolysis_suspected", "wrong_tube"]


def test_qc_measurement_persists(db_url):
    with session_scope(db_url) as s:
        camp = Campaign(
            name="c", protocol_version="v1", location_label="X", start_date=date(2026, 1, 1)
        )
        s.add(camp)
        s.flush()
        qcm = QCMeasurement(
            campaign_id=camp.id,
            analyte_code="glucose",
            control_level="L1",
            value=95.0,
            target_mean=95.0,
            target_sd=2.0,
            unit="mg/dL",
            measured_at=datetime(2026, 3, 1, 9, tzinfo=UTC),
        )
        s.add(qcm)
        s.flush()
        qcm_id = qcm.id

    with session_scope(db_url) as s:
        rows = s.exec(select(QCMeasurement).where(QCMeasurement.id == qcm_id)).all()
        assert len(rows) == 1


def test_subject_person_uid_is_unique(db_url):
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        with session_scope(db_url) as s:
            s.add(Subject(person_uid_global="puid_DUP", key_version="v1"))
            s.add(Subject(person_uid_global="puid_DUP", key_version="v1"))


def test_audit_metadata_column_named_to_avoid_reserved(db_url):
    # SQLModel/SQLAlchemy reserves `metadata`; we persist it as `event_metadata`.
    cols = {c["name"] for c in inspect(get_engine(db_url)).get_columns("audit_log")}
    assert "event_metadata" in cols
    assert "metadata" not in cols
    assert hasattr(models.AuditLog, "event_metadata")
