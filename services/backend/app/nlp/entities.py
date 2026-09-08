"""Explicit trained English spaCy adapter. No downloads or blank-model fallback."""

from typing import Any

from app.nlp.errors import NlpError
from app.nlp.skills import ALIASES

MODEL_ID = "en_core_web_sm"
MODEL_VERSION = "3.8.0"
SPACY_VERSION = "3.8.7"


class EnglishPipeline:
    def __init__(self) -> None:
        try:
            import spacy
            from spacy.symbols import ORTH
        except ImportError as exc:
            raise NlpError(
                "NLP_MODEL_UNAVAILABLE", "Install the pinned A-02 NLP dependencies."
            ) from exc
        if spacy.__version__ != SPACY_VERSION:
            raise NlpError("NLP_MODEL_VERSION", "The spaCy runtime does not match the A-02 pin.")
        try:
            self.pipeline = spacy.load(MODEL_ID)
        except OSError as exc:
            raise NlpError(
                "NLP_MODEL_UNAVAILABLE", "Install the pinned English NLP model."
            ) from exc
        if self.pipeline.meta.get("version") != MODEL_VERSION:
            raise NlpError("NLP_MODEL_VERSION", "The English NLP model has an unexpected revision.")
        if not {"tagger", "attribute_ruler", "lemmatizer", "ner"}.issubset(
            self.pipeline.pipe_names
        ):
            raise NlpError("NLP_MODEL_UNAVAILABLE", "The model must provide POS, lemmas and NER.")
        for canonical, aliases in ALIASES.items():
            for spelling in {canonical, *aliases}:
                if " " not in spelling:
                    for variant in {spelling, spelling.lower(), spelling.upper()}:
                        self.pipeline.tokenizer.add_special_case(variant, [{ORTH: variant}])

    def __call__(self, text: str) -> Any:
        try:
            return self.pipeline(text)
        except Exception as exc:
            # No user text or upstream details in the public-facing message.
            raise NlpError("NLP_PROCESSING_FAILED", "English NLP processing failed.") from exc
