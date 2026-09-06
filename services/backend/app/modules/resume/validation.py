"""Validate upload bytes before invoking a document parser; never opens a filename."""

from app.modules.resume.errors import ErrorCode, ResumeExtractionError
from app.modules.resume.types import MEDIA_TYPES, ExtractionLimits, ResumeFormat

OLE_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")


def validate_upload(
    data: bytes, filename: str, media_type: str | None, limits: ExtractionLimits
) -> ResumeFormat:
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    if not data:
        raise ResumeExtractionError(ErrorCode.EMPTY_FILE)
    if len(data) > limits.max_file_bytes:
        raise ResumeExtractionError(ErrorCode.FILE_TOO_LARGE)
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    try:
        kind = ResumeFormat(suffix)
    except ValueError:
        raise ResumeExtractionError(ErrorCode.UNSUPPORTED_FORMAT) from None
    declared = (media_type or "").partition(";")[0].strip().lower()
    if declared not in ("", "application/octet-stream", MEDIA_TYPES[kind]):
        raise ResumeExtractionError(ErrorCode.FILE_TYPE_MISMATCH)
    if kind == ResumeFormat.DOCX and data.startswith(OLE_SIGNATURE):
        raise ResumeExtractionError(ErrorCode.UNSUPPORTED_WORD_CONTAINER)
    has_pdf_header = data.startswith(b"%PDF-")
    has_zip_header = data[:4] in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
    if (kind == ResumeFormat.PDF and not has_pdf_header) or (
        kind == ResumeFormat.DOCX and not has_zip_header
    ):
        raise ResumeExtractionError(ErrorCode.FILE_TYPE_MISMATCH)
    return kind
