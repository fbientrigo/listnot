"""Small value types for the identity layer.

These carry only pseudonymous identifiers — never a RUT.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SubjectIdentity:
    """The pseudonymous identity derived for a subject at ingestion.

    Deliberately has no field capable of holding a RUT. ``person_uid_global`` is
    operational-zone only and must never be serialized into an API response
    (docs/PRIVACY_MODEL.md §4-5).
    """

    person_uid_global: str
    key_version: str
