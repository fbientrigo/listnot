# DEPLOYMENT.md

**Project:** `pucv-aq-qc`. Three deployment profiles selected by `PUCV_AQ_ENV`.
Core logic must never hard-depend on cloud-specific APIs; storage/secret/DB are the only things that change between profiles.

---

## 1. Local (development / demo)

```bash
# one-time
cp .env.example .env
python scripts/generate_secret.py --write   # writes PUCV_ID_SECRET_V1 into .env (DEMO ONLY)
pip install -e ".[dev]"

# run
make demo        # full synthetic pipeline (see README / SDD §MVP demo flow)
uvicorn apps.api.main:app --reload
streamlit run apps/dashboard/app.py
```

- DB: `sqlite:///data/pucv.db`.
- Data: **synthetic only.**
- Secret: local `.env` (gitignored) or auto-generated in demo mode.
- Debug allowed — **but no RUT in logs, ever** (enforced by `scan_for_forbidden_identifiers.py`).
- Access: open on localhost.

## 2. PUCV server (pilot)

- DB: **PostgreSQL** via Docker Compose (`docker-compose.yml`).
- Secret: **server environment variable** or a `chmod 600` file outside the repo, owned by the service user — never in the image, never in git.
- Transport: **HTTPS via reverse proxy** (nginx/Caddy) terminating TLS in front of uvicorn.
- Data: pseudonymized pilot (`Weeks 5–6`). Still no raw RUT persisted.
- Backups: scheduled `pg_dump` to a restricted location; test restores.
- Access: restricted admin; single API key or network ACL for the stat API in MVP.

```bash
export PUCV_AQ_ENV=server
export DATABASE_URL=postgresql+psycopg://pucv:***@db:5432/pucv
export PUCV_ID_SECRET_V1="$(cat /etc/pucv/secret_v1)"   # outside repo
docker compose up -d db api dashboard
```

## 3. Cloud

- DB: **managed PostgreSQL** (RDS / Cloud SQL / Azure DB).
- Secret: **managed secret manager**, injected at runtime; app fails closed if absent.
- Storage: **object storage** (`PUCV_STORAGE_BACKEND=s3|gcs|azure`) for reports/exports.
- Logs: centralized; TLS mandatory end-to-end.
- **No hard dependency** on any provider SDK in `src/pucv_aq_qc/` core — cloud specifics live at the edges (config + a storage adapter).

---

## 4. Environment variables

| Variable | Example | Meaning |
|---|---|---|
| `PUCV_AQ_ENV` | `local` \| `server` \| `cloud` | Active deployment profile |
| `DATABASE_URL` | `sqlite:///data/pucv.db` / `postgresql+psycopg://…` | DB connection |
| `PUCV_ID_SECRET_V1` | `<≥32 random bytes, base64>` | HMAC identity secret (**never committed**) |
| `PUCV_ACTIVE_KEY_VERSION` | `v1` | Which secret version to use for new IDs |
| `PUCV_MIN_GROUP_SIZE` | `10` | Small-group suppression threshold |
| `PUCV_STORAGE_BACKEND` | `local` \| `s3` \| `gcs` \| `azure` | Export/report storage adapter |
| `PUCV_DEMO_MODE` | `true` \| `false` | Enables demo secret auto-gen + `/demo/*` endpoints |

`.env.example` ships every key with placeholder/empty values and comments. **Real secrets never land in git** (`.gitignore` covers `.env`, `data/`, `*.db`).

---

## 5. Secrets handling

- Loaded by `config/settings.py` from environment (12-factor). No secret in code, DB, report, or log.
- Non-demo profiles **fail to start** if `PUCV_ID_SECRET_V1` is missing or `< 32` bytes — no insecure fallback.
- `scripts/generate_secret.py` creates a strong secret; with `--write` it edits `.env` **only when `PUCV_DEMO_MODE=true`**, otherwise it prints to stdout for the operator to place manually.
- Rotation: add `PUCV_ID_SECRET_V2`, set `PUCV_ACTIVE_KEY_VERSION=v2`; see `PRIVACY_MODEL.md §7`. Rotation is an audited admin action.

## 6. Backup notes

- **Local:** none required (synthetic, disposable). Delete `data/pucv.db` to reset.
- **Server:** nightly `pg_dump`, encrypted at rest, retention per PUCV policy; periodic restore drills. Backups inherit the same forbidden-identifier guarantees (no RUT present to leak).
- **Cloud:** managed automated snapshots + PITR; export bucket versioned with lifecycle rules.
- The HMAC secret is **backed up separately** from the DB (losing it de-links historical `person_uid_global`; leaking it with the DB is the A3 worst case). Keep them in different trust domains.

## 7. What changes between profiles (summary)

| Concern | Local | Server | Cloud |
|---|---|---|---|
| DB engine | SQLite | PostgreSQL | Managed PostgreSQL |
| Secret source | `.env`/demo-gen | server env/file | secret manager |
| Storage | local FS | local FS | object storage |
| TLS | none | reverse proxy | mandatory e2e |
| Backups | none | pg_dump | managed snapshots |
| Data | synthetic | pseudonymized pilot | pseudonymized |
| `/demo/*` | on | off | off |

Everything else — the models, QC engine, privacy layer, API contract — is **identical** across profiles by design. That identity is the whole point of "reproducible."
