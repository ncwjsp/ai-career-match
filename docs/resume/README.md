# A-01: resume validation and text extraction

Implemented on `feat/m1/a-01-resume-parsers`, based on main at `858c58b`.
Status: **In Progress** pending M3 dependency integration, review and merge.
The central plan is maintained by M3 and was not edited by this branch.

A-01 validates bytes, extracts selectable text from PDF and DOCX, and returns the
existing `ProcessedText` / `EvidenceRef` contracts with internal extraction
metadata. It does not produce a CandidateProfile, infer skills/language, invoke
models, match jobs, store files or implement the upload API.

## Run the tests

From `services/backend`:

```bash
uv run --locked --with-requirements ../../docs/resume/requirements-a01.txt pytest tests/resume -q
uv run --locked --with-requirements ../../docs/resume/requirements-a01.txt pytest
uv run --locked ruff check app/modules/resume tests/resume
uv run --locked ruff format --check app/modules/resume tests/resume
```

Verified: **58 A-01 tests; 90 total backend tests passed**, with the two existing
upstream test-client deprecation warnings. Lint and formatting pass.
Tests construct small, real PDF/DOCX byte streams in memory. No personal resumes,
network services, AWS, PostgreSQL, Word installation or model download is needed.

The requirement file pins `pypdf==6.17.0` and `defusedxml==0.7.1`. It is a
temporary A-01 dependency handoff, not a replacement shared lockfile. M3 must add
these to the backend manifest and lockfile before merging this feature into a
fresh CI environment. Tests do not silently skip missing parser dependencies.
See [M3 handoff](M3_HANDOFF.md).

## Entry point

```python
from app.modules.resume.extraction import extract_resume
from app.modules.resume.types import ExtractionLimits

limits = ExtractionLimits()
# The caller must cap reads/uploads at limits.max_file_bytes + 1.
result = extract_resume(
    upload_bytes,
    filename="resume.pdf",  # used only for format validation, never as a filesystem path
    media_type="application/pdf",  # optional; generic binary MIME is also accepted
    document_id="resume-123",
    document_version=1,
    limits=limits,
)
text = result.content.text
for ref in result.content.evidence:
    assert text[ref.start:ref.end] == ref.excerpt
```

Result metadata is internal to the resume module:
`content: ProcessedText`, actual `media_type`, `page_count` (PDF only), and
`warnings`. Keep both the canonical text and these warnings when adapting it to
the A-03/A-05 pipeline. The existing ResumeProcessor protocol returns a profile;
this low-level extraction function does not pretend to implement that protocol.

Catch `ResumeExtractionError` and use `error.as_detail(request_id)` for the
existing shared ErrorDetail DTO. Invalid document IDs/versions are caller
contract errors and raise Pydantic ValidationError separately.

## Formats and evidence

| Format | Extracted content | Evidence / caveats |
| --- | --- | --- |
| PDF | Page text using pypdf's layout mode, with rotated text retained where supported | Physical 1-based page numbers; blank pages keep their number and generate a warning |
| DOCX | Main-body paragraphs, table rows/cells, visible hyperlink labels, referenced headers/footers, inserted revision text | Structural part/paragraph/table locators; page is null because DOCX pagination requires a rendering engine |
| DOC, DOCM, images and other formats | Rejected | Re-export as ordinary PDF/DOCX |
| Password-protected PDF | Rejected, including encryption with an empty user password | Export an unencrypted copy |
| OLE Word container | Rejected as encrypted-or-legacy Word | Save an unencrypted DOCX |
| Empty, corrupt or image-only documents | Actionable error; no fabricated or partially truncated result | OCR is outside A-01 |

File extension and declared MIME must agree with bytes. DOCX additionally checks
the package content type and office-document relationship. ZIP members are read
in memory, with original member names checked before Windows normalization;
nothing is unpacked to disk. XML DTDs, entities, traversal names, duplicate names,
symlinks, encrypted ZIP entries and macro markers are rejected. External header
or footer references are rejected. Hyperlink labels are text only; destinations
are never fetched or executed.

Evidence offsets are zero-based, end-exclusive **Unicode code-point offsets**
into `result.content.text`, not PDF byte offsets, glyph coordinates or original
DOCX XML offsets. Chunks are joined with two newlines. CR/CRLF is normalized to LF,
ASCII controls other than tab/newline are removed with a warning, and outer
chunk whitespace is trimmed. Technical terms such as C++, C#, PyTorch and
Unicode characters are preserved; NLP normalization is deferred to A-02.

