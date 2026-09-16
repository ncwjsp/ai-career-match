"""Precision/recall/F1 for a ranked list against binary relevance labels.
Owner: M2 (B-08).

Deliberately has no dependency on `app.contracts` or any matching method: it
only knows about a ranked list of opaque IDs and a set of "relevant" IDs, so
it is testable in complete isolation and reusable for any ranking, not only
this project's matching methods.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RankMetrics:
    precision_at_k: float
    recall_at_k: float
    f1_at_k: float
    k: int
    relevant_total: int
    retrieved_relevant: int


def evaluate_ranking(ranked_ids: list[str], relevant_ids: set[str], k: int) -> RankMetrics:
    """`ranked_ids` is one query's full ranking, best first. `relevant_ids` is
    that query's complete ground truth, not itself truncated to `k`."""
    if k < 1:
        raise ValueError("k must be at least 1.")
    top_k = ranked_ids[:k]
    retrieved_relevant = len(set(top_k) & relevant_ids)
    precision = retrieved_relevant / len(top_k) if top_k else 0.0
    recall = retrieved_relevant / len(relevant_ids) if relevant_ids else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return RankMetrics(
        precision_at_k=precision,
        recall_at_k=recall,
        f1_at_k=f1,
        k=k,
        relevant_total=len(relevant_ids),
        retrieved_relevant=retrieved_relevant,
    )


def average_metrics(per_query: list[RankMetrics]) -> RankMetrics:
    """Macro-average across queries (one profile = one query): every query
    counts equally regardless of how many relevant jobs it has."""
    if not per_query:
        raise ValueError("Cannot average metrics over zero queries.")
    k = per_query[0].k
    if any(m.k != k for m in per_query):
        raise ValueError("All queries must share the same k to average together.")
    n = len(per_query)
    return RankMetrics(
        precision_at_k=sum(m.precision_at_k for m in per_query) / n,
        recall_at_k=sum(m.recall_at_k for m in per_query) / n,
        f1_at_k=sum(m.f1_at_k for m in per_query) / n,
        k=k,
        relevant_total=sum(m.relevant_total for m in per_query),
        retrieved_relevant=sum(m.retrieved_relevant for m in per_query),
    )
