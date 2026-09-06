"""Internal extraction values; canonical public text/evidence DTOs are reused."""

from dataclasses import dataclass, fields
from enum import StrEnum

from app.contracts.models import ProcessedText


class ResumeFormat(StrEnum):
    PDF = "pdf"
    DOCX = "docx"


MEDIA_TYPES = {
    ResumeFormat.PDF: "application/pdf",
    ResumeFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
EXTRACTION_VERSION = "resume-extraction-v1"


@dataclass(frozen=True)
class ExtractionLimits:
    # Provisional engineering defaults for M3/SET-03 review, not source requirements.
    max_file_bytes: int = 10 * 1024 * 1024
    max_pdf_pages: int = 30
    max_pdf_stream_bytes: int = 8 * 1024 * 1024
    max_text_chars: int = 200_000
    max_zip_members: int = 1000
    max_zip_expanded_bytes: int = 32 * 1024 * 1024
    max_xml_bytes: int = 8 * 1024 * 1024
    max_zip_ratio: int = 200

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{field.name} must be a positive integer")


@dataclass(frozen=True)
class TextBlock:
    text: str
    locator: str
    page: int | None = None


@dataclass(frozen=True)
class ExtractionResult:
    content: ProcessedText
    media_type: str
    page_count: int | None
    warnings: tuple[str, ...]
