"""Sentence-embedding baseline. Owner: M2 (B-04).

Embeds the resume and job text through the shared `EmbeddingClient` (local
deterministic hash in tests/CI, SageMaker in deployment — see
`app.core.inference`) and takes their cosine similarity. This is the live
semantic component `scoring.py`'s `Matcher` uses as `S`: it needs no
precomputed, persisted vector (that is B-03's job for stored, batch retrieval),
just the two texts at match time.

Common interface with `keyword.py`/`tfidf.py`: returns a float in `[0, 1]`.
Cosine is clamped to zero rather than allowed negative, per plan.md's scoring
section — a negative similarity is not "half a match".
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from app.contracts.models import CandidateProfile, JobPosting
from app.core.inference import EmbeddingClient
from app.modules.matching.text import job_text, profile_text


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError("Vectors must share the same dimensionality to compare.")
    numerator = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return max(0.0, min(1.0, numerator / (norm_a * norm_b)))


def score(profile: CandidateProfile, job: JobPosting, embedding_client: EmbeddingClient) -> float:
    batch = embedding_client.embed([profile_text(profile), job_text(job)])
    resume_vector, job_vector = batch.vectors
    return cosine(resume_vector, job_vector)
