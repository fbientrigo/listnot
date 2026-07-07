# SDD — Software Design Document

**Project:** `pucv-aq-qc`
**Title:** Plataforma reproducible para adquisición, vigilancia bioquímica comunitaria y control de calidad
**Owner (eng):** Fabian · **Owner (clinical):** Beatriz
**Status:** MVP architecture, approved for build.

---

## 1. System purpose

`pucv-aq-qc` is a **reproducible data-quality and research layer** that sits *beside* existing PUCV / Centro de Bioanálisis Clínico workflows. It receives a **minimal, validated, identity-safe copy** of operational lab data and provides:

- safe acquisition/import of clinical-chemistry campaign data,
- deterministic **pseudonymization** at ingestion (RUT never persisted),
- a **QC engine** (Levey-Jennings, z-score, CV, Westgard-like rules),
- a **privacy-preserving statistical API** for students/researchers,
- reproducible **reports and dashboards**.

The guiding product principle: **do not replace the current workflow.** The platform is a downstream mirror optimized for QC, reproducibility, and safe statistics.

---

## 2. Scope and non-scope

### In scope (MVP)
| Capability | MVP form |
|---|---|
| Identity-safe ingestion core | HMAC pseudonymization, RUT discarded in-memory |
| Synthetic data generation | Campaigns, subjects, samples, analyte results, QC controls |
| Ingestion validation | CSV/Excel → Pydantic contracts → internal models |
| QC engine | LJ data, z-score, mean/SD/CV, Westgard-like rules, run status |
| Persistence | SQLite local, PostgreSQL-compatible SQLModel schema |
| Privacy layer | Aggregation, min-group suppression, export policy, audit |
| Statistical API | FastAPI, aggregated-only endpoints |
| Dashboard | Streamlit |
| Reporting | Markdown/HTML |

### Out of scope (explicitly NOT built)
LIS · EHR · patient scheduling · clinical diagnosis · patient portal · user-invitation system · full OAuth/RBAC · Kubernetes · microservices · FHIR server · OMOP CDM · complex SPA frontend · mobile app · real-time streaming · differential privacy · ML · hospital-system integration · production identity vault with **real** RUTs.

### Postponed (recognized, not now)
Real patient data · cloud-native architecture · advanced consent management · institutional SSO · role-management UI · FHIR/LOINC/SNOMED mappings · PDF generation (HTML/MD is enough) · multi-tenant · audit dashboard · external connectors.

---

## 3. Architecture diagram (text)

```
                        ┌──────────────────────────────────────────────┐
                        │                INGESTION ZONE                  │
   CSV / Excel / Form   │  may see raw input (MVP: synthetic only)       │
   Synthetic generator ─┼─► ingestion.validators ─► schemas (Pydantic)   │
                        │                     │                          │
                        │                     ▼                          │
                        │            identity gateway                    │
                        │   rut.normalize → rut.validate → hmac_id       │
                        │   derive person_uid_global → DISCARD raw RUT    │
                        └──────────────────────┬───────────────────────┘
                                               │ (only pseudonymous IDs cross)
                        ┌──────────────────────▼───────────────────────┐
                        │           PROTECTED OPERATIONAL ZONE          │
                        │  database: Campaign, Subject, StudySubject,   │
                        │  Sample, AnalyteResult, QCMeasurement, QCFlag │
                        │  NO RUT / name / phone / address (MVP)        │
                        │                     │                         │
                        │            qc engine (LJ / Westgard)          │
                        └──────────────────────┬───────────────────────┘
                                               │
                     ┌─────────────────────────┼─────────────────────────┐
                     ▼                          ▼                         ▼
        ┌────────────────────┐   ┌─────────────────────────┐  ┌────────────────────┐
        │ RESEARCH/STAT ZONE │   │      EXPORT ZONE         │  │  reporting          │
        │ privacy.aggregation│   │ privacy.export_policy    │  │  markdown / html    │
        │ study/export_uid   │   │ min_group_size, suppress │  │  (aggregated only)  │
        │ FastAPI (apps/api) │   │ StatisticalExport + audit│  │                     │
        │ Streamlit dashboard│   └─────────────────────────┘  └────────────────────┘
        └────────────────────┘
                     ▲
                     └──── audit.logger records access / export / ingestion / admin
```

**Invariant:** the raw RUT exists only inside the Ingestion Zone, only in memory, only long enough to derive `person_uid_global`. Nothing to its left of the "DISCARD" line is ever written to disk, DB, log, response, or report.

---

## 4. Module responsibilities

