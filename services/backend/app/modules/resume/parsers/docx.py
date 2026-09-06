"""Bounded DOCX package reads. No ZIP extraction, external fetches or Word execution."""

import posixpath
from collections.abc import Iterator
from io import BytesIO
from xml.etree.ElementTree import Element, ParseError
from zipfile import BadZipFile, ZipFile
from zlib import error as DecompressionError

from app.modules.resume.errors import ErrorCode, ResumeExtractionError
from app.modules.resume.types import ExtractionLimits, TextBlock

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
CT = "{http://schemas.openxmlformats.org/package/2006/content-types}"
OFFICE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
MAIN_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"


def _check_archive(archive: ZipFile, limits: ExtractionLimits) -> None:
    members = archive.infolist()
    if len(members) > limits.max_zip_members:
        raise ResumeExtractionError(ErrorCode.EXTRACTION_LIMIT_EXCEEDED)
    total = 0
    seen = set()
    for info in members:
        name = info.orig_filename
        if (
            name != info.filename
            or name.casefold() in seen
            or "\\" in name
            or name.startswith("/")
            or any(part in ("..", ".") for part in name.split("/"))
            or ":" in name
            or (info.external_attr >> 16) & 0o170000 == 0o120000
        ):
            raise ResumeExtractionError(ErrorCode.UNSAFE_DOCUMENT)
        seen.add(name.casefold())
        if info.flag_bits & 1:
            raise ResumeExtractionError(ErrorCode.UNSAFE_DOCUMENT)
        if name.lower().endswith("vbaproject.bin"):
            raise ResumeExtractionError(ErrorCode.UNSAFE_DOCUMENT)
        total += info.file_size
        if (
            total > limits.max_zip_expanded_bytes
            or info.file_size > max(info.compress_size, 1) * limits.max_zip_ratio
        ):
            raise ResumeExtractionError(ErrorCode.EXTRACTION_LIMIT_EXCEEDED)


