"""Deterministic job-description summary (B-02, R10)."""

from app.modules.jobs.summary import summarize


def test_empty_description_summarizes_to_none():
    assert summarize("") is None
    assert summarize("   ") is None


def test_short_description_is_returned_whole():
    assert summarize("Build things with Python.") == "Build things with Python."


def test_joins_sentences_up_to_the_sentence_limit():
    text = "One. Two. Three. Four."

    assert summarize(text, max_sentences=2) == "One. Two."


def test_stops_before_exceeding_the_char_budget():
    text = "Short one. " + ("Word " * 20).strip() + "."

    result = summarize(text, max_chars=20, max_sentences=5)

    assert result == "Short one."


def test_a_single_long_sentence_is_truncated_with_ellipsis():
    text = "word " * 100

    result = summarize(text.strip() + ".", max_chars=30)

    assert result is not None
    assert len(result) == 30
    assert result.endswith("…")
