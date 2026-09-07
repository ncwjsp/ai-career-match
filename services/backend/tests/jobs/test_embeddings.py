"""Persisted job vectors. Owner: M2 (B-09; consumed by B-03)."""

from app.contracts.models import EmbeddingRecord
from tests.jobs.factories import make_embedding, make_event, make_job


def test_save_and_get_round_trip(job_repository, job_embedding_repository):
    job_repository.save_with_event(make_job(), make_event())
    record = make_embedding()

    job_embedding_repository.save(record)

    assert job_embedding_repository.get("job-1", 1, "job-embed-v1") == record


def test_save_replaces_the_vector_for_the_same_key(job_repository, job_embedding_repository):
    job_repository.save_with_event(make_job(), make_event())
    job_embedding_repository.save(make_embedding(dimensions=4))

    rebuilt = EmbeddingRecord(
        entity_id="job-1",
        entity_version=1,
        vector=[0.9, 0.8, 0.7, 0.6],
        model_id="fixture-encoder",
        model_revision="rev-2",
        dimensions=4,
        preprocessing_version="prep-v2",
        embedding_version="job-embed-v1",
    )
    job_embedding_repository.save(rebuilt)

    stored = job_embedding_repository.get("job-1", 1, "job-embed-v1")
    assert stored.model_revision == "rev-2"
    assert stored.vector == [0.9, 0.8, 0.7, 0.6]


def test_different_embedding_versions_coexist(job_repository, job_embedding_repository):
    job_repository.save_with_event(make_job(), make_event())
    job_embedding_repository.save(make_embedding(embedding_version="job-embed-v1"))
    job_embedding_repository.save(make_embedding(embedding_version="job-embed-v2"))

    assert job_embedding_repository.get("job-1", 1, "job-embed-v1") is not None
    assert job_embedding_repository.get("job-1", 1, "job-embed-v2") is not None


def test_get_missing_embedding_returns_none(job_embedding_repository):
    assert job_embedding_repository.get("job-1", 1, "job-embed-v1") is None


def test_save_requires_an_existing_job_version(job_embedding_repository):
    import pytest
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        job_embedding_repository.save(make_embedding())
