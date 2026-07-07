# DELIVERY_PLAN.md

**Project:** `pucv-aq-qc`. Engineering milestones and the first eight commits.
Maps the 8-week pitch onto concrete, testable increments. Prioritizes a system Fabian can start coding **today**.

---

## Milestone map (pitch → engineering)

| Week | Pitch | Engineering milestone |
|---|---|---|
| 1 | Workflow abstraction, data dictionary, QC protocol | Repo, architecture docs, **identity module**, RUT validation, HMAC IDs |
| 2 | (cont.) | Schemas, data dictionary, ingestion contracts, **no-RUT persistence test** |
| 3 | Synthetic-data demo | Synthetic campaign/subject/sample/result generator |
| 4 | (cont.) | QC engine + dashboard prototype |
| 5 | Controlled pilot | CSV/Excel import validation + protected operational DB (SQLite→Postgres) |
| 6 | (cont.) | Privacy layer: aggregation + small-group suppression |
| 7 | Statistical API + report | FastAPI statistical endpoints + audit logs |
| 8 | (cont.) | Reproducible report, `make demo`, deployment-profile docs |

---

## First 8 commits

Each commit is small, green, and independently reviewable. `make lint test` must pass at every step.

### Commit 1 — Identity core (RUT + HMAC IDs)
- **Files:** `pyproject.toml`, `.env.example`, `.gitignore`, `README.md`, `src/pucv_aq_qc/__init__.py`, `src/pucv_aq_qc/config/settings.py`, `identity/{__init__,rut,hmac_id,models,exceptions}.py`, `scripts/generate_secret.py`, `tests/{test_rut_validation,test_identity_hmac,test_no_rut_persistence}.py`
- **Reason:** The privacy boundary is the riskiest, load-bearing part; build and prove it first (identity-safe ingestion core, not dashboard-first).
- **Acceptance tests:** valid RUTs normalize; invalid RUTs raise; same RUT+secret ⇒ same ID; different secret ⇒ different ID; ID has `puid_`/`suid_`/`euid_` prefix; RUT never returned; RUT never written to any generated artifact.
- **Command:** `pytest tests/test_rut_validation.py tests/test_identity_hmac.py tests/test_no_rut_persistence.py -q`
- **DoD:** all three test files pass; `scripts/generate_secret.py` produces a ≥32-byte secret; no RUT appears in any output or file.

### Commit 2 — Pydantic schemas + data contracts
- **Files:** `schemas/{campaign,subject,sample,result,qc,export}.py`, `ingestion/contracts.py`
- **Reason:** Freeze the data shapes the whole system agrees on before persistence/QC touch them.
- **Acceptance tests:** valid payloads parse; forbidden fields (`rut`, `name`, `phone`, `address`) are **absent** from persisted-model schemas; unit/enum validation works.
- **Command:** `pytest tests/test_schemas.py -q`
- **DoD:** schemas import cleanly; a schema-level test asserts no forbidden field exists on operational models.

### Commit 3 — Database models + session (SQLite)
- **Files:** `database/{models,session,init_db}.py`
- **Reason:** Persist pseudonymous entities per DATA_DICTIONARY; establish Postgres-portable subset.
- **Acceptance tests:** `init_db` creates all tables; a round-trip insert/select works on SQLite; no table has a RUT/name/phone/address column.
- **Command:** `pytest tests/test_database.py -q`
- **DoD:** SQLite file created under `data/`; schema matches DATA_DICTIONARY; portability constraints (ADR-0004) respected.

### Commit 4 — Synthetic generator + valid synthetic RUTs
- **Files:** `synthetic/{rut_generator,analytes,generator,scenarios}.py`, `scripts/generate_synthetic_data.py`, `tests/test_synthetic_generation.py`
- **Reason:** Realistic seeded data to drive QC and demos (ADR-0003).
- **Acceptance tests:** generated RUTs pass `rut.validate`; generator is deterministic under a seed; scenarios inject bias/drift/imprecision/outliers/missing/pre-analytical; **no raw RUT persisted** after generation.
- **Command:** `pytest tests/test_synthetic_generation.py -q`
- **DoD:** a synthetic campaign with subjects/samples/results/QC is produced end-to-end; RUTs discarded post-ID.

### Commit 5 — Ingestion validators + CSV/Excel loader
- **Files:** `ingestion/{validators,csv_loader}.py`, `tests/test_ingestion_validation.py`
- **Reason:** Safe acquisition layer: parse → validate → identity gateway → internal models, never persisting raw input.
- **Acceptance tests:** valid CSV validates; bad rows produce generic errors **without echoing RUT**; identity gateway derives IDs and discards RUT.
- **Command:** `pytest tests/test_ingestion_validation.py -q`
- **DoD:** validate path returns normalized preview with `puid` (not returned) and no RUT anywhere in output.

### Commit 6 — QC engine (LJ, metrics, Westgard, run status)
- **Files:** `qc/{levey_jennings,metrics,westgard,summary}.py`, `tests/test_qc_rules.py`
- **Reason:** Core product capability; must fire correctly on injected scenarios.
- **Acceptance tests:** z-score correct; mean/SD/CV correct; each Westgard rule triggers on a crafted series and is silent otherwise; run status = most-severe; messages are the TM-readable Spanish templates.
- **Command:** `pytest tests/test_qc_rules.py -q`
- **DoD:** rules validated against ground-truth injected faults; run-status logic matches QC_MODEL §6.

