# Matching score formula — `semantic-skills-v1`

Owner: M2 (B-05/B-06/B-10). Implemented in
`services/backend/app/modules/matching/scoring.py`. Both matching triggers
(a candidate's `profile.ready` event and a job's `job.created`/`job.updated`
event, see `app/orchestration/job_events.py`) call the same `Matcher.score_pair`
code path, so a pair's score cannot differ depending on which trigger produced
it — enforced directly by `match_job` calling `score_pair` per profile rather
than duplicating the calculation.

**The 70/30 weights and the 0.5 partial-credit rule below are plan.md's
proposed starting values, not measured findings.** B-08's held-out evaluation
is where they get reviewed against real judgments; nothing here should be read
as a tuned result.

## The formula

```text
S = clamp(cosine(candidate_text_embedding, job_text_embedding), 0, 1)

For each distinct required skill i:
    credit_i = 1.0 if present, 0.5 if partial, 0.0 if missing
K = sum(credit_i) / number_of_distinct_required_skills

If the job has at least one reliably extracted required skill:
    raw_match_score = 100 * (0.70 * S + 0.30 * K)
    score_basis = "semantic_skills"
Otherwise:
    raw_match_score = 100 * S
    skill_coverage = null
    score_basis = "semantic_only"

display_match_score = round(raw_match_score, 1)
```

Worked example (from plan.md, reproduced as
`tests/matching/test_scoring.py::test_the_plan_md_worked_example_gives_77_point_0`):
`S = 0.80` with five required skills, three present, one partial, one missing
gives `K = (3 + 0.5) / 5 = 0.70`, so
`display_match_score = 100 * (0.70 * 0.80 + 0.30 * 0.70) = 77.0`.

### Semantic fit (`S`)

`S` is the cosine similarity between one embedding of the candidate's
matchable text and one embedding of the job's matchable text
(`app/modules/matching/text.py` builds both: summary, skills, titles,
organizations, experience and projects for a resume; title, company,
description, summary and requirement skills for a job). Both are embedded in
the same call to the shared `EmbeddingClient` (`app.core.inference` —
`DeterministicEmbeddingClient` locally/in tests, the SageMaker endpoint in
deployment), so they are always produced by the same model revision. Cosine is
clamped to zero rather than left negative — a negative similarity is not "half
a match" (`app/modules/matching/bi_encoder.py::cosine`).

This computes the embedding live at match time rather than reading a
persisted vector. Persisted, batch-retrievable job vectors are B-03's
job (`app/search/`); this scorer does not depend on them existing yet.

### Skill coverage (`K`) and the present/partial/missing rubric

`app/modules/matching/skills.py::compare_skills` produces one
`SkillComparison` per distinct skill the job mentions (required or preferred),
resolving both the job's skill name and the candidate's extracted skill names
through the same shared alias registry A-02 uses
(`app.nlp.skills.ALIASES`) — case-insensitively, and falling back to a plain
case-insensitive string match for skills the registry does not cover (e.g.
"AWS"). Duplicate requirement rows for the same resolved skill are merged into
one comparison; a skill required in any one row is treated as required.

- **`present`** — the job's skill resolves to a skill in
  `CandidateProfile.skills`. That list already contains only A-02's
  confidently-mentioned skills (not negated, not hedged/beginner-language —
  A-03 excludes both of those with a `SKILL_*_EXCLUDED` warning before the
  profile is built), so an exact/alias match here is the strongest evidence
  available at this layer.
- **`partial`** — this module's own first-draft rubric, not part of A-02/A-03:
  the skill's own name appears as a case-insensitive substring inside another
  evidenced part of the resume — an experience entry's title/organization, a
  project's name/description, or (if the profile carries top-level evidence)
  the free-text summary — without having been extracted as a standalone
  canonical skill. That is weaker evidence (a passing mention, not a listed
  competency), which is exactly what the 0.5 credit is meant to represent, and
  it is exactly the rule B-08 should stress-test against human judgment.
- **`missing`** — neither of the above. Absence means *not evidenced in the
  resume*, never "confirmed the candidate lacks it": nothing here fabricates
  resume evidence for a missing skill, and the shared contract's own validator
  (`SkillComparison.evidence_matches_state`) refuses a `missing` result that
  carries resume evidence.

`K`'s denominator is the count of distinct **required** skills only.
Preferred (`required=False`) skills still get a `SkillComparison` (so the UI
can show them), but do not enter `K`, and a missing preferred skill is not
reported as a `MatchResult.gap` (`strengths_and_gaps` filters gaps to
`required and state == "missing"`).

### No reliably extracted requirement

If a job posting has no requirements at all (extraction produced nothing, or
none yet — this can legitimately happen before B-02's job-NLP normalizes a raw
posting), `K` is not computed: the score is semantic fit alone,
`score_basis = "semantic_only"`, and `skill_coverage` is `null`. This is never
silently treated as `K = 1` or `K = 0` for an unknown denominator.

## What gets persisted

Every `MatchResult.score_components` (`app.contracts.models.ScoreComponents`)
records `semantic_fit`, `skill_coverage`, the weights actually used,
`score_basis`, the embedding model's reported `model_revision`, and this
module's `preprocessing_version` — so a later change to the text extraction or
the embedding model is visible on every future score without having to guess
which version produced an old one. `MatchResult.scoring_version` is the
formula version, `"semantic-skills-v1"`
(`app.modules.matching.scoring.SCORING_VERSION`); a future weight or
transformation change (B-05's cross-encoder/hybrid re-ranking, in particular)
must ship under a new `scoring_version` rather than silently reinterpreting
old stored scores.

Sorting for a ranked list uses the unrounded score with a stable job-id
tie-break before rounding for display (`app/orchestration/refresh.py`), so two
jobs that round to the same displayed percentage still have a deterministic
order.

## Known limitations (honest, not yet fixed)

- The `partial` rubric is a plain substring match, not NLP: it will both
  miss genuine paraphrases ("k8s" for "Kubernetes") and occasionally hit
  coincidental substrings. It is deliberately conservative in scope (checked
  only inside fields that already carry their own evidence) so that a
  `partial` result always has real evidence to show, not to claim linguistic
  accuracy.
- `S` is computed from whatever text extraction currently produces; it has
  not been evaluated against human relevance judgments. That comparison is
  B-08's job, using the keyword/TF-IDF/bi-encoder baselines in
  `app/modules/matching/{keyword,tfidf,bi_encoder}.py` alongside this scorer.
- A percentage from this formula is a fit index against one deterministic,
  documented calculation — not a hiring probability, and not a claim of model
  accuracy.
