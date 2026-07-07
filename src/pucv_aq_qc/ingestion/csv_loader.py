"""CSV/Excel-ish loading for ingestion (docs/DELIVERY_PLAN.md Commit 5).

Parses delimited text into row dicts and validates them. The loader never
persists raw input and never logs a RUT. (Excel support is a thin future
adapter; MVP handles CSV, which covers the pilot import path.)
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from pucv_aq_qc.ingestion.validators import ValidationReport, validate_rows

# Columns recognized on an ingestion row. 'rut' is consumed in memory only.
KNOWN_COLUMNS = {
    "rut",
    "analyte_code",
    "value",
    "unit",
    "campaign_id",
    "reagent_lot",
    "method",
    "instrument_id",
}


def _coerce(row: dict[str, str]) -> dict:
    out: dict = {}
    for key, value in row.items():
        if key is None or key not in KNOWN_COLUMNS:
            continue
        value = (value or "").strip()
        if key == "value":
            out[key] = None if value == "" else _to_float(value)
        else:
            out[key] = value or None
    return out


def _to_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        # leave as a marker that validation will reject, without echoing a RUT
        return None


def parse_csv_text(text: str) -> list[dict]:
    """Parse CSV text into a list of row dicts (restricted to known columns)."""
    reader = csv.DictReader(io.StringIO(text))
    return [_coerce(row) for row in reader]


def load_csv(path: str | Path) -> list[dict]:
    """Read a CSV file into row dicts. The file is never persisted onward."""
    text = Path(path).read_text(encoding="utf-8")
    return parse_csv_text(text)


def validate_csv_text(text: str, secret: bytes | None = None) -> ValidationReport:
    """Parse and validate CSV text in one step."""
    return validate_rows(parse_csv_text(text), secret=secret)


def validate_csv_file(path: str | Path, secret: bytes | None = None) -> ValidationReport:
    """Parse and validate a CSV file in one step."""
    return validate_rows(load_csv(path), secret=secret)
