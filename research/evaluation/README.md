# Evaluation harness (B-08)

Owner: M2. Status: **the harness exists and is tested; no real comparison
report exists yet.** Those are different things — see "What is NOT here yet"
before treating any number this code produces as a finding.

## What is here

- `metrics.py` — precision@k/recall@k/F1@k against binary relevance labels,
  plus a macro-average across queries. Pure functions, no dependency on this
  project's contracts or matching methods, so it is testable in complete
  isolation (`test_metrics.py`).
- `rubric.py` — `RUBRIC`, the actual wording a human labeler (VAL-01) is
  given, versioned as `RUBRIC_VERSION`; `Label` (one candidate/job relevance
  judgment); `EvaluationSplit` (a frozen candidate list + frozen job pool +
  its labels, so a later re-run is comparable to an earlier one).
- `harness.py` — `from_pairwise` adapts any `(profile, job) -> float` scorer
  (keyword/TF-IDF/bi-encoder, and a future cross-encoder) into a full
  ranking of one job pool; `run_method`/`compare_methods` run one or more
  such rankers against a split, returning per-method precision/recall/F1,
  wall-clock latency, and a list of failures (a missing profile fixture, no
  labels for a candidate, or the ranker itself raising) instead of silently
  dropping them — plan.md's "document latency and failure cases."

Run the tests from anywhere (`services/backend`'s venv has the only
dependencies this needs — `pytest`, and the backend package itself):

```bash
cd services/backend
uv run python -m pytest ../../research/evaluation -q
```

`harness.py` puts `services/backend` on `sys.path` itself at import time
(there is no top-level `pyproject.toml`/`PYTHONPATH` this repo relies on),
so this works regardless of the invocation directory.

## What is NOT here yet

- **No real human labels.** `Label`/`EvaluationSplit` are the *shape* VAL-01's
  labels will take, not a substitute for collecting them — VAL-01 ("Human
  labels and NLP/summary/skill/explanation review") is still "Not Started"
  in plan.md's tracker. `test_harness.py`'s fixtures are a handful of
  synthetic candidates/jobs built only to exercise the harness's own logic
  (ranking, skipping, failure handling) — never read them as findings about
  which method is better.
- **Only 4 of 5 methods can run through this today**: keyword, TF-IDF,
  bi-encoder, and hybrid (`app/modules/matching/{keyword,tfidf,bi_encoder,
  hybrid}.py`). The fifth, transformer pair (cross-encoder) matching, is
  blocked on a new ML runtime dependency that needs M3 coordination
  (`docs/matching/scoring.md`'s hybrid section explains why). Any of the
  four existing methods slots in today via `from_pairwise(...)` (or, for
  hybrid, a small wrapper — its own shape ranks a whole pool at once rather
  than one pair, since it already bounds the candidate pool internally).
- **No written comparison report.** plan.md's B-08 acceptance bar is "a
  reproducible comparison report and model/weight recommendation with
  actual measured values" — that requires running `compare_methods` against
  a real `EvaluationSplit` built from real VAL-01 labels over a real job
  corpus (which itself needs jobs actually imported through B-02, not just
  the capability to import them). None of that data exists in this sandbox.
  Building the harness now, ahead of the data, is what plan.md's own
  recommended order asks for ("Build harness early; complete final report
  after labels freeze") — this file is that early half, honestly labeled as
  incomplete rather than padded out with fixture numbers dressed up as
  results.

## Once real labels and a real job corpus exist

1. Import real jobs through B-02 (`app.modules.jobs.ingest.JobIngestionService`)
   so there is a real corpus to draw an `EvaluationSplit.job_pool_ids` from.
2. Have labelers follow `RUBRIC` (`rubric.py`) to produce `Label` rows for a
   frozen `(candidate_ids, job_pool_ids)` split.
3. Build the `methods` dict (`{"keyword": from_pairwise(keyword.score), ...}`,
   wiring a real `EmbeddingClient` and `background` corpus where a method
   needs one) and call `compare_methods(methods, profiles, jobs, split, k=...)`.
4. Write the actual comparison report from the returned `MethodResult`s into
   `docs/matching/` (per plan.md's file list for B-08), including latency
   and the failure lists — not just the headline precision/recall/F1.
