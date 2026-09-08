"""Cached grounded explanations. Owner: M3 (C-02).

An explanation is cached per candidate/revision/job, so regenerating it after a
new revision is deliberate rather than accidental, and a cached text can never
be shown beside a ranking it was not written for. Nothing here feeds scoring:
the row is written *after* the score and skill states exist.
"""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.contracts.models import MatchExplanation
from app.core.clock import Clock
from app.core.timeutil import to_storage_utc
from app.db.app.models import ExplanationRow


class SqlExplanationStore:
    def __init__(self, factory: sessionmaker[Session], clock: Clock):
        self._factory = factory
        self._clock = clock

    def get(self, candidate_id: str, revision: int, job_id: str) -> MatchExplanation | None:
        with self._factory() as session:
            row = session.get(ExplanationRow, (candidate_id, revision, job_id))
            return MatchExplanation.model_validate(row.payload) if row is not None else None

    def put(self, explanation: MatchExplanation) -> None:
        now = to_storage_utc(self._clock.now())
        key = (explanation.candidate_id, explanation.revision, explanation.job_id)
        payload = explanation.model_dump(mode="json")
        with self._factory() as session:
            row = session.get(ExplanationRow, key)
            if row is None:
                session.add(
                    ExplanationRow(
                        candidate_id=explanation.candidate_id,
                        revision=explanation.revision,
                        job_id=explanation.job_id,
                        state=explanation.state,
                        payload=payload,
                        prompt_version=explanation.prompt_version,
                        model_version=explanation.model_version,
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                row.state = explanation.state
                row.payload = payload
                row.prompt_version = explanation.prompt_version
                row.model_version = explanation.model_version
                row.updated_at = now
            session.commit()
