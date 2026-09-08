# A-03 handoff: Plai to M3/M2

Branch: `feat/m1/a-03-candidate-profile`; base: `e02a0e2` (merged A-02).
Status: implemented for review, not committed/pushed/merged by this task.

## Delivered

`build_candidate_profile` consumes A-02 NlpAnalysis and returns the existing
CandidateProfile. It covers evidenced skills, education, roles, organizations,
experience/date union, projects and a deterministic factual summary. See
[A-03 behavior](A03_PROFILE.md) for supported layouts and limitations.
Only the resume module, its tests and docs/resume were changed. No new dependency,
shared DTO, generated client, migration, API route or infrastructure change.

## Actual verification

Windows/Python 3.12.14, isolated `.cache/a02-env` with the existing A-02 pins:

| Check | Result |
| --- | --- |
| A-03 profile/date/evidence/summary tests | 43 passed |
| Full backend regression suite | 359 passed, 2 existing upstream deprecation warnings |
| Resume module/tests Ruff lint and format | Passed |
| OpenAPI snapshot | Current |
| AWS / production inference | Not invoked; no deployed-inference claim |
| Locked dependency workflow / GitHub CI | Not established; A-02 dependencies are still absent from the shared manifest |

The suite uses synthetic data and SQLite for existing repository tests. No real
resume extraction accuracy, PostgreSQL concurrency or hosted-service parity is
claimed. NER is genuinely invoked in one handoff test; most profile tests use
small deterministic A-02 annotations to make expected fields/date totals explicit.

## M3 coordination before integration

1. Finish the existing [A-02 dependency handoff](A02_M3_HANDOFF.md): promote its
   pins to pyproject/uv.lock, then verify locked installation and CI. A-03 itself
   needs no additional packages. Do not mistake feature merge for dependency
   readiness; current START_HERE/plan status also contains stale earlier entries.
2. Persist the exact extracted text/evidence alongside the profile. Canonical
   skill/education/experience/project fields retain source evidence; summary,
   job_titles and organizations derive from those objects. Do not replace source
   text with normalized text while retaining its original offsets.
3. Record `PROFILE_EXTRACTION_VERSION="resume-profile-rules-v1"` and the explicit
   `as_of` date in analysis metadata. No new public metadata DTO was introduced.
4. Confirm date-string handling before exposing profile UI/API: YYYY-MM for
   known months, YYYY for year-only precision, `present` for ongoing ends, null
   for unknown values. The existing Experience contract accepts these strings.
   Missing/year-only/unusable intervals make the total null, not a partial total.
5. Confirm how UI presents warnings and unknown values. Negated/uncertain skill
   occurrences are excluded from confirmed skills; conflicting positive/negative
   mentions exclude that skill. A Project with no evidenced description is
   omitted with a warning because Project.description currently cannot be null.
   If the product must display title-only projects or uncertain skills separately,
   M3 should coordinate a public contract extension before dependent code.
6. A-05 supplies candidate/resume/profile IDs, matching_enabled, timezone-aware
   expires_at and as_of. The extractor has no persistence/event side effects.
   Save the resulting profile and enqueue profile.ready only in later orchestration.

M2 can consume the existing CandidateProfile shape immediately using synthetic
outputs. Do not infer missing skill evidence as proof of absence, or use the
calendar-span estimate as verified full-time experience. Matching remains M2's
responsibility. S3, SageMaker transport, queues and shared route wiring remain
M3-owned; A-04/A-07 embedding/model packaging are still separate M1 tasks.

## Proposed central tracker row (M3 is the editor)

| Task | Owner | Status | Dependencies | Evidence / remaining |
| --- | --- | --- | --- | --- |
| A-03 | Plai/M1 | In Progress | Merged A-01/A-02; M3 A-02 dependency integration; review/merge | Evidence-backed profiles and deterministic summaries implemented; 43 new and 359 total tests pass locally. Supported-layout/NER/date limitations documented. Locked CI and representative-corpus evaluation remain. |

No central tracker status was changed by this branch. Suggested future commit:
`feat(resume): extract candidate profiles and factual summaries (A-03)`.
