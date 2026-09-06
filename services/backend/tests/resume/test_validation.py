from dataclasses import replace
from io import BytesIO
from zipfile import ZipFile

import pytest

from app.modules.resume.errors import ErrorCode, ResumeExtractionError
from app.modules.resume.extraction import extract_resume
from app.modules.resume.types import ExtractionLimits

IDENTITY = {"document_id": "resume-synthetic", "document_version": 1}


@pytest.mark.parametrize(
    "data,filename,mime,code",
    [
        (b"", "resume.pdf", None, ErrorCode.EMPTY_FILE),
        (b"fake", "resume.doc", None, ErrorCode.UNSUPPORTED_FORMAT),
        (b"fake", "resume.docm", None, ErrorCode.UNSUPPORTED_FORMAT),
        (b"fake", "resume", None, ErrorCode.UNSUPPORTED_FORMAT),
        (b"not a PDF", "resume.pdf", None, ErrorCode.FILE_TYPE_MISMATCH),
        (b"%PDF-1.7", "resume.docx", None, ErrorCode.FILE_TYPE_MISMATCH),
        (b"%PDF-1.7", "resume.pdf", "image/png", ErrorCode.FILE_TYPE_MISMATCH),
        (
            bytes.fromhex("D0CF11E0A1B11AE1"),
            "resume.docx",
            None,
            ErrorCode.UNSUPPORTED_WORD_CONTAINER,
        ),
    ],
)
def test_type_validation_uses_contents_extension_and_mime(data, filename, mime, code):
    with pytest.raises(ResumeExtractionError) as caught:
        extract_resume(data, filename=filename, media_type=mime, **IDENTITY)
    assert caught.value.code == code


def test_upload_limit_runs_before_pdf_library(pdf_factory):
    data = pdf_factory()
    with pytest.raises(ResumeExtractionError) as caught:
        extract_resume(
            data,
            filename="resume.pdf",
            **IDENTITY,
            limits=replace(ExtractionLimits(), max_file_bytes=len(data) - 1),
        )
    assert caught.value.code == ErrorCode.FILE_TOO_LARGE


def test_generic_mime_and_exact_size_are_allowed(pdf_factory):
    data = pdf_factory()
    result = extract_resume(
        data,
        filename="resume.pdf",
        media_type="application/octet-stream",
        limits=replace(ExtractionLimits(), max_file_bytes=len(data)),
        **IDENTITY,
    )
    assert result.media_type == "application/pdf"


@pytest.mark.parametrize(
    "values",
    [
        {"max_file_bytes": 0},
        {"max_pdf_pages": -1},
        {"max_text_chars": True},
        {"max_xml_bytes": 1.5},
    ],
)
def test_limits_must_be_positive_integers(values):
    with pytest.raises(ValueError):
        ExtractionLimits(**values)


@pytest.mark.parametrize(
    "member",
    ["../escape", "/absolute", "bad\\path", "C:/path", "WORD/DOCUMENT.XML", "word/vbaProject.bin"],
)
def test_unsafe_zip_members_are_rejected_without_writes(
    docx_factory, member, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    data = docx_factory(extras={member: "synthetic"})
    if member == "bad\\path":
        # ZipFile normalizes Windows separators while writing; restore the hostile filename.
        data = data.replace(b"bad/path", b"bad\\path")
    with pytest.raises(ResumeExtractionError) as caught:
        extract_resume(data, filename="resume.docx", **IDENTITY)
    assert caught.value.code == ErrorCode.UNSAFE_DOCUMENT
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "limits",
    [
        replace(ExtractionLimits(), max_zip_members=2),
        replace(ExtractionLimits(), max_zip_expanded_bytes=10),
        replace(ExtractionLimits(), max_xml_bytes=10),
        replace(ExtractionLimits(), max_zip_ratio=1),
        replace(ExtractionLimits(), max_text_chars=5),
    ],
)
def test_docx_expansion_and_text_limits(docx_factory, limits):
    with pytest.raises(ResumeExtractionError) as caught:
        extract_resume(docx_factory(), filename="resume.docx", limits=limits, **IDENTITY)
    assert caught.value.code == ErrorCode.EXTRACTION_LIMIT_EXCEEDED


