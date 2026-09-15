"""Reproducible job-embedding rebuilds. Owner: M2 (B-03).

Re-embeds every active job's matchable text under one `embedding_version`
through the shared `EmbeddingClient` (`app.core.inference` -- the
deterministic offline client in tests/CI, SageMaker in deployment) and stores
the result via B-09's `SqlJobEmbeddingRepository`. "Reproducible" means: the
same jobs, the same client, and the same `embedding_version` produce the same
stored vectors, because `save()` replaces the row for that
(job_id, content_version, embedding_version) key rather than growing an
unbounded history -- running this again after nothing changed is a no-op in
effect, and running it after a real model change under a *new*
`embedding_version` leaves the old vectors (and anything ranked from them)
untouched.
"""

from __future__ import annotations

from datetime import datetime

from app.contracts.interfaces import JobRepository
from app.contracts.models import EmbeddingRecord
from app.core.inference import EmbeddingClient
from app.db.jobs.embeddings import SqlJobEmbeddingRepository
from app.modules.matching.text import job_text

PREPROCESSING_VERSION = "matching-text-v1"


def rebuild_job_embeddings(
    jobs: JobRepository,
    embeddings: SqlJobEmbeddingRepository,
    embedding_client: EmbeddingClient,
    embedding_version: str,
    at: datetime,
) -> int:
    """Re-embed every active job. Returns how many were (re)written."""
    rebuilt = 0
    for job in jobs.list_active(at):
        batch = embedding_client.embed([job_text(job)])
        embeddings.save(
            EmbeddingRecord(
                entity_id=job.job_id,
                entity_version=job.content_version,
                vector=batch.vectors[0],
                model_id=batch.model_id,
                model_revision=batch.model_revision,
                dimensions=batch.dimensions,
                preprocessing_version=PREPROCESSING_VERSION,
                embedding_version=embedding_version,
            )
        )
        rebuilt += 1
    return rebuilt
