"""The `semantic-skills-v1` formula and the real `Matcher` (B-05/B-06/B-10)."""

from datetime import UTC, datetime

import pytest

from app.core.clock import FixedClock
from app.core.inference import DeterministicEmbeddingClient
from app.modules.matching.scoring import SCORING_VERSION, Matcher, compute_score
from tests.jobs.factories import make_job, requirement
from tests.matching.factories import make_candidate

NOW = datetime(2026, 9, 5, tzinfo=UTC)


# --- compute_score: plan.md's worked example and edge cases -----------------


def test_the_plan_md_worked_example_gives_77_point_0():
    # S=0.80, five required skills: three present, one partial, one missing.
    result = compute_score(0.80, ["present", "present", "present", "partial", "missing"])
    assert result.skill_coverage == pytest.approx(0.70)
    assert result.display_score == 77.0
    assert result.score_basis == "semantic_skills"


def test_no_required_skills_falls_back_to_semantic_only():
    result = compute_score(0.5, [])
    assert result.score_basis == "semantic_only"
    assert result.skill_coverage is None
    assert result.display_score == 50.0


def test_semantic_fit_is_clamped_to_zero_and_one():
    assert compute_score(-0.4, []).semantic_fit == 0.0
    assert compute_score(1.4, []).semantic_fit == 1.0


def test_all_missing_required_skills_gives_zero_coverage():
    result = compute_score(0.9, ["missing", "missing"])
    assert result.skill_coverage == 0.0
    assert result.display_score == pytest.approx(100 * 0.7 * 0.9, abs=0.05)


def test_all_present_required_skills_gives_full_coverage():
    result = compute_score(0.5, ["present", "present"])
    assert result.skill_coverage == 1.0
    assert result.display_score == pytest.approx(100 * (0.7 * 0.5 + 0.3 * 1.0), abs=0.05)


def test_display_score_is_rounded_to_one_decimal():
    result = compute_score(0.333, ["present"])
    assert result.display_score == round(result.display_score, 1)


# --- Matcher: protocol compliance and real behavior --------------------------


@pytest.fixture
def matcher():
    return Matcher(embedding_client=DeterministicEmbeddingClient(), clock=FixedClock(NOW))


def test_matcher_is_constructible_with_no_arguments():
    """`scripts/run_worker.py` calls `Matcher()`; it must not require injection."""
    Matcher()


def test_matcher_declares_scoring_version_it_defaults_to():
    # scripts/run_worker.py and MatchService both pass "semantic-skills-v1"
    # explicitly, but this constant is what this module's formula documents.
    assert SCORING_VERSION == "semantic-skills-v1"


def test_matcher_exposes_the_three_protocol_methods(matcher):
    # `Matcher` subclasses `app.contracts.interfaces.Matcher`, a non-runtime-
    # checkable Protocol, so a static/type check (not isinstance) is what
    # actually enforces the shape; this asserts the same thing at runtime.
    assert callable(matcher.score_pair)
    assert callable(matcher.match_job)
    assert callable(matcher.recommend)


def test_score_pair_returns_a_valid_match_result(matcher):
    profile = make_candidate()
    job = make_job()

    result = matcher.score_pair(profile, job, SCORING_VERSION)

    assert result.candidate_id == profile.candidate_id
    assert result.job_id == job.job_id
    assert result.job_version == job.content_version
    assert result.scoring_version == SCORING_VERSION
    assert result.data_origin == "computed"
    assert result.matched_at == NOW
    assert 0.0 <= result.score <= 100.0


def test_score_pair_and_match_job_give_the_same_score_for_a_pair(matcher):
    """The contract Finish_nai.md requires: both matching triggers must agree."""
    profile = make_candidate()
    job = make_job()

    direct = matcher.score_pair(profile, job, SCORING_VERSION)
    [via_match_job] = matcher.match_job(job, [profile], SCORING_VERSION)

    assert direct.score == via_match_job.score
    assert direct.score_components == via_match_job.score_components
    assert direct.skill_comparison == via_match_job.skill_comparison


def test_match_job_scores_every_profile_in_order(matcher):
    job = make_job()
    profiles = [make_candidate("cand-1"), make_candidate("cand-2"), make_candidate("cand-3")]

    results = matcher.match_job(job, profiles, SCORING_VERSION)

    assert [r.candidate_id for r in results] == ["cand-1", "cand-2", "cand-3"]


def test_score_pair_is_deterministic_for_the_same_inputs(matcher):
    profile = make_candidate()
    job = make_job()
    first = matcher.score_pair(profile, job, SCORING_VERSION)
    second = matcher.score_pair(profile, job, SCORING_VERSION)
    assert first == second


def test_a_job_with_no_reliably_extracted_requirement_is_semantic_only(matcher):
    profile = make_candidate()
    job = make_job(requirements=[])

    result = matcher.score_pair(profile, job, SCORING_VERSION)

    assert result.score_components.score_basis == "semantic_only"
    assert result.score_components.skill_coverage is None
    assert result.score == pytest.approx(100 * result.score_components.semantic_fit, abs=0.05)


def test_present_required_skills_are_reflected_in_strengths_and_score(matcher):
    profile = make_candidate()  # has "Python"
    job = make_job(requirements=[requirement("Python", required=True)])

    result = matcher.score_pair(profile, job, SCORING_VERSION)

    assert result.strengths == ["Python"]
    assert result.gaps == []
    assert result.score_components.skill_coverage == 1.0


def test_missing_required_skills_are_reflected_in_gaps(matcher):
    profile = make_candidate(skills=[])
    job = make_job(requirements=[requirement("Rust", required=True)])

    result = matcher.score_pair(profile, job, SCORING_VERSION)

    assert result.gaps == ["Rust"]
    assert result.score_components.skill_coverage == 0.0


def test_evidence_is_never_fabricated_for_a_missing_skill(matcher):
    profile = make_candidate(skills=[])
    job = make_job(requirements=[requirement("Rust", required=True)])

    [comparison] = matcher.score_pair(profile, job, SCORING_VERSION).skill_comparison

    assert comparison.state == "missing"
    assert comparison.resume_evidence == []


def test_recommend_is_not_used_by_the_live_pipeline(matcher):
    with pytest.raises(NotImplementedError):
        matcher.recommend(make_candidate(), "snapshot-1", 10)
