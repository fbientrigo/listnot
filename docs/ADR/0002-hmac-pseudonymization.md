# ADR-0002 — HMAC-SHA256 deterministic pseudonymization

**Status:** Accepted · **Date:** 2026-07-07 · **Deciders:** Fabian, Beatriz

## Context
Ingestion may see a Chilean RUT. The RUT space is small and publicly linkable, so any **keyless** transform (`SHA256(rut)`, or a hash with a repo/DB-stored salt) is trivially reversed by enumerating all RUTs. We need deterministic IDs (for longitudinal joins) that are non-reversible in practice.

## Decision
Derive all subject identifiers with **HMAC-SHA256 keyed by a secret held outside repo and DB**, in three domain-separated, namespaced layers:

```
person_uid_global = "puid_" + BASE32(HMAC(secret_v1, "pucv-aq-qc/person/rut/v1:"        + normalized_rut))
study_subject_uid = "suid_" + BASE32(HMAC(secret_v1, "pucv-aq-qc/study/{campaign_id}/v1:"+ person_uid_global))
export_subject_uid= "euid_" + BASE32(HMAC(secret_v1, "pucv-aq-qc/export/{export_id}/v1:" + study_subject_uid))
```

Store the **full 256-bit** HMAC (BASE32). Truncate only for display, never for storage/join keys. Every subject row records `key_version` for rotation.

## Rationale
- **Keyed** ⇒ dictionary attack requires the secret; the secret becomes the single, guardable point of protection.
- **Domain separation** (constant prefixes) prevents cross-layer/cross-protocol collisions and reuse.
- **Layering** blocks cross-export linkage: `euid` values are per-export namespaced; the globally-linking `puid` never leaves the operational zone.
- **Full-width output** preserves collision resistance; shortening is cosmetic only.

## Consequences
- (+) Deterministic, non-reversible-in-practice, rotatable.
- (−) Secret compromise re-enables re-identification of pre-rotation IDs → treat secret as crown jewel; rotation caps blast radius (`PRIVACY_MODEL.md §7`).
- (−) This is **pseudonymization, not anonymization** — naming discipline enforced in docs and code.

## Rejected
`SHA256(rut)`, unsalted/repo-salted hashes (reversible via enumeration); storing a RUT↔ID mapping table (forbidden — becomes the re-identification key); truncated IDs as join keys (collision risk).
