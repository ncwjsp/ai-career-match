"""Exact cosine retrieval over persisted job vectors (B-03)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.contracts.models import EmbeddingRecord
from app.search.retrieval import JobVectorSearch
from tests.jobs.factories import make_event, make_job

NOW = datetime(2026, 9, 5, tzinfo=UTC)


@pytest.fixture
def search(job_repository, job_embedding_repository):
    return JobVectorSearch(job_repository, job_embedding_repository)


def _seed(job_repository, job_embedding_repository, job_id, vector, **job_kwargs):
    job = make_job(job_id, **job_kwargs)
    job_repository.save_with_event(job, make_event(job_id=job_id, event_id=f"event-{job_id}"))
    job_embedding_repository.save(
        EmbeddingRecord(
            entity_id=job_id,
            entity_version=1,
            vector=vector,
            model_id="fixture-encoder",
            model_revision="rev-1",
            dimensions=len(vector),
            preprocessing_version="prep-v1",
            embedding_version="job-embed-v1",
        )
    )
    return job


def test_ranks_by_cosine_similarity_descending(search, job_repository, job_embedding_repository):
    _seed(job_repository, job_embedding_repository, "job-close", [1.0, 0.0])
    _seed(job_repository, job_embedding_repository, "job-far", [0.0, 1.0])

    hits = search.search([1.0, 0.0], "job-embed-v1", NOW)

    assert [h.job_id for h in hits] == ["job-close", "job-far"]
    assert hits[0].score == pytest.approx(1.0)
    assert hits[1].score == pytest.approx(0.0)


def test_a_stored_vector_of_a_different_dimension_is_skipped_not_blended(
    search, job_repository, job_embedding_repository
):
    _seed(job_repository, job_embedding_repository, "job-2d", [1.0, 0.0])
    _seed(job_repository, job_embedding_repository, "job-3d", [1.0, 0.0, 0.0])

    hits = search.search([1.0, 0.0], "job-embed-v1", NOW)

    assert [h.job_id for h in hits] == ["job-2d"]


def test_a_job_with_no_vector_under_the_requested_embedding_version_is_skipped(
    search, job_repository
):
    job = make_job("job-unembedded")
    job_repository.save_with_event(job, make_event(job_id="job-unembedded"))

    hits = search.search([1.0, 0.0], "job-embed-v1", NOW)

    assert hits == []


def test_inactive_and_expired_jobs_are_excluded(search, job_repository, job_embedding_repository):
    _seed(job_repository, job_embedding_repository, "job-active", [1.0, 0.0], active=True)
    _seed(job_repository, job_embedding_repository, "job-inactive", [1.0, 0.0], active=False)
    _seed(
        job_repository,
        job_embedding_repository,
        "job-expired",
        [1.0, 0.0],
        active=True,
        expires_at=NOW - timedelta(days=1),
    )

    hits = search.search([1.0, 0.0], "job-embed-v1", NOW)

    assert [h.job_id for h in hits] == ["job-active"]


def test_limit_bounds_the_returned_hits(search, job_repository, job_embedding_repository):
    for i in range(5):
        _seed(job_repository, job_embedding_repository, f"job-{i}", [1.0, 0.0])

    hits = search.search([1.0, 0.0], "job-embed-v1", NOW, limit=2)

    assert len(hits) == 2


def test_ties_break_on_job_id(search, job_repository, job_embedding_repository):
    _seed(job_repository, job_embedding_repository, "job-b", [1.0, 0.0])
    _seed(job_repository, job_embedding_repository, "job-a", [1.0, 0.0])

    hits = search.search([1.0, 0.0], "job-embed-v1", NOW)

    assert [h.job_id for h in hits] == ["job-a", "job-b"]


def test_a_zero_length_query_vector_is_rejected(search):
    with pytest.raises(ValueError, match="dimension"):
        search.search([], "job-embed-v1", NOW)
