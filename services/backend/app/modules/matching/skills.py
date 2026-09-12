"""Present/partial/missing skill comparison. Owner: M2 (B-06).

`present` means the job's required/preferred skill resolves, via the same
shared alias registry A-02 uses for resume extraction (`app.nlp.skills.ALIASES`),
to a skill A-03 already extracted with confident (`mentioned`, not `negated` or
`uncertain`) evidence — `CandidateProfile.skills` only ever contains that
confident set, so an exact/alias name match is the strongest available signal.

`partial` is this module's own documented rubric (proposed, not measured):
the skill's own name appears as a case-insensitive mention inside other
evidenced parts of the profile — an experience title/organization, a project's
name/description, or the free-text summary — without having been extracted as
a standalone canonical skill. That is weaker evidence (a passing mention, not
a listed competency) but it is not nothing, and plan.md's B-08 evaluation is
where this half-credit rule gets reviewed against real judgments.

`missing` means neither of the above: the resume gives no evidence for it.
Absence here is "not evidenced", never "confirmed absent" (a candidate may
simply not have listed something they know).
"""

from __future__ import annotations

from app.contracts.models import (
    CandidateProfile,
    EvidenceRef,
    JobPosting,
    JobRequirement,
    SkillComparison,
)
from app.nlp.skills import ALIASES

# alias-variant (casefolded) -> canonical name, built once from the shared registry.
_ALIAS_TO_CANONICAL: dict[str, str] = {
    variant.casefold(): canonical
    for canonical, variants in ALIASES.items()
    for variant in (*variants, canonical)
}


def _canonical_key(name: str) -> str:
    """Resolve a skill name to a comparison key: the shared canonical form when
    the registry knows it, otherwise the name's own casefold (so "AWS" and "aws"
    still count as the same skill even though A-02's registry does not cover it)."""
    return _ALIAS_TO_CANONICAL.get(name.casefold(), name.casefold())


def _distinct_requirements(job: JobPosting) -> list[JobRequirement]:
    """One entry per distinct skill key, keeping the first occurrence's evidence.
    A requirement is `required` if any duplicate row marks it so."""
    by_key: dict[str, JobRequirement] = {}
    for requirement in job.requirements:
        key = _canonical_key(requirement.skill)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = requirement
        elif requirement.required and not existing.required:
            by_key[key] = existing.model_copy(update={"required": True})
    return list(by_key.values())


def _candidate_skill_keys(profile: CandidateProfile) -> set[str]:
    return {_canonical_key(skill.name) for skill in profile.skills}


def _partial_evidence(profile: CandidateProfile, skill_name: str) -> list[EvidenceRef]:
    """A weaker, non-canonical mention of `skill_name` elsewhere in the resume."""
    needle = skill_name.casefold()
    for entry in profile.experience:
        haystack = f"{entry.job_title or ''} {entry.organization or ''}".casefold()
        if needle in haystack and entry.evidence:
            return list(entry.evidence)
    for project in profile.projects:
        haystack = f"{project.name} {project.description}".casefold()
        if needle in haystack and project.evidence:
            return list(project.evidence)
    if profile.summary and needle in profile.summary.casefold() and profile.evidence:
        return list(profile.evidence)
    return []


def compare_skills(profile: CandidateProfile, job: JobPosting) -> list[SkillComparison]:
    """One `SkillComparison` per distinct skill the job mentions (required or not)."""
    candidate_keys = _candidate_skill_keys(profile)
    comparisons: list[SkillComparison] = []
    for requirement in _distinct_requirements(job):
        key = _canonical_key(requirement.skill)
        if key in candidate_keys:
            resume_evidence = _matching_skill_evidence(profile, key)
            comparisons.append(
                SkillComparison(
                    skill=requirement.skill,
                    required=requirement.required,
                    state="present",
                    job_evidence=list(requirement.evidence),
                    resume_evidence=resume_evidence,
                )
            )
            continue
        partial_evidence = _partial_evidence(profile, requirement.skill)
        if partial_evidence:
            comparisons.append(
                SkillComparison(
                    skill=requirement.skill,
                    required=requirement.required,
                    state="partial",
                    job_evidence=list(requirement.evidence),
                    resume_evidence=partial_evidence,
                    uncertainty_note=(
                        "Mentioned in the resume but not extracted as a listed skill."
                    ),
                )
            )
            continue
        comparisons.append(
            SkillComparison(
                skill=requirement.skill,
                required=requirement.required,
                state="missing",
                job_evidence=list(requirement.evidence),
                resume_evidence=[],
            )
        )
    return comparisons


def _matching_skill_evidence(profile: CandidateProfile, key: str) -> list[EvidenceRef]:
    for skill in profile.skills:
        if _canonical_key(skill.name) == key:
            return list(skill.evidence)
    return []  # pragma: no cover - key came from candidate_keys, so this always finds one


def strengths_and_gaps(comparisons: list[SkillComparison]) -> tuple[list[str], list[str]]:
    """Short, evidence-backed strings for `MatchResult.strengths`/`gaps`.

    Gaps are limited to required skills: a missing preferred skill is not
    reported as a gap, matching the scoring formula's treatment of preferred
    skills as informational only.
    """
    strengths = [c.skill for c in comparisons if c.state == "present"]
    gaps = [c.skill for c in comparisons if c.state == "missing" and c.required]
    return strengths, gaps
