# ADR-0004 — SQLite now, PostgreSQL-compatible path

**Status:** Accepted · **Date:** 2026-07-07 · **Deciders:** Fabian, Beatriz

## Context
Local development and demo must be zero-setup, but the pilot/cloud profiles need PostgreSQL. We do not want two schemas or a painful migration.

## Decision
Use **SQLModel/SQLAlchemy** with a **single model definition** targeting SQLite locally (`sqlite:///data/pucv.db`) and PostgreSQL on server/cloud, selected only by `DATABASE_URL`. Constrain modeling to the **portable subset**:

- UUID/string PKs generated in Python (`camp_…`, `subj_…`) — no reliance on DB-specific UUID types.
- `list[str]` fields (e.g. `preanalytical_flags`, `result_flags`) stored as JSON — works on both engines.
- Timezone-aware UTC datetimes; avoid SQLite-only or Postgres-only column types.
- **Synchronous** sessions in MVP (`database/session.py`); async is postponed (SDD §7 critique).
- Introduce Alembic migrations at the SQLite→Postgres transition (Week 5), not before.

## Rationale
- Zero-friction local dev and CI (file DB, no server).
- One schema, one set of models ⇒ no drift between dev and prod.
- Portable-subset discipline avoids the classic "worked on SQLite, broke on Postgres" trap.

## Consequences
- (+) `make demo` runs with no external services.
- (+) Switching to Postgres is a config + Alembic step, not a rewrite.
- (−) Cannot use Postgres-only features (native arrays, `jsonb` operators) in core queries during MVP — acceptable; aggregations are simple.
- (−) JSON-encoded list columns are less queryable than native arrays — fine at pilot scale.

## Rejected
Postgres from day one (setup friction for a 2-person team, no MVP benefit); raw SQL per engine (duplicated, drift-prone); NoSQL (relational QC/aggregation is the natural fit).
