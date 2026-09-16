"""The B-08 labeling rubric and fixed evaluation splits. Owner: M2 (B-08).

`RUBRIC` is the actual instruction text given to a human labeler (VAL-01).
Binary, not graded: precision/recall/F1 (what plan.md's B-08 asks this
harness to compute) are defined against binary relevance, and a graded scale
would need a different metric family (e.g. NDCG) this module does not
compute. Do not reword `RUBRIC` without bumping `RUBRIC_VERSION` -- a wording
change can shift what "relevant" means, so labels collected under different
wordings must stay distinguishable rather than silently pooled together.
"""

from __future__ import annotations

from dataclasses import dataclass, field

RUBRIC_VERSION = "binary-relevance-v1"

RUBRIC = """\
For the given candidate profile and job posting, mark exactly one:

  relevant     - A reasonable recruiter would forward this candidate to this
                 job's hiring team: the candidate's evidenced skills and
                 experience plausibly satisfy most of the job's *required*
                 skills, even if some preferred skills are missing.
  not_relevant - The candidate's evidenced skills/experience do not
                 plausibly satisfy the job's required skills, or the job is
                 in a substantially different domain or seniority than the
                 candidate's evidenced experience.

Judge only the resume evidence and job posting text actually shown. Never
assume a skill the candidate did not evidence, and never penalize a skill
the job posting does not actually require. When genuinely unsure, mark
not_relevant and say why in the comment field -- an unexplained "relevant"
is not usable evidence for comparing the five methods.
"""


@dataclass(frozen=True)
class Label:
    candidate_id: str
    job_id: str
    relevant: bool
    labeled_by: str
    comment: str | None = None
    rubric_version: str = RUBRIC_VERSION


@dataclass(frozen=True)
class EvaluationSplit:
    """One frozen, reproducible evaluation query set: which candidates to
    evaluate and the fixed job pool each is ranked against. Freezing both
    (not just the labels) is what makes a later re-run comparable to an
    earlier one -- a pool that silently grew or shrank between runs would
    make precision/recall differences meaningless."""

    split_id: str
    candidate_ids: tuple[str, ...]
    job_pool_ids: tuple[str, ...]
    labels: tuple[Label, ...] = field(default_factory=tuple)

    def relevant_job_ids(self, candidate_id: str) -> set[str]:
        return {
            label.job_id
            for label in self.labels
            if label.candidate_id == candidate_id and label.relevant
        }
