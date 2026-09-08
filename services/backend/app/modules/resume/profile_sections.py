"""Explicit English section/entry patterns; unknown prose is not invented data."""

import re
from dataclasses import dataclass

from app.contracts.models import EvidenceRef, ProcessedText
from app.nlp.skills import ALIASES

HEADINGS = {
    "skills": "skills",
    "technical skills": "skills",
    "core skills": "skills",
    "experience": "experience",
    "work experience": "experience",
    "professional experience": "experience",
    "employment history": "experience",
    "education": "education",
    "academic background": "education",
    "projects": "projects",
    "personal projects": "projects",
    "academic projects": "projects",
    "summary": "summary",
    "professional summary": "summary",
    "profile": "summary",
    "objective": "ignore",
    "career objective": "ignore",
    "references": "ignore",
    "job description": "ignore",
    "requirements": "ignore",
    "interests": "ignore",
    "certifications": "ignore",
    "languages": "ignore",
    "awards": "ignore",
}
ROLE = re.compile(
    r"\b(?:engineer|developer|analyst|scientist|manager|designer|consultant|intern|"
    r"researcher|assistant|architect|technician|specialist|administrator|coordinator|"
    r"director|officer|lecturer|teacher|lead)\b",
    re.I,
)
DEGREE = re.compile(
    r"\b(?:bachelor|master|doctor|ph\.?d|b\.?sc|m\.?sc|b\.?s|m\.?s|"
    r"b\.?eng|m\.?eng|mba|diploma|associate)\b",
    re.I,
)
INSTITUTION = re.compile(r"\b(?:university|college|institute|school)\b", re.I)


@dataclass(frozen=True)
class Line:
    text: str
    start: int
    end: int
    section: str


def lines(source: ProcessedText) -> list[Line]:
    result = []
    section = "unknown"
    for match in re.finditer(r"[^\r\n]+", source.text):
        text = match[0].strip()
        if not text:
            continue
        heading = text.rstrip(":").casefold()
        if heading in HEADINGS:
            section = HEADINGS[heading]
            continue
        inline = text.split(":", 1)
        inline_section = HEADINGS.get(inline[0].casefold()) if len(inline) == 2 else None
        if inline_section:
            section = inline_section
            body = inline[1].strip()
            if body:
                start = match.start() + match[0].index(":") + 1
                start += len(inline[1]) - len(inline[1].lstrip())
                result.append(Line(body, start, start + len(body), section))
            continue
        # Treat unrecognized uppercase headings as an unknown section boundary.
        if text.isupper() and len(text.split()) > 1 and not any(c in text for c in "|,;"):
            skill_words = {a.casefold() for variants in ALIASES.values() for a in variants}
            if (
                len(text) < 55
                and not ROLE.search(text)
                and not DEGREE.search(text)
                and not any(word.casefold() in skill_words for word in text.split())
            ):
                section = "unknown"
                continue
        start = match.start() + len(match[0]) - len(match[0].lstrip())
        result.append(Line(text, start, start + len(text), section))
    return result


def refs(source: ProcessedText, start: int, end: int) -> list[EvidenceRef]:
    result = []
    for ref in source.evidence:
        lo, hi = max(start, ref.start), min(end, ref.end)
        if lo < hi:
            result.append(
                ref.model_copy(
                    update={
                        "start": lo,
                        "end": hi,
                        "excerpt": source.text[lo:hi],
                    }
                )
            )
    return result


def role_header(text: str) -> tuple[str | None, str | None] | None:
    cleaned = text.strip()
    if cleaned.startswith(("-", "•", "*")):
        return None
    labelled = re.match(r"^(?:job title|role|position):\s*(.+)$", cleaned, re.I)
    if labelled:
        return labelled[1].strip(), None
    parts = re.split(r"\s+(?:at|@)\s+|\s*[|]\s*|\s+[–—-]\s+", cleaned, maxsplit=1)
    title = parts[0].strip()
    # Do not convert a task sentence or desired role into a job title.
    if (
        len(title.split()) > 9
        or not ROLE.search(title)
        or re.match(
            r"^(?:built|developed|worked|assisted|seeking|aspiring|want|helped)\b", title, re.I
        )
    ):
        return None
    organization = parts[1].strip() if len(parts) > 1 else None
    return title, organization
