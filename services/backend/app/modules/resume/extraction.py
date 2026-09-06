"""A-01 entry point. This returns text/evidence, not a CandidateProfile or match."""

from pydantic import TypeAdapter

from app.contracts.models import Identifier, Version
from app.modules.resume.parsers.common import assemble_text
from app.modules.resume.parsers.docx import extract_docx
from app.modules.resume.parsers.pdf import extract_pdf
from app.modules.resume.types import MEDIA_TYPES, ExtractionLimits, ExtractionResult, ResumeFormat
from app.modules.resume.validation import validate_upload


def extract_resume(
    data: bytes,
    *,
    filename: str,
    document_id: str,
    document_version: int,
    media_type: str | None = None,
    limits: ExtractionLimits | None = None,
) -> ExtractionResult:
    # Invalid identity is a caller/contract error, not an unreadable-file error.
    document_id = TypeAdapter(Identifier).validate_python(document_id)
    document_version = TypeAdapter(Version).validate_python(document_version)
    policy = limits or ExtractionLimits()
    kind = validate_upload(data, filename, media_type, policy)
    if kind == ResumeFormat.PDF:
        blocks, page_count, warnings = extract_pdf(data, policy)
    else:
        blocks, warnings = extract_docx(data, policy)
        page_count = None
    content = assemble_text(blocks, document_id, document_version, policy, warnings)
    return ExtractionResult(content, MEDIA_TYPES[kind], page_count, tuple(warnings))
