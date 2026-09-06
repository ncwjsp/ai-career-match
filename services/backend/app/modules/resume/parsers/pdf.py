"""Selectable-text PDF extraction. OCR and hard resource isolation belong elsewhere."""

from io import BytesIO
from zlib import error as DecompressionError

from app.modules.resume.errors import ErrorCode, ResumeExtractionError
from app.modules.resume.types import ExtractionLimits, TextBlock


def extract_pdf(data: bytes, limits: ExtractionLimits) -> tuple[list[TextBlock], int, list[str]]:
    try:
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
    except ImportError:
        raise ResumeExtractionError(ErrorCode.EXTRACTOR_UNAVAILABLE) from None
    blocks: list[TextBlock] = []
    warnings = ["PDF_READING_ORDER_REQUIRES_REVIEW"]
    try:
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise ResumeExtractionError(ErrorCode.ENCRYPTED_DOCUMENT)
        page_count = len(reader.pages)
        if page_count > limits.max_pdf_pages:
            raise ResumeExtractionError(ErrorCode.EXTRACTION_LIMIT_EXCEEDED)
        extracted_chars = 0
        for number, page in enumerate(reader.pages, start=1):
            content = page.get_contents()
            # This is a post-decompression bound, not a process memory limit.
            if content is not None and len(content.get_data()) > limits.max_pdf_stream_bytes:
                raise ResumeExtractionError(ErrorCode.EXTRACTION_LIMIT_EXCEEDED)
            text = (
                page.extract_text(
                    extraction_mode="layout",
                    layout_mode_space_vertically=False,
                    layout_mode_strip_rotated=False,
                )
                or ""
            )
            extracted_chars += len(text)
            if extracted_chars > limits.max_text_chars:
                raise ResumeExtractionError(ErrorCode.EXTRACTION_LIMIT_EXCEEDED)
            if not text.strip():
                warnings.append(f"PDF_PAGE_WITHOUT_TEXT:{number}")
            blocks.append(TextBlock(text, f"pdf/page[{number}]", number))
    except ResumeExtractionError:
        raise
    except (
        DecompressionError,
        EOFError,
        NotImplementedError,
        PyPdfError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        RecursionError,
        OverflowError,
    ):
        raise ResumeExtractionError(ErrorCode.CORRUPT_DOCUMENT) from None
    return blocks, page_count, warnings
