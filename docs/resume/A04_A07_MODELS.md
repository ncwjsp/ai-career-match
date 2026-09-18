# A-04 / A-07: shared embeddings and packaged inference

Owner: Plai (M1). Baseline implementation, pending teammate review and live AWS verification.

## Representation and compatibility

`app/nlp/embeddings.py::VersionedEmbedder` implements the existing `Embedder` port.
`encode(texts, version)` takes the document identity from evidence; ambiguous or missing
identities fail. `encode_entity(source, candidate_id, profile_version)` is the explicit
candidate-identity variant. Neither changes public DTOs or evidence offsets.

- Model: `sentence-transformers/all-MiniLM-L6-v2`.
- Revision: `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`.
- Dimensions: **384**; preprocessing: `shared-text-v1`.
- Embedding version: `minilm-1110a243-shared-v1-token254-mean-v1`.
- Reviewed artifact hashes: `services/backend/app/nlp/model_manifest.json`.
- Baseline selection is provisional until M2 completes B-08; no quality win is claimed.

The [upstream model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
describes the 384-dimensional English encoder and its default 256-wordpiece truncation.
Our CPU client instead splits into nonoverlapping 254-token chunks plus special tokens,
uses attention-masked mean pooling, normalizes each chunk, then averages by token count
and normalizes the document vector. Every tail chunk is processed. This aggregation is
an engineering baseline that still needs evaluation on resumes/jobs.

Limits: 200,000 normalized characters and 256 chunks per document; 32 documents per
transport call, 16 chunks per CPU forward pass, two CPU threads by default. The public
Embedder splits larger document batches into transport batches. Empty/unsupported-language
inputs fail; mismatched model identity, dimensions and invalid vectors never enter storage.
No weights are downloaded during inference. Only the explicit packaging command downloads.

## Run locally

From `services/backend`:

```bash
uv sync --locked --extra ml
uv run --extra ml python -m scripts.package_resume_model --output .models/resume
uv run --extra ml python -m scripts.benchmark_resume_model --model-dir .models/resume
```

Set `EMBEDDING_BACKEND=cpu` and `EMBEDDING_MODEL_DIR=.models/resume` in the ignored
backend `.env` for local integration. Keep `OBJECT_STORE_BACKEND=local` and `APP_MODE=mock`
locally; this mode still uses real CPU embeddings when explicitly selected. `local` embedding
means the old hash fixture, not semantic inference. The worker refuses that fixture backend.
The API/worker must use the same working directory, database URLs and object-store directory.

Ordinary `uv sync --locked` installs NLP and the API without the optional large ML stack.
Use `uv run --extra ml ...` for CPU commands, otherwise uv may remove optional dependencies.
Offline inference requires packaging first; never silently fall back when artifacts are missing.

## Private SageMaker container

From the repository root:

```bash
docker build -f ml/resume/Dockerfile -t career-resume-inference .
docker run --rm -p 127.0.0.1:8080:8080 -v "ABSOLUTE_MODEL_DIRECTORY:/opt/ml/model:ro" career-resume-inference serve
```

The image accepts SageMaker's `serve` argument, listens on 8080, has `/ping` and
`/invocations`, and loads models at startup. The model directory is read-only; serve
sets offline flags. Upload an archive containing the model-directory **contents** as
the approved SageMaker model artifact. No ECR push, bucket creation, endpoint or paid
resource is created by these commands.

Embedding protocol stays M3's existing JSON contract:

```json
{"inputs":["Python developer"]}
```

Response: `vectors`, `model_id`, `model_revision`, `dimensions`. NLP uses the same
endpoint with `{"task":"nlp","source": <ProcessedText>}` and returns
`{"analysis": <serialized NlpAnalysis>}`. This is an internal sidecar, not a new public
DTO. `SageMakerNlpProcessor` verifies source and NLP/preprocessing/skill versions. Original
source evidence remains unchanged. Request bodies are capped at 4 MiB.

In deployment keep required S3/SageMaker settings from `.env.example`. The same endpoint
must support both request forms. Workers select remote NLP when embedding backend is
SageMaker. IAM should allow only the named endpoint and resume-object prefix; see M3's
deployment runbook. Do not expose this internal container as a public unauthenticated API.

## Evidence and limits

`tests/nlp/test_endpoint.py` checks NLP serialization equality, malformed requests,
artifact validation and local HTTP transport. With `ACM_MODEL_DIR=.models/resume`, its
real-model test compares local and endpoint vectors within `1e-6`, verifies unit norms,
single/batch agreement and that a long-document tail changes its embedding. That test
uses the actual CPU encoder through an injected HTTP-to-SageMaker-shaped transport;
it is **not** a live SageMaker call.

Synthetic Windows CPU measurement (2026-09-17, Python 3.12, two threads): load 29.960 s,
four-document batch 0.616 s, peak process working set 380.52 MiB. One document had 1,000
repeated tokens. These are one-process smoke measurements, not capacity or cloud latency
promises. Use the benchmark script on the chosen host before sizing deployment.

Live endpoint parity, IAM, S3 lifecycle, cross-cloud latency/egress and target-instance
memory remain INT-02/deployment gates. No AWS credentials, endpoint or approved budget
was supplied for this run. Fine-tuning is deferred until consented/labeled training data
and a held-out evaluation exist; the current model is pretrained, not trained on team data.

## M2 handoff

Use `job_text(job)` and `profile_text(profile)` from your existing matching module.
Apply the shared normalization/encoder to both; the resume worker already uses
`profile_text`. Store candidates in `career_app` and jobs in `career_jobs`. Pass
`EMBEDDING_VERSION` when saving/querying compatible vectors and rebuild on revision,
dimension, preprocessing or representation changes. B-03 must not mix older fixture
vectors with these. B-03 retrieval, cross-encoder, LDA and real evaluation remain M2's work.
