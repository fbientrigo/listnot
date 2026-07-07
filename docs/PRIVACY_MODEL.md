# PRIVACY_MODEL.md

**Project:** `pucv-aq-qc` — identity, pseudonymization, and statistical-disclosure model.
**Audience:** Fabian (implementation), Beatriz (clinical validity), future institutional reviewer.

> **One sentence:** A Chilean RUT may transit ingestion *in memory only*; it is normalized, validated, converted to a keyed HMAC pseudonym, and then discarded. No raw RUT is ever persisted, logged, exported, or returned in the MVP.

---

## 1. RUT threat model

A RUT (`Rol Único Tributario`) is a **strong, universal, publicly-formatted** Chilean identifier. Its threat profile:

| Property | Consequence for us |
|---|---|
| Low entropy | Effective space is ~10⁷–10⁸ real values; the check digit is deterministic. **Brute-forceable.** |
| Structured & guessable | An attacker can enumerate *all plausible RUTs* cheaply. |
| Publicly linkable | RUT ↔ name/address exists in many external datasets. |
| Reused everywhere | Re-identification links our data to health, financial, civil records. |

**Adversaries we defend against:**
- **A1 — Curious student/researcher** with legitimate API/export access trying to single out an individual.
- **A2 — DB reader** (backup leak, misconfigured Postgres) who obtains the operational tables.
- **A3 — Insider with the operational DB *and* the HMAC secret** (worst case).

**Attacks:**
- **Dictionary/enumeration:** compute `f(rut)` for every plausible RUT, match against stored IDs.
- **Differencing:** subtract two overlapping aggregate queries to isolate one person.
- **Linkage:** join `person_uid_global` across exports to rebuild a longitudinal profile.

---

## 2. Why plain hashes are unsafe

```
BAD:  id = SHA256(rut)
BAD:  id = SHA256("salt_hardcoded" + rut)   # salt in repo = no salt
```

Because the RUT space is small and hashing is **fast and keyless**, an adversary (A1/A2) precomputes `SHA256(rut)` for **every** valid RUT in minutes and builds a full reverse lookup. A hardcoded or per-row-stored salt does not help: if it lives in the repo/DB, the adversary has it too. **Unsalted or repo-salted hashing of a low-entropy identifier provides no real protection.** This is why the brief forbids `SHA256(RUT)`.

---

## 3. HMAC design

We use **HMAC-SHA256 with a secret key stored outside the repository and outside the database.**

```
person_uid_global =
  "puid_" + BASE32( HMAC_SHA256(secret_v1,
      "pucv-aq-qc/person/rut/v1:" + normalized_rut) )
```

Why this resists the attacks in §1:
- **Keyed:** without `secret_v1`, HMAC output is (computationally) unlinkable to the RUT. Defeats A1/A2 dictionary attacks even though the RUT space is tiny.
- **Domain-separated:** the constant prefix (`pucv-aq-qc/person/rut/v1:`) prevents cross-protocol collisions and cross-layer reuse.
- **Versioned:** `secret_v1` + `key_version` column enable rotation (§7) without ambiguity.
- **Deterministic:** same RUT + same secret ⇒ same ID (required for longitudinal joins).
- **Non-reversible in practice:** reversal requires the secret; the secret is the single point of protection.

> **Naming discipline:** this is **deterministic pseudonymization**, *not* anonymization. Re-identification remains *possible for a holder of the secret*. True anonymization applies only to aggregated/irreversibly-transformed exports (§9).

### Reference interface (`identity/hmac_id.py`)
```python
def person_uid_global(normalized_rut: str, secret: bytes, key_version: str = "v1") -> str: ...
def study_subject_uid(person_uid: str, campaign_id: str, secret: bytes, key_version: str = "v1") -> str: ...
def export_subject_uid(study_uid: str, export_id: str, secret: bytes, key_version: str = "v1") -> str: ...
```
Rules for every function:
- Accept an **already normalized+validated** RUT (identity gateway enforces order).
- Return the prefixed BASE32 string only. **Never** return, log, or embed the input RUT.
- Raise `MissingSecretError` if the secret is empty/unset — never fall back to an insecure default.

---

## 4. ID layers

| Layer | ID | Derived from | Scope | Exposure |
|---|---|---|---|---|
| 1 | `person_uid_global` (`puid_…`) | normalized RUT + secret | Protected operational zone only | **Never** to students / public exports |
| 2 | `study_subject_uid` (`suid_…`) | `person_uid_global` + `campaign_id` + secret | Stable within one campaign/protocol | Longitudinal joins inside a campaign |
| 3 | `export_subject_uid` (`euid_…`) | `study_subject_uid` + `export_id` + secret | Stable only inside one approved export | Only value that leaves in exports |

```
person_uid_global = "puid_" + BASE32(HMAC(secret_v1, "pucv-aq-qc/person/rut/v1:"   + normalized_rut))
study_subject_uid = "suid_" + BASE32(HMAC(secret_v1, "pucv-aq-qc/study/{campaign_id}/v1:" + person_uid_global))
export_subject_uid= "euid_" + BASE32(HMAC(secret_v1, "pucv-aq-qc/export/{export_id}/v1:"  + study_subject_uid))
```

