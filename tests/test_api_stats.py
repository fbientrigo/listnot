"""API contract + privacy enforcement (docs/DELIVERY_PLAN.md Commit 8).

Central assertion: statistical/export responses never contain forbidden fields
or small groups.
"""

import pytest
from fastapi.testclient import TestClient

from pucv_aq_qc.config.settings import get_settings
from pucv_aq_qc.database.session import get_engine
from pucv_aq_qc.privacy import forbidden

FORBIDDEN_SUBSTRINGS = [
    "rut",
    '"name"',
    "phone",
    "address",
    "person_uid_global",
    "study_subject_uid",
    "puid_",
    "suid_",
]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path}/api.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("PUCV_DEMO_MODE", "true")
    monkeypatch.setenv("PUCV_MIN_GROUP_SIZE", "10")
    get_settings.cache_clear()
    get_engine.cache_clear()
    from apps.api.main import create_app

    app = create_app()
    return TestClient(app)


def _generate(client, n=120, seed=42):
    resp = client.post("/api/v1/demo/generate-synthetic", json={"n_subjects": n, "seed": seed})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["demo_mode"] is True


def test_demo_generate_reports_rut_not_persisted(client):
    body = _generate(client)
    assert body["rut_persisted"] is False
    assert body["counts"]["subjects"] == 120
    assert body["campaign_id"].startswith("camp_")


def test_ingestion_validate_never_echoes_rut(client):
    r = client.post(
        "/api/v1/ingestion/validate",
        json={"format": "csv", "rows": [{"rut": "12.345.678-5", "analyte_code": "glucose", "value": 92, "unit": "mg/dL"}]},
    )
    assert r.status_code == 200
    text = r.text
    assert "12345678" not in text
    assert "12.345.678" not in text
    assert forbidden.scan_text(text) == []


def test_ingestion_validate_generic_error_on_bad_rut(client):
    r = client.post(
        "/api/v1/ingestion/validate",
        json={"format": "csv", "rows": [{"rut": "12345678-4", "analyte_code": "glucose", "value": 92, "unit": "mg/dL"}]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is False
    assert body["errors"][0]["message"] == "invalid RUT format"
    assert "12345678" not in r.text


def test_qc_summary_has_no_subject_linkage(client):
    camp = _generate(client)["campaign_id"]
    r = client.get(f"/api/v1/qc/{camp}/summary")
    assert r.status_code == 200
    text = r.text
    for bad in FORBIDDEN_SUBSTRINGS:
        assert bad not in text
    assert r.json()["analytes"]


def test_stats_summary_is_aggregated_and_privacy_safe(client):
    camp = _generate(client)["campaign_id"]
    r = client.get(f"/api/v1/stats/{camp}/summary?group_by=sex,age_band")
    assert r.status_code == 200
    body = r.json()
    assert body["min_group_size"] == 10
    text = r.text
    for bad in FORBIDDEN_SUBSTRINGS:
        assert bad not in text
    assert forbidden.scan_text(text) == []
    # every visible group meets the threshold; suppressed groups expose no mean
    for g in body["groups"]:
        if g.get("status") == "suppressed":
            assert "mean" not in g or g.get("mean") is None
        else:
            assert g["n"] >= body["min_group_size"]


def test_stats_small_groups_are_suppressed(client):
    camp = _generate(client, n=120)["campaign_id"]
    # group by many dims to force some cells below threshold
    r = client.get(f"/api/v1/stats/{camp}/summary?group_by=sex,age_band")
    body = r.json()
    # with 120 subjects across 2 sexes x 5 age bands x 8 analytes, some cells small
    suppressed = [g for g in body["groups"] if g.get("status") == "suppressed"]
    visible = [g for g in body["groups"] if g.get("status") != "suppressed"]
    assert visible  # some groups pass
    for g in suppressed:
        assert g["n"] < body["min_group_size"]


def test_aggregated_export_is_audited_and_safe(client):
    camp = _generate(client)["campaign_id"]
    r = client.post(
        f"/api/v1/exports/{camp}/aggregated",
        json={"export_id": "proj_epi_2026a", "group_by": ["sex", "age_band"], "analytes": ["glucose", "chol_total"]},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["subject_id_kind"] == "export_subject_uid"
    assert body["audit_id"].startswith("aud_")
    assert "suppressed_cells" in body
    # the written CSV contains no rut/puid/suid
    from pathlib import Path

    csv_text = Path(body["output_uri"]).read_text()
    assert "puid_" not in csv_text and "suid_" not in csv_text
    assert forbidden.scan_text(csv_text) == []


def test_campaign_detail_404(client):
    r = client.get("/api/v1/campaigns/camp_missing")
    assert r.status_code == 404
