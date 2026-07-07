"""Ingestion validation: parse → validate → identity gateway → preview.

Guarantees (docs/API_CONTRACT.md §2, docs/PRIVACY_MODEL.md §8):
- the RUT is normalized/validated and (if a secret is supplied) converted to a
  ``person_uid_global`` that is then discarded — never returned;
- the normalized preview contains no ``rut`` (only a masked ``subject_ref``);
- errors are generic and never echo the offending RUT.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, ValidationError

from pucv_aq_qc.identity import hmac_id, rut
from pucv_aq_qc.identity.exceptions import InvalidRUTError
from pucv_aq_qc.ingestion.contracts import RawIngestionRow
from pucv_aq_qc.synthetic.analytes import ANALYTES

# Marker returned instead of any real subject identifier.
SUBJECT_REF_MASK = "puid_… (not returned)"


class RowError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row: int
    field: str
    code: str
    message: str  # generic; never contains a RUT


class PreviewRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analyte_code: str
    value: float | None
    unit: str
    subject_ref: str = SUBJECT_REF_MASK  # masked; never the puid or rut


class ValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    row_count: int
    errors: list[RowError]
    normalized_preview: list[PreviewRow]


def _validate_one(index: int, raw: dict, secret: bytes | None) -> tuple[PreviewRow | None, list[RowError]]:
    errors: list[RowError] = []

    # Structural parse (this may carry a rut, in memory only).
    try:
        row = RawIngestionRow.model_validate(raw)
    except ValidationError as exc:
        for err in exc.errors():
            field = str(err["loc"][0]) if err["loc"] else "row"
            # Never include the input value in the message.
            errors.append(
                RowError(row=index, field=field, code="invalid_field", message="invalid field")
            )
        return None, errors

    # Identity gateway: normalize → validate → derive → discard.
    try:
        normalized = rut.normalize(row.rut)
        rut.validate(normalized)
        if secret:
            _puid = hmac_id.person_uid_global(normalized, secret)
            del _puid  # derived to prove the path; never returned
        del normalized
    except InvalidRUTError:
        errors.append(
            RowError(row=index, field="rut", code="invalid_rut", message="invalid RUT format")
        )
        return None, errors

    # Domain checks that do not depend on identity.
    if row.analyte_code not in ANALYTES:
        errors.append(
            RowError(
                row=index,
                field="analyte_code",
                code="unknown_analyte",
                message="unknown analyte_code",
            )
        )
        return None, errors

    preview = PreviewRow(analyte_code=row.analyte_code, value=row.value, unit=row.unit)
    return preview, errors


def validate_rows(rows: list[dict], secret: bytes | None = None) -> ValidationReport:
    """Validate raw ingestion rows without persisting anything.

    Returns a report whose preview and errors never contain a RUT.
    """
    all_errors: list[RowError] = []
    preview: list[PreviewRow] = []
    for i, raw in enumerate(rows):
        row_preview, row_errors = _validate_one(i, raw, secret)
        all_errors.extend(row_errors)
        if row_preview is not None:
            preview.append(row_preview)
    return ValidationReport(
        valid=not all_errors,
        row_count=len(rows),
        errors=all_errors,
        normalized_preview=preview,
    )
