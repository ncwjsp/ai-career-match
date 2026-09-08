"""Shared fixtures for `career_app` persistence tests. Owner: M3 (C-01).

Runs the real Alembic chain (`alembic-app.ini`) against a fresh temp-file SQLite
database per test, the same approach M2 uses for `career_jobs`, so a broken
migration fails these tests too. PostgreSQL is not available in this environment
(no Docker daemon); the schema is dialect-portable and CI's database job plus
plan.md's staging milestone cover the real PostgreSQL path.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from app.core.clock import FixedClock
from app.db.app.database import create_app_engine, session_factory

BACKEND_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 5, tzinfo=UTC)


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
def app_db_url(tmp_path, monkeypatch) -> str:
    db_path = tmp_path / "career_app.sqlite"
    url = f"sqlite:///{db_path}"
    monkeypatch.setenv("APP_DATABASE_URL", url)
    command.upgrade(Config(str(BACKEND_ROOT / "alembic-app.ini")), "head")
    return url


@pytest.fixture
def app_session_factory(app_db_url):
    engine = create_app_engine()
    try:
        yield session_factory(engine)
    finally:
        engine.dispose()
