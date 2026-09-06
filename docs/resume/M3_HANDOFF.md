# A-01 handoff to M3

Status: **ready for dependency/contract review; not merged or released**.
Prepared by Plai/M1 on `feat/m1/a-01-resume-parsers` from `858c58b`.
No message or PR was sent to a teammate automatically.

## Concrete shared changes requested

M3 owns and should make the following changes in a separate focused dependency
PR before the A-01 feature is merged. M1 has not edited shared files.

1. Add exact runtime dependencies `pypdf==6.17.0` and `defusedxml==0.7.1` to
   `services/backend/pyproject.toml` and regenerate `uv.lock`.
   From `services/backend`, the proposed owner command is:

   ```bash
   uv add pypdf==6.17.0 defusedxml==0.7.1
   uv sync --locked
   uv run pytest
   ```

   Fresh CI currently installs the bootstrap dependencies only. The new tests
   need these packages and intentionally do not skip missing dependencies.
   No python-docx, office executable, OCR engine or PDF-generation package is
   required. Fixture builders use pypdf plus Python's standard library.

2. Confirm the evidence convention in the shared contract guide: A-01 produces
   Unicode code-point offsets, zero-based and end-exclusive. JavaScript consumers
   must use `Array.from(text).slice(start, end).join("")` (or an equivalent
   conversion) rather than UTF-16 `String.slice` when rendering these spans.
   No DTO shape or generated API-type change is required by this implementation.

3. Confirm the provisional limits in README.md against SET-03/D06 and enforce
   upload byte caps, worker deadlines and memory limits in the application layer.
   Decoded PDF stream checks alone are not a resource sandbox.

4. Persist the exact canonical text and extraction-version metadata along with
   document identity/version. Do not reuse an evidence version for changed text.
   Carry `ExtractionResult.warnings` forward to the profile's extraction warnings.
   Request a shared metadata extension only if the storage design needs one.

The local exact requirement file in this directory lets M1 verify the complete
feature before M3's dependency PR. It is not a second shared dependency authority.
After M3 promotes the pins, the ordinary locked workflow should pass without
`--with-requirements`; the temporary test instructions can then be simplified.

## Integration boundary

Call `app.modules.resume.extraction.extract_resume` with bounded bytes and a
server-assigned document ID/version. Consume its existing `ProcessedText` and
`EvidenceRef` values. The surrounding ExtractionResult is private resume-module
metadata. Use `ResumeExtractionError.as_detail(request_id)` for ErrorDetail.

A-01 does not emit profile.ready: a structured retained profile must first be
created by A-03/A-05. It does not enqueue matches or parse again for new jobs.
The current upload endpoints remain planned/501 until their owner wires A-05.
Neither the public contracts nor root API routes changed in this branch.

## Proposed tracker update for M3

| Task | Member | Status | Dependencies | Evidence / notes |
| --- | --- | --- | --- | --- |
| A-01 | Plai / M1 | In Progress | M3 dependency PR, SET-03 limit/language decisions, review/merge | PDF/DOCX extraction implemented; 58 new tests and 90 total backend tests pass with pinned A-01 requirements; lint/format pass. OCR, legacy DOC, NLP and API integration are outside this task. |

Do not mark A-01 Done until its relevant shared dependencies and feature have
merged and acceptance evidence is attached. Language extraction coverage is not
established by one Unicode DOCX fixture; model/language decisions remain open.

## Review and commit scope

Only these paths contain changes:

- `services/backend/app/modules/resume/`
- `services/backend/tests/resume/`
- `docs/resume/`

Suggested future commit title: `feat(resume): validate and extract PDF/DOCX text (A-01)`.
This feature branch is for review. Merge only after M3 integrates the shared dependencies.
