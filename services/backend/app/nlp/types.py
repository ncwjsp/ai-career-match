"""Internal A-02 annotations, not competing public API DTOs."""

from dataclasses import dataclass
from typing import Literal

from app.contracts.models import EvidenceRef, ProcessedText

PREPROCESSING_VERSION = "shared-text-v1"
SKILL_VERSION = "skill-aliases-v1"


@dataclass(frozen=True)
class NormalizedText:
    text: str
    # One original [start, end) range for each normalized Unicode code point.
    offsets: tuple[tuple[int, int], ...]

    def source_span(self, start: int, end: int) -> tuple[int, int]:
        if not 0 <= start < end <= len(self.offsets):
            raise ValueError("Invalid normalized span.")
        return self.offsets[start][0], self.offsets[end - 1][1]


@dataclass(frozen=True)
class TokenAnnotation:
    text: str
    lemma: str
    pos: str
    tag: str
    start: int
    end: int
    evidence: tuple[EvidenceRef, ...]


@dataclass(frozen=True)
class EntityAnnotation:
    text: str
    label: str
    start: int
    end: int
    evidence: tuple[EvidenceRef, ...]


@dataclass(frozen=True)
class SkillMention:
    canonical: str
    text: str
    assertion: Literal["mentioned", "negated", "uncertain"]
    start: int
    end: int
    evidence: tuple[EvidenceRef, ...]


@dataclass(frozen=True)
class NlpAnalysis:
    source: ProcessedText
    normalized: NormalizedText
    tokens: tuple[TokenAnnotation, ...]
    entities: tuple[EntityAnnotation, ...]
    skills: tuple[SkillMention, ...]
    warnings: tuple[str, ...]
    model_id: str
    model_version: str
    preprocessing_version: str = PREPROCESSING_VERSION
    skill_version: str = SKILL_VERSION
    language: str = "en"
