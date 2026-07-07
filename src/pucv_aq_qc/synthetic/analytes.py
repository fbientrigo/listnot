"""Analyte specifications for synthetic generation (docs/DATA_DICTIONARY.md).

Ranges/SDs are plausible placeholders for synthetic data ONLY and must not be
used clinically (Beatriz owns the authoritative table). Each spec carries a
patient-population distribution plus two QC control levels (L1 low/normal,
L2 high) with assigned target mean/SD, and an allowable CV%.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AnalyteSpec:
    code: str
    name_es: str
    unit: str
    ref_low: float | None
    ref_high: float | None
    pop_mean: float
    pop_sd: float
    qc_l1_mean: float
    qc_l1_sd: float
    qc_l2_mean: float
    qc_l2_sd: float
    allowable_cv: float  # percent


# A representative subset of docs/DATA_DICTIONARY.md "Units and example analytes".
ANALYTES: dict[str, AnalyteSpec] = {
    "glucose": AnalyteSpec(
        "glucose", "Glicemia", "mg/dL", 70, 99, 92.0, 12.0, 95.0, 2.5, 250.0, 6.0, 3.0
    ),
    "chol_total": AnalyteSpec(
        "chol_total", "Colesterol total", "mg/dL", None, 200, 185.0, 30.0,
        150.0, 4.0, 260.0, 6.5, 3.0
    ),
    "triglycerides": AnalyteSpec(
        "triglycerides", "Triglicéridos", "mg/dL", None, 150, 130.0, 45.0,
        100.0, 4.0, 220.0, 8.0, 4.0
    ),
    "creatinine": AnalyteSpec(
        "creatinine", "Creatinina", "mg/dL", 0.6, 1.3, 0.95, 0.20,
        0.90, 0.05, 3.5, 0.15, 4.0
    ),
    "urea": AnalyteSpec(
        "urea", "Urea", "mg/dL", 15, 45, 30.0, 8.0, 20.0, 1.5, 60.0, 3.0, 4.0
    ),
    "alt": AnalyteSpec(
        "alt", "ALT / GPT", "U/L", 7, 56, 28.0, 12.0, 30.0, 2.5, 90.0, 5.0, 5.0
    ),
    "ast": AnalyteSpec(
        "ast", "AST / GOT", "U/L", 10, 40, 24.0, 10.0, 30.0, 2.5, 115.0, 5.0, 5.0
    ),
    "albumin": AnalyteSpec(
        "albumin", "Albúmina", "g/dL", 3.5, 5.0, 4.3, 0.4, 3.8, 0.12, 5.2, 0.15, 3.0
    ),
}

ANALYTE_CODES: list[str] = list(ANALYTES)
