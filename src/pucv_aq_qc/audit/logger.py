"""Append-only audit logging (docs/DATA_DICTIONARY.md §9, PRIVACY_MODEL §8).

Every access/export/ingestion/admin/key_rotation event is recorded. Event
metadata must never contain a RUT or identifier; the logger actively scans
metadata and refuses to write if it would leak one (fail closed).
"""

from __future__ import annotations

import json

from sqlmodel import Session

from pucv_aq_qc.database.models import AuditLog
from pucv_aq_qc.privacy import forbidden
from pucv_aq_qc.schemas.enums import EventType


class MetadataLeakError(ValueError):
    """Raised when audit metadata would contain a RUT-shaped value."""


def _assert_clean(metadata: dict) -> None:
    blob = json.dumps(metadata, default=str)
    if forbidden.contains_forbidden(blob):
        # Do not include the offending value in the error.
        raise MetadataLeakError("audit metadata contains a forbidden identifier pattern")


class AuditLogger:
    """Writes audit rows through a provided session (caller controls the txn)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def log(
        self,
        event_type: EventType | str,
        *,
        actor: str,
        role: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        metadata: dict | None = None,
        commit: bool = True,
    ) -> AuditLog:
        meta = metadata or {}
        _assert_clean(meta)
        row = AuditLog(
            event_type=str(event_type),
            actor=actor,
            role=role,
            resource_type=resource_type,
            resource_id=resource_id,
            event_metadata=meta,
        )
        self._session.add(row)
        if commit:
            self._session.commit()
        else:
            self._session.flush()
        return row
