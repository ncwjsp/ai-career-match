# A-03: candidate profile extraction and factual summaries

Plai/M1, `feat/m1/a-03-candidate-profile`, based on merged A-02 at `e02a0e2`.
English-first; S3 and SageMaker remain required for later deployment. A-03
performs no storage, embedding, upload routing, matching, network call or LLM
generation. Its output is the existing canonical CandidateProfile.

## Entry point

```python
from datetime import date
from app.nlp import SharedTextProcessor
from app.modules.resume.profile import build_candidate_profile

# extracted is A-01 ExtractionResult, with server-assigned resume identity.
analysis = SharedTextProcessor(resume_id, document_version).analyze(
    extracted.content, language="en"
)
profile = build_candidate_profile(
    analysis,
    candidate_id=candidate_id,
    resume_id=resume_id,
    profile_version=profile_version,
    matching_enabled=matching_enabled,
    expires_at=expires_at,
    as_of=date(2026, 9, 8),
    extraction_warnings=extracted.warnings,
)
```

The caller supplies identity, version, consent/retention metadata and the
reference date. `resume_id` must equal source evidence document_id; profile
version may differ from the extraction document version. No current date,
default consent or retention duration is invented. `expires_at` must be timezone
aware. A-05/M3 will persist the profile and enqueue profile.ready separately.
Use one shared loaded EnglishPipeline per worker as documented in A-02.

## Extraction behavior

| Field | Supported evidence and behavior |
| --- | --- |
| Skills | Consume A-02 aliases in explicit skills, experience, projects or summary sections. Deduplicate names and retain positive occurrence evidence. |
| Negated/uncertain skills | Exclude uncertain and negated occurrences. Conflicting positive/negative mentions of a canonical skill exclude that skill entirely and produce a warning. A positive mention plus an uncertain mention retains only the positive evidence. |
| Education | Recognize degree/institution patterns under Education, including separate lines, pipe-separated fields and `at`. Explicit Qualification/Institution labels are supported. Unknown institution or qualification stays null. |
| Job titles | Explicit Role/Job title/Position labels or short role headers under Experience, using a bounded role vocabulary. Duty bullets and obvious desired-role prose do not become roles. |
| Organizations | Extract employer from a role header (`Engineer at Acme`, `Engineer | Acme`), explicit Company/Employer labels, or a whole-line A-02 ORG annotation immediately within the active experience entry. A random ORG in a summary is not an employer. |
| Education organizations | A whole-line ORG in Education can supply an institution such as MIT. This remains contextual statistical evidence, not verified attendance. |
| Dates and years | Preserve recognized precision, require a single range per entry, and union valid month intervals before estimating years. Incomplete/unusable intervals make the total unknown. |
| Projects | Explicit `Project: Name | description`, `Name: description`, or `Name | description`; a short standalone name can introduce following description lines. A title without description is omitted with a warning because canonical Project.description cannot be null. |
| Summary | Deterministic sentences from extracted roles, skills, education/institutions, project names and a valid date estimate. No generation, score, hiring claim, invented proficiency or assumed completed degree. Empty supported content yields null. |

Supported headings include Skills/Technical skills, Experience/Work experience,
Education/Academic background, Projects/Personal projects and Summary/Profile.
Inline headings such as `Skills: Python, C++` work. Objective, Requirements,
Job description, References, Certifications, Languages, Interests and Awards
are excluded from confirmed skill/employment extraction. Some unknown uppercase
headings terminate the current section. Arbitrary unstructured prose, unknown
headings, swapped company/title layouts and multi-column reading order are not
general-purpose parsing guarantees. Review omissions on representative resumes.

Blank lines are not assumed to end entries: A-01 inserts them between DOCX
paragraphs. A new role header starts a new employment entry; a new explicit
project header starts a new project. Multiple dates in one employment entry
remain ambiguous rather than being silently assigned to a title.

