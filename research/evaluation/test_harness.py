"""The evaluation harness (B-08) against tiny, clearly-synthetic fixtures.

These fixtures are test data for the harness's own logic, never a stand-in
for VAL-01's real human labels -- see README.md for that distinction.
Importing `harness` first is what puts `services/backend` on `sys.path`, so
`app.contracts.models` becomes importable below.
"""

import sys
from datetime import UTC, datetime

import harness
import pytest
from harness import MethodResult, compare_methods, from_pairwise, run_method
from rubric import EvaluationSplit, Label

from app.contracts.models import CandidateProfile, JobPosting

NOW = datetime(2026, 9, 16, tzinfo=UTC)


def _profile(candidate_id: str) -> CandidateProfile:
    return CandidateProfile(
        candidate_id=candidate_id,
        resume_id=f"resume-{candidate_id}",
        profile_version=1,
        language="en",
        summary="Backend engineer.",
        skills=[],
        education=[],
        job_titles=[],
        organizations=[],
        experience=[],
        estimated_experience_years=3.0,
        projects=[],
        evidence=[],
        extraction_warnings=[],
        matching_enabled=True,
        expires_at=NOW,
    )


def _job(job_id: str) -> JobPosting:
    return JobPosting(
        job_id=job_id,
        source_id="fixture-source",
        source_url=f"https://jobs.example.test/{job_id}",
        content_version=1,
        title="Backend Engineer",
        company="Example Labs",
        description="Some job text.",
        summary=None,
        requirements=[],
        other_requirements=[],
        evidence=[],
        language="en",
        fetched_at=NOW,
        last_seen_at=NOW,
        active=True,
        data_origin="fixture",
    )


def _split() -> EvaluationSplit:
    return EvaluationSplit(
        split_id="fixture-split",
        candidate_ids=("cand-1",),
        job_pool_ids=("job-a", "job-b"),
        labels=(Label(candidate_id="cand-1", job_id="job-a", relevant=True, labeled_by="tester"),),
    )


def test_from_pairwise_ranks_by_descending_score():
    def score(profile, job):
        return {"job-a": 0.9, "job-b": 0.1}[job.job_id]

    rank_fn = from_pairwise(score)
    profile = _profile("cand-1")
    jobs = [_job("job-b"), _job("job-a")]

    assert rank_fn(profile, jobs) == ["job-a", "job-b"]


def test_from_pairwise_breaks_ties_by_job_id():
    rank_fn = from_pairwise(lambda profile, job: 0.5)
    profile = _profile("cand-1")
    jobs = [_job("job-b"), _job("job-a")]

    assert rank_fn(profile, jobs) == ["job-a", "job-b"]


def test_run_method_computes_metrics_for_a_perfect_method():
    rank_fn = from_pairwise(lambda profile, job: {"job-a": 1.0, "job-b": 0.0}[job.job_id])
    profiles = {"cand-1": _profile("cand-1")}
    jobs = {"job-a": _job("job-a"), "job-b": _job("job-b")}

    result = run_method("perfect", rank_fn, profiles, jobs, _split(), k=1)

    assert isinstance(result, MethodResult)
    assert result.metrics.precision_at_k == 1.0
    assert result.failures == []
    assert result.latency_seconds >= 0.0


def test_run_method_skips_a_candidate_with_no_profile_fixture():
    split = EvaluationSplit(
        split_id="s", candidate_ids=("cand-missing",), job_pool_ids=("job-a",), labels=()
    )
    rank_fn = from_pairwise(lambda profile, job: 1.0)

    with pytest.raises(ValueError, match="no queries could be evaluated"):
        run_method("m", rank_fn, {}, {"job-a": _job("job-a")}, split, k=1)


def test_run_method_records_a_ranking_failure_without_crashing():
    def exploding(profile, jobs):
        raise RuntimeError("boom")

    profiles = {"cand-1": _profile("cand-1")}
    jobs = {"job-a": _job("job-a"), "job-b": _job("job-b")}

    with pytest.raises(ValueError, match="no queries could be evaluated"):
        run_method("broken", exploding, profiles, jobs, _split(), k=1)


def test_a_candidate_with_no_relevance_labels_is_skipped_not_errored():
    split = EvaluationSplit(
        split_id="s",
        candidate_ids=("cand-1", "cand-unlabeled"),
        job_pool_ids=("job-a", "job-b"),
        labels=(Label(candidate_id="cand-1", job_id="job-a", relevant=True, labeled_by="t"),),
    )
    rank_fn = from_pairwise(lambda profile, job: 1.0)
    profiles = {"cand-1": _profile("cand-1"), "cand-unlabeled": _profile("cand-unlabeled")}
    jobs = {"job-a": _job("job-a"), "job-b": _job("job-b")}

    result = run_method("m", rank_fn, profiles, jobs, split, k=1)

    assert any("cand-unlabeled" in f for f in result.failures)
    assert result.metrics.relevant_total == 1  # only cand-1's label counted


def test_compare_methods_runs_every_method_in_order():
    profiles = {"cand-1": _profile("cand-1")}
    jobs = {"job-a": _job("job-a"), "job-b": _job("job-b")}
    methods = {
        "always_a_first": from_pairwise(lambda p, j: {"job-a": 1.0, "job-b": 0.0}[j.job_id]),
        "always_b_first": from_pairwise(lambda p, j: {"job-a": 0.0, "job-b": 1.0}[j.job_id]),
    }

    results = compare_methods(methods, profiles, jobs, _split(), k=1)

    assert [r.method for r in results] == ["always_a_first", "always_b_first"]
    assert results[0].metrics.precision_at_k == 1.0
    assert results[1].metrics.precision_at_k == 0.0


def test_harness_puts_backend_root_on_sys_path():
    assert str(harness._BACKEND_ROOT) in sys.path
