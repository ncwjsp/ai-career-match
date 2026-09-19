"""Shared fixtures for `career_jobs` repository tests. Owner: M2 (B-09).

Runs the real Alembic migration chain (`alembic-jobs.ini`) against a fresh
temp-file SQLite database for each test, rather than `Base.metadata.create_all`,
so a broken migration fails these tests too. PostgreSQL is not available in
this environment (no Docker daemon); the schema is dialect-portable and
`tests/core/test_migrations.py`/CI's staging milestone cover the real Postgres
path per plan.md's testing layers.
"""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

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
    postgres = os.environ.get("ACM_TEST_JOB_POSTGRES_URL")
    if postgres:
        base = make_url(postgres)
        if base.get_backend_name() != "postgresql":
            pytest.fail("ACM_TEST_JOB_POSTGRES_URL requires a disposable PostgreSQL database")
        schema = "job_test_" + uuid4().hex
        engine = create_engine(base)
        with engine.begin() as connection:
            connection.execute(CreateSchema(schema))
        try:
            url = base.update_query_dict(
                {"options": f"-csearch_path={schema} -cstatement_timeout=15000"}
            ).render_as_string(hide_password=False)
            monkeypatch.setenv("JOB_DATABASE_URL", url)
            command.upgrade(Config(str(BACKEND_ROOT / "alembic-jobs.ini")), "head")
            yield url
        finally:
            with engine.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
            engine.dispose()
        return
    db_path = tmp_path / "career_jobs.sqlite"
    url = f"sqlite:///{db_path}"
    monkeypatch.setenv("JOB_DATABASE_URL", url)
    config = Config(str(BACKEND_ROOT / "alembic-jobs.ini"))
    command.upgrade(config, "head")
    yield url


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
