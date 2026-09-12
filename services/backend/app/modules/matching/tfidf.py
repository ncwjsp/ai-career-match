"""TF-IDF + cosine baseline. Owner: M2 (B-04).

A pure-Python implementation (no numpy/scikit-learn: neither is an approved
shared dependency yet) using smoothed IDF, `idf(t) = ln((1+N)/(1+df(t))) + 1`,
so a term in every document still gets a small positive weight instead of
zero. `background` lets B-08's evaluation harness supply the frozen job
corpus for a more realistic document-frequency estimate; with none given, the
IDF is computed from just the one pair, which is enough to rank a single
candidate against a single job but not to compare rankings across a corpus.

Common interface with `keyword.py`/`bi_encoder.py`: `score(profile, job, ...)
-> float` in `[0, 1]`, deterministic for the same inputs.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence

from app.contracts.models import CandidateProfile, JobPosting
from app.modules.matching.text import job_text, profile_text, tokenize


def _tf(tokens: Sequence[str]) -> Counter[str]:
    return Counter(tokens)


def _idf(documents: Sequence[Sequence[str]]) -> dict[str, float]:
    n = len(documents)
    df: Counter[str] = Counter()
    for tokens in documents:
        df.update(set(tokens))
    return {term: math.log((1 + n) / (1 + count)) + 1 for term, count in df.items()}


def _tfidf_vector(tf: Counter[str], idf: dict[str, float]) -> dict[str, float]:
    return {term: count * idf.get(term, 0.0) for term, count in tf.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    shared = a.keys() & b.keys()
    numerator = sum(a[term] * b[term] for term in shared)
    norm_a = math.sqrt(sum(value * value for value in a.values()))
    norm_b = math.sqrt(sum(value * value for value in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return max(0.0, min(1.0, numerator / (norm_a * norm_b)))


def score(profile: CandidateProfile, job: JobPosting, *, background: Sequence[str] = ()) -> float:
    resume_tokens = tokenize(profile_text(profile))
    job_tokens = tokenize(job_text(job))
    if not resume_tokens or not job_tokens:
        return 0.0
    documents = [resume_tokens, job_tokens, *(tokenize(text) for text in background)]
    idf = _idf(documents)
    resume_vector = _tfidf_vector(_tf(resume_tokens), idf)
    job_vector = _tfidf_vector(_tf(job_tokens), idf)
    return _cosine(resume_vector, job_vector)
