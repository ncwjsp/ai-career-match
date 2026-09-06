import pytest
from pydantic import TypeAdapter, ValidationError

from app.contracts.models import (
    CandidateProfile,
    DomainEvent,
    EmbeddingRecord,
    EvidenceRef,
    MatchResult,
    RecommendationSet,
    ScoreComponents,
    SkillComparison,
)
from app.testing.fixtures import load_fixtures


def test_complete_fixture_bundle_and_references():
    fixtures = load_fixtures()
    assert fixtures.mode == "fixture"
    assert {e.event_type for e in fixtures.events} == {"profile.ready", "job.created"}
    assert {s.state for s in fixtures.matches[0].skill_comparison} == {
        "present",
        "partial",
        "missing",
    }
    known = {}
    for document in [*fixtures.profiles, *fixtures.jobs]:
        for ref in document.evidence:
            known[(ref.document_id, ref.document_version, ref.chunk_id)] = ref

    def check(value):
        if isinstance(value, dict):
            if "document_id" in value:
                ref = EvidenceRef.model_validate(value)
                assert known[(ref.document_id, ref.document_version, ref.chunk_id)] == ref
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)

    check(fixtures.model_dump(mode="json"))


def test_fixture_scores_follow_documented_example_without_running_a_ranker():
    for result in load_fixtures().matches:
        required = [s for s in result.skill_comparison if s.required]
        credit = {"present": 1, "partial": 0.5, "missing": 0}
        coverage = sum(credit[s.state] for s in required) / len(required)
        components = result.score_components
        assert coverage == components.skill_coverage
        expected = 100 * (
            components.semantic_weight * components.semantic_fit
            + components.skills_weight * coverage
        )
        assert result.score == pytest.approx(expected)
    assert load_fixtures().matches[0].score == 77


@pytest.mark.parametrize("score", [-0.1, 101, float("nan"), float("inf")])
def test_invalid_match_scores_are_rejected(score):
    data = load_fixtures().matches[0].model_dump()
    data["score"] = score
    with pytest.raises(ValidationError):
        MatchResult.model_validate(data)


@pytest.mark.parametrize("vector", [[0, 0, 0], [1, 0], [float("nan"), 0, 1]])
def test_invalid_embeddings_are_rejected(vector):
    data = load_fixtures().embeddings[0].model_dump()
    data["vector"] = vector
    with pytest.raises(ValidationError):
        EmbeddingRecord.model_validate(data)


def test_evidence_state_and_revision_invariants():
    fixtures = load_fixtures()
    skill = fixtures.matches[0].skill_comparison[0].model_dump()
    skill["resume_evidence"] = []
    with pytest.raises(ValidationError):
        SkillComparison.model_validate(skill)
    ref = fixtures.profiles[0].evidence[0].model_dump()
    ref["end"] = ref["start"]
    with pytest.raises(ValidationError):
        EvidenceRef.model_validate(ref)
    result_set = fixtures.recommendations.model_dump()
    result_set["results"][0]["candidate_id"] = "another-candidate"
    with pytest.raises(ValidationError):
        RecommendationSet.model_validate(result_set)


def test_unknown_requirements_are_not_full_coverage():
    data = load_fixtures().matches[0].score_components.model_dump()
    data.update(
        score_basis="semantic_only", skill_coverage=None, semantic_weight=1, skills_weight=0
    )
    assert ScoreComponents.model_validate(data).skill_coverage is None
    data["skill_coverage"] = 1
    with pytest.raises(ValidationError):
        ScoreComponents.model_validate(data)


def test_job_event_is_independent_of_upload_and_rejects_unknown_fields():
    event = load_fixtures().events[1].model_dump(mode="json")
    assert "resume_id" not in event and "analysis_id" not in event
    assert TypeAdapter(DomainEvent).validate_python(event).event_type == "job.created"
    event["analysis_id"] = "accidental-upload-coupling"
    with pytest.raises(ValidationError):
        TypeAdapter(DomainEvent).validate_python(event)
    profile = load_fixtures().profiles[0].model_dump()
    profile["candidate_id"] = ""
    with pytest.raises(ValidationError):
        CandidateProfile.model_validate(profile)
