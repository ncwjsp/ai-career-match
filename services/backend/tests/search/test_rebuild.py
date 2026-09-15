"""Reproducible job-embedding rebuilds (B-03)."""

from datetime import UTC, datetime

from app.core.inference import DeterministicEmbeddingClient
from app.search.rebuild import rebuild_job_embeddings
from tests.jobs.factories import make_event, make_job

NOW = datetime(2026, 9, 5, tzinfo=UTC)


def _seed(job_repository, job_id):
    job = make_job(job_id)
    job_repository.save_with_event(job, make_event(job_id=job_id, event_id=f"event-{job_id}"))
    return job


def test_rebuilds_a_vector_for_every_active_job(job_repository, job_embedding_repository):
    _seed(job_repository, "job-1")
    _seed(job_repository, "job-2")

    count = rebuild_job_embeddings(
        job_repository, job_embedding_repository, DeterministicEmbeddingClient(), "rebuild-v1", NOW
    )

    assert count == 2
    assert job_embedding_repository.get("job-1", 1, "rebuild-v1") is not None
    assert job_embedding_repository.get("job-2", 1, "rebuild-v1") is not None


def test_running_it_twice_with_the_deterministic_client_reproduces_the_same_vector(
    job_repository, job_embedding_repository
):
    _seed(job_repository, "job-1")
    client = DeterministicEmbeddingClient()

    rebuild_job_embeddings(job_repository, job_embedding_repository, client, "rebuild-v1", NOW)
    first = job_embedding_repository.get("job-1", 1, "rebuild-v1")
    rebuild_job_embeddings(job_repository, job_embedding_repository, client, "rebuild-v1", NOW)
    second = job_embedding_repository.get("job-1", 1, "rebuild-v1")

    assert first == second


def test_an_inactive_job_is_not_rebuilt(job_repository, job_embedding_repository):
    job = make_job("job-inactive", active=False)
    job_repository.save_with_event(job, make_event(job_id="job-inactive"))

    count = rebuild_job_embeddings(
        job_repository, job_embedding_repository, DeterministicEmbeddingClient(), "rebuild-v1", NOW
    )

    assert count == 0
    assert job_embedding_repository.get("job-inactive", 1, "rebuild-v1") is None


def test_a_new_embedding_version_does_not_touch_the_old_one(
    job_repository, job_embedding_repository
):
    _seed(job_repository, "job-1")
    rebuild_job_embeddings(
        job_repository, job_embedding_repository, DeterministicEmbeddingClient(), "v1", NOW
    )

    rebuild_job_embeddings(
        job_repository,
        job_embedding_repository,
        DeterministicEmbeddingClient(dimensions=32),
        "v2",
        NOW,
    )

    old = job_embedding_repository.get("job-1", 1, "v1")
    new = job_embedding_repository.get("job-1", 1, "v2")
    assert old is not None and old.dimensions == 16
    assert new is not None and new.dimensions == 32