def _read_xml(archive: ZipFile, name: str, limits: ExtractionLimits) -> Element:
    try:
        from defusedxml.common import DefusedXmlException
        from defusedxml.ElementTree import fromstring
    except ImportError:
        raise ResumeExtractionError(ErrorCode.EXTRACTOR_UNAVAILABLE) from None
    info = archive.getinfo(name)
    if info.file_size > limits.max_xml_bytes:
        raise ResumeExtractionError(ErrorCode.EXTRACTION_LIMIT_EXCEEDED)
    with archive.open(info) as stream:
        raw = stream.read(limits.max_xml_bytes + 1)
    if len(raw) > limits.max_xml_bytes:
        raise ResumeExtractionError(ErrorCode.EXTRACTION_LIMIT_EXCEEDED)
    try:
        return fromstring(raw, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except DefusedXmlException:
        raise ResumeExtractionError(ErrorCode.UNSAFE_DOCUMENT) from None


def _target(base: str, target: str) -> str:
    if not target or "\\" in target or ":" in target or target.startswith("/"):
        raise ResumeExtractionError(ErrorCode.UNSAFE_DOCUMENT)
    path = posixpath.normpath(posixpath.join(base, target))
    if path.startswith("../") or path in ("", ".", ".."):
        raise ResumeExtractionError(ErrorCode.UNSAFE_DOCUMENT)
    return path


def _relationships(root: Element) -> dict[str, Element]:
    if root.tag != REL + "Relationships":
        raise ResumeExtractionError(ErrorCode.CORRUPT_DOCUMENT)
    items = {}
    for item in root:
        if item.tag != REL + "Relationship":
            continue
        key = item.get("Id")
        if not key or key in items:
            raise ResumeExtractionError(ErrorCode.CORRUPT_DOCUMENT)
        items[key] = item
    return items


def _validate_package(archive: ZipFile, limits: ExtractionLimits) -> Element:
    types = _read_xml(archive, "[Content_Types].xml", limits)
    if types.tag != CT + "Types":
        raise ResumeExtractionError(ErrorCode.CORRUPT_DOCUMENT)
    overrides = [
        entry.get("ContentType")
        for entry in types
        if entry.tag == CT + "Override" and entry.get("PartName") == "/word/document.xml"
    ]
    if overrides != [MAIN_TYPE]:
        raise ResumeExtractionError(ErrorCode.FILE_TYPE_MISMATCH)
    if any("macroEnabled" in entry.get("ContentType", "") for entry in types):
        raise ResumeExtractionError(ErrorCode.UNSAFE_DOCUMENT)
    relationships = _relationships(_read_xml(archive, "_rels/.rels", limits))
    office = [
        entry
        for entry in relationships.values()
        if entry.get("Type") == OFFICE_REL + "officeDocument"
    ]
    if len(office) != 1:
        raise ResumeExtractionError(ErrorCode.FILE_TYPE_MISMATCH)
    if office[0].get("TargetMode") == "External":
        raise ResumeExtractionError(ErrorCode.UNSAFE_DOCUMENT)
    if _target("", office[0].get("Target", "")) != "word/document.xml":
        raise ResumeExtractionError(ErrorCode.FILE_TYPE_MISMATCH)
    document = _read_xml(archive, "word/document.xml", limits)
    if document.tag != W + "document" or document.find(W + "body") is None:
        raise ResumeExtractionError(ErrorCode.CORRUPT_DOCUMENT)
    return document


def _paragraph_text(element: Element) -> str:
    # Deleted revisions, fields' instructions and drawing/textbox contents are not resume text.
    if element.tag in (W + "del", W + "drawing", W + "pict", W + "instrText", W + "delText"):
        return ""
    if element.tag == W + "t":
        return element.text or ""
    if element.tag == W + "tab":
        return "\t"
    if element.tag in (W + "br", W + "cr"):
        return "\n"
    if element.tag == W + "noBreakHyphen":
        return "\u2011"
    if element.tag == W + "softHyphen":
        return "\u00ad"
    return "".join(_paragraph_text(child) for child in element)


def _blocks(root: Element, location: str) -> Iterator[TextBlock]:
    counts: dict[str, int] = {}
    for child in root:
        tag = child.tag.removeprefix(W)
        if tag in ("del", "drawing", "pict"):
            continue
        counts[tag] = counts.get(tag, 0) + 1
        locator = f"{location}/{tag}[{counts[tag]}]"
        if child.tag == W + "p":
            yield TextBlock(_paragraph_text(child), locator)
        else:
            # This preserves paragraph/table-row/cell order and handles inserted revisions.
            yield from _blocks(child, locator)


def _header_footer_parts(
    archive: ZipFile, document: Element, limits: ExtractionLimits
) -> tuple[list[tuple[str, Element]], list[tuple[str, Element]]]:
    refs = [
        node
        for node in document.iter()
        if node.tag in (W + "headerReference", W + "footerReference")
    ]
    if not refs:
        return [], []
    relations = _relationships(_read_xml(archive, "word/_rels/document.xml.rels", limits))
    headers: list[tuple[str, Element]] = []
    footers: list[tuple[str, Element]] = []
    seen = set()
    for ref in refs:
        relation = relations[ref.attrib[R + "id"]]
        kind = "header" if ref.tag == W + "headerReference" else "footer"
        if relation.get("Type") != OFFICE_REL + kind or relation.get("TargetMode") == "External":
            raise ResumeExtractionError(ErrorCode.UNSAFE_DOCUMENT)
        target = _target("word", relation.get("Target", ""))
        if not target.startswith("word/"):
            raise ResumeExtractionError(ErrorCode.UNSAFE_DOCUMENT)
        if target in seen:
            continue
        seen.add(target)
        part = _read_xml(archive, target, limits)
        if part.tag != W + ("hdr" if kind == "header" else "ftr"):
            raise ResumeExtractionError(ErrorCode.CORRUPT_DOCUMENT)
        (headers if kind == "header" else footers).append((target, part))
    return headers, footers


def extract_docx(data: bytes, limits: ExtractionLimits) -> tuple[list[TextBlock], list[str]]:
    warnings = ["DOCX_PAGINATION_UNAVAILABLE"]
    try:
        with ZipFile(BytesIO(data)) as archive:
            _check_archive(archive, limits)
            document = _validate_package(archive, limits)
            headers, footers = _header_footer_parts(archive, document, limits)
            roots = [*headers, ("word/document.xml", document.find(W + "body")), *footers]
            blocks = []
            length = 0
            for name, root in roots:
                if any(node.tag in (W + "drawing", W + "pict") for node in root.iter()):
                    warnings.append("DOCX_DRAWINGS_NOT_EXTRACTED")
                if any(node.tag == W + "tbl" for node in root.iter()):
                    warnings.append("DOCX_TABLES_READ_ROW_WISE")
                if any(node.tag in (W + "del", W + "ins") for node in root.iter()):
                    warnings.append("DOCX_TRACKED_CHANGES_CURRENT_TEXT_ONLY")
                if any(
                    node.tag in (W + "altChunk", W + "footnoteReference", W + "endnoteReference")
                    for node in root.iter()
                ):
                    warnings.append("DOCX_EMBEDDED_PARTS_OR_NOTES_NOT_EXTRACTED")
                for block in _blocks(root, name):
                    length += len(block.text)
                    if length > limits.max_text_chars:
                        raise ResumeExtractionError(ErrorCode.EXTRACTION_LIMIT_EXCEEDED)
                    blocks.append(block)
    except ResumeExtractionError:
        raise
    except (
        DecompressionError,
        EOFError,
        BadZipFile,
        KeyError,
        ValueError,
        ParseError,
        RuntimeError,
        RecursionError,
        NotImplementedError,
    ):
        raise ResumeExtractionError(ErrorCode.CORRUPT_DOCUMENT) from None
    return blocks, list(dict.fromkeys(warnings))
