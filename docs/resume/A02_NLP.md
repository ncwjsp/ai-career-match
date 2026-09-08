# A-02: English shared NLP and evidence mapping

Plai/M1, branch `feat/m1/a-02-shared-nlp`, based on main `63740c4`.
English-first was confirmed by Plai on 2026-09-08. Status: implemented for
review; dependency promotion and merge remain. This is the A-02 increment,
not completion of A-03 profiles, A-04 embeddings, A-05 upload APIs or A-07
SageMaker packaging. AWS S3 and SageMaker remain required deployment services.

## What works

- Shared resume/job normalization: compatibility Unicode normalization (NFKC),
  whitespace/control normalization, case and technical punctuation preservation.
  Negation and stopwords are retained.
- A per-character map from normalized text back to the exact original Unicode
  code-point ranges, including expanding ligatures and combining characters.
- Real English tokenization, lemmas, POS tags and statistical named entities
  using pinned spaCy 3.8.7 and en_core_web_sm 3.8.0. Importing the module loads
  no model; loading the adapter performs no runtime download or AWS call.
- A small versioned skill alias registry that preserves C++, C#, PyTorch,
  Node.js, .NET and similar technical names. It keeps individual occurrences
  and evidence rather than discarding conflicting mentions.
- Conservative `mentioned`, `negated` and `uncertain` assertion flags. These are
  not the matching contract's present/partial/missing states, proficiency,
  required/preferred job requirements, or scores. A-03/B-02/B-06 interpret them.
- Clear errors for absent/mismatched models, unsupported/unknown languages,
  empty/oversized text, and invalid/mixed/overlapping source evidence.

The alias registry is a reviewed starting vocabulary, not an exhaustive skill
ontology. It avoids ambiguous abbreviations such as R, C, ML and AI; PyTorch
is not automatically an alias for Python. NER is a pretrained statistical
prediction, not verified profile data. Education, experience estimation,
projects and domain-specific profile construction remain A-03.

## Entry points

From the backend package:

```python
from app.nlp import SharedTextProcessor

processor = SharedTextProcessor("resume-123", 1)
# extracted.content is the existing A-01 ProcessedText.
analysis = processor.analyze(extracted.content, language="en")

assert analysis.source.text == extracted.content.text
normalized_for_later_embedding = analysis.normalized.text
for skill in analysis.skills:
    for ref in skill.evidence:
        assert analysis.source.text[ref.start:ref.end] == ref.excerpt
```

For raw job text, use a server-assigned job/document identity and immutable
version, then `processor.analyze_text(job_text, "en")`. This creates a single
whole-document evidence chunk. If M2 already has section/page evidence, pass
that ProcessedText to `analyze` instead. Both paths run the same NLP rules.

To reuse one loaded model across many documents within a bounded worker:

```python
from app.nlp.entities import EnglishPipeline
from app.nlp import SharedTextProcessor

pipeline = EnglishPipeline()
resume_processor = SharedTextProcessor("resume-123", 1, pipeline=pipeline)
job_processor = SharedTextProcessor("job-456", 3, pipeline=pipeline)
```

A processor lazily loads its own model if one is not supplied. Reuse an explicitly
loaded pipeline per worker instead of retaining one model per candidate/job.
Do not share mutable pipeline configuration while processing concurrently.

`process(text, language) -> ProcessedText` implements the existing TextProcessor
signature as a compatibility bridge: it runs validation/NLP and returns the
canonical source snapshot, preserving its coordinates. The current public DTO
cannot carry tokens, model metadata or the normalized offset map. Consumers
that need those use `analyze`/`analyze_text` and the internal `NlpAnalysis`;
there is no new HTTP DTO or generated type in this branch.

## Coordinate and version contract

`analysis.source` is a deep copy with exact source text, original extraction
version, language metadata and evidence. It is not rewritten or relabeled as
normalized text. `analysis.language` records the explicitly selected English
pipeline, even if A-01 left source.language unknown.

