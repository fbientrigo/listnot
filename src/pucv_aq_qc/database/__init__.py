"""Persistence: SQLModel models, engine/session, and schema init.

SQLite locally, PostgreSQL on server/cloud, one model set, selected only by
``DATABASE_URL`` (ADR-0004). Constrained to the portable subset: string PKs
generated in Python, JSON-encoded list columns, timezone-aware UTC datetimes,
synchronous sessions. No table stores rut/name/phone/address.
"""

from pucv_aq_qc.database.ids import new_id
from pucv_aq_qc.database.session import get_engine, get_session, session_scope

__all__ = ["new_id", "get_engine", "get_session", "session_scope"]
