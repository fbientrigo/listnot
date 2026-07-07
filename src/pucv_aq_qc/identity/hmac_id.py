"""Keyed HMAC pseudonym derivation (docs/PRIVACY_MODEL.md §3-4, ADR-0002).

Three domain-separated, namespaced layers derived with HMAC-SHA256 keyed by a
secret held outside repo and DB:

    person_uid_global = "puid_" + BASE32(HMAC(secret, "pucv-aq-qc/person/rut/v1:" + rut))
    study_subject_uid = "suid_" + BASE32(HMAC(secret, "pucv-aq-qc/study/{campaign}/v1:" + puid))
    export_subject_uid= "euid_" + BASE32(HMAC(secret, "pucv-aq-qc/export/{export}/v1:" + suid))

The full 256-bit HMAC is kept (BASE32, no truncation) — truncation is cosmetic
only and must never be used for storage/join keys. No function returns, logs, or
embeds a raw RUT.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

from pucv_aq_qc.identity.exceptions import MissingSecretError

_PERSON_PREFIX = "puid_"
_STUDY_PREFIX = "suid_"
_EXPORT_PREFIX = "euid_"


def _b32(digest: bytes) -> str:
    """Base32-encode without padding, uppercase (URL/log/display safe)."""
    return base64.b32encode(digest).decode("ascii").rstrip("=")


def _derive(secret: bytes, domain: str, message: str, prefix: str) -> str:
    if not secret:
        raise MissingSecretError()
    mac = hmac.new(secret, (domain + message).encode("utf-8"), hashlib.sha256)
    return prefix + _b32(mac.digest())


def person_uid_global(normalized_rut: str, secret: bytes, key_version: str = "v1") -> str:
    """Layer 1: global operational pseudonym from an already-normalized RUT.

    The caller (identity gateway) must pass a normalized+validated RUT.
    Returns ``puid_…``; never returns or logs the RUT.
    """
    domain = f"pucv-aq-qc/person/rut/{key_version}:"
    return _derive(secret, domain, normalized_rut, _PERSON_PREFIX)


def study_subject_uid(
    person_uid: str, campaign_id: str, secret: bytes, key_version: str = "v1"
) -> str:
    """Layer 2: per-campaign pseudonym; stable within one campaign/protocol.

    Returns ``suid_…``.
    """
    domain = f"pucv-aq-qc/study/{campaign_id}/{key_version}:"
    return _derive(secret, domain, person_uid, _STUDY_PREFIX)


def export_subject_uid(
    study_uid: str, export_id: str, secret: bytes, key_version: str = "v1"
) -> str:
    """Layer 3: per-export pseudonym; the only subject id that leaves in exports.

    Per-export namespacing blocks cross-export linkage. Returns ``euid_…``.
    """
    domain = f"pucv-aq-qc/export/{export_id}/{key_version}:"
    return _derive(secret, domain, study_uid, _EXPORT_PREFIX)
