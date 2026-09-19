# Executable research tools

Install optional research and CPU dependencies from `services/backend`:

```powershell
uv sync --locked --extra ml --extra research
uv run --extra ml python -m scripts.package_cross_encoder --output .models/cross-encoder
```

The cross-encoder uses [MS MARCO MiniLM-L6-v2](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2),
pinned at `233902d25c440f23af6f7d6e94d2946bac0bee0a`. It loads safetensors
locally and applies sigmoid to one logit per pair, following the
[upstream usage](https://www.sbert.net/docs/cross_encoder/usage/usage.html).
This is a passage-ranking baseline, not a model validated for resume matching.
Paired inputs truncate to 512 tokens; this differs from the bi-encoder's
full-document chunking and must be reported when comparing results.

## Five-method comparison

Input JSON contains `data_origin` (`synthetic` or `human_labeled`), `split_id`,
canonical `profiles` and `jobs` arrays, and `labels`. Each label has
`candidate_id`, `job_id`, boolean `relevant`, `labeled_by`, and optional
`comment`. Label every candidate/job pair exactly once using rubric.py.
Human labels must come from people; do not relabel generated judgments as human.

From `services/backend`:

```powershell
uv run --extra ml --extra research python ../../research/evaluation/compare.py INPUT.json --embedding-model .models/resume --cross-encoder-model .models/cross-encoder --output REPORT.json --k 5
```

Reports include keyword, TF-IDF, bi-encoder, cross-encoder and hybrid results,
precision/recall/F1 from the existing harness, input hash, versions and timing.
Timing includes harness overhead and excludes model loading; bi-encoder and
hybrid currently make repeated per-pair calls. It is not an optimized serving
latency comparison. Freeze tuning data separately from the held-out report.
Queries without positive labels cannot produce meaningful recall and the
harness reports them as skipped; inspect failures before interpreting averages.

## LDA

Input JSON: `{"data_origin":"synthetic","documents":["job text one","job text two"]}`.

```powershell
uv run --extra research python ../../research/evaluation/topics.py CORPUS.json --topics 3 --output TOPICS.json
```

Outputs include seeded topics, document distributions, training perplexity
and a corpus hash. Use raw count features, not TF-IDF, for this LDA model.
Topic names/skill-cluster interpretation require inspection; no hiring quality
or held-out generalization is implied by training perplexity.

## Evidence and remaining research gate

On 2026-09-19, the five-method CLI completed using actual local bi/cross-encoder
weights and synthetic canonical profiles/jobs/labels. LDA reproducibility and
normalization tests passed. This is a smoke test only; there is no finished
human-labeled research report or justified final model selection yet.
