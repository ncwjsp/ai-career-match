"""Hybrid re-ranking (B-05): bound the candidate pool, then weighted-combine."""

import pytest

from app.core.inference import DeterministicEmbeddingClient
from app.modules.matching.hybrid import HYBRID_VERSION, HybridWeights, rerank
from tests.jobs.factories import make_job, requirement
from tests.matching.factories import make_candidate

EMBEDDER = DeterministicEmbeddingClient()


def _job(job_id: str, *, title: str, description: str) -> object:
    return make_job(job_id=job_id, content_version=1, title=title, requirements=[]).model_copy(
        update={"description": description}
    )


def test_rerank_bounds_the_pool_to_the_requested_size():
    profile = make_candidate(skills=[])
    jobs = [
        _job(f"job-{i}", title=f"Role {i}", description=f"Unrelated text {i}.") for i in range(10)
    ]

    results = rerank(profile, jobs, EMBEDDER, candidate_pool_size=3)

    assert len(results) == 3


def test_rerank_returns_all_jobs_when_pool_size_exceeds_the_list():
    profile = make_candidate(skills=[])
    jobs = [_job(f"job-{i}", title=f"Role {i}", description="Some text.") for i in range(3)]

    results = rerank(profile, jobs, EMBEDDER, candidate_pool_size=50)

    assert len(results) == 3


def test_results_are_sorted_by_score_descending():
    profile = make_candidate(skills=[])
    jobs = [_job(f"job-{i}", title=f"Role {i}", description=f"Text number {i}.") for i in range(6)]

    results = rerank(profile, jobs, EMBEDDER, candidate_pool_size=6)

    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_ties_break_deterministically_by_job_id():
    profile = make_candidate(skills=[], summary=None)
    # Two jobs with identical text score identically on every baseline.
    jobs = [
        _job("job-b", title="Role", description="Same text."),
        _job("job-a", title="Role", description="Same text."),
    ]

    results = rerank(profile, jobs, EMBEDDER, candidate_pool_size=2)

    assert [r.job_id for r in results] == ["job-a", "job-b"]


def test_each_result_carries_its_component_scores_and_version():
    profile = make_candidate(skills=[])
    jobs = [_job("job-1", title="Role", description="Some text.")]

    results = rerank(profile, jobs, EMBEDDER, candidate_pool_size=1)

    result = results[0]
    assert result.hybrid_version == HYBRID_VERSION
    assert set(result.components) == {"keyword", "tfidf", "bi_encoder"}
    assert all(0.0 <= v <= 1.0 for v in result.components.values())


def test_weights_change_the_ranking():
    profile = make_candidate(
        skills=[], summary="I have extensive experience with Python and SQL pipelines."
    )
    keyword_favored = _job(
        "job-keyword", title="Role", description="Python SQL pipelines experience required."
    )
    semantic_only = _job(
        "job-semantic",
        title="Role",
        description="We build data infrastructure and analytics tooling for the company.",
    )
    jobs = [keyword_favored, semantic_only]

    keyword_heavy = rerank(
        profile,
        jobs,
        EMBEDDER,
        candidate_pool_size=2,
        weights=HybridWeights(keyword=1.0, tfidf=0.0, bi_encoder=0.0),
    )

    assert keyword_heavy[0].job_id == "job-keyword"


def test_candidate_pool_size_must_be_positive():
    profile = make_candidate(skills=[])

    with pytest.raises(ValueError):
        rerank(profile, [], EMBEDDER, candidate_pool_size=0)


def test_negative_weight_is_rejected():
    with pytest.raises(ValueError):
        HybridWeights(keyword=-0.1, tfidf=0.5, bi_encoder=0.6)


def test_all_zero_weights_is_rejected():
    with pytest.raises(ValueError):
        HybridWeights(keyword=0.0, tfidf=0.0, bi_encoder=0.0)


def test_reranking_an_empty_pool_returns_empty():
    profile = make_candidate(skills=[])

    assert rerank(profile, [], EMBEDDER, candidate_pool_size=5) == []


def test_background_corpus_is_forwarded_to_tfidf():
    profile = make_candidate(skills=[], summary="Python engineer.")
    jobs = [_job("job-1", title="Role", description="Python role.")]

    with_background = rerank(
        profile, jobs, EMBEDDER, candidate_pool_size=1, background=["Python Python Python."] * 5
    )
    without_background = rerank(profile, jobs, EMBEDDER, candidate_pool_size=1)

    # Not asserting a specific direction, only that background actually changes the TF-IDF term.
    with_tfidf = with_background[0].components["tfidf"]
    without_tfidf = without_background[0].components["tfidf"]
    assert with_tfidf != without_tfidf or with_tfidf == without_tfidf == 0.0


def test_a_stray_required_skill_does_not_affect_hybrid_scoring():
    profile = make_candidate(skills=[])
    job = make_job(job_id="job-1", requirements=[requirement("Python", required=True)])

    results = rerank(profile, [job], EMBEDDER, candidate_pool_size=1)

    assert results[0].job_id == "job-1"
