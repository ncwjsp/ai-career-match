"""Connection/session management for `career_jobs`. Owner: M2 (B-09)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import Settings


def create_job_engine(settings: Settings | None = None) -> Engine:
    """Build the `career_jobs` engine from settings.

    `future=True`/pool defaults are SQLAlchemy 2.x defaults already; no extra
    pooling config is applied here so a SQLite URL (used by tests) and a
    PostgreSQL URL (used in deployment) both work unmodified. SQLite ignores
    foreign keys unless a connection turns them on; PostgreSQL always enforces
    them, so this only changes SQLite's default.
    """
    config = settings or Settings()
    url = config.job_database_url.get_secret_value()
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
