# ADR-0003 — Synthetic-data-first

**Status:** Accepted · **Date:** 2026-07-07 · **Deciders:** Fabian, Beatriz

## Context
The platform's value is QC and safe statistics, but touching real patient data prematurely creates legal, ethical, and security exposure before any protective machinery exists. We need realistic data to build and demo QC behavior now.

## Decision
Build and validate the **entire pipeline on synthetic data first**. Real/pilot data is postponed to Weeks 5–6 and only as pseudonymized. The synthetic module generates: campaigns, valid synthetic Chilean RUTs, subjects, samples, analyte results, and QC controls (L1/L2), with **injectable error scenarios** — bias, drift, imprecision increase, outliers, missing values, and pre-analytical flags — so QC rules fire realistically.

## Rationale
- De-risks the build: privacy machinery, QC engine, and API can be fully exercised and tested without any real identity in the system.
- Reproducible: `make demo` regenerates the whole world deterministically (seeded), enabling reproducible reports and CI.
- Lets Beatriz validate QC message quality and rule behavior against known injected faults (ground truth).

## Consequences
- (+) Zero real-data risk during the highest-churn phase.
- (+) Ground-truth scenarios make QC rules testable (`test_qc_rules.py`).
- (−) Synthetic realism is a modeling task; ranges/SDs must be plausible (Beatriz owns the parameters). Explicitly acceptable per MVP shortcuts.

## Rejected
Starting with a real pilot extract (blocked on approvals, unsafe before privacy layer exists); using generic random noise without injected clinical error patterns (would not demonstrate meaningful QC behavior).
