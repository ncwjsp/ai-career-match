"""Shared fixtures for `career_jobs` repository tests. Owner: M2 (B-09).

Runs the real Alembic migration chain (`alembic-jobs.ini`) against a fresh
temp-file SQLite database for each test, rather than `Base.metadata.create_all`,
so a broken migration fails these tests too. PostgreSQL is not available in
this environment (no Docker daemon); the schema is dialect-portable and
`tests/core/test_migrations.py`/CI's staging milestone cover the real Postgres
path per plan.md's testing layers.
"""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from app.db.jobs.database import create_job_engine, session_factory
from app.db.jobs.embeddings import SqlJobEmbeddingRepository
from app.db.jobs.repository import SqlJobRepository
from app.db.jobs.sources import (
    SqlJobImportRunRepository,
    SqlJobRawSnapshotRepository,
    SqlJobSourceRepository,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def job_db_url(tmp_path, monkeypatch) -> str:
    db_path = tmp_path / "career_jobs.sqlite"
    url = f"sqlite:///{db_path}"
    monkeypatch.setenv("JOB_DATABASE_URL", url)
    config = Config(str(BACKEND_ROOT / "alembic-jobs.ini"))
    command.upgrade(config, "head")
    return url


@pytest.fixture
def job_session_factory(job_db_url):
    engine = create_job_engine()
    try:
        yield session_factory(engine)
    finally:
        engine.dispose()


@pytest.fixture
def job_repository(job_session_factory) -> SqlJobRepository:
    return SqlJobRepository(job_session_factory)


@pytest.fixture
def job_source_repository(job_session_factory) -> SqlJobSourceRepository:
    return SqlJobSourceRepository(job_session_factory)


@pytest.fixture
def job_import_run_repository(job_session_factory) -> SqlJobImportRunRepository:
    return SqlJobImportRunRepository(job_session_factory)


@pytest.fixture
def job_raw_snapshot_repository(job_session_factory) -> SqlJobRawSnapshotRepository:
    return SqlJobRawSnapshotRepository(job_session_factory)


@pytest.fixture
def job_embedding_repository(job_session_factory) -> SqlJobEmbeddingRepository:
    return SqlJobEmbeddingRepository(job_session_factory)
