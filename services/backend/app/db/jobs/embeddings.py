"""Persisted job vectors for `career_jobs`. Owner: M2 (B-09; consumed by B-03).

Stores `EmbeddingRecord` (the shared contract) keyed by job id/content version
and embedding model revision, so a re-embed under a new model/preprocessing
version does not overwrite the previous one — B-03's retrieval selects by
`embedding_version` and checks `dimensions` instead of assuming one live vector.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker

from app.contracts.models import EmbeddingRecord
from app.db.jobs.models import JobEmbeddingRow


def _row_to_record(row: JobEmbeddingRow) -> EmbeddingRecord:
    return EmbeddingRecord(
        entity_id=row.job_id,
        entity_version=row.content_version,
        vector=row.vector,
        model_id=row.model_id,
        model_revision=row.model_revision,
        dimensions=row.dimensions,
        preprocessing_version=row.preprocessing_version,
        embedding_version=row.embedding_version,
    )


class SqlJobEmbeddingRepository:
    def __init__(self, factory: sessionmaker[Session]):
        self._factory = factory

    def save(self, record: EmbeddingRecord) -> None:
        """Insert or replace the vector for (job_id, content_version, embedding_version).

        Requires a matching `job_versions` row to already exist (foreign key);
        raises the database's integrity error otherwise rather than silently
        persisting a vector for content that isn't there.
        """
        key = (record.entity_id, record.entity_version, record.embedding_version)
        with self._factory() as session:
            row = session.get(JobEmbeddingRow, key)
            if row is None:
                row = JobEmbeddingRow(
                    job_id=record.entity_id,
                    content_version=record.entity_version,
                    embedding_version=record.embedding_version,
                    created_at=datetime.now(UTC),
                )
                session.add(row)
            row.model_id = record.model_id
            row.model_revision = record.model_revision
            row.dimensions = record.dimensions
            row.preprocessing_version = record.preprocessing_version
            row.vector = list(record.vector)
            session.commit()

    def get(
        self, job_id: str, content_version: int, embedding_version: str
    ) -> EmbeddingRecord | None:
        with self._factory() as session:
            row = session.get(JobEmbeddingRow, (job_id, content_version, embedding_version))
            return _row_to_record(row) if row is not None else None
