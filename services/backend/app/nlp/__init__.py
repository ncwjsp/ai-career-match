"""M1 shared NLP; imports do not load a model or access a service."""

from app.nlp.errors import NlpError
from app.nlp.processor import SharedTextProcessor

__all__ = ["NlpError", "SharedTextProcessor"]
