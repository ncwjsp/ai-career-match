"""Sentence-embedding baseline (B-04): cosine of live-embedded texts."""

import pytest

from app.core.inference import DeterministicEmbeddingClient
from app.modules.matching.bi_encoder import cosine, score
from tests.jobs.factories import make_job
from tests.matching.factories import make_candidate


def test_identical_text_has_cosine_one():
    client = DeterministicEmbeddingClient()
    batch = client.embed(["Python engineer.", "Python engineer."])
    assert cosine(batch.vectors[0], batch.vectors[1]) == pytest.approx(1.0)


def test_score_is_bounded_between_zero_and_one():
    client = DeterministicEmbeddingClient()
    profile = make_candidate()
    job = make_job()
    result = score(profile, job, client)
    assert 0.0 <= result <= 1.0


def test_is_deterministic_for_the_same_pair_and_client():
    client = DeterministicEmbeddingClient()
    profile = make_candidate()
    job = make_job()
    assert score(profile, job, client) == score(profile, job, client)


def test_cosine_rejects_mismatched_dimensions():
    with pytest.raises(ValueError, match="dimensionality"):
        cosine([1.0, 0.0], [1.0, 0.0, 0.0])


def test_cosine_of_opposite_vectors_is_clamped_to_zero_not_negative():
    assert cosine([1.0, 0.0], [-1.0, 0.0]) == 0.0


def test_cosine_of_a_zero_vector_is_zero():
    assert cosine([0.0, 0.0], [1.0, 0.0]) == 0.0
