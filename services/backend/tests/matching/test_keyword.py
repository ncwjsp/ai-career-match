"""Keyword-overlap baseline (B-04)."""

from app.modules.matching.keyword import score
from tests.jobs.factories import make_job
from tests.matching.factories import make_candidate


def test_full_overlap_scores_one():
    profile = make_candidate(summary="Python role experience.")
    job = make_job(title="Python", requirements=[])
    job = job.model_copy(update={"company": "Python", "description": "Python role."})
    assert score(profile, job) == 1.0


def test_no_overlap_scores_zero():
    profile = make_candidate(summary="Baker with pastry experience.", skills=[])
    job = make_job(requirements=[])
    assert score(profile, job) == 0.0


def test_partial_overlap_is_between_zero_and_one():
    profile = make_candidate(summary="Python developer.", skills=[])
    job = make_job(requirements=[])  # description mentions "Required skills: Python."
    result = score(profile, job)
    assert 0.0 < result < 1.0


def test_a_job_with_no_letter_tokens_scores_zero_rather_than_dividing_by_zero():
    profile = make_candidate()
    job = make_job(title="123", requirements=[])
    job = job.model_copy(update={"company": "456", "description": "789."})
    assert score(profile, job) == 0.0


def test_is_deterministic():
    profile = make_candidate()
    job = make_job()
    assert score(profile, job) == score(profile, job)
