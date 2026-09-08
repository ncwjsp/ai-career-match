"""A-03 conservative profile construction from canonical A-02 annotations."""

import re
from collections import defaultdict
from datetime import date, datetime

from app.contracts.models import CandidateProfile, Education, Experience, Project, SkillEvidence
from app.modules.resume.profile_dates import RANGE, extract_dates, union_years
from app.modules.resume.profile_sections import (
    DEGREE,
    INSTITUTION,
    Line,
    lines,
    refs,
    role_header,
)
from app.modules.resume.summary import summarize_profile
from app.nlp.text import evidence_for, normalize_text, validate_source
from app.nlp.types import NlpAnalysis

PROFILE_EXTRACTION_VERSION = "resume-profile-rules-v1"


def _experiences(source, rows: list[Line], warnings: list[str], org_spans: set) -> list[Experience]:
    entries = []
    current = []
    title = company = None

    def finish():
        if not current:
            return
        text = "\n".join(row.text for row in current)
        start, end, valid = extract_dates(text)
        if not valid:
            warnings.append("EXPERIENCE_DATES_UNKNOWN")
        entries.append(
            Experience(
                job_title=title,
                organization=company,
                start_date=start,
                end_date=end,
                evidence=[ref for row in current for ref in refs(source, row.start, row.end)],
            )
        )

    for row in rows:
        if row.section != "experience":
            finish()
            current = []
            title = company = None
            continue
        header_text = RANGE.sub("", row.text).strip(" |,;–—-")
        header = role_header(header_text)
        if header:
            finish()
            current = [row]
            title, company = header
        elif re.match(r"^(?:company|organization|employer):", row.text, re.I):
            value = row.text.split(":", 1)[1].strip() or None
            if company is not None:
                finish()
                current = []
                title = None
            company = value
            current.append(row)
        elif current:
            if company is None and (row.start, row.end) in org_spans:
                company = row.text
            current.append(row)
        elif RANGE.search(row.text):
            current = [row]  # Keep evidenced dates with null title/company.
    finish()
    return entries


def _education(source, rows: list[Line], org_spans: set) -> list[Education]:
    result = []
    qualification = institution = None
    evidence = []

    def finish():
        if evidence and (qualification or institution):
            result.append(
                Education(
                    qualification=qualification,
                    institution=institution,
                    evidence=list(evidence),
                )
            )

    for row in rows:
        if row.section != "education":
            finish()
            qualification = institution = None
            evidence = []
            continue
        pieces = [p.strip() for p in re.split(r"\s*[|]\s*|\s+[–—]\s+|\s+at\s+", row.text)]
        q = next((p for p in pieces if DEGREE.search(p)), None)
        i = next((p for p in pieces if INSTITUTION.search(p) and not DEGREE.search(p)), None)
        if i is None and q is None and (row.start, row.end) in org_spans:
            i = row.text
        if row.text.lower().startswith("qualification:"):
            q = row.text.split(":", 1)[1].strip() or None
        if row.text.lower().startswith("institution:"):
            i = row.text.split(":", 1)[1].strip() or None
        if q and qualification or i and institution:
            finish()
            qualification = institution = None
            evidence = []
        if q or i:
            qualification = q or qualification
            institution = i or institution
            evidence.extend(refs(source, row.start, row.end))
    finish()
    return result


def _projects(source, rows: list[Line], warnings: list[str]) -> list[Project]:
    result = []
    name = None
    body = []
    evidence = []

    def finish():
        if name and body:
            result.append(Project(name=name, description="\n".join(body), evidence=list(evidence)))
        elif name:
            warnings.append("PROJECT_DESCRIPTION_UNKNOWN")

    for row in rows:
        if row.section != "projects":
            finish()
            name, body, evidence = None, [], []
            continue
        explicit = re.match(r"^(?:project|project name):\s*(.+)$", row.text, re.I)
        inline = re.match(r"^([^:|]{1,80})\s*[:|]\s*(.+)$", row.text)
        if explicit:
            finish()
            parts = re.split(r"\s*[|]\s*", explicit[1], maxsplit=1)
            name, body = parts[0], parts[1:]
            evidence = refs(source, row.start, row.end)
        elif inline and not row.text.startswith(("-", "•", "*")):
            finish()
            name, body = inline[1].strip(), [inline[2].strip()]
            evidence = refs(source, row.start, row.end)
        elif name is None and len(row.text.split()) <= 8 and not row.text.endswith("."):
            name = row.text
            evidence = refs(source, row.start, row.end)
        elif name:
            body.append(row.text)
            evidence.extend(refs(source, row.start, row.end))
    finish()
    return result


