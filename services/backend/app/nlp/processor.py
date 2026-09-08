"""A-02 shared resume/job text processing, with canonical source evidence."""

import re

from pydantic import TypeAdapter

from app.contracts.models import EvidenceRef, Identifier, ProcessedText, Version
from app.nlp.entities import MODEL_ID, MODEL_VERSION, EnglishPipeline
from app.nlp.errors import NlpError
from app.nlp.skills import find_skills
from app.nlp.text import evidence_for, normalize_text, validate_source
from app.nlp.types import EntityAnnotation, NlpAnalysis, TokenAnnotation


class SharedTextProcessor:
    """One worker-local model reused for resumes/jobs, never loaded on module import.

    process implements the canonical TextProcessor port for raw text using the
    caller's document identity. analyze accepts A-01/ingestor evidence unchanged
    and exposes internal annotations for A-03/B-02. Neither creates profiles.
    """

    def __init__(
        self,
        document_id: str,
        document_version: int,
        *,
        max_chars: int = 200_000,
        pipeline: EnglishPipeline | None = None,
    ):
        self.document_id = TypeAdapter(Identifier).validate_python(document_id)
        self.document_version = TypeAdapter(Version).validate_python(document_version)
        if max_chars < 1:
            raise ValueError("max_chars must be positive.")
        self.max_chars = max_chars
        self._pipeline = pipeline

    def process(self, text: str, language: str | None) -> ProcessedText:
        return self.analyze_text(text, language).source

    def analyze_text(self, text: str, language: str | None) -> NlpAnalysis:
        if not text.strip():
            raise NlpError("NLP_EMPTY_TEXT", "Provide nonempty extracted text.")
        source = ProcessedText(
            text=text,
            language=language,
            preprocessing_version="raw-text-v1",
            evidence=[
                EvidenceRef(
                    document_id=self.document_id,
                    document_version=self.document_version,
                    chunk_id="text-0001",
                    start=0,
                    end=len(text),
                    excerpt=text,
                )
            ],
        )
        return self.analyze(source)

    def analyze(self, source: ProcessedText, language: str | None = None) -> NlpAnalysis:
        selected = language if language is not None else source.language
        if selected is None:
            raise NlpError(
                "NLP_LANGUAGE_REQUIRED", "Declare English; automatic detection is not enabled."
            )
        if selected.casefold() not in {"en", "en-us", "en-gb"}:
            raise NlpError(
                "NLP_UNSUPPORTED_LANGUAGE", "The initial NLP pipeline supports English only."
            )
        if source.language and source.language.casefold() not in {"en", "en-us", "en-gb"}:
            raise NlpError(
                "NLP_LANGUAGE_CONFLICT", "Do not override a non-English source language."
            )
        validate_source(source, self.max_chars)
        if any(
            (e.document_id, e.document_version) != (self.document_id, self.document_version)
            for e in source.evidence
        ):
            raise NlpError("INVALID_EVIDENCE", "Source identity does not match this processor.")
        normalized = normalize_text(source.text)
        if len(normalized.text) > self.max_chars:
            raise NlpError("NLP_TEXT_TOO_LONG", "Normalized text exceeds the NLP limit.")
        if not normalized.text:
            raise NlpError("NLP_EMPTY_TEXT", "Provide nonempty extracted text.")
        if self._pipeline is None:
            self._pipeline = EnglishPipeline()
        doc = self._pipeline(normalized.text)
        tokens = tuple(
            TokenAnnotation(
                token.text,
                token.lemma_,
                token.pos_,
                token.tag_,
                token.idx,
                token.idx + len(token.text),
                evidence_for(source, normalized, token.idx, token.idx + len(token.text)),
            )
            for token in doc
            if not token.is_space
        )
        entities = tuple(
            EntityAnnotation(
                ent.text,
                ent.label_,
                ent.start_char,
                ent.end_char,
                evidence_for(source, normalized, ent.start_char, ent.end_char),
            )
            for ent in doc.ents
        )
        warnings = ["SKILL_ASSERTIONS_ARE_HEURISTIC", "NER_REQUIRES_DOMAIN_REVIEW"]
        if re.search(r"[\u0e00-\u0e7f]", source.text):
            warnings.append("THAI_TEXT_PRESERVED_NOT_ANALYZED_AS_THAI")
        # Evidence resolves into exact source.text, not into normalized.text.
        # Preserve the original preprocessing version as part of that snapshot.
        return NlpAnalysis(
            source.model_copy(deep=True),
            normalized,
            tokens,
            entities,
            find_skills(source, normalized),
            tuple(warnings),
            MODEL_ID,
            MODEL_VERSION,
        )
