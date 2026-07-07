"""Prove the derive path never emits a RUT into any produced artifact.

docs/PRIVACY_MODEL.md §8, docs/DELIVERY_PLAN.md Commit 1.
"""

import json

from pucv_aq_qc.identity import hmac_id, rut
from pucv_aq_qc.privacy import forbidden

SECRET = b"z" * 40

# Valid synthetic RUTs exercised through the full derive path.
SYNTHETIC_RUTS = ["12345678-5", "11111111-1", "22222222-2", "5126663-3", "9743918-4"]


def _derive_all(raw_rut: str) -> dict:
    normalized = rut.normalize(raw_rut)
    rut.validate(normalized)
    puid = hmac_id.person_uid_global(normalized, SECRET)
    suid = hmac_id.study_subject_uid(puid, "camp_demo", SECRET)
    euid = hmac_id.export_subject_uid(suid, "exp_demo", SECRET)
    # local RUT variable goes out of scope here; only pseudonyms are returned
    return {"person_uid_global": puid, "study_subject_uid": suid, "export_subject_uid": euid}


def test_derived_ids_contain_no_rut():
    for raw in SYNTHETIC_RUTS:
        ids = _derive_all(raw)
        blob = json.dumps(ids)
        assert not forbidden.contains_forbidden(blob), forbidden.scan_text(blob)
        # also assert the concrete digits are absent
        digits = raw.split("-")[0]
        assert digits not in blob


def test_artifacts_written_to_disk_have_no_rut(tmp_path):
    # Simulate the pipeline writing pseudonymous artifacts to disk.
    out_dir = tmp_path / "artifacts"
    out_dir.mkdir()
    records = [_derive_all(r) for r in SYNTHETIC_RUTS]

    (out_dir / "subjects.json").write_text(json.dumps(records, indent=2))
    (out_dir / "export.csv").write_text(
        "export_subject_uid\n" + "\n".join(r["export_subject_uid"] for r in records)
    )
    (out_dir / "report.md").write_text(
        "# Demo report\n\n" + "\n".join(f"- {r['study_subject_uid']}" for r in records)
    )

    matches = forbidden.scan_paths([out_dir])
    assert matches == [], [m.redacted for m in matches]


def test_scanner_would_catch_a_leaked_rut(tmp_path):
    # Guard: the scanner must actually detect a RUT if one ever leaked.
    leaky = tmp_path / "bad.csv"
    leaky.write_text("subject,rut\n1,12.345.678-5\n")
    matches = forbidden.scan_paths([tmp_path])
    assert matches, "scanner failed to detect a known RUT-shaped value"
    # and the reported match is redacted, not the real value
    assert all("12345678" not in m.redacted for m in matches)