**Why three layers:** layering blocks **linkage (A1)**. A student receiving export A gets `euid` values that cannot be joined to export B's `euid` values for the same person, because each export is HMAC-namespaced. The `person_uid_global` that *could* link everything never leaves the operational zone.

---

## 5. Data zones (privacy boundaries)

| Zone | Sees | Persists | Access |
|---|---|---|---|
| **Ingestion** | Raw input (MVP: synthetic). Future: RUT in memory | Nothing raw | Ingestion process only |
| **Protected operational** | Campaign/sample/result/QC + `person_uid_global` | Pseudonymous rows; **no** name/phone/address/RUT | Authorized operational roles |
| **Research/statistical** | `study_subject_uid` / `export_subject_uid`, aggregates | Aggregated/pseudonymized only | Students/researchers |
| **Export** | Safe datasets, reports | Files + `StatisticalExport` audit record | Enforced by export policy |

The zones are **code boundaries**, not just docs: the API/dashboard packages import from `privacy/` and `qc/`, and must not import the operational DB models in a way that can select `person_uid_global` into a response. A test (`test_api_stats.py`) asserts stat responses contain no such field.

---

## 6. Key storage

| Profile | `PUCV_ID_SECRET_V1` location |
|---|---|
| Local/demo | `.env` (gitignored) or auto-generated by `scripts/generate_secret.py` **only when `PUCV_DEMO_MODE=true`** |
| PUCV server | Server environment variable or a `chmod 600` file outside the repo tree, owned by the service user |
| Cloud | Managed secret manager (AWS Secrets Manager / GCP Secret Manager / Azure Key Vault), injected at runtime |

Hard rules:
- The secret is **never** in git, never in the DB, never in a report, never in a log line.
- `config/settings.py` loads it from env; if absent in non-demo mode, the app **fails to start** (loud, not silent-insecure).
- Minimum length enforced (≥ 32 bytes / 256 bits of entropy).

---

## 7. Key rotation strategy

Because `person_uid_global` is deterministic on the secret, rotation is a **re-keying event**, not a drop-in.

- Every subject row stores `key_version` (e.g. `v1`). New secret ⇒ new version `v2` (`PUCV_ID_SECRET_V1`, `PUCV_ID_SECRET_V2`, `PUCV_ACTIVE_KEY_VERSION=v2`).
- **New ingestion** uses the active version. Historical rows keep their `key_version` and remain joinable within their era.
- **Cross-era linkage** of the same person requires re-deriving from the RUT — which we no longer hold (by design). So rotation is *effectively a fresh cohort boundary*. This is acceptable and intentional: it caps the blast radius of a leaked secret.
- **On suspected secret compromise:** rotate immediately; treat pre-rotation `person_uid_global` values as burned (re-identifiable by the attacker) and, per protocol, quarantine/rebuild affected exports.
- Rotation is an **audited admin action** (`audit.logger`, `event_type="key_rotation"`, metadata **without** any key material).

---

## 8. Logging rules

- **Never** log a RUT — normalized or raw — at any level, in any module.
- **Never** put a RUT in exception messages, stack traces, `repr`/`__str__`, or test fixtures/snapshots.
- Identity errors carry a **generic** message (`"invalid RUT format"`) plus a non-identifying correlation id; they must not echo the offending value.
- `scripts/scan_for_forbidden_identifiers.py` greps DB files, exports, logs, and reports for RUT-shaped patterns and fails CI if any match. `test_no_rut_persistence.py` runs the demo end-to-end and asserts zero matches.

---

## 9. Forbidden persistence rules

Never written to any persisted file or table (MVP):
`RUT` · `name` · `phone` · `address` · exact geolocation · any direct identifier.

The only subject key persisted operationally is `person_uid_global` (+ `key_version`). Names/phones/addresses have **no column** in the schema — they cannot be stored even by mistake.

---

## 10. Statistical API privacy rules

Statistical/export endpoints must **never** return: RUT · name · phone · address · exact location · direct identifiers · **small groups** · raw row-level data enabling re-identification.

- **Aggregation only.** Endpoints return counts/means/SD/CV/quantiles by group, never rows.
- **Minimum group size:** `PUCV_MIN_GROUP_SIZE` (default **10**). Any cell with `n < min_group_size` is **suppressed** (returned as `null`/`"suppressed"`) or **coarsened** (merged into a broader bucket). No exceptions for "trusted" users in MVP.
- **Subject identifier in exports:** only `export_subject_uid`, never `study_subject_uid` or `person_uid_global`.
- **Every export audited:** `StatisticalExport` row + `AuditLog` event with policy, `min_group_size`, actor, and output URI.
- **Known limitation (documented, not solved):** repeated overlapping aggregate queries permit differencing attacks; MVP mitigates via per-export namespacing + audit, not formal DP. Flagged for Week-8+ review.
