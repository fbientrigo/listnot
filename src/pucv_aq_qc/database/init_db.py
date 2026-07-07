"""Schema creation. Alembic migrations are introduced at the SQLite→Postgres
transition (Week 5, ADR-0004); for MVP we create tables directly.
"""

from __future__ import annotations

from sqlmodel import SQLModel

from pucv_aq_qc.database import models  # noqa: F401 — registers tables on SQLModel.metadata
from pucv_aq_qc.database.session import get_engine


def init_db(database_url: str | None = None) -> None:
    """Create all tables on the configured (or given) database."""
    engine = get_engine(database_url)
    SQLModel.metadata.create_all(engine)


def drop_all(database_url: str | None = None) -> None:
    """Drop all tables (used by tests / demo reset)."""
    engine = get_engine(database_url)
    SQLModel.metadata.drop_all(engine)
