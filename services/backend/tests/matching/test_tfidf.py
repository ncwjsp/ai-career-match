"""TF-IDF + cosine baseline (B-04)."""

import pytest

from app.modules.matching.tfidf import score
from tests.jobs.factories import make_job
from tests.matching.factories import make_candidate


def test_identical_text_scores_close_to_one():
    text = "Backend engineer with Python and PostgreSQL experience."
    profile = make_candidate(summary=text, skills=[])
    job = make_job(title=text, requirements=[])
    job = job.model_copy(update={"company": text, "description": text})
    assert score(profile, job) == pytest.approx(1.0)


def test_unrelated_text_scores_low():
    profile = make_candidate(summary="Baker with pastry and bread experience.", skills=[])
    job = make_job(requirements=[])
    assert score(profile, job) < 0.3


def test_score_is_bounded_between_zero_and_one():
    profile = make_candidate()
    job = make_job()
    result = score(profile, job)
    assert 0.0 <= result <= 1.0


def test_empty_resume_text_scores_zero():
    profile = make_candidate(summary=None, skills=[])
    job = make_job()
    assert score(profile, job) == 0.0


def test_is_deterministic_for_the_same_pair():
    profile = make_candidate()
    job = make_job()
    assert score(profile, job) == score(profile, job)


def test_background_corpus_changes_the_idf_but_not_the_bounds():
    profile = make_candidate(summary="Python engineer.")
    job = make_job(requirements=[])
    background = ["Python is common in every posting in this corpus." for _ in range(20)]
    with_background = score(profile, job, background=background)
    assert 0.0 <= with_background <= 1.0
