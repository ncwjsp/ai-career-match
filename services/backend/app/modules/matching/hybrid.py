"""Hybrid re-ranking: bound a candidate pool, then rank it by a tunable
weighted combination of the baseline methods. Owner: M2 (B-05).

Transformer pair (cross-encoder) matching is the other half of B-05 and is
still blocked: `cross_encoder.py` does not exist yet because it needs a new
ML runtime dependency (a cross-encoder model/runtime), which is a
shared-manifest change requiring M3 coordination unlike the pure-Python
baselines this module combines. `HybridWeights`/`HYBRID_VERSION` are
designed so a cross-encoder term can be added as a fourth weighted input
later without changing this module's public shape.

"Hybrid" is two things plan.md asks for together:

  1. Bound the candidate pool -- score every job in the pool with one cheap
     method (the bi-encoder; already O(1) per pair once an embedding client
     exists) and keep only the top `candidate_pool_size` before doing
     anything more expensive.
  2. Re-rank that bounded pool with a weighted combination of all three
     existing baselines (keyword/TF-IDF/bi-encoder) rather than the coarse
     score alone -- more informative than any single method, and still
     fully deterministic (ties broken by `job_id`, matching plan.md's "score
     ordering and tie handling are deterministic" acceptance bar).

This produces its own `HybridScore` results and does not write
`scoring_version = "semantic-skills-v1"` results (`scoring.py`'s `Matcher`
owns that) -- `HYBRID_VERSION` is a distinct, separately versioned formula,
per docs/matching/scoring.md's note that a hybrid weight/transformation
change must ship under its own version rather than reinterpreting stored
`semantic-skills-v1` scores.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.contracts.models import CandidateProfile, JobPosting
from app.core.inference import EmbeddingClient
from app.modules.matching import bi_encoder, keyword, tfidf

HYBRID_VERSION = "hybrid-weighted-v1"


@dataclass(frozen=True)
class HybridWeights:
    keyword: float = 0.2
    tfidf: float = 0.3
    bi_encoder: float = 0.5

    def __post_init__(self) -> None:
        if self.keyword < 0 or self.tfidf < 0 or self.bi_encoder < 0:
            raise ValueError("Hybrid weights must be nonnegative.")
        if self.keyword + self.tfidf + self.bi_encoder <= 0:
            raise ValueError("Hybrid weights must sum to a positive number.")


_DEFAULT_WEIGHTS = HybridWeights()


@dataclass(frozen=True)
class HybridScore:
    job_id: str
    score: float
    components: dict[str, float]
    hybrid_version: str = HYBRID_VERSION


def rerank(
    profile: CandidateProfile,
    jobs: Sequence[JobPosting],
    embedding_client: EmbeddingClient,
    *,
    candidate_pool_size: int,
    weights: HybridWeights = _DEFAULT_WEIGHTS,
    background: Sequence[str] = (),
) -> list[HybridScore]:
    """Bound `jobs` to the top `candidate_pool_size` by bi-encoder score, then
    return that bounded pool ranked by the full weighted combination,
    highest first. `background` is the same optional frozen-corpus token
    background `tfidf.score` accepts, for a more realistic IDF estimate."""
    if candidate_pool_size < 1:
        raise ValueError("candidate_pool_size must be at least 1.")

    coarse_scores = {job.job_id: bi_encoder.score(profile, job, embedding_client) for job in jobs}
    bounded = sorted(jobs, key=lambda job: (-coarse_scores[job.job_id], job.job_id))[
        :candidate_pool_size
    ]

    total_weight = weights.keyword + weights.tfidf + weights.bi_encoder
    results = []
    for job in bounded:
        components = {
            "keyword": keyword.score(profile, job),
            "tfidf": tfidf.score(profile, job, background=background),
            "bi_encoder": coarse_scores[job.job_id],
        }
        combined = (
            weights.keyword * components["keyword"]
            + weights.tfidf * components["tfidf"]
            + weights.bi_encoder * components["bi_encoder"]
        ) / total_weight
        results.append(HybridScore(job_id=job.job_id, score=combined, components=components))

    results.sort(key=lambda result: (-result.score, result.job_id))
    return results