@pytest.mark.parametrize("part", ["[Content_Types].xml", "_rels/.rels", "word/document.xml"])
def test_missing_required_docx_part(docx_factory, part):
    with pytest.raises(ResumeExtractionError) as caught:
        extract_resume(docx_factory(replacements={part: None}), filename="resume.docx", **IDENTITY)
    assert caught.value.code == ErrorCode.CORRUPT_DOCUMENT


def test_arbitrary_zip_is_not_a_docx():
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("hello.txt", "not a Word document")
    with pytest.raises(ResumeExtractionError) as caught:
        extract_resume(output.getvalue(), filename="resume.docx", **IDENTITY)
    assert caught.value.code == ErrorCode.CORRUPT_DOCUMENT


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16"])
def test_docx_dtd_entities_rejected_including_utf16(docx_factory, encoding):
    xml = (
        f'<?xml version="1.0" encoding="{encoding}"?>'
        '<!DOCTYPE document [<!ENTITY secret SYSTEM "file:///private/synthetic.txt">]>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>&secret;</w:t></w:r></w:p></w:body></w:document>"
    )
    with pytest.raises(ResumeExtractionError) as caught:
        extract_resume(
            docx_factory(replacements={"word/document.xml": xml.encode(encoding)}),
            filename="resume.docx",
            **IDENTITY,
        )
    assert caught.value.code == ErrorCode.UNSAFE_DOCUMENT
    assert "private" not in str(caught.value)


def test_malformed_xml_is_a_readable_error(docx_factory):
    with pytest.raises(ResumeExtractionError) as caught:
        extract_resume(
            docx_factory(replacements={"word/document.xml": "<broken>"}),
            filename="resume.docx",
            **IDENTITY,
        )
    assert caught.value.code == ErrorCode.CORRUPT_DOCUMENT


def test_external_header_is_never_fetched(docx_factory, monkeypatch):
    def forbid_network(*args, **kwargs):
        pytest.fail("An extractor must not make network requests")

    monkeypatch.setattr("urllib.request.urlopen", forbid_network)
    rels = (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="header" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" '
        'TargetMode="External" Target="https://example.test/header.xml"/></Relationships>'
    )
    with pytest.raises(ResumeExtractionError) as caught:
        extract_resume(
            docx_factory(
                header="Synthetic",
                replacements={
                    "word/_rels/document.xml.rels": rels,
                },
            ),
            filename="resume.docx",
            **IDENTITY,
        )
    assert caught.value.code == ErrorCode.UNSAFE_DOCUMENT


def test_pdf_dependency_failure_has_an_actionable_error(pdf_factory, monkeypatch):
    import builtins

    data = pdf_factory()
    original = builtins.__import__

    def missing(name, *args, **kwargs):
        if name == "pypdf":
            raise ImportError("simulated missing optional dependency")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing)
    with pytest.raises(ResumeExtractionError) as caught:
        extract_resume(data, filename="resume.pdf", **IDENTITY)
    assert caught.value.code == ErrorCode.EXTRACTOR_UNAVAILABLE


def test_zip_nul_filename_cannot_hide_a_member(docx_factory):
    data = docx_factory(extras={"bad-path": "synthetic"}).replace(b"bad-path", b"bad\x00path")
    with pytest.raises(ResumeExtractionError) as caught:
        extract_resume(data, filename="resume.docx", **IDENTITY)
    assert caught.value.code == ErrorCode.UNSAFE_DOCUMENT


def test_truncated_zip_is_a_readable_error(docx_factory):
    with pytest.raises(ResumeExtractionError) as caught:
        extract_resume(docx_factory()[:-40], filename="resume.docx", **IDENTITY)
    assert caught.value.code == ErrorCode.CORRUPT_DOCUMENT


def test_missing_referenced_header_is_not_silently_omitted(docx_factory):
    with pytest.raises(ResumeExtractionError) as caught:
        extract_resume(
            docx_factory(header="Synthetic", replacements={"word/header1.xml": None}),
            filename="resume.docx",
            **IDENTITY,
        )
    assert caught.value.code == ErrorCode.CORRUPT_DOCUMENT


def test_content_type_override_must_be_a_normal_word_document(docx_factory):
    content_types = (
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.ms-word.document.macroEnabled.main+xml"/></Types>'
    )
    with pytest.raises(ResumeExtractionError) as caught:
        extract_resume(
            docx_factory(replacements={"[Content_Types].xml": content_types}),
            filename="resume.docx",
            **IDENTITY,
        )
    assert caught.value.code == ErrorCode.FILE_TYPE_MISMATCH
