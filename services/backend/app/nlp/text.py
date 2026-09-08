"""Conservative normalization with a reversible reference to source spans."""

import unicodedata

from app.contracts.models import EvidenceRef, ProcessedText
from app.nlp.errors import NlpError
from app.nlp.types import NormalizedText


def normalize_text(text: str) -> NormalizedText:
    """Normalize compatibility characters/whitespace; preserve case and punctuation.

    A combining cluster shares its source range. A collapsed whitespace run maps
    to the complete run. Never remove stopwords, negation, or skill punctuation.
    """
    chars: list[str] = []
    offsets: list[tuple[int, int]] = []
    i = 0
    while i < len(text):
        start = i
        i += 1
        while i < len(text) and unicodedata.combining(text[i]):
            i += 1
        for char in unicodedata.normalize("NFKC", text[start:i]):
            # Replace controls instead of joining words across an invisible byte.
            if char.isspace() or unicodedata.category(char) == "Cc":
                char = " "
            if char == " " and chars and chars[-1] == " ":
                offsets[-1] = (offsets[-1][0], i)
            else:
                chars.append(char)
                offsets.append((start, i))
    left = 1 if chars and chars[0] == " " else 0
    right = len(chars) - (1 if chars and chars[-1] == " " else 0)
    return NormalizedText("".join(chars[left:right]), tuple(offsets[left:right]))


def validate_source(source: ProcessedText, max_chars: int) -> None:
    if len(source.text) > max_chars:
        raise NlpError("NLP_TEXT_TOO_LONG", "Text exceeds the configured NLP limit.")
    if not source.evidence:
        raise NlpError("INVALID_EVIDENCE", "NLP requires source document evidence.")
    identity = {(e.document_id, e.document_version) for e in source.evidence}
    if len(identity) != 1:
        raise NlpError("INVALID_EVIDENCE", "Evidence must belong to one document version.")
    previous_end = 0
    chunks: set[str] = set()
    for ref in source.evidence:
        if (
            ref.start < previous_end
            or ref.end > len(source.text)
            or source.text[ref.start : ref.end] != ref.excerpt
            or ref.chunk_id in chunks
        ):
            raise NlpError("INVALID_EVIDENCE", "Source evidence is inconsistent or overlapping.")
        if source.text[previous_end : ref.start].strip():
            raise NlpError("INVALID_EVIDENCE", "Non-whitespace source text lacks evidence.")
        previous_end = ref.end
        chunks.add(ref.chunk_id)
    if source.text[previous_end:].strip():
        raise NlpError("INVALID_EVIDENCE", "Non-whitespace source text lacks evidence.")


def evidence_for(
    source: ProcessedText, normalized: NormalizedText, start: int, end: int
) -> tuple[EvidenceRef, ...]:
    source_start, source_end = normalized.source_span(start, end)
    refs = []
    for ref in source.evidence:
        lo, hi = max(source_start, ref.start), min(source_end, ref.end)
        if lo < hi:
            refs.append(
                ref.model_copy(
                    update={
                        "start": lo,
                        "end": hi,
                        "excerpt": source.text[lo:hi],
                    }
                )
            )
    if not refs:
        raise NlpError("INVALID_EVIDENCE", "Annotation has no source evidence.")
    return tuple(refs)