### Commit 7 — Privacy layer (aggregation + suppression) + audit
- **Files:** `privacy/{aggregation,suppression,export_policy}.py`, `audit/logger.py`, `tests/test_privacy_suppression.py`
- **Reason:** Enforce statistical-disclosure rules before anything is exposed.
- **Acceptance tests:** cells with `n < min_group_size` are suppressed/coarsened; exports carry only `export_subject_uid`; every export writes an `AuditLog` row; audit metadata contains no identifiers.
- **Command:** `pytest tests/test_privacy_suppression.py -q`
- **DoD:** default `min_group_size=10` enforced; suppression provable by test; audit records present.

### Commit 8 — FastAPI service + Streamlit dashboard + report + `make demo`
- **Files:** `apps/api/main.py`, `apps/dashboard/app.py`, `reporting/{markdown_report,html_report}.py`, `scripts/{scan_for_forbidden_identifiers,demo_local}.py`, `Makefile`, `docker-compose.yml`, `tests/test_api_stats.py`
- **Reason:** Assemble the end-to-end demo flow and prove no RUT persists.
- **Acceptance tests:** `/health` ok; stat endpoints never return forbidden fields/small groups; `make demo` runs steps 1–16; `scan_for_forbidden_identifiers.py` finds zero RUTs in `data/` and reports.
- **Command:** `make demo && pytest tests/test_api_stats.py -q`
- **DoD:** demo produces campaign → QC → dashboard → aggregated report/export; forbidden-identifier scan passes; step 16 proves `rut_persisted == false`.

---

## FIRST CODING TASK

> **This is the exact task Fabian should execute in the blank repo, today. It is Commit 1.**

**Goal:** stand up the identity-safe core — the privacy boundary — with tests, before anything else.

**Do exactly this:**

1. **Initialize the repo & tooling.**
   - `pyproject.toml`: package `pucv_aq_qc` (src layout), Python `>=3.11`. Runtime deps: `pydantic>=2`. Dev deps: `pytest`, `ruff`. Configure `pytest` `testpaths=["tests"]` and `ruff`.
   - `.gitignore`: `.env`, `data/*.db`, `data/exports/*`, `data/staging/*`, `__pycache__/`, `.venv/`.
   - `.env.example`: every var from DEPLOYMENT §4 with empty/placeholder values (no real secret).
   - `README.md`: one-paragraph purpose + `make demo` intent + link to `docs/`.

2. **`src/pucv_aq_qc/config/settings.py`** — load env (pydantic-settings or `os.environ`). Expose `id_secret_v1: bytes`, `active_key_version: str`, `min_group_size: int`, `demo_mode: bool`. **Fail loudly** if `id_secret_v1` is missing/`<32` bytes in non-demo mode.

3. **`src/pucv_aq_qc/identity/rut.py`**
   ```python
   def normalize(raw: str) -> str:
       """Strip dots/spaces, uppercase K, return 'NNNNNNNN-DV'. Raise InvalidRUTError on malformed input (message must NOT contain the RUT)."""
   def validate(normalized: str) -> bool:
       """Verify módulo-11 check digit. Return True; raise InvalidRUTError if invalid."""
   def compute_dv(body: int) -> str:
       """Return the módulo-11 check digit ('0'–'9' or 'K')."""
   ```

4. **`src/pucv_aq_qc/identity/hmac_id.py`**
   ```python
   def person_uid_global(normalized_rut: str, secret: bytes, key_version: str = "v1") -> str
   def study_subject_uid(person_uid: str, campaign_id: str, secret: bytes, key_version: str = "v1") -> str
   def export_subject_uid(study_uid: str, export_id: str, secret: bytes, key_version: str = "v1") -> str
   ```
   Construction per PRIVACY_MODEL §3–4: `HMAC-SHA256(secret, "pucv-aq-qc/<domain>/…/v1:" + input)` → BASE32 (full width) → prefixed (`puid_`/`suid_`/`euid_`). Raise `MissingSecretError` on empty secret. **Never** return, log, or embed the raw RUT.

5. **`identity/exceptions.py`** (`InvalidRUTError`, `MissingSecretError` — generic messages, no RUT) and **`identity/models.py`** (small dataclasses/Pydantic types if useful).

6. **`scripts/generate_secret.py`** — emit a ≥32-byte cryptographically random secret (base64); `--write` edits `.env` **only when `PUCV_DEMO_MODE=true`**, else prints to stdout.

7. **Tests:**
   - `tests/test_rut_validation.py`: known valid synthetic RUTs normalize/validate; malformed and bad-check-digit RUTs raise; assert **no exception message contains a RUT**.
   - `tests/test_identity_hmac.py`: same RUT+secret ⇒ identical ID; same RUT+**different** secret ⇒ different ID; each layer returns its correct prefix; empty secret raises; the raw RUT is **never** in any return value.
   - `tests/test_no_rut_persistence.py`: run the full derive path over synthetic RUTs, write any produced artifacts to a temp dir, then scan every produced string/file for RUT-shaped patterns and assert **zero** matches.

**Acceptance criteria (must all hold):**
- valid Chilean RUTs normalize correctly;
- invalid RUTs fail;
- same RUT + same secret gives the same ID;
- same RUT + different secret gives a different ID;
- ID has the expected prefix (`puid_`/`suid_`/`euid_`);
- the raw RUT is never returned;
- the raw RUT is not written to any generated artifact;
- `pytest` is green.

**Run:** `pip install -e ".[dev]" && pytest -q`

**Definition of done:** all three test files pass, `generate_secret.py` produces a valid secret, and a manual `grep` for any test RUT across the working tree and `data/` returns nothing. Commit as *"Identity core: RUT validation + HMAC pseudonymization + no-RUT-persistence tests"* and push to `claude/pucv-aq-qc-architecture-7v8ykz`.
