"""`career_jobs` database package. Owner: M2 (B-09).

- `models`: SQLAlchemy tables (sources, import runs, raw snapshots, canonical
  jobs, immutable job versions, job embeddings, the job-change outbox).
- `database`: engine/session-factory construction from `Settings.job_database_url`.
- `repository.SqlJobRepository`: implements the shared `JobRepository` and
  `JobEventOutbox` protocols from `app.contracts.interfaces`.
- `sources`: job-source registration and manual import-run/check metadata.
- `embeddings.SqlJobEmbeddingRepository`: persisted job vectors.
"""

from app.db.jobs.database import create_job_engine, session_factory
from app.db.jobs.embeddings import SqlJobEmbeddingRepository
from app.db.jobs.repository import JobEventConflict, JobVersionConflict, SqlJobRepository
from app.db.jobs.sources import (
    SqlJobImportRunRepository,
    SqlJobRawSnapshotRepository,
    SqlJobSourceRepository,
)

__all__ = [
    "create_job_engine",
    "session_factory",
    "SqlJobRepository",
    "JobEventConflict",
    "JobVersionConflict",
    "SqlJobEmbeddingRepository",
    "SqlJobSourceRepository",
    "SqlJobImportRunRepository",
    "SqlJobRawSnapshotRepository",
]
