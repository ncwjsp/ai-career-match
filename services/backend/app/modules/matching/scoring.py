"""The deterministic `semantic-skills-v1` formula and the real `Matcher`.
Owner: M2 (B-05/B-06/B-10).

    S = clamp(cosine(candidate_embedding, job_embedding), 0, 1)
    For each distinct required skill: credit = 1.0 present, 0.5 partial, 0.0 missing
    K = sum(credit) / number_of_distinct_required_skills
    If the job has at least one reliably extracted required skill:
        raw = 100 * (0.70 * S + 0.30 * K)
    Otherwise:
        raw = 100 * S           # score_basis = "semantic_only", skill_coverage = None
    display = round(raw, 1)

This is plan.md's proposed starting formula, not a measured result: the 70/30
weights and the 0.5 partial-credit rule are first-draft values B-08's held-out
evaluation is meant to revisit, not settled facts. Documented in full at
`docs/matching/scoring.md`.

`Matcher` is the concrete `app.contracts.interfaces.Matcher` this scoring
formula backs — the object `scripts/run_worker.py` imports at
`app.modules.matching.scoring.Matcher` and constructs with no arguments.
`score_pair` and `match_job` share one code path (`match_job` simply calls
`score_pair` per profile), so a pair's score cannot differ between the two
matching triggers.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.contracts.interfaces import Matcher as MatcherProtocol
from app.contracts.models import (
    CandidateProfile,
    JobPosting,
    MatchResult,
    Recommendation,
    ScoreComponents,
    SkillComparison,
)
from app.core.clock import Clock, SystemClock
from app.core.inference import EmbeddingClient, build_embedding_client
from app.core.settings import Settings
from app.modules.matching.bi_encoder import cosine
from app.modules.matching.skills import compare_skills, strengths_and_gaps
from app.modules.matching.text import job_text, profile_text

SCORING_VERSION = "semantic-skills-v1"
SEMANTIC_WEIGHT = 0.70
SKILLS_WEIGHT = 0.30
_CREDIT: dict[str, float] = {"present": 1.0, "partial": 0.5, "missing": 0.0}

ScoreBasis = Literal["semantic_skills", "semantic_only"]


@dataclass(frozen=True)
class ScoreCalculation:
    semantic_fit: float
    skill_coverage: float | None
    score_basis: ScoreBasis
    display_score: float


def compute_score(semantic_fit: float, required_states: Sequence[str]) -> ScoreCalculation:
    """The formula above, isolated from embeddings/skill-extraction so it can be
    tested against plan.md's worked example directly: `compute_score(0.80,
    ["present", "present", "present", "partial", "missing"])` gives 77.0."""
    s = max(0.0, min(1.0, semantic_fit))
    if required_states:
        coverage = sum(_CREDIT[state] for state in required_states) / len(required_states)
        raw = 100 * (SEMANTIC_WEIGHT * s + SKILLS_WEIGHT * coverage)
        basis: ScoreBasis = "semantic_skills"
    else:
        coverage = None
        raw = 100 * s
        basis = "semantic_only"
    return ScoreCalculation(s, coverage, basis, round(raw, 1))


def _short_reason(strengths: list[str], gaps: list[str]) -> str | None:
    if not strengths and not gaps:
        return None
    parts = []
    if strengths:
        parts.append(f"Present: {', '.join(strengths[:3])}")
    if gaps:
        parts.append(f"Missing: {', '.join(gaps[:3])}")
    return "; ".join(parts)


def _collect_evidence(comparisons: list[SkillComparison]):
    evidence = []
    seen = set()
    for comparison in comparisons:
        for ref in (*comparison.job_evidence, *comparison.resume_evidence):
            key = (ref.document_id, ref.chunk_id, ref.start, ref.end)
            if key not in seen:
                seen.add(key)
                evidence.append(ref)
    return evidence


class Matcher(MatcherProtocol):
    """The live scorer: sentence-embedding semantic fit plus skill coverage."""

    def __init__(
        self,
        embedding_client: EmbeddingClient | None = None,
        clock: Clock | None = None,
        *,
        preprocessing_version: str = "matching-text-v1",
    ):
        self._embedding_client = embedding_client or build_embedding_client(Settings())
        self._clock = clock or SystemClock()
        self._preprocessing_version = preprocessing_version

    def score_pair(
        self, profile: CandidateProfile, job: JobPosting, scoring_version: str
    ) -> MatchResult:
        batch = self._embedding_client.embed([profile_text(profile), job_text(job)])
        semantic_fit = cosine(batch.vectors[0], batch.vectors[1])

        comparisons = compare_skills(profile, job)
        required_states = [c.state for c in comparisons if c.required]
        calc = compute_score(semantic_fit, required_states)
        strengths, gaps = strengths_and_gaps(comparisons)

        semantic_weight = 1.0 if calc.score_basis == "semantic_only" else SEMANTIC_WEIGHT
        skills_weight = 0.0 if calc.score_basis == "semantic_only" else SKILLS_WEIGHT
        return MatchResult(
            candidate_id=profile.candidate_id,
            profile_version=profile.profile_version,
            job_id=job.job_id,
            job_version=job.content_version,
            score=calc.display_score,
            score_components=ScoreComponents(
                semantic_fit=calc.semantic_fit,
                skill_coverage=calc.skill_coverage,
                semantic_weight=semantic_weight,
                skills_weight=skills_weight,
                score_basis=calc.score_basis,
                model_revision=batch.model_revision,
                preprocessing_version=self._preprocessing_version,
            ),
            scoring_version=scoring_version,
            skill_comparison=comparisons,
            strengths=strengths,
            gaps=gaps,
            short_reason=_short_reason(strengths, gaps),
            evidence=_collect_evidence(comparisons),
            matched_at=self._clock.now(),
            data_origin="computed",
        )

    def match_job(
        self, job: JobPosting, active_profiles: Sequence[CandidateProfile], scoring_version: str
    ) -> Sequence[MatchResult]:
        # One code path with score_pair: a pair's score cannot depend on which
        # matching trigger (profile.ready vs job.created/updated) produced it.
        return [self.score_pair(profile, job, scoring_version) for profile in active_profiles]

    def recommend(
        self, profile: CandidateProfile, corpus_snapshot: str, limit: int
    ) -> Sequence[Recommendation]:
        # Unused by the live pipeline: C-08 publishes ranked, stored score_pair/
        # match_job results (app/orchestration/refresh.py). On-demand, corpus-
        # snapshot-scoped search belongs to B-03/B-05 and does not exist yet.
        raise NotImplementedError(
            "recommend() needs a versioned job corpus snapshot (B-03/B-05); "
            "C-08 ranks stored score_pair/match_job results instead."
        )
