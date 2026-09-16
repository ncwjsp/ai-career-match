"""Precision/recall/F1 computation (B-08). Pure functions; no imports outside
the standard library and this module's own `metrics.py`."""

import pytest
from metrics import average_metrics, evaluate_ranking


def test_perfect_ranking_scores_one_everywhere():
    result = evaluate_ranking(["a", "b", "c"], {"a", "b", "c"}, k=3)

    assert result.precision_at_k == 1.0
    assert result.recall_at_k == 1.0
    assert result.f1_at_k == 1.0


def test_no_overlap_scores_zero():
    result = evaluate_ranking(["x", "y", "z"], {"a", "b"}, k=3)

    assert (result.precision_at_k, result.recall_at_k, result.f1_at_k) == (0.0, 0.0, 0.0)


def test_partial_overlap_within_k():
    result = evaluate_ranking(["a", "x", "b", "y"], {"a", "b", "c"}, k=4)

    assert result.retrieved_relevant == 2
    assert result.precision_at_k == 2 / 4
    assert result.recall_at_k == 2 / 3
    assert result.f1_at_k == pytest.approx(2 * (0.5 * (2 / 3)) / (0.5 + 2 / 3))


def test_k_smaller_than_the_full_ranking_only_counts_the_top_k():
    result = evaluate_ranking(["a", "x", "y", "z"], {"a"}, k=1)

    assert result.retrieved_relevant == 1
    assert result.precision_at_k == 1.0
    assert result.recall_at_k == 1.0


def test_relevant_id_outside_the_top_k_is_not_counted():
    result = evaluate_ranking(["x", "y", "a"], {"a"}, k=2)

    assert result.retrieved_relevant == 0
    assert result.recall_at_k == 0.0


def test_empty_ranking_does_not_divide_by_zero():
    result = evaluate_ranking([], {"a", "b"}, k=5)

    assert result.precision_at_k == 0.0
    assert result.recall_at_k == 0.0


def test_no_relevant_ids_gives_zero_recall_not_an_error():
    result = evaluate_ranking(["a", "b"], set(), k=2)

    assert result.recall_at_k == 0.0
    assert result.relevant_total == 0


def test_k_must_be_positive():
    with pytest.raises(ValueError):
        evaluate_ranking(["a"], {"a"}, k=0)


def test_average_metrics_is_a_macro_average_across_queries():
    perfect = evaluate_ranking(["a"], {"a"}, k=1)
    zero = evaluate_ranking(["x"], {"a"}, k=1)

    averaged = average_metrics([perfect, zero])

    assert averaged.precision_at_k == 0.5
    assert averaged.recall_at_k == 0.5


def test_average_metrics_rejects_an_empty_list():
    with pytest.raises(ValueError):
        average_metrics([])


def test_average_metrics_rejects_mismatched_k():
    at_1 = evaluate_ranking(["a"], {"a"}, k=1)
    at_2 = evaluate_ranking(["a", "b"], {"a"}, k=2)

    with pytest.raises(ValueError):
        average_metrics([at_1, at_2])
