"""Exact cosine retrieval over persisted job vectors. Owner: M2 (B-03).

Job vectors are stored per (job_id, content_version, embedding_version) by
B-09's `SqlJobEmbeddingRepository`; this module turns "the active job corpus,
each job maybe embedded under several model revisions" into a ranked list for
one query vector. Retrieval is exact (brute-force cosine over the active
corpus, not an approximate index) -- the revised scope's manually-imported
`career_jobs` is a small corpus by design (see plan.md/START_HERE.md: "no
external search cluster required"), so an index structure would be premature.

Everything compared must share the same `embedding_version` and dimensions. A
job with no vector under the requested `embedding_version`, or a stored
vector whose dimensions do not match the query's, is skipped rather than
compared anyway -- a changed embedding model must never silently blend two
vector spaces into one ranking.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from app.contracts.interfaces import JobRepository
from app.db.jobs.embeddings import SqlJobEmbeddingRepository
from app.modules.matching.bi_encoder import cosine


@dataclass(frozen=True)
class SearchHit:
    job_id: str
    content_version: int
    score: float


class JobVectorSearch:
    def __init__(
        self,
        jobs: JobRepository,
        embeddings: SqlJobEmbeddingRepository,
        *,
        batch_size: int = 100,
    ):
        self._jobs = jobs
        self._embeddings = embeddings
        self._batch_size = batch_size

    def search(
        self,
        query_vector: Sequence[float],
        embedding_version: str,
        at: datetime,
        limit: int = 10,
    ) -> list[SearchHit]:
        """Rank active, non-expired jobs by cosine similarity to `query_vector`.

        `JobRepository.list_active` has no cursor today -- career_jobs is a
        small, manually-imported corpus by design -- so this fetches the full
        active set and scores it in `batch_size` chunks. Scoring is chunked
        (not the fetch itself) so this stays correct without change if
        `list_active` grows pagination later.
        """
        dimensions = len(query_vector)
        if dimensions == 0:
            raise ValueError("A query vector needs at least one dimension.")
        hits: list[SearchHit] = []
        active = list(self._jobs.list_active(at))
        for start in range(0, len(active), self._batch_size):
            for job in active[start : start + self._batch_size]:
                record = self._embeddings.get(job.job_id, job.content_version, embedding_version)
                if record is None:
                    continue  # Not embedded under this model revision (yet).
                if record.dimensions != dimensions:
                    continue  # Never blend two vector spaces into one ranking.
                score = cosine(query_vector, record.vector)
                hits.append(SearchHit(job.job_id, job.content_version, score))
        # Unrounded score, stable job-id tie-break -- same rule plan.md's
        # scoring section uses for ranked results.
        hits.sort(key=lambda hit: (-hit.score, hit.job_id))
        return hits[:limit]