def _skills(analysis: NlpAnalysis, rows: list[Line], warnings: list[str]) -> list[SkillEvidence]:
    grouped = defaultdict(list)
    negated = set()
    for mention in analysis.skills:
        if not (0 <= mention.start < mention.end <= len(analysis.normalized.text)):
            raise ValueError("Invalid skill annotation span.")
        if analysis.normalized.text[mention.start : mention.end] != mention.text:
            raise ValueError("Skill annotation does not match normalized text.")
        expected = evidence_for(analysis.source, analysis.normalized, mention.start, mention.end)
        if tuple(mention.evidence) != expected:
            raise ValueError("Skill annotation evidence does not match its source.")
        lo, hi = analysis.normalized.source_span(mention.start, mention.end)
        contexts = [row for row in rows if row.start < hi and row.end > lo]
        if not contexts or any(
            row.section not in {"skills", "experience", "projects", "summary"} for row in contexts
        ):
            warnings.append("SKILL_CONTEXT_UNCONFIRMED")
            continue
        if mention.assertion not in {"mentioned", "negated", "uncertain"}:
            raise ValueError("Unknown skill assertion.")
        if mention.assertion == "negated":
            negated.add(mention.canonical)
        if mention.assertion != "mentioned":
            warnings.append("SKILL_" + mention.assertion.upper() + "_EXCLUDED")
            continue
        grouped[mention.canonical].extend(ref.model_copy(deep=True) for ref in mention.evidence)
    if negated.intersection(grouped):
        warnings.append("CONFLICTING_SKILL_EVIDENCE_EXCLUDED")
    return [
        SkillEvidence(name=name, evidence=evidence)
        for name, evidence in grouped.items()
        if name not in negated
    ]


def build_candidate_profile(
    analysis: NlpAnalysis,
    *,
    candidate_id: str,
    resume_id: str,
    profile_version: int,
    matching_enabled: bool,
    expires_at: datetime,
    as_of: date,
    extraction_warnings: tuple[str, ...] = (),
) -> CandidateProfile:
    """Lifecycle fields come from the caller; this function performs no I/O.

    as_of is an explicit reference date for ongoing employment. No implicit wall
    clock, default consent, generated identifiers, database write or match event.
    """
    if type(as_of) is not date:
        raise ValueError("as_of must be a date, not a timestamp.")
    if analysis.language != "en":
        raise ValueError("A-03 supports English annotations only.")
    validate_source(analysis.source, 200_000)
    if analysis.normalized != normalize_text(analysis.source.text):
        raise ValueError("Normalized text/map does not match the source snapshot.")
    if any(ref.document_id != resume_id for ref in analysis.source.evidence):
        raise ValueError("Resume ID must match source evidence identity.")
    warnings = [*extraction_warnings, *analysis.warnings, "PROFILE_EXTRACTION_RULE_BASED"]
    rows = lines(analysis.source)
    # NER only helps within an explicit section; a random ORG is not employment.
    org_spans = set()
    for entity in analysis.entities:
        if entity.label != "ORG":
            continue
        if not (0 <= entity.start < entity.end <= len(analysis.normalized.text)):
            raise ValueError("Invalid entity annotation span.")
        if analysis.normalized.text[entity.start : entity.end] != entity.text:
            raise ValueError("Entity annotation does not match normalized text.")
        expected = evidence_for(analysis.source, analysis.normalized, entity.start, entity.end)
        if tuple(entity.evidence) != expected:
            raise ValueError("Entity evidence does not match its source.")
        org_spans.add(analysis.normalized.source_span(entity.start, entity.end))
    experience = _experiences(analysis.source, rows, warnings, org_spans)
    years = union_years([(e.start_date, e.end_date) for e in experience], as_of)
    if experience and years is None:
        warnings.append("EXPERIENCE_TOTAL_UNKNOWN")
    if any(e.end_date == "present" for e in experience):
        warnings.append("EXPERIENCE_PRESENT_USES_AS_OF_MONTH")
    education = _education(analysis.source, rows, org_spans)
    projects = _projects(analysis.source, rows, warnings)
    skills = _skills(analysis, rows, warnings)
    if not any((skills, experience, education, projects)):
        warnings.append("NO_SUPPORTED_PROFILE_FIELDS")
    profile = CandidateProfile(
        candidate_id=candidate_id,
        resume_id=resume_id,
        profile_version=profile_version,
        language=analysis.language,
        summary=None,
        skills=skills,
        education=education,
        job_titles=list(dict.fromkeys(e.job_title for e in experience if e.job_title)),
        organizations=list(dict.fromkeys(e.organization for e in experience if e.organization)),
        experience=experience,
        estimated_experience_years=years,
        projects=projects,
        evidence=[ref.model_copy(deep=True) for ref in analysis.source.evidence],
        extraction_warnings=list(dict.fromkeys(warnings)),
        matching_enabled=matching_enabled,
        expires_at=expires_at,
    )
    profile.summary = summarize_profile(profile)
    return profile
