"""Sync engine + session scope for Celery workers and Alembic."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()

sync_engine = create_engine(
    _settings.sync_database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
)

SyncSessionFactory: sessionmaker[Session] = sessionmaker(
    sync_engine,
    expire_on_commit=False,
    autoflush=False,
)


@contextmanager
def sync_session_scope() -> Iterator[Session]:
    """Transactional scope for worker tasks: commit on success, rollback on error."""
    session = SyncSessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
