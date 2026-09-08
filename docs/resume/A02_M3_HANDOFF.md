# A-02 handoff to M3 and M2

Plai/M1, 2026-09-08. Feature branch: `feat/m1/a-02-shared-nlp`, based on
main `63740c4`. English-first was explicitly confirmed by Plai. AWS S3 and
SageMaker remain required, with local model tests independent of AWS.

## Evidence and exact scope

A-02 implements English text normalization/offset mapping, real spaCy POS/NER,
skill aliases and conservative assertion flags. See [behavior and usage](A02_NLP.md).
Only `services/backend/app/nlp/`, `services/backend/tests/nlp/` and `docs/resume/`
are changed. No matching, job ingestion, profiles, routes or shared dependencies
were edited. No external message, PR, commit or push was made for this handoff.

Verification on Windows, Python 3.12.14, in ignored `.cache/a02-env`:

| Check | Evidence |
| --- | --- |
| New A-02 tests | 59 passed, including real en_core_web_sm inference and synthetic A-01 DOCX integration |
| Complete backend suite | 316 passed; two existing upstream test-client deprecation warnings |
| Scoped Ruff lint/format | Passed |
| AWS / hosted NLP | Not invoked; this is local inference evidence only |
| Shared frozen install / CI | Not established by isolated tests; M3 must integrate pins and rerun the locked workflow |

The full suite used the shared manifest dependencies plus explicit A-02 pins;
it does not prove the existing uv.lock or GitHub CI is healthy. Existing database
tests use SQLite, and no PostgreSQL concurrency claim is made by this feature.
Model output checks demonstrate interfaces and a tiny synthetic acceptance set,
not measured extraction accuracy across real resumes or supported Thai NLP.

## M3: focused shared dependency work before merge

Promote the exact dependencies in [requirements-a02.txt](requirements-a02.txt):
spaCy 3.8.7, en_core_web_sm 3.8.0 from the explicit wheel URL, Typer 0.16.0,
and Click 8.1.8. Regenerate uv.lock and run locked sync, the full backend suite,
lint and contract drift checks on the supported platforms. Freeze transitive
resolution there; the temporary requirements file is not a second shared lock.
The model is installed ahead of time: production processing never downloads it.

Keep model loading in bounded workers or the later SageMaker package; do not
load it into each API request or every retained candidate object. The API is
`SharedTextProcessor(document_id, document_version, pipeline=shared_pipeline)`.
Reuse one trained `EnglishPipeline` per worker where appropriate. A-07 will
package the implementation and verify actual endpoint parity; this branch does
not claim that the current embedding-only endpoint returns POS/NER annotations.

## Contract/persistence coordination

Public `ProcessedText` has text, language, evidence and preprocessing version;
it cannot represent token/entity annotations or a separate normalized offset map.
No public DTO was changed unilaterally. `analyze` returns internal `NlpAnalysis`
with source, normalized text/map, selected language, tokens, entities, skills,
model/preprocessing/alias versions and warnings. Its `source` keeps the original
extraction version and exact text. The existing `process` port returns this
canonical source snapshot after analysis; use `analyze` to consume annotations.

M3 should agree with M1/M2 whether the sidecar is recomputed from retained source
text or stored as versioned internal metadata; add a canonical public contract
only if an API actually needs it. Persist original text for EvidenceRef offsets.
Never combine normalized text with original offsets or silently discard unknown
language, negated/uncertain mentions or warnings when creating profiles.

A-04 must apply the same normalization/model revisions for candidate and job
embedding inputs. The normalization alone is not an embedding or a semantic
matcher. The existing SageMaker embedding transport remains M3-owned; A-04/A-07
will use its documented vectors/model revision/dimensions contract.

## M2: consume without waiting for A-03

Use `analyze_text` with a real job/document ID/version, or `analyze` with your
source ProcessedText to retain sections. Synthetic resume and job text already
exercise identical processing. Use returned evidence references, not private
normalization helpers. `mentioned` is a surface mention, `negated` flags local
negative context, and `uncertain` flags elementary learning/limited-exposure
language. These are not final required/preferred or present/partial/missing
states. B-02/B-06 own those interpretations and the scoring formula.

The registry is deliberately small. Send proposed aliases and counterexamples
to M1 via the normal review process; do not duplicate it inside matching. B-01
source access, manual import UI/API, B-03 retrieval and ranking remain M2 work.

## Proposed central tracker update (M3 edits plan.md)

| Task | Owner | Status | Dependencies | Evidence / remaining |
| --- | --- | --- | --- | --- |
| A-02 | Plai/M1 | In Progress | M3 shared dependency promotion, review and merge | English-first implementation; 59 new / 316 total backend tests passed locally. Source evidence preserved; trained POS/NER and documented heuristic aliases/assertions. No AWS or real-corpus quality evidence yet. |

Do not mark Done until shared dependencies and the feature are reviewed, merged
and verified in the intended locked setup. Update D02 to record Plai's English-first
confirmation; Thai text preservation does not establish Thai NLP support.

Next Plai task is A-03 candidate entities/experience/projects and summary, with
A-04 embeddings following the agreed model decision. Do not infer profile fields
just because the generic NER model emitted a label.
