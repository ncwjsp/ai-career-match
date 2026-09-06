"""A-01 errors; messages never include filenames, document text or parser internals."""

from enum import StrEnum

from app.contracts.models import ErrorDetail


class ErrorCode(StrEnum):
    EMPTY_FILE = "EMPTY_FILE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    FILE_TYPE_MISMATCH = "FILE_TYPE_MISMATCH"
    UNSUPPORTED_WORD_CONTAINER = "UNSUPPORTED_WORD_CONTAINER"
    ENCRYPTED_DOCUMENT = "ENCRYPTED_DOCUMENT"
    CORRUPT_DOCUMENT = "CORRUPT_DOCUMENT"
    UNSAFE_DOCUMENT = "UNSAFE_DOCUMENT"
    NO_EXTRACTABLE_TEXT = "NO_EXTRACTABLE_TEXT"
    EXTRACTION_LIMIT_EXCEEDED = "EXTRACTION_LIMIT_EXCEEDED"
    EXTRACTOR_UNAVAILABLE = "EXTRACTOR_UNAVAILABLE"


MESSAGES = {
    ErrorCode.EMPTY_FILE: "The file is empty. Upload a PDF or DOCX containing selectable text.",
    ErrorCode.FILE_TOO_LARGE: "The file exceeds the upload limit. Export a smaller PDF or DOCX.",
    ErrorCode.UNSUPPORTED_FORMAT: "Use PDF or DOCX. Legacy DOC, DOCM and images are not supported.",
    ErrorCode.FILE_TYPE_MISMATCH: (
        "The file contents, extension or declared type disagree. Re-export as PDF or DOCX; "
        "renaming an extension does not convert a file."
    ),
    ErrorCode.UNSUPPORTED_WORD_CONTAINER: (
        "This Word container is encrypted or legacy format. Open it in Word and save "
        "an unencrypted DOCX copy."
    ),
    ErrorCode.ENCRYPTED_DOCUMENT: (
        "Password-protected PDFs are not supported. Export an unencrypted copy."
    ),
    ErrorCode.CORRUPT_DOCUMENT: (
        "The document could not be read reliably. Open it in its original application "
        "and export a new PDF or DOCX."
    ),
    ErrorCode.UNSAFE_DOCUMENT: (
        "The Word package contains unsupported or unsafe structures. Export a plain DOCX copy."
    ),
    ErrorCode.NO_EXTRACTABLE_TEXT: (
        "No readable text was found. Export a document with selectable text. "
        "Scanned or image-only documents require OCR, which is not available yet."
    ),
    ErrorCode.EXTRACTION_LIMIT_EXCEEDED: (
        "The document exceeds extraction limits. Reduce its pages, text or embedded content."
    ),
    ErrorCode.EXTRACTOR_UNAVAILABLE: (
        "A required extraction dependency is unavailable. Ask the maintainer to install "
        "the pinned A-01 requirements."
    ),
}


class ResumeExtractionError(Exception):
    def __init__(self, code: ErrorCode):
        self.code = code
        super().__init__(MESSAGES[code])

    def as_detail(self, request_id: str) -> ErrorDetail:
        return ErrorDetail(
            code=self.code.value, message=str(self), retryable=False, request_id=request_id
        )
