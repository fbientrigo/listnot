# DATA_DICTIONARY.md

**Project:** `pucv-aq-qc`. Authoritative field-level definition of persisted entities.
Types are SQLModel/SQLAlchemy-compatible and PostgreSQL-ready. `PK` = primary key, `FK` = foreign key.

> **Global rule:** No table in this dictionary contains `rut`, `name`, `phone`, `address`, or exact location. If you are tempted to add one, stop and read `PRIVACY_MODEL.md §9`.

---

## 1. Campaign
A community/lab acquisition campaign under one protocol.

| Field | Type | Null | Notes |
|---|---|---|---|
| id | str/uuid | PK | `camp_<uuid>` |
| name | str | no | Human label, e.g. "Screening comunitario Valparaíso 2026-Q1" |
| protocol_version | str | no | e.g. `v1.2` |
| location_label | str | no | **Coarse** label only (comuna/región), never address/coords |
| start_date | date | no | |
| end_date | date | yes | Null while active |
| status | enum | no | `planned` \| `active` \| `closed` |
| synthetic | bool | no | `true` for all MVP data |

Relationships: 1 Campaign → N StudySubject, N Sample, N QCMeasurement, N StatisticalExport.

## 2. Subject
A pseudonymous person in the protected operational zone. **No RUT.**

| Field | Type | Null | Notes |
|---|---|---|---|
| id | str/uuid | PK | `subj_<uuid>` |
| person_uid_global | str | no, unique | `puid_…` HMAC pseudonym; operational zone only |
| key_version | str | no | e.g. `v1`, for key rotation |
| synthetic | bool | no | |
| created_at | datetime | no | UTC |

Relationships: 1 Subject → N StudySubject.

## 3. StudySubject
A subject's participation within one campaign.

| Field | Type | Null | Notes |
|---|---|---|---|
| id | str/uuid | PK | `stsu_<uuid>` |
| campaign_id | str | FK→Campaign | |
| subject_id | str | FK→Subject | |
| study_subject_uid | str | no | `suid_…`; stable within campaign |
| consent_status | enum | no | `unknown` \| `granted` \| `withdrawn` (synthetic: `granted`) |
| created_at | datetime | no | |

Unique: (`campaign_id`, `subject_id`). Relationships: 1 StudySubject → N Sample.

## 4. Sample
A biological sample collected from a study subject.

| Field | Type | Null | Notes |
|---|---|---|---|
| id | str/uuid | PK | `samp_<uuid>` |
| campaign_id | str | FK→Campaign | |
| study_subject_id | str | FK→StudySubject | |
| sample_uid | str | no | `smp_…` opaque sample id |
| sample_type | enum | no | `serum` \| `plasma` \| `whole_blood` |
| collected_at | datetime | yes | Null ⇒ `missing_collection_time` flag |
| preanalytical_flags | list[str] | no | subset of §Pre-analytical flags; may be empty |
| created_at | datetime | no | |

Relationships: 1 Sample → N AnalyteResult.

**Pre-analytical flags (enum values):** `hemolysis_suspected`, `insufficient_sample`, `delayed_processing`, `missing_fasting_status`, `wrong_tube`, `sample_clotting`, `temperature_excursion`, `missing_collection_time`.

## 5. AnalyteResult
One measured analyte for one sample.

| Field | Type | Null | Notes |
|---|---|---|---|
| id | str/uuid | PK | `res_<uuid>` |
| sample_id | str | FK→Sample | |
| analyte_code | str | no | see §Analytes |
| value | float | yes | Null ⇒ missing value |
| unit | str | no | canonical unit for the analyte |
| method | str | yes | e.g. `enzymatic`, `colorimetric` |
| instrument_id | str | yes | opaque instrument label |
| reagent_lot | str | yes | lot id (joins to QC by lot) |
| reference_low | float | yes | reference range low |
| reference_high | float | yes | reference range high |
| result_flags | list[str] | no | e.g. `below_ref`, `above_ref`, `critical`, `missing` |
| created_at | datetime | no | |

