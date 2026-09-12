"""Present/partial/missing skill comparison (B-06)."""

from app.contracts.models import Experience, Project, SkillEvidence
from app.modules.matching.skills import compare_skills, strengths_and_gaps
from tests.jobs.factories import make_job, requirement
from tests.matching.factories import evidence, make_candidate


def test_present_when_the_candidate_lists_the_exact_skill():
    profile = make_candidate(skills=[SkillEvidence(name="Python", evidence=[evidence()])])
    job = make_job(requirements=[requirement("Python")])

    [comparison] = compare_skills(profile, job)

    assert comparison.state == "present"
    assert comparison.resume_evidence == [evidence()]
    assert comparison.job_evidence  # JobRequirement.evidence is never empty


def test_present_resolves_the_shared_alias_registry_case_insensitively():
    profile = make_candidate(skills=[SkillEvidence(name="PyTorch", evidence=[evidence()])])
    job = make_job(requirements=[requirement("pytorch")])  # A-02's registered alias, lowercased

    [comparison] = compare_skills(profile, job)

    assert comparison.state == "present"


def test_present_matches_case_insensitively_outside_the_alias_registry():
    """ "AWS" is not in the shared registry; matching still should not be case-sensitive."""
    profile = make_candidate(skills=[SkillEvidence(name="AWS", evidence=[evidence()])])
    job = make_job(requirements=[requirement("aws")])

    [comparison] = compare_skills(profile, job)

    assert comparison.state == "present"


def test_partial_when_only_mentioned_in_a_project_description():
    profile = make_candidate(
        skills=[],
        projects=[
            Project(
                name="Deploy pipeline",
                description="Used Docker to containerize the service.",
                evidence=[evidence(excerpt="Used Docker to containerize the service.")],
            )
        ],
    )
    job = make_job(requirements=[requirement("Docker")])

    [comparison] = compare_skills(profile, job)

    assert comparison.state == "partial"
    assert comparison.resume_evidence
    assert comparison.uncertainty_note is not None


def test_partial_when_only_mentioned_in_an_experience_entry():
    profile = make_candidate(
        skills=[],
        experience=[
            Experience(
                job_title="Kubernetes administrator",
                organization="Example Corp",
                evidence=[evidence(excerpt="Kubernetes administrator")],
            )
        ],
    )
    job = make_job(requirements=[requirement("Kubernetes")])

    [comparison] = compare_skills(profile, job)

    assert comparison.state == "partial"


def test_partial_when_only_mentioned_in_the_summary():
    profile = make_candidate(
        skills=[],
        summary="Familiar with Terraform for infrastructure.",
        profile_evidence=[evidence(excerpt="Familiar with Terraform.")],
    )
    job = make_job(requirements=[requirement("Terraform")])

    [comparison] = compare_skills(profile, job)

    assert comparison.state == "partial"
    assert comparison.resume_evidence


def test_missing_when_there_is_no_evidence_at_all():
    profile = make_candidate(skills=[])
    job = make_job(requirements=[requirement("Rust")])

    [comparison] = compare_skills(profile, job)

    assert comparison.state == "missing"
    assert comparison.resume_evidence == []


def test_a_missing_skill_is_not_proof_the_candidate_lacks_it():
    """Contract: absence means not evidenced, and the model must not fabricate
    resume evidence for it either way."""
    profile = make_candidate(skills=[])
    job = make_job(requirements=[requirement("Go")])

    [comparison] = compare_skills(profile, job)

    assert comparison.state == "missing"
    assert comparison.uncertainty_note is None


def test_duplicate_requirements_for_the_same_skill_are_merged():
    profile = make_candidate(skills=[])
    job = make_job(
        requirements=[requirement("Python", required=False), requirement("Python", required=True)]
    )

    comparisons = compare_skills(profile, job)

    assert len(comparisons) == 1
    assert comparisons[0].required is True


def test_preferred_skills_are_reported_but_do_not_count_as_gaps():
    profile = make_candidate(skills=[])
    job = make_job(requirements=[requirement("Scala", required=False)])

    comparisons = compare_skills(profile, job)
    _, gaps = strengths_and_gaps(comparisons)

    assert comparisons[0].state == "missing"
    assert gaps == []  # A missing preferred skill is not a gap.


def test_strengths_and_gaps_only_count_required_present_and_missing():
    profile = make_candidate(skills=[SkillEvidence(name="Python", evidence=[evidence()])])
    job = make_job(
        requirements=[
            requirement("Python", required=True),
            requirement("Rust", required=True),
            requirement("Go", required=False),
        ]
    )

    strengths, gaps = strengths_and_gaps(compare_skills(profile, job))

    assert strengths == ["Python"]
    assert gaps == ["Rust"]
