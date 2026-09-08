import pytest

from app.contracts.models import EvidenceRef, ProcessedText
from app.nlp.errors import NlpError
from app.nlp.text import evidence_for, normalize_text, validate_source


def source(text, refs=None):
    return ProcessedText(
        text=text,
        language="en",
        preprocessing_version="synthetic-v1",
        evidence=refs
        if refs is not None
        else [
            EvidenceRef(
                document_id="demo",
                document_version=1,
                chunk_id="chunk-1",
                start=0,
                end=len(text),
                excerpt=text,
            )
        ],
    )


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("  C++\tC#\r\nPyTorch  ", "C++ C# PyTorch"),
        ("Python\x00SQL", "Python SQL"),
        ("Ｐｙｔｈｏｎ ﬁle", "Python file"),
        ("cafe\u0301", "café"),
        ("ภาษาไทย 😀", "ภาษาไทย 😀"),
        ("not only Python", "not only Python"),
        (" \n ", ""),
    ],
)
def test_normalization_preserves_meaning_and_maps_characters(raw, expected):
    view = normalize_text(raw)
    assert view.text == expected
    assert len(view.offsets) == len(expected)
    assert all(0 <= lo < hi <= len(raw) for lo, hi in view.offsets)
    assert list(view.offsets) == sorted(view.offsets)


def test_expanded_ligature_and_combining_cluster_resolve_to_source():
    original = source("ﬁ cafe\u0301")
    view = normalize_text(original.text)
    assert evidence_for(original, view, 0, 2)[0].excerpt == "ﬁ"
    assert evidence_for(original, view, 3, 7)[0].excerpt == "cafe\u0301"


def test_entity_across_chunks_keeps_page_and_chunk_provenance():
    text = "New\n\nYork"
    refs = [
        EvidenceRef(
            document_id="demo",
            document_version=1,
            chunk_id="one",
            page=1,
            start=0,
            end=3,
            excerpt="New",
        ),
        EvidenceRef(
            document_id="demo",
            document_version=1,
            chunk_id="two",
            page=2,
            start=5,
            end=9,
            excerpt="York",
        ),
    ]
    original = source(text, refs)
    validate_source(original, 100)
    found = evidence_for(original, normalize_text(text), 0, 8)
    assert [(x.page, x.chunk_id, x.excerpt) for x in found] == [
        (1, "one", "New"),
        (2, "two", "York"),
    ]


@pytest.mark.parametrize("start,end", [(-1, 1), (0, 0), (1, 5), (2, 1)])
def test_invalid_normalized_spans_rejected(start, end):
    with pytest.raises(ValueError):
        normalize_text("abc").source_span(start, end)


@pytest.mark.parametrize(
    "update",
    [
        {"excerpt": "wrong"},
        {"end": 100},
        {"start": 1, "excerpt": "ython"},
    ],
)
def test_invalid_evidence_rejected(update):
    original = source("Python")
    original.evidence[0] = original.evidence[0].model_copy(update=update)
    with pytest.raises(NlpError, match="evidence"):
        validate_source(original, 100)


def test_uncovered_text_and_mixed_identity_rejected():
    original = source("Python SQL")
    first = original.evidence[0].model_copy(update={"end": 6, "excerpt": "Python"})
    with pytest.raises(NlpError):
        validate_source(source(original.text, [first]), 100)
    second = first.model_copy(
        update={"document_id": "other", "chunk_id": "two", "start": 7, "end": 10, "excerpt": "SQL"}
    )
    with pytest.raises(NlpError):
        validate_source(source(original.text, [first, second]), 100)


def test_overlapping_and_duplicate_chunks_rejected():
    original = source("Python SQL")
    with pytest.raises(NlpError):
        validate_source(source(original.text, original.evidence * 2), 100)


def test_empty_evidence_rejected():
    with pytest.raises(NlpError):
        validate_source(source("Python", []), 100)
