"""Pair scores and the immutability of a published ranking."""

import pytest

from app.core.errors import ConflictError
from app.db.app.matches import SqlMatchRepository, SqlRecommendationRepository
from app.db.app.sessions import SqlSessionStore
from tests.app.factories import make_match, make_recommendation_set


@pytest.fixture
def matches(app_session_factory):
    return SqlMatchRepository(app_session_factory)


@pytest.fixture
def recommendations(app_session_factory, clock):
    return SqlRecommendationRepository(app_session_factory, clock)


@pytest.fixture
def candidate(app_session_factory, clock):
    return SqlSessionStore(app_session_factory, clock).start()[1]


def test_a_pair_score_round_trips(matches):
    result = make_match()
    matches.upsert(result)
    assert matches.list_for_candidate("cand-1", 1) == [result]


def test_reprocessing_the_same_pair_does_not_duplicate_it(matches):
    matches.upsert(make_match())
    matches.upsert(make_match())
    assert matches.count_for_candidate("cand-1", 1) == 1


def test_a_new_scoring_version_is_stored_beside_the_old_one(matches):
    matches.upsert(make_match(score=77.0))
    matches.upsert(make_match(score=81.0, scoring_version="hybrid-v2"))
    assert matches.count_for_candidate("cand-1", 1) == 2


def test_a_new_job_version_is_a_separate_score(matches):
    matches.upsert(make_match(job_version=1))
    matches.upsert(make_match(job_version=2, score=80.0))
    assert matches.count_for_candidate("cand-1", 1) == 2


def test_results_come_back_highest_first_with_a_stable_tie_break(matches):
    matches.upsert(make_match(job_id="job-b", score=80.0))
    matches.upsert(make_match(job_id="job-a", score=80.0))
    matches.upsert(make_match(job_id="job-c", score=91.0))
    assert [r.job_id for r in matches.list_for_candidate("cand-1", 1)] == [
        "job-c",
        "job-a",
        "job-b",
    ]


def test_removing_a_job_drops_only_that_job(matches):
    matches.upsert(make_match(job_id="job-1"))
    matches.upsert(make_match(job_id="job-2"))
    matches.remove_job("job-1")
    assert [r.job_id for r in matches.list_for_candidate("cand-1", 1)] == ["job-2"]


def test_a_replaced_profile_keeps_its_own_results(matches):
    matches.upsert(make_match(profile_version=1))
    matches.upsert(make_match(profile_version=2, score=88.0))
    assert matches.count_for_candidate("cand-1", 1) == 1
    assert matches.list_for_candidate("cand-1", 2)[0].score == 88.0


def test_nothing_is_published_before_the_first_revision(recommendations):
    assert recommendations.latest("cand-1") is None
    assert recommendations.next_revision("cand-1") == 1


def test_a_published_revision_reads_back_ranked(recommendations):
    published = make_recommendation_set(jobs=("job-1", "job-2"))
    recommendations.publish(published)
    latest = recommendations.latest("cand-1")
    assert latest.revision == 1
    assert [r.rank for r in latest.results] == [1, 2]
    assert [r.job_id for r in latest.results] == ["job-1", "job-2"]


def test_a_new_revision_replaces_what_the_browser_sees(recommendations):
    recommendations.publish(make_recommendation_set(revision=1, jobs=("job-1",)))
    recommendations.publish(make_recommendation_set(revision=2, jobs=("job-1", "job-9")))
    assert recommendations.latest("cand-1").revision == 2
    assert len(recommendations.latest("cand-1").results) == 2
    # The earlier revision is still readable, so an in-flight page stays coherent.
    assert len(recommendations.get("cand-1", 1).results) == 1


def test_republishing_the_same_revision_is_a_no_op(recommendations):
    published = make_recommendation_set(revision=1, jobs=("job-1",))
    recommendations.publish(published)
    recommendations.publish(published)
    assert recommendations.latest("cand-1").revision == 1


def test_replaying_an_older_revision_leaves_the_newest_one_visible(recommendations):
    recommendations.publish(make_recommendation_set(revision=1, jobs=("job-1",)))
    recommendations.publish(make_recommendation_set(revision=2, jobs=("job-1", "job-2")))
    # An out-of-order redelivery of revision 1 is an identical no-op, not a rollback.
    recommendations.publish(make_recommendation_set(revision=1, jobs=("job-1",)))
    assert recommendations.latest("cand-1").revision == 2


def test_a_never_published_revision_behind_the_newest_one_is_refused(recommendations):
    recommendations.publish(make_recommendation_set(revision=1, jobs=("job-1",)))
    recommendations.publish(make_recommendation_set(revision=3, jobs=("job-1", "job-2")))
    with pytest.raises(ConflictError, match="behind"):
        recommendations.publish(make_recommendation_set(revision=2, jobs=("job-9",)))
    assert recommendations.latest("cand-1").revision == 3


def test_changing_a_published_revision_is_refused(recommendations):
    recommendations.publish(make_recommendation_set(revision=1, jobs=("job-1",)))
    with pytest.raises(ConflictError, match="different content"):
        recommendations.publish(make_recommendation_set(revision=1, jobs=("job-1", "job-2")))


def test_refresh_state_marks_an_in_flight_update(recommendations):
    recommendations.publish(make_recommendation_set(revision=1, jobs=("job-1",)))
    recommendations.set_refresh_state("cand-1", "pending")
    assert recommendations.latest("cand-1").refresh_state == "pending"


def test_two_candidates_number_their_revisions_independently(recommendations):
    recommendations.publish(make_recommendation_set("cand-1", revision=1, jobs=("job-1",)))
    recommendations.publish(make_recommendation_set("cand-1", revision=2, jobs=("job-1",)))
    assert recommendations.next_revision("cand-2") == 1
