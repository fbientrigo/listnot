"""Engine + synchronous session management (ADR-0004: sync sessions in MVP)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import cache
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from pucv_aq_qc.config.settings import get_settings


def _ensure_sqlite_dir(database_url: str) -> None:
    """Create the parent directory for a SQLite file URL if needed."""
    prefix = "sqlite:///"
    if database_url.startswith(prefix):
        path = Path(database_url[len(prefix):])
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)


@cache
def get_engine(database_url: str | None = None) -> Engine:
    """Return a cached engine for the given (or configured) database URL."""
    url = database_url or get_settings().database_url
    _ensure_sqlite_dir(url)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, echo=False, connect_args=connect_args)


def get_session(database_url: str | None = None) -> Session:
    """Return a new synchronous session bound to the engine.

    ``expire_on_commit=False`` so generated/queried ORM instances stay usable
    after the transactional scope closes (we routinely read ids/values from
    detached objects for reports and API responses).
    """
    return Session(get_engine(database_url), expire_on_commit=False)


@contextmanager
def session_scope(database_url: str | None = None) -> Iterator[Session]:
    """Transactional scope: commit on success, rollback on error, always close."""
    session = get_session(database_url)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
