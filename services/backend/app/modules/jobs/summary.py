"""Deterministic job-description summary (R10). Owner: M2 (B-02).

Extractive, not generative: pick leading sentences up to a character budget.
This is not C-02's LLM-generated explanation text (a different R10 producer,
M3-owned) -- it is a cheap, dependency-free fallback good enough for a list
view, and it is what `JobPosting.summary` is filled with until/unless a
richer summarizer replaces it.
"""

from __future__ import annotations

import re

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def summarize(description: str, *, max_chars: int = 280, max_sentences: int = 3) -> str | None:
    text = description.strip()
    if not text:
        return None
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]
    if not sentences:
        return None
    picked: list[str] = []
    length = 0
    for sentence in sentences[:max_sentences]:
        if picked and length + len(sentence) + 1 > max_chars:
            break
        picked.append(sentence)
        length += len(sentence) + 1
    summary = " ".join(picked)
    if len(summary) > max_chars:
        summary = summary[: max_chars - 1].rstrip() + "…"
    return summary