| Module | Package | Responsibility | Must NOT |
|---|---|---|---|
| identity | `identity/` | RUT normalize/validate; HMAC ID derivation (3 layers); typed errors | persist RUT; log RUT; put RUT in exceptions |
| schemas | `schemas/` | Pydantic v2 data contracts (wire + internal) | contain RUT fields in persisted models |
| ingestion | `ingestion/` | CSV/Excel/form parse → validate → convert to internal models via identity gateway | write raw input to DB |
| synthetic | `synthetic/` | Generate campaigns, valid synthetic RUTs, samples, results, QC, injected error scenarios | be importable in production data path |
| qc | `qc/` | LJ series, z-score, mean/SD/CV, Westgard rules, run status, TM-readable messages | make clinical decisions |
| database | `database/` | SQLModel models (SQLite now, Postgres-ready), session, init | store forbidden identifiers |
| privacy | `privacy/` | Aggregation, small-group suppression, export policy enforcement | emit row-level identifiable data |
| api | `apps/api/` | FastAPI service; aggregated-only stat endpoints; health; demo generate | return direct identifiers or small groups |
| dashboard | `apps/dashboard/` | Streamlit views over QC + aggregated stats | bypass privacy layer |
| reporting | `reporting/` | Markdown/HTML reports from aggregated data | embed raw RUT/identifiers |
| config | `config/` | Env profiles (`local/server/cloud`), secret loading from env | commit real secrets |
| audit | `audit/` | Append-only event log: access, exports, ingestion, admin | store RUT in metadata |

---

## 5. Data flow (canonical)

```
CSV/Excel/Form/Synthetic  →  ingestion.validators  →  identity gateway
   →  operational database (pseudonymous)  →  qc engine
   →  dashboard / report  →  privacy layer  →  statistical API / export
```

**Ingestion gateway sequence (per row):**
1. `rut.normalize(raw)` → canonical `NNNNNNNN-DV` (no dots, uppercase K).
2. `rut.validate(normalized)` → `True` or raise `InvalidRUTError` (message contains **no** RUT).
3. `hmac_id.person_uid_global(normalized_rut, secret, key_version)` → `puid_…`.
4. Bind result columns to internal model; **delete local RUT variable** (no return, no retention).
5. Row persisted with `person_uid_global` only.

**Statistical read sequence:** query → aggregate by group → `privacy.suppression.apply(min_group_size)` → serialize → `audit.log(export/access)` → response.

---

## 6. Deployment profiles

| Concern | Local | PUCV server | Cloud |
|---|---|---|---|
| DB | SQLite file | PostgreSQL (Docker Compose) | Managed PostgreSQL |
| Secret `PUCV_ID_SECRET_V1` | local `.env` (gitignored) / demo-generated | server env or protected file outside repo | managed secret store |
| Data | synthetic only | pseudonymized pilot | pseudonymized |
| Transport | http localhost | HTTPS via reverse proxy | TLS mandatory |
| Storage backend | local FS | local FS | object storage (s3/gcs/azure) |
| Backups | none | scheduled DB dumps | managed snapshots |
| Access | open localhost / API key | restricted admin | centralized logs, restricted |

Core logic must not hard-depend on any cloud-specific API. Storage is abstracted by `PUCV_STORAGE_BACKEND`.

---

## 7. Explicit anti-overengineering decisions

| Temptation | Decision | Rationale |
|---|---|---|
| Full RBAC/OAuth now | Config-declared roles + local API key for demo | MVP has 2 users; auth is postponable without privacy risk if network-restricted |
| Microservices | Single modular monolith | Two developers, one deploy unit; boundaries enforced by packages not networks |
| PDF engine | Markdown/HTML first | HTML prints to PDF; no wkhtmltopdf/Chromium dependency in MVP |
| Postgres from day 1 | SQLite dev, Postgres-compatible SQLModel | Zero-setup local dev; migration path preserved (ADR-0004) |
| FHIR/OMOP models | Flat internal schema | Standards mapping is a Week-8+ concern, not a QC blocker |
| Identity vault w/ real RUT | Synthetic RUT only; vault is a documented future protocol | Legal/ethical approval required before real identity handling |
| Differential privacy | Deterministic min-group suppression (`n<10`) | Simple, auditable, defensible for a student-facing API |

### Architectural critique (where I push back on the brief)
1. **`Subject.person_uid_global` stored globally is a residual re-identification surface.** Even without a mapping table, if the HMAC secret leaks, a known-RUT dictionary attack re-links everyone. **Minimum correction:** treat `PUCV_ID_SECRET_V1` as the crown jewel (rotation + versioning in `PRIVACY_MODEL.md`), and *never* expose `person_uid_global` beyond the operational zone — the API layer must physically not have a code path that selects that column.
2. **BASE32 of full HMAC-SHA256 is 52 chars; "shortened" IDs invite collision.** Recommendation: keep **full 256-bit** HMAC (truncation trades collision-resistance for cosmetics). Shorten only display, never storage/join keys. (ADR-0002.)
3. **`min_group_size` alone does not stop differencing attacks** across successive exports. Mitigation for MVP: `export_subject_uid` is per-export namespaced (prevents cross-export linkage) + every export audited. Documented as a known limitation, not solved with DP.
4. **SQLModel + async FastAPI has rough edges.** MVP uses **synchronous** SQLModel sessions; async is postponed. Keeps Fabian productive.

These are corrections within the chosen architecture, not a redesign.
