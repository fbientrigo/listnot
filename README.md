# pucv-aq-qc

**Plataforma reproducible para adquisición, vigilancia bioquímica comunitaria y control de calidad.**

A reproducible data-quality and research layer for PUCV / Tecnología Médica / Centro de Bioanálisis
Clínico workflows. It sits **beside** existing workflows (it is *not* a LIS, EHR, scheduling, or diagnosis
system) and receives a **minimal, validated, identity-safe copy** of operational lab data for:

- deterministic **pseudonymization** at ingestion (a Chilean RUT never persists),
- a **QC engine** (Levey-Jennings, z-score, CV, Westgard-like rules),
- a **privacy-preserving statistical API** for students/researchers,
- reproducible **reports and dashboards**.

> **MVP uses synthetic data only.** No raw RUT is ever persisted, logged, exported, or returned.
> This is deterministic *pseudonymization*, not anonymization. See [`docs/PRIVACY_MODEL.md`](docs/PRIVACY_MODEL.md).

## Architecture at a glance

Modular Python monolith with explicit privacy boundaries (ingestion → protected operational →
research/statistical → export zones). See [`docs/SDD.md`](docs/SDD.md).

## Getting started

The MVP is implemented (modules `identity → schemas → database → synthetic →
ingestion → qc → privacy → api/dashboard/reporting`) and tested end-to-end.

```bash
cp .env.example .env
python scripts/generate_secret.py --write   # demo mode only
pip install -e ".[dev]"
make lint test     # ruff + pytest (synthetic data, no real RUT anywhere)
make demo          # full synthetic pipeline: campaign → QC → stats → report → export
make api           # uvicorn apps.api.main:app  (FastAPI, docs/API_CONTRACT.md)
make dashboard     # streamlit run apps/dashboard/app.py  (needs .[dashboard])
```

`make demo` regenerates the world deterministically, writes an aggregated report
(`data/reports/`) and an audited export (`data/exports/`), then runs
`scripts/scan_for_forbidden_identifiers.py` to prove **zero** RUT-shaped values
were persisted (`rut_persisted = false`).

## Documentation

| Doc | Contents |
|---|---|
| [`docs/SDD.md`](docs/SDD.md) | System design, modules, data flow, deployment, anti-overengineering |
| [`docs/PRIVACY_MODEL.md`](docs/PRIVACY_MODEL.md) | RUT threat model, HMAC design, ID layers, zones, key rotation |
| [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md) | All entities, fields, units, example analytes |
| [`docs/QC_MODEL.md`](docs/QC_MODEL.md) | LJ, z-score, CV, Westgard rules, run status, TM messages |
| [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) | Endpoints, examples, privacy restrictions, suppression |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Local / PUCV server / cloud profiles, secrets, backups |
| [`docs/DELIVERY_PLAN.md`](docs/DELIVERY_PLAN.md) | Milestones, first 8 commits, **first coding task** |
| [`docs/ADR/`](docs/ADR/) | Architecture decisions (monolith, HMAC, synthetic-first, SQLite→Postgres) |

## Team

- **Fabian** — Python, APIs, reproducible architecture, statistics, automation, testing, dashboards.
- **Beatriz** — clinical biochemistry, Tecnología Médica workflow, QC interpretation, units, reference ranges.
