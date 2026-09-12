"""Shared text extraction for the B-04 baselines. Owner: M2.

Each baseline method (keyword, TF-IDF, sentence embedding) needs one
representative text blob per side of a pair. Centralizing that here means all
three methods see the same input and a change to what counts as "the resume
text" or "the job text" does not have to be repeated three times.
"""

from __future__ import annotations

import re

from app.contracts.models import CandidateProfile, JobPosting


def profile_text(profile: CandidateProfile) -> str:
    """A resume's matchable text: summary, skills, titles, experience, projects."""
    parts: list[str] = []
    if profile.summary:
        parts.append(profile.summary)
    parts.extend(skill.name for skill in profile.skills)
    parts.extend(profile.job_titles)
    parts.extend(profile.organizations)
    for entry in profile.experience:
        if entry.job_title:
            parts.append(entry.job_title)
        if entry.organization:
            parts.append(entry.organization)
    for project in profile.projects:
        parts.append(project.name)
        parts.append(project.description)
    return " ".join(parts)


def job_text(job: JobPosting) -> str:
    """A posting's matchable text: title, company, description, requirements."""
    parts = [job.title, job.company, job.description]
    if job.summary:
        parts.append(job.summary)
    parts.extend(requirement.skill for requirement in job.requirements)
    parts.extend(job.other_requirements)
    return " ".join(parts)


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens. Keeps `c++`/`c#`/`node.js`-style tokens intact for
    the keyword baseline (exact alias handling belongs to `skills.py`), but a
    dot must be followed by another letter/digit to be part of the token — a
    plain sentence-ending period is never swallowed into the preceding word."""
    return re.findall(r"[a-zA-Z][a-zA-Z0-9+#]*(?:\.[a-zA-Z0-9+#]+)*", text.lower())
