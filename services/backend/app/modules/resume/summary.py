"""Deterministic summary of extracted fields; no unsupported LLM claims."""

from app.contracts.models import CandidateProfile


def summarize_profile(profile: CandidateProfile) -> str | None:
    parts = []
    if profile.job_titles:
        parts.append("Reported roles: " + "; ".join(profile.job_titles[:3]) + ".")
    if profile.skills:
        parts.append("Resume lists skills: " + ", ".join(s.name for s in profile.skills[:8]) + ".")
    qualifications = [e.qualification for e in profile.education if e.qualification]
    if qualifications:
        parts.append("Reported education: " + "; ".join(qualifications[:2]) + ".")
    institutions = [e.institution for e in profile.education if e.institution]
    if institutions:
        parts.append("Reported institutions: " + "; ".join(institutions[:2]) + ".")
    if profile.projects:
        parts.append("Listed projects: " + "; ".join(p.name for p in profile.projects[:3]) + ".")
    if profile.estimated_experience_years is not None:
        parts.append(
            f"Dated employment spans approximately {profile.estimated_experience_years:g} "
            "non-overlapping years (month-based estimate)."
        )
    return " ".join(parts) or None