`TokenAnnotation`, `EntityAnnotation` and `SkillMention` start/end values index
`analysis.normalized.text`. Their EvidenceRef objects index `analysis.source.text`.
`normalized.source_span(start, end)` converts a normalized span to a source
range; an annotation crossing chunks contains multiple source references,
preserving document/version/chunk/page/section. Whitespace gaps between source
chunks need no invented evidence. Non-whitespace gaps are rejected.

Persist the source snapshot for evidence resolution. If normalized text is
stored or embedded later, retain `shared-text-v1`, `skill-aliases-v1`, the model
identity/revision and the offset map or a reproducible derivation. Never store
normalized text under an old source version while keeping old offsets. Frontend
consumers must convert Unicode code points rather than slicing UTF-16 units.
M3 owns any persistence/public-contract additions needed for the sidecar.

## Language, limits and limitations

English (`en`, `en-US`, `en-GB`) is explicit; there is no automatic language
identification. Unknown language returns `NLP_LANGUAGE_REQUIRED`; another
language returns `NLP_UNSUPPORTED_LANGUAGE`. An English override cannot disguise
a source explicitly labeled Thai or French. Thai characters in English-labeled
mixed text are preserved, with a warning that Thai NLP is unsupported. Labels
are caller declarations, not evidence that arbitrary input is actually English.

The configurable default cap is 200,000 Unicode code points, applied to both
source and normalized text; it is an engineering default for M3 review, not a
measured throughput guarantee. M3 still enforces process time/memory bounds.
No truncated-success output or blank-model fallback is returned.

Skill assertion rules cover straightforward negation, contractions, elementary
learning cues and clause boundaries. They do not resolve arbitrary grammar,
long-distance scope, idioms or multilingual text. They may over- or under-mark
complex sentences. Always retain the flags/warnings for downstream review;
`mentioned` does not establish skill proficiency. Generic NER has no calibrated
per-entity confidence here; do not invent one or equate a recognized ORG with
verified employment. Source text that looks like instructions remains data.

## Verification and dependency handoff

Verified 2026-09-08 on Windows/Python 3.12.14: **59 A-02 tests; 316 total backend
tests passed**, plus scoped Ruff lint/format. The full suite has two existing
test-client deprecation warnings. Database fixtures use SQLite; this is not
PostgreSQL, GitHub CI, SageMaker or live-corpus quality evidence.

M3 must promote [requirements-a02.txt](requirements-a02.txt) into the shared
manifest/uv.lock and confirm platform compatibility before merging A-02. It pins
spaCy, the exact English model wheel and compatible Typer/Click versions. The
first unconstrained CLI resolution lacked Click; the explicit pins were tested.
No shared manifests, generated contracts or central tracker were edited here.
See [A-02 handoff](A02_M3_HANDOFF.md).

After dependency promotion, from `services/backend`:

```bash
uv sync --locked
uv run --locked pytest tests/nlp -q
uv run --locked pytest -q
uv run --locked ruff check app/nlp tests/nlp
uv run --locked ruff format --check app/nlp tests/nlp
```

Before promotion, verification uses an ignored isolated environment so a stale
shared lockfile cannot be mistaken for a working locked installation. From root:

```bash
uv venv .cache/a02-env --python 3.12
uv pip install --python .cache/a02-env/Scripts/python.exe -r services/backend/pyproject.toml -r docs/resume/requirements-a02.txt pytest==9.1.1 ruff==0.16.6 httpx==0.28.1
cd services/backend
../../.cache/a02-env/Scripts/python.exe -m pytest -q
```

On macOS/Linux substitute `.cache/a02-env/bin/python` for `Scripts/python.exe`.
The shared lockfile remains authoritative after M3 integrates the pins; this
isolated recipe tests compatibility, not frozen transitive reproducibility.
Tests deliberately fail when a required trained model is missing rather than
silently skipping the POS/NER checks. Only tiny synthetic text and in-memory
DOCX bytes are used. No resumes or model weights are committed.

Implementation references: [spaCy linguistic features](https://spacy.io/usage/linguistic-features),
[model installation](https://spacy.io/usage/models), and
[English pipeline](https://spacy.io/models/en/).
