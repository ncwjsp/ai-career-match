import pytest
from topics import analyze


def test_lda_reproducible_normalized_distributions():
    pytest.importorskip("sklearn")
    documents = [
        "python software data developer",
        "python sql data engineer",
        "sales customer accounts manager",
        "sales customer retail service",
    ]
    first = analyze(documents, topics=2)
    second = analyze(documents, topics=2)
    assert first == second
    assert len(first["topics"]) == 2
    for row in first["document_topic_probabilities"]:
        assert sum(row) == pytest.approx(1)


def test_empty_corpus_rejected():
    pytest.importorskip("sklearn")
    with pytest.raises(ValueError):
        analyze([])
