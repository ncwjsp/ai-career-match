"""The labeling rubric and evaluation split model (B-08). No backend import."""

from rubric import RUBRIC_VERSION, EvaluationSplit, Label


def _label(candidate_id: str, job_id: str, relevant: bool) -> Label:
    return Label(candidate_id=candidate_id, job_id=job_id, relevant=relevant, labeled_by="tester")


def test_a_label_defaults_to_the_current_rubric_version():
    label = _label("cand-1", "job-1", True)

    assert label.rubric_version == RUBRIC_VERSION


def test_relevant_job_ids_returns_only_labels_marked_relevant_for_that_candidate():
    split = EvaluationSplit(
        split_id="split-1",
        candidate_ids=("cand-1", "cand-2"),
        job_pool_ids=("job-1", "job-2", "job-3"),
        labels=(
            _label("cand-1", "job-1", True),
            _label("cand-1", "job-2", False),
            _label("cand-2", "job-3", True),
        ),
    )

    assert split.relevant_job_ids("cand-1") == {"job-1"}
    assert split.relevant_job_ids("cand-2") == {"job-3"}


def test_relevant_job_ids_is_empty_for_an_unlabeled_candidate():
    split = EvaluationSplit(split_id="split-1", candidate_ids=("cand-1",), job_pool_ids=("job-1",))

    assert split.relevant_job_ids("cand-1") == set()
