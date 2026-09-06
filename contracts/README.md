# Initial v1 contract guide

Status: implemented bootstrap contracts, pending M2/M3 review. M3 maintains these
after Plai's review/commit checkpoint. This guide describes the current code;
the full plan still defines the eventual product.

## Single source and ownership

- Canonical DTOs: `services/backend/app/contracts/models.py`.
- Python ports: `services/backend/app/contracts/interfaces.py`.
- Planned HTTP signatures: `services/backend/app/api/planned.py`.
- Generated HTTP schema: `contracts/openapi.json`.
- Generated frontend DTOs: `apps/web/src/lib/api/generated.ts`.
- Synthetic examples: `contracts/examples/bootstrap.json`.

Run the two generation commands in the root README after any contract change.
CI detects stale generated files. Pydantic validators enforce rules that
TypeScript alone cannot enforce; keep producer/consumer tests.

## Boundaries and version rules

| Contract | Responsibility and invariant |
| --- | --- |
| CandidateProfile | Retained candidate/resume IDs, monotonic profile version, extracted entities, evidence, matching opt-in and UTC expiry |
| JobPosting | Independent job ID/source URL, content version, requirements and evidence, provenance/freshness/expiry; no candidate or analysis reference |
| EvidenceRef | Document ID/version and chunk ID; optional page/section; zero-based, end-exclusive character offsets into the versioned canonical extracted text and its excerpt |
| EmbeddingRecord | Entity and model/preprocessing/embedding versions, declared dimension, finite nonzero vector; 3D fixture vectors are not a model decision |
| SkillComparison | Required/optional skill; present/partial/missing; job evidence always, resume evidence only for supported present/partial states |
| MatchResult | Candidate/profile/job/scoring versions, score components, skill states, strengths/gaps, evidence and fixture/computed origin |
| RecommendationSet | Candidate/profile and immutable result revision, ordered unique ranks, refresh state and optional page cursor |
| MatchExplanation | Same candidate/profile/job/scoring/recommendation revision, pending/ready/unavailable state and source evidence; generation cannot change scores |
| AnalysisRun | Tracks the initial upload/profile workflow |
| MatchRun | Separately tracks a matching event, checkpoint, failures and published candidate revisions |
| ErrorResponse | Stable code/message/retryable/request_id envelope for implemented planned-route errors |

Unknown values are `null` or empty lists as appropriate, not invented extracted
facts. Evidence coordinates refer to normalized extraction text, not PDF bytes.
M1/M2 must retain that text/version for evidence resolution. The fixture test
checks references against the example evidence catalog; it is not an NLP quality
test or a validation of real document offsets.

M2 owns `career_jobs` and its transactional outbox; M3 owns retained candidates,
match runs, result sets and queues in `career_app`. Cross-database relationships
are versioned IDs resolved through repositories, not cross-database foreign keys.

## Two independent matching triggers

1. `profile.ready` identifies a retained candidate and profile version. Match that
   version to active jobs. An upload request need not remain open.
2. M2 commits a new/changed job and `job.created` or `job.updated` outbox event in
   the same job-database transaction. The event identifies the job/version and
   content reference; it has no upload, analysis or candidate ID.
3. M3 dispatches events and reads active retained profiles in bounded, ordered
   batches. M2's `match_job` must reuse `score_pair`. Old job/profile events
   must not overwrite newer results. Candidates whose retention expired or who
   disabled matching are excluded.
4. M2 marks jobs inactive and emits `job.expired`/`job.removed`. M3 invalidates
   affected results and publishes a fresh coherent revision.
5. M3 handles retries, checkpoints, reconciliation, atomic revision publication
   and frontend refresh. Event IDs and pair/version keys support idempotency.

The interfaces expose repositories, job outbox, match/analysis queues, worker,
object store, resume/text processing, embeddings, ingestion, matching and
explanation ports. Claim leases, retry backoff and transaction implementations
belong to C-01/C-08/B-09. The `reconciliation.requested` event is modeled; the
fixture harness deliberately raises NotImplementedError for it.

## Score contract

Initial scoring version: `semantic-skills-v1`.

```text
semantic_fit = clamp(cosine_similarity, 0, 1)
required_skill_coverage = (present + 0.5 * partial) / required_skill_count
score = 100 * (0.70 * semantic_fit + 0.30 * required_skill_coverage)
```

Use unique canonical required skills. Optional skills do not enter this coverage
denominator. With no reliable required-skill list, coverage is null and the score
uses semantic weight 1, skills weight 0 and basis `semantic_only`. Do not silently
score invalid/zero vectors. Use the plan's full edge-case and versioning rules.
A displayed score is a relevance score, not a probability of being hired.

The fixture pairs use semantic fits 0.8 and 0.9 and required coverage 0.7:
77 and 84. Tests verify those examples against the formula.
**There is no scoring algorithm here:** FixtureMatcher only returns a known
candidate/profile/job/scoring-version lookup, and raises for unknown pairs.
M2 implements actual scoring, retrieval, ranking, tie-breaking and evaluation.

## Mock adapters and remaining work

`app/testing/` contains deep-copying in-memory profile/job/match repositories,
an outbox/queue double, fixed resume/matcher/explainer adapters, a fixture loader
and a synchronous matching contract harness. They lose state on exit and provide
no durability, database transactions, distributed locks, auth or cloud behavior.

The bundle contains one synthetic candidate, two jobs on example.test, toy
embeddings, profile/new-job events, a ready explanation/recommendation, runs and
error examples. Tests also construct expiry, removal, duplicate, stale-event and
invalid-data cases. M3 will add further UI scenarios (pending/empty/loading),
persistence adapters and real worker behavior as those tasks begin.

All valid planned HTTP requests return 501 until wired to domain implementations.
Schema response shapes describe future success responses; the generated snapshot
labels these paths `x-implementation-status: planned`. Only health and the
read-only fixture endpoint return successful implemented responses now.
