"""Keyword-overlap baseline. Owner: M2 (B-04).

The simplest of the five methods B-08 compares: how much of the job posting's
own vocabulary shows up anywhere in the resume text, with no notion of meaning
or synonymy at all. It is expected to lose to the semantic methods on
paraphrased postings and is kept precisely so that comparison is honest.

Common interface with `tfidf.py`/`bi_encoder.py`: `score(profile, job) -> float`
in `[0, 1]`, deterministic for the same two documents.
"""

from __future__ import annotations

from app.contracts.models import CandidateProfile, JobPosting
from app.modules.matching.text import job_text, profile_text, tokenize


def score(profile: CandidateProfile, job: JobPosting) -> float:
    job_tokens = set(tokenize(job_text(job)))
    if not job_tokens:
        return 0.0
    resume_tokens = set(tokenize(profile_text(profile)))
    return len(job_tokens & resume_tokens) / len(job_tokens)
