"""Prefixed string ID generation (ADR-0004: PKs generated in Python, not the DB).

Prefixes follow docs/DATA_DICTIONARY.md: camp_, subj_, stsu_, samp_, res_,
qcm_, qcf_, exp_, aud_. These are opaque entity keys and never derived from a
RUT — subject *pseudonyms* (puid_/suid_/euid_) come from identity.hmac_id.
"""

from __future__ import annotations

from uuid import uuid4


def new_id(prefix: str) -> str:
    """Return ``<prefix>_<uuid4-hex>`` (portable across SQLite and Postgres)."""
    return f"{prefix}_{uuid4().hex}"
