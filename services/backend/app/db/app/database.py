"""Connection/session management for `career_app`. Owner: M3 (C-01).

Deliberately a copy of the `career_jobs` shape rather than a shared engine: the
two databases have separate roles, URLs and migration chains, and no code path
may open a transaction across both. SQLite (tests) and PostgreSQL (deployment)
both work unmodified.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import Settings


def create_app_engine(settings: Settings | None = None) -> Engine:
    config = settings or Settings()
    url = config.app_database_url.get_secret_value()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    if url.startswith("sqlite"):
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """One atomic unit of work. Rolls back and re-raises on any failure."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def supports_skip_locked(session: Session) -> bool:
    """PostgreSQL can hand each worker a different row; SQLite cannot."""
    return session.bind is not None and session.bind.dialect.name == "postgresql"
