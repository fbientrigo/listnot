# API_CONTRACT.md

**Project:** `pucv-aq-qc` — FastAPI service contract (MVP, `/api/v1`).
Base app: `apps/api/main.py`. All examples are illustrative; shapes are stable, values are synthetic.

> **Hard rule (enforced in code + tests):** statistical/export endpoints must **never** return `rut`, `name`, `phone`, `address`, exact location, any direct identifier, **small groups** (`n < min_group_size`), or raw row-level re-identifiable data. Subject identifiers in exports are `export_subject_uid` only.

---

## 1. Endpoint list

| Method | Path | Purpose | Zone |
|---|---|---|---|
| GET | `/health` | Liveness/readiness | — |
| POST | `/api/v1/demo/generate-synthetic` | Generate a synthetic campaign end-to-end (demo mode only) | Ingestion |
| GET | `/api/v1/campaigns` | List campaigns | Operational (metadata) |
| GET | `/api/v1/campaigns/{campaign_id}` | Campaign detail | Operational (metadata) |
| POST | `/api/v1/ingestion/validate` | Validate a CSV/Excel/form payload against contracts (no persist) | Ingestion |
| GET | `/api/v1/qc/{campaign_id}/summary` | QC summary per analyte/level | QC |
| GET | `/api/v1/qc/{campaign_id}/analytes/{analyte_code}` | LJ series + flags for one analyte | QC |
| GET | `/api/v1/stats/{campaign_id}/summary` | Aggregated statistics (privacy-enforced) | Research |
| GET | `/api/v1/stats/{campaign_id}/analytes/{analyte_code}` | Aggregated stats for one analyte | Research |
| POST | `/api/v1/exports/{campaign_id}/aggregated` | Produce an audited aggregated export | Export |

Auth (MVP): local-only or a single `X-API-Key` header (see DEPLOYMENT.md). Full auth is postponed.

---

## 2. Request/response examples

### GET /health
```json
200 OK
{ "status": "ok", "env": "local", "demo_mode": true, "version": "0.1.0" }
```

### POST /api/v1/demo/generate-synthetic
```json
// request
{ "n_subjects": 120, "scenarios": ["bias", "drift", "imprecision", "outliers", "missing", "preanalytical"] }

// 201 Created
{
  "campaign_id": "camp_9f2a...",
  "counts": { "subjects": 120, "samples": 240, "results": 2640, "qc_measurements": 96, "qc_flags": 14 },
  "rut_persisted": false
}
```
`rut_persisted` is always `false`; it is a self-check surfaced for the demo (step 16).

### POST /api/v1/ingestion/validate
```json
// request (row-level, NOT persisted)
{ "format": "csv", "rows": [ { "rut": "12.345.678-5", "analyte_code": "glucose", "value": 92, "unit": "mg/dL" } ] }

// 200 OK  — note: NO rut echoed back
{
  "valid": true,
  "row_count": 1,
  "errors": [],
  "normalized_preview": [ { "analyte_code": "glucose", "value": 92.0, "unit": "mg/dL", "subject_ref": "puid_… (not returned)" } ]
}

// 422 on invalid rows — error text NEVER contains the RUT
{ "valid": false, "row_count": 1, "errors": [ { "row": 0, "field": "rut", "code": "invalid_rut", "message": "invalid RUT format" } ] }
```

### GET /api/v1/qc/{campaign_id}/summary
```json
200 OK
{
  "campaign_id": "camp_9f2a...",
  "analytes": [
    { "analyte_code": "glucose", "control_level": "L1", "reagent_lot": "L23A",
      "n": 24, "mean": 95.1, "sd": 2.3, "cv_percent": 2.42,
      "run_status": "warning", "flags": { "1_2s": 1, "4_1s": 1 } },
    { "analyte_code": "ast", "control_level": "L2", "reagent_lot": "C11B",
      "n": 24, "mean": 118.7, "sd": 6.9, "cv_percent": 5.81,
      "run_status": "rejected", "flags": { "1_3s": 1 } }
  ]
}
```

### GET /api/v1/qc/{campaign_id}/analytes/{analyte_code}
```json
200 OK
{
  "analyte_code": "ast", "control_level": "L2", "reagent_lot": "C11B",
  "target_mean": 115.0, "target_sd": 5.0,
  "series": [
    { "measured_at": "2026-03-01T09:00:00Z", "value": 116.2, "z": 0.24, "band": "in_1sd" },
    { "measured_at": "2026-03-02T09:00:00Z", "value": 131.0, "z": 3.20, "band": "beyond_3sd" }
  ],
  "flags": [
    { "rule_code": "1_3s", "severity": "reject", "run_status": "rejected",
      "message": "⛔ Rechazo (1₃ₛ): el control Nivel 2 de AST superó ±3 DE. No libere resultados." }
  ]
}
```

### GET /api/v1/stats/{campaign_id}/summary  (privacy-enforced)
```json
200 OK
{
  "campaign_id": "camp_9f2a...",
  "min_group_size": 10,
  "groups": [
    { "group": { "sex": "F", "age_band": "40-49" }, "n": 34,
      "analytes": { "glucose": { "mean": 96.4, "sd": 10.1, "p50": 94.0 } } }
  ]
}
```

### POST /api/v1/exports/{campaign_id}/aggregated
```json
// request
{ "export_id": "proj_epi_2026a", "group_by": ["sex", "age_band"], "analytes": ["glucose", "chol_total"] }

// 201 Created
{
  "export_id": "proj_epi_2026a",
  "min_group_size": 10,
  "output_uri": "data/exports/proj_epi_2026a.csv",
  "audit_id": "aud_5b1c...",
  "subject_id_kind": "export_subject_uid",
  "suppressed_cells": 3
}
```

---

## 3. Privacy restrictions (per endpoint)

| Endpoint | Restriction |
|---|---|
| `stats/*`, `exports/*` | Aggregated only; suppress cells `n < min_group_size`; subject id = `export_subject_uid`; audited |
| `qc/*` | Control-level data only; contains no subject linkage at all |
| `campaigns/*` | Metadata only; `location_label` is coarse (comuna/región) |
| `ingestion/validate` | Never echoes RUT; errors are generic; nothing persisted |
| all | No response body ever contains `rut`/`name`/`phone`/`address`/`person_uid_global`/`study_subject_uid` |

`test_api_stats.py` asserts these fields are absent from serialized responses.

---

## 4. Suppressed small-group response examples

When a requested group has `n < min_group_size`, the cell is suppressed rather than returned:

```json
// GET /api/v1/stats/{campaign_id}/analytes/glucose?group_by=comuna
200 OK
{
  "analyte_code": "glucose", "min_group_size": 10,
  "groups": [
    { "group": { "comuna": "Valparaíso" }, "n": 41, "mean": 95.7, "sd": 11.2 },
    { "group": { "comuna": "Juan Fernández" }, "n": 6, "status": "suppressed", "reason": "n_below_min_group_size" }
  ],
  "suppressed_group_count": 1
}
```

Coarsening alternative (server may merge instead of drop):
```json
{ "group": { "comuna": "OTRAS (n<10 combinadas)" }, "n": 14, "mean": 97.1, "sd": 12.9, "coarsened": true }
```

Export endpoints apply the same rule at file-generation time and record `suppressed_cells` in the response and the `AuditLog` metadata. A request whose **entire** result would be suppressed returns `200` with empty `groups` and `"all_groups_suppressed": true` — never an error that leaks the underlying counts.
