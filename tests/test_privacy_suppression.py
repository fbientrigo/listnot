"""Privacy layer + audit (docs/DELIVERY_PLAN.md Commit 7, PRIVACY_MODEL §10)."""

import json

import pytest

from pucv_aq_qc.audit.logger import AuditLogger, MetadataLeakError
from pucv_aq_qc.database.init_db import init_db
from pucv_aq_qc.database.models import AuditLog
from pucv_aq_qc.database.session import session_scope
from pucv_aq_qc.identity import hmac_id
from pucv_aq_qc.privacy import forbidden
from pucv_aq_qc.privacy.aggregation import aggregate
from pucv_aq_qc.privacy.export_policy import (
    build_aggregated_export,
    namespace_subject_uids,
    rows_to_csv,
)
from pucv_aq_qc.privacy.suppression import coarsen, suppress

SECRET = b"p" * 32


def _observations():
    obs = []
    # Valparaíso: 41 F observations for glucose
    for i in range(41):
        obs.append({"comuna": "Valparaíso", "sex": "F", "analyte_code": "glucose", "value": 90 + i % 10})
    # Juan Fernández: only 6 -> below threshold
    for i in range(6):
        obs.append({"comuna": "Juan Fernández", "sex": "F", "analyte_code": "glucose", "value": 95 + i})
    return obs


# --- aggregation + suppression ----------------------------------------------


def test_aggregate_computes_group_stats():
    cells = aggregate(_observations(), group_by=["comuna"])
    by_comuna = {tuple(c.group.values())[0]: c for c in cells}
    assert by_comuna["Valparaíso"].n == 41
    assert by_comuna["Valparaíso"].mean is not None
    assert by_comuna["Juan Fernández"].n == 6


def test_suppression_hides_small_groups():
    cells = aggregate(_observations(), group_by=["comuna"])
    result = suppress(cells, min_group_size=10)
    assert result.suppressed_count == 1
    small = next(c for c in result.cells if c.group.get("comuna") == "Juan Fernández")
    assert small.suppressed is True
    assert small.mean is None
    assert small.reason == "n_below_min_group_size"
    big = next(c for c in result.cells if c.group.get("comuna") == "Valparaíso")
    assert big.suppressed is False and big.mean is not None


def test_suppressed_cell_serialization_leaks_no_values():
    cells = aggregate(_observations(), group_by=["comuna"])
    result = suppress(cells, min_group_size=10)
    blob = json.dumps([c.as_dict() for c in result.cells])
    assert '"mean"' not in json.dumps(
        next(c.as_dict() for c in result.cells if c.group.get("comuna") == "Juan Fernández")
    )
    assert "suppressed" in blob


def test_all_suppressed_flag():
    obs = [{"comuna": f"c{i}", "analyte_code": "glucose", "value": 1.0} for i in range(3)]
    cells = aggregate(obs, group_by=["comuna"])
    result = suppress(cells, min_group_size=10)
    assert result.all_suppressed is True


def test_coarsening_merges_small_groups():
    obs = []
    obs += [{"comuna": "A", "analyte_code": "glucose", "value": 10.0} for _ in range(4)]
    obs += [{"comuna": "B", "analyte_code": "glucose", "value": 20.0} for _ in range(4)]
    obs += [{"comuna": "C", "analyte_code": "glucose", "value": 30.0} for _ in range(5)]
    cells = aggregate(obs, group_by=["comuna"])
    result = coarsen(obs, cells, min_group_size=10, value_field="value", group_by=["comuna"])
    merged = next(c for c in result.cells if "OTRAS" in str(c.group))
    assert merged.n == 13
    assert merged.coarsened is True
    assert merged.mean is not None


# --- export policy ----------------------------------------------------------


def test_export_only_contains_export_subject_uid():
    puid = hmac_id.person_uid_global("12345678-5", SECRET)
    suid = hmac_id.study_subject_uid(puid, "camp_1", SECRET)
    euids = namespace_subject_uids([suid], "exp_1", SECRET)
    assert euids[0].startswith("euid_")
    assert puid not in euids[0] and suid not in euids[0]


def test_export_uids_are_per_export_unlinkable():
    puid = hmac_id.person_uid_global("12345678-5", SECRET)
    suid = hmac_id.study_subject_uid(puid, "camp_1", SECRET)
    a = namespace_subject_uids([suid], "exp_A", SECRET)[0]
    b = namespace_subject_uids([suid], "exp_B", SECRET)[0]
    assert a != b


def test_aggregated_export_suppresses_and_reports_cells():
    result = build_aggregated_export(
        _observations(), group_by=["comuna"], analytes=["glucose"], min_group_size=10
    )
    assert result.suppressed_cells == 1
    statuses = {r["comuna"]: r["status"] for r in result.rows}
    assert statuses["Juan Fernández"] == "suppressed"
    assert statuses["Valparaíso"] == "ok"


def test_export_csv_never_contains_subject_ids_or_rut():
    result = build_aggregated_export(
        _observations(), group_by=["comuna"], analytes=["glucose"], min_group_size=10
    )
    csv_text = rows_to_csv(result.rows, group_by=["comuna"])
    assert "puid_" not in csv_text
    assert "suid_" not in csv_text
    assert forbidden.scan_text(csv_text) == []
    # suppressed row exposes no mean
    assert "Juan Fernández,glucose,6,,,," in csv_text.replace('"', "")


# --- audit ------------------------------------------------------------------


def test_audit_writes_row(tmp_path):
    url = f"sqlite:///{tmp_path}/audit.db"
    init_db(url)
    with session_scope(url) as s:
        logger = AuditLogger(s)
        row = logger.log(
            "export",
            actor="student_01",
            role="student",
            resource_type="export",
            resource_id="exp_1",
            metadata={"min_group_size": 10, "suppressed_cells": 1},
            commit=False,
        )
        assert row.id.startswith("aud_")

    with session_scope(url) as s:
        from sqlmodel import select

        rows = s.exec(select(AuditLog)).all()
        assert len(rows) == 1
        assert rows[0].event_type == "export"


def test_audit_refuses_metadata_with_rut(tmp_path):
    url = f"sqlite:///{tmp_path}/audit2.db"
    init_db(url)
    with session_scope(url) as s:
        logger = AuditLogger(s)
        with pytest.raises(MetadataLeakError):
            logger.log(
                "export",
                actor="a",
                role="student",
                metadata={"note": "subject 12.345.678-5 exported"},
            )
