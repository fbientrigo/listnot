# ADR-0001 — Modular Python monolith

**Status:** Accepted · **Date:** 2026-07-07 · **Deciders:** Fabian, Beatriz

## Context
Two developers, an 8-week horizon, and a system whose hardest requirement is a **privacy boundary**, not scale. Options considered: (a) microservices, (b) dashboard-first Streamlit app with logic inline, (c) modular monolith.

## Decision
Build a **single deployable Python package** (`src/pucv_aq_qc/`) with strong *internal* module boundaries (`identity`, `schemas`, `ingestion`, `synthetic`, `qc`, `database`, `privacy`, `reporting`, `audit`, `config`) and thin entry points (`apps/api`, `apps/dashboard`). Boundaries are enforced by package structure and tests, not by network calls.

## Rationale
- The privacy boundary is a **code invariant** (RUT never crosses out of ingestion). A monolith lets a single test suite prove that invariant across the whole flow; microservices would scatter it across services and network hops.
- Two people cannot operate a fleet of services in 8 weeks.
- One deploy unit ⇒ trivial local dev, reproducible `make demo`.

## Consequences
- (+) Fast to build, easy to test end-to-end, one artifact to deploy.
- (+) Module packages give clean seams to extract services later *if ever needed*.
- (−) No independent scaling of components — irrelevant at pilot scale.
- Discipline required: `apps/*` and `privacy/` must not import operational DB models in a way that can select `person_uid_global` into a response (test-enforced).

## Rejected
Microservices, K8s, dashboard-first architecture — all violate the anti-overengineering constraints and add operational cost with zero MVP benefit.