## 6. QCMeasurement
One QC control measurement (Levey-Jennings point).

| Field | Type | Null | Notes |
|---|---|---|---|
| id | str/uuid | PK | `qcm_<uuid>` |
| campaign_id | str | FK→Campaign | |
| analyte_code | str | no | |
| control_level | enum | no | `L1` \| `L2` (level 1 / level 2) |
| value | float | no | measured control value |
| target_mean | float | no | assigned mean for lot/level |
| target_sd | float | no | assigned SD for lot/level |
| unit | str | no | |
| instrument_id | str | yes | |
| reagent_lot | str | yes | |
| measured_at | datetime | no | ordering key for LJ series |

Derived (not stored): `z = (value - target_mean) / target_sd`.

## 7. QCFlag
A rule evaluation result attached to a QC measurement.

| Field | Type | Null | Notes |
|---|---|---|---|
| id | str/uuid | PK | `qcf_<uuid>` |
| qc_measurement_id | str | FK→QCMeasurement | |
| rule_code | enum | no | `1_2s` \| `1_3s` \| `2_2s` \| `R_4s` \| `4_1s` \| `10x` |
| severity | enum | no | `info` \| `warning` \| `reject` |
| run_status | enum | no | `accepted` \| `warning` \| `rejected` |
| message | str | no | TM-readable Spanish message (see QC_MODEL.md) |
| created_at | datetime | no | |

## 8. StatisticalExport
Record of a safe export (audit + provenance).

| Field | Type | Null | Notes |
|---|---|---|---|
| id | str/uuid | PK | `exp_<uuid>` |
| campaign_id | str | FK→Campaign | |
| export_id | str | no, unique | namespace used to derive `export_subject_uid` |
| export_policy | str | no | policy name/version applied |
| min_group_size | int | no | effective threshold at export time |
| created_by | str | no | actor label / role |
| created_at | datetime | no | |
| output_uri | str | no | local path or object-storage URI |

## 9. AuditLog
Append-only event log.

| Field | Type | Null | Notes |
|---|---|---|---|
| id | str/uuid | PK | `aud_<uuid>` |
| event_type | enum | no | `access` \| `export` \| `ingestion` \| `admin` \| `key_rotation` |
| actor | str | no | user/service label |
| role | str | no | e.g. `student`, `researcher`, `operator`, `admin` |
| resource_type | str | yes | e.g. `campaign`, `export` |
| resource_id | str | yes | |
| metadata | json | yes | **must never contain RUT or identifiers** |
| created_at | datetime | no | UTC |

---

## Units and example analytes

| analyte_code | Nombre (ES) | Name (EN) | Unit | Typical adult ref. range* |
|---|---|---|---|---|
| `glucose` | Glicemia | Glucose (fasting) | mg/dL | 70–99 |
| `chol_total` | Colesterol total | Total cholesterol | mg/dL | < 200 |
| `triglycerides` | Triglicéridos | Triglycerides | mg/dL | < 150 |
| `hdl` | Colesterol HDL | HDL cholesterol | mg/dL | > 40 (M) / > 50 (F) |
| `creatinine` | Creatinina | Creatinine | mg/dL | 0.7–1.3 (M) / 0.6–1.1 (F) |
| `urea` | Urea | Urea | mg/dL | 15–45 |
| `alt` | ALT / GPT | Alanine aminotransferase | U/L | 7–56 |
| `ast` | AST / GOT | Aspartate aminotransferase | U/L | 10–40 |
| `albumin` | Albúmina | Albumin | g/dL | 3.5–5.0 |
| `total_protein` | Proteínas totales | Total protein | g/dL | 6.0–8.3 |
| `hemoglobin` | Hemoglobina | Hemoglobin | g/dL | 13.5–17.5 (M) / 12.0–15.5 (F) |

\* Reference ranges are **method/instrument/population dependent**; Beatriz owns the authoritative table. These are placeholders for synthetic generation only and must not be used clinically.
