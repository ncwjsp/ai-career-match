"""Session scope is the only thing authorizing candidate-scoped reads."""

import pytest

from app.core.errors import Forbidden
from app.db.app.sessions import SqlSessionStore


@pytest.fixture
def store(app_session_factory, clock):
    return SqlSessionStore(app_session_factory, clock, retention_days=30)


def test_each_session_gets_its_own_candidate(store):
    first_session, first_candidate = store.start()
    second_session, second_candidate = store.start()
    assert first_session != second_session
    assert first_candidate != second_candidate


def test_a_session_token_is_not_derived_from_the_candidate_id(store):
    session_id, candidate_id = store.start()
    assert candidate_id not in session_id
    assert len(session_id) >= 32


def test_a_returning_session_still_resolves(store, clock):
    session_id, candidate_id = store.start()
    clock.advance(60 * 60 * 24 * 7)
    assert store.resolve(session_id) == candidate_id


def test_an_expired_or_unknown_token_resolves_to_nothing(store, clock):
    session_id, _ = store.start()
    clock.advance(60 * 60 * 24 * 31)
    assert store.resolve(session_id) is None
    assert store.resolve("not-a-session") is None
    assert store.resolve(None) is None


def test_one_session_cannot_read_another_candidate(store):
    session_id, _ = store.start()
    _, other_candidate = store.start()
    with pytest.raises(Forbidden):
        store.require_candidate(session_id, other_candidate)


def test_the_refusal_message_does_not_distinguish_unknown_from_foreign(store):
    session_id, _ = store.start()
    _, other_candidate = store.start()
    with pytest.raises(Forbidden) as foreign:
        store.require_candidate(session_id, other_candidate)
    with pytest.raises(Forbidden) as unknown:
        store.require_candidate("not-a-session", other_candidate)
    assert str(foreign.value) == str(unknown.value)


def test_an_authorized_read_returns_the_candidate(store):
    session_id, candidate_id = store.start()
    assert store.require_candidate(session_id, candidate_id) == candidate_id