Chunk IDs are deterministic for the same document/version and parser output.
The tuple (document_id, document_version, chunk_id) identifies evidence, not
chunk_id alone. Preserve the exact text snapshot with its extraction version
`resume-extraction-v1`; later normalization needs a mapping or a new version.
Filename changes do not change extraction or evidence IDs.

PDF reading order is approximate, especially for complex columns and forms.
DOCX headers are emitted once before the body and footers once afterward, in
reference order. Tables are read row by row, not flattened as a single run.
Evidence sections identify structural locations, not NLP-inferred headings.
Deleted revisions and drawing/textbox text are omitted; inserted revisions are
included. Hidden runs, field results and numbering may differ from Word's visual
display. Embedded documents, footnotes/endnotes, form widgets and text embedded
in graphics are not a completeness guarantee. Warnings make selected omissions
visible; neither this parser nor the tests certify arbitrary layout fidelity.
Documents with an existing OCR text layer can be read, but OCR quality is not
validated.

## Provisional configurable limits

These are engineering defaults for M3/SET-03 review, not requirements asserted
by the slides or script.

| Limit | Default |
| --- | --- |
| Input bytes | 10 MiB |
| PDF pages | 30 |
| Each decoded PDF page content stream | 8 MiB |
| Extracted canonical text | 200,000 code points, including chunk separators |
| DOCX ZIP members | 1,000 |
| Total declared expanded ZIP bytes | 32 MiB |
| Each XML part read | 8 MiB |
| Per-member expansion ratio | 200:1 |

Limit violations fail the complete extraction rather than silently truncating
the resume. Valid highly repetitive or complex documents can exceed these
provisional limits and should be re-exported or reviewed against an adjusted
policy.

These bounds are **not process isolation**. PDF parsing and decompression occur
before some bounds can be evaluated and can consume substantial memory.
M3 must run extraction in a worker with enforced memory/time limits and bound
the upload/read before this function receives bytes. A-01 is synchronous;
it must not be wired directly into an async request handler for arbitrary input.
No production throughput, timeout or hostile-input resource guarantee is claimed.

## Error codes

| Code | Meaning / user action |
| --- | --- |
| EMPTY_FILE | Upload a nonempty document |
| FILE_TOO_LARGE | Export a smaller file |
| UNSUPPORTED_FORMAT | Use PDF or ordinary DOCX |
| FILE_TYPE_MISMATCH | Re-export instead of renaming an extension |
| UNSUPPORTED_WORD_CONTAINER | Save unencrypted DOCX instead of encrypted/legacy Word |
| ENCRYPTED_DOCUMENT | Export an unencrypted PDF |
| CORRUPT_DOCUMENT | Open and re-export the document |
| UNSAFE_DOCUMENT | Export a plain DOCX without unsupported package structures |
| NO_EXTRACTABLE_TEXT | Use selectable text; scans require future OCR |
| EXTRACTION_LIMIT_EXCEEDED | Reduce pages/text/embedded content |
| EXTRACTOR_UNAVAILABLE | Maintainer installs the pinned dependencies |

Error messages do not echo filenames, raw document text, URLs or library errors.
HTTP status mapping and route wiring belong to A-05/M3 coordination.

## Evidence from tests

- Single/multiple PDF pages and a simple two-column layout; blank page numbering.
- DOCX body, row/cell order, header/footer references, breaks, hyperlinks,
  tracked revisions, Thai/accented text/emoji and technical terms.
- Every evidence excerpt resolves to its exact canonical text slice.
- Stable results across repeated calls and changed filenames.
- Empty, encrypted, image-only, truncated/corrupt and falsely labeled inputs.
- Archive/XML expansion limits, unsafe original filenames, missing references,
  invalid content types and DTD/entity rejection including UTF-16 XML.
- Instruction-like resume text remains plain data; no matching or model calls.
- Configured limits reject whole results; no silent truncation.

References used for implementation:
[pypdf extraction behavior and memory caveats](https://pypdf.readthedocs.io/en/stable/user/extract-text.html),
[defusedxml parser controls](https://github.com/tiran/defusedxml).
