"""Small reviewed alias registry; mentions are not proficiency or match scores."""

import re
from collections.abc import Mapping, Sequence
from typing import Literal

from app.contracts.models import ProcessedText
from app.nlp.text import evidence_for
from app.nlp.types import NormalizedText, SkillMention

# Conservative aliases only: frameworks are not aliases for their parent language.
# Ambiguous single letters and abbreviations such as R, C, ML, AI are excluded.
ALIASES: Mapping[str, tuple[str, ...]] = {
    "Python": ("python",),
    "C++": ("c++", "cplusplus"),
    "C#": ("c#", "csharp", "c sharp"),
    "PyTorch": ("pytorch", "py torch"),
    "TensorFlow": ("tensorflow", "tensor flow"),
    "JavaScript": ("javascript", "java script"),
    "TypeScript": ("typescript",),
    "Java": ("java",),
    "SQL": ("sql", "structured query language"),
    "PostgreSQL": ("postgresql", "postgres"),
    "scikit-learn": ("scikit-learn", "scikit learn", "sklearn"),
    "Node.js": ("node.js", "nodejs"),
    ".NET": (".net", "dotnet"),
    "React": ("react", "react.js", "reactjs"),
    "Docker": ("docker",),
    "Git": ("git",),
    "machine learning": ("machine learning",),
    "deep learning": ("deep learning",),
    "natural language processing": ("natural language processing",),
}


def _assertion(source: str, start: int, end: int) -> Literal["mentioned", "negated", "uncertain"]:
    # Preserve newlines as clause boundaries by using original, not folded text.
    before = re.split(r"[.!?;\n\r]|\b(?:but|however|yet)\b", source[:start], flags=re.IGNORECASE)[
        -1
    ].casefold()
    after = re.split(r"[.!?;\n\r]", source[end:])[0].casefold()
    before = re.sub(r"\bnot\s+(?:only|just)\b", "", before)
    if re.search(r"\b(?:no|not|never|without|lack|lacks|lacking|\w+n['’]t)\b", before):
        return "negated"
    if re.match(r"\s+(?:(?:is|are)\s+)?(?:not\s+(?:required|needed|known)|unnecessary)\b", after):
        return "negated"
    if re.search(r"\b(?:learning|beginner|basic|basics|introductory|aspiring|exposure)\b", before):
        return "uncertain"
    return "mentioned"


def find_skills(
    source: ProcessedText,
    normalized: NormalizedText,
    aliases: Mapping[str, Sequence[str]] = ALIASES,
) -> tuple[SkillMention, ...]:
    candidates: list[tuple[int, int, str]] = []
    for canonical, variants in aliases.items():
        for alias in variants:
            # A punctuation suffix must not turn C++ into C or JavaScript into Java.
            pattern = r"(?<![\w.+#-])" + re.escape(alias) + r"(?![\w+#-])"
            for match in re.finditer(pattern, normalized.text, flags=re.IGNORECASE):
                candidates.append((match.start(), match.end(), canonical))
    # Longest match wins at each position; repeated mentions keep their evidence.
    candidates.sort(key=lambda item: (item[0], -(item[1] - item[0]), item[2]))
    result = []
    last_end = -1
    for start, end, canonical in candidates:
        if start < last_end:
            continue
        lo, hi = normalized.source_span(start, end)
        result.append(
            SkillMention(
                canonical,
                normalized.text[start:end],
                _assertion(source.text, lo, hi),
                start,
                end,
                evidence_for(source, normalized, start, end),
            )
        )
        last_end = end
    return tuple(result)
