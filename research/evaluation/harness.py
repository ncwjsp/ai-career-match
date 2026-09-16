"""Runs matching methods against a frozen evaluation split and compares them.
Owner: M2 (B-08).

Needs the backend package (`app.contracts`, `app.modules.matching`)
importable. `research/` is not itself a Python package rooted at the
backend, so this inserts `services/backend` onto `sys.path` explicitly
rather than relying on a `PYTHONPATH` the caller might not have set --
importing this module is then enough regardless of the current directory or
invocation method.

Known limitation, not yet addressed: `from_pairwise` calls a per-pair scorer
once per (profile, job) in the pool, so a method like the bi-encoder
re-embeds the same profile text once per job in the pool instead of batching
it. Fine at evaluation-harness scale (a frozen split, not live traffic); a
real latency comparison across methods should treat this as a harness cost,
not each method's own inherent cost.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_BACKEND_ROOT = _THIS_DIR.parents[1] / "services" / "backend"
for _path in (_THIS_DIR, _BACKEND_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from metrics import RankMetrics, average_metrics, evaluate_ranking  # noqa: E402
from rubric import EvaluationSplit  # noqa: E402

from app.contracts.models import CandidateProfile, JobPosting  # noqa: E402

PairScoreFn = Callable[[CandidateProfile, JobPosting], float]
RankFn = Callable[[CandidateProfile, Sequence[JobPosting]], list[str]]


def from_pairwise(score_fn: PairScoreFn) -> RankFn:
    """Adapt a `(profile, job) -> float` scorer (keyword/TF-IDF/bi-encoder/a
    future cross-encoder all share this shape) into a `RankFn` by scoring
    every job in the pool and sorting, ties broken by `job_id`."""

    def rank(profile: CandidateProfile, jobs: Sequence[JobPosting]) -> list[str]:
        scored = [(job.job_id, score_fn(profile, job)) for job in jobs]
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        return [job_id for job_id, _ in scored]

    return rank


@dataclass(frozen=True)
class MethodResult:
    method: str
    metrics: RankMetrics
    latency_seconds: float
    failures: list[str]


def run_method(
    method: str,
    rank_fn: RankFn,
    profiles: dict[str, CandidateProfile],
    jobs: dict[str, JobPosting],
    split: EvaluationSplit,
    *,
    k: int,
) -> MethodResult:
    per_query: list[RankMetrics] = []
    failures: list[str] = []
    job_pool = [jobs[job_id] for job_id in split.job_pool_ids]
    start = time.perf_counter()
    for candidate_id in split.candidate_ids:
        profile = profiles.get(candidate_id)
        if profile is None:
            failures.append(f"{method}/{candidate_id}: no profile fixture for this candidate")
            continue
        relevant = split.relevant_job_ids(candidate_id)
        if not relevant:
            failures.append(f"{method}/{candidate_id}: no relevance labels; skipped")
            continue
        try:
            ranked = rank_fn(profile, job_pool)
        except Exception as error:  # noqa: BLE001 - a method's own failure is data to report
            failures.append(f"{method}/{candidate_id}: ranking raised {error!r}")
            continue
        per_query.append(evaluate_ranking(ranked, relevant, k))
    elapsed = time.perf_counter() - start
    if not per_query:
        raise ValueError(f"{method}: no queries could be evaluated. Failures: {failures}")
    return MethodResult(
        method=method,
        metrics=average_metrics(per_query),
        latency_seconds=elapsed,
        failures=failures,
    )


def compare_methods(
    methods: dict[str, RankFn],
    profiles: dict[str, CandidateProfile],
    jobs: dict[str, JobPosting],
    split: EvaluationSplit,
    *,
    k: int = 10,
) -> list[MethodResult]:
    """One `MethodResult` per entry in `methods`, in the given order. Does not
    itself sort/pick a winner -- plan.md's "model/weight recommendation"
    is a judgment call for the written report, not something to automate
    silently here."""
    return [run_method(name, fn, profiles, jobs, split, k=k) for name, fn in methods.items()]
