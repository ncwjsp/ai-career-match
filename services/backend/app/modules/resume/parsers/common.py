from collections.abc import Iterable

from app.contracts.models import EvidenceRef, ProcessedText
from app.modules.resume.errors import ErrorCode, ResumeExtractionError
from app.modules.resume.types import EXTRACTION_VERSION, ExtractionLimits, TextBlock


def assemble_text(
    blocks: Iterable[TextBlock],
    document_id: str,
    document_version: int,
    limits: ExtractionLimits,
    warnings: list[str],
) -> ProcessedText:
    parts: list[str] = []
    evidence: list[EvidenceRef] = []
    length = 0
    for block in blocks:
        text = block.text.replace("\r\n", "\n").replace("\r", "\n")
        cleaned = "".join(c for c in text if ord(c) >= 32 or c in "\n\t")
        if cleaned != text and "CONTROL_CHARACTERS_REMOVED" not in warnings:
            warnings.append("CONTROL_CHARACTERS_REMOVED")
        cleaned = cleaned.strip()
        if not cleaned:
            continue
        start = length + (2 if parts else 0)
        end = start + len(cleaned)
        if end > limits.max_text_chars:
            raise ResumeExtractionError(ErrorCode.EXTRACTION_LIMIT_EXCEEDED)
        evidence.append(
            EvidenceRef(
                document_id=document_id,
                document_version=document_version,
                chunk_id=f"chunk-{len(evidence) + 1:04d}",
                page=block.page,
                section=block.locator,
                start=start,
                end=end,
                excerpt=cleaned,
            )
        )
        parts.append(cleaned)
        length = end
    if not parts:
        raise ResumeExtractionError(ErrorCode.NO_EXTRACTABLE_TEXT)
    return ProcessedText(
        text="\n\n".join(parts),
        language=None,
        evidence=evidence,
        preprocessing_version=EXTRACTION_VERSION,
    )
