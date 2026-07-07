"""Ingestion validation (docs/DELIVERY_PLAN.md Commit 5, API_CONTRACT §2).

Central guarantee: no RUT is ever echoed in a preview or an error.
"""

import json

from pucv_aq_qc.ingestion.csv_loader import parse_csv_text, validate_csv_text
from pucv_aq_qc.ingestion.validators import SUBJECT_REF_MASK, validate_rows
from pucv_aq_qc.privacy import forbidden

SECRET = b"i" * 32
RUT = "12345678-5"


def test_valid_row_validates_and_masks_subject():
    report = validate_rows(
        [{"rut": RUT, "analyte_code": "glucose", "value": 92, "unit": "mg/dL"}], secret=SECRET
    )
    assert report.valid is True
    assert report.row_count == 1
    assert report.errors == []
    assert len(report.normalized_preview) == 1
    prev = report.normalized_preview[0]
    assert prev.analyte_code == "glucose"
    assert prev.value == 92.0
    assert prev.subject_ref == SUBJECT_REF_MASK


def test_preview_never_contains_rut():
    report = validate_rows(
        [{"rut": RUT, "analyte_code": "glucose", "value": 92, "unit": "mg/dL"}], secret=SECRET
    )
    blob = report.model_dump_json()
    assert RUT not in blob
    assert "12345678" not in blob
    assert forbidden.scan_text(blob) == []


def test_invalid_rut_produces_generic_error_without_echo():
    bad_rut = "12345678-4"  # wrong check digit
    report = validate_rows(
        [{"rut": bad_rut, "analyte_code": "glucose", "value": 92, "unit": "mg/dL"}], secret=SECRET
    )
    assert report.valid is False
    assert len(report.errors) == 1
    err = report.errors[0]
    assert err.field == "rut"
    assert err.code == "invalid_rut"
    assert err.message == "invalid RUT format"
    blob = json.dumps([e.model_dump() for e in report.errors])
    assert "12345678" not in blob
    assert bad_rut not in blob


def test_unknown_analyte_rejected():
    report = validate_rows(
        [{"rut": RUT, "analyte_code": "unobtanium", "value": 1, "unit": "mg/dL"}], secret=SECRET
    )
    assert report.valid is False
    assert report.errors[0].code == "unknown_analyte"


def test_missing_required_field_rejected_without_echo():
    # no unit provided
    report = validate_rows([{"rut": RUT, "analyte_code": "glucose", "value": 92}], secret=SECRET)
    assert report.valid is False
    blob = json.dumps([e.model_dump() for e in report.errors])
    assert "12345678" not in blob


def test_validate_without_secret_still_masks_and_validates():
    report = validate_rows(
        [{"rut": RUT, "analyte_code": "glucose", "value": 92, "unit": "mg/dL"}], secret=None
    )
    assert report.valid is True
    assert report.normalized_preview[0].subject_ref == SUBJECT_REF_MASK


def test_csv_parsing_restricts_to_known_columns():
    text = "rut,analyte_code,value,unit,secret_note\n12345678-5,glucose,92,mg/dL,ignore-me\n"
    rows = parse_csv_text(text)
    assert rows[0].get("secret_note") is None
    assert "secret_note" not in rows[0]


def test_csv_end_to_end_no_rut_in_output():
    text = (
        "rut,analyte_code,value,unit\n"
        "12345678-5,glucose,92,mg/dL\n"
        "11111111-1,creatinine,0.9,mg/dL\n"
        "98765432-9,glucose,100,mg/dL\n"  # invalid check digit
    )
    report = validate_csv_text(text, secret=SECRET)
    assert report.row_count == 3
    assert report.valid is False  # one bad rut
    blob = report.model_dump_json()
    assert forbidden.scan_text(blob) == []
    assert "12345678" not in blob