NER supplies contextual organization evidence only. Its generic labels cannot
verify employment, degree completion or skill depth. The dated experience list
retains duplicate source entries for auditability; aggregated titles and
organizations are deduplicated, and dates are unioned so duplicates add no time.
The initial role and degree patterns are deliberately limited, not exhaustive.

## Date policy: resume-profile-rules-v1

- Accept English month/year (`Jan 2020`, `January 2020`), `YYYY-MM`, bare years,
  and present/current/now endpoints, with hyphen/en dash/em dash or `to` ranges.
- Store month dates as `YYYY-MM`, year-only dates as `YYYY`, and ongoing ends as
  `present`. Unknown dates stay null. These are strings allowed by the existing
  contract; M3 should confirm their interpretation before UI/API integration.
- A closed interval includes its ending month. `Jan 2020-Dec 2020` is 12 months.
- Present counts completed months before the explicit `as_of` month. January
  2026 to present with September 8, 2026 as reference is 8 months, or 0.67 years.
- Merge overlaps, nested intervals, duplicates and adjacent intervals. Gaps do
  not count. January 2020-December 2021 plus July 2021-June 2022 is 30 months,
  or 2.5 years, not 3 years.
- Year-only, missing, invalid, reversed or future dates make the aggregate null.
  A closed end in the still-incomplete reference month is also unknown. A valid
  present interval starting that month contributes zero completed months.
- If any extracted employment entry lacks a usable interval, do not present
  the known subset as total experience. Keep the entries/evidence and warnings.
- This is reported calendar span, not verified full-time employment or a measure
  of proficiency. Part-time workload is not inferred or multiplied.

Persist PROFILE_EXTRACTION_VERSION and as_of with analysis-run metadata for
reproducibility; they are explicit function inputs/constants, not new public
DTO fields. The calculation has no hidden clock. Raw self-claims like “20 years”
without dated employment do not override the calculation.

## Evidence and unknown values

The source text and extraction evidence are never rewritten. All field evidence
retains original document/version/chunk/page/section and Unicode code-point
coordinates. Source/normalized maps and consumed skill/ORG annotations are
validated before use. Overlapping, inconsistent or mismatched identity evidence
is rejected rather than accepted as a plausible profile. Aggregated string
fields and the deterministic summary are derived from the evidenced objects;
profile.evidence also retains the complete original extraction references.

The function deep-copies evidence, preserves incoming A-01/A-02 warnings, and
adds stable warning codes for uncertain/conflicting skill mentions, unknown
experience dates/totals, missing project descriptions and absent supported fields.
Null means unknown; empty lists mean no supported extraction, not proof that the
candidate has no skills or experience. Text resembling instructions is treated
as source data and cannot set scores or invoke tools.

## Verification

Verified locally: **43 A-03 tests and 359 total backend tests passed**, with two
existing upstream deprecation warnings. Resume lint/format passed; OpenAPI is
current. This is isolated-environment evidence, not locked CI or AWS evidence.

Run from services/backend after M3 promotes the A-02 dependencies:

```bash
uv sync --locked
uv run --locked pytest tests/resume/test_profile.py -q
uv run --locked pytest -q
uv run --locked ruff check app/modules/resume tests/resume
uv run --locked ruff format --check app/modules/resume tests/resume
uv run --locked python -m scripts.export_openapi --check
```

The current shared manifest still lacks A-02's spaCy/model pins. This increment
adds no dependencies. Local verification uses the existing ignored `.cache/a02-env`
from the [A-02 recipe](A02_NLP.md), not a claim that `uv sync --locked` or CI works.
The tests include deterministic A-02-shaped annotations, a real English-model
handoff, A-01 chunk/evidence integration, synthetic profiles, unknown/conflicting
fields, date boundaries/overlaps and summary grounding. No personal data is used.

See [A-03 M3 handoff](A03_M3_HANDOFF.md) for measured results and the proposed
tracker update. M3 owns central tracker/contract/persistence changes.
