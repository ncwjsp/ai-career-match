"""The durable worker loop. Owner: M3 (C-01/C-08).

A plain polling process, not a scheduler: it claims one event at a time from the
`career_app` queue, hands it to `MatchService`, then acknowledges or retries.
`run_forever` is what a deployed worker service runs; `run_until_idle` is the
same loop with a stop condition, which is what tests and an operator command use.

Startup runs a reconciliation pass so that anything left inflight by a crash,
and any outbox event that was committed but never dispatched, is picked up
without an external cron.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from app.contracts.models import ReconciliationEvent
from app.core.clock import Clock
from app.core.ids import new_id
from app.db.app.queue import SqlMatchQueue
from app.orchestration.job_events import MatchService, OutboxDispatcher

logger = logging.getLogger(__name__)


class MatchWorker:
    def __init__(
        self,
        queue: SqlMatchQueue,
        service: MatchService,
        clock: Clock,
        dispatcher: OutboxDispatcher | None = None,
        poll_seconds: float = 1.0,
    ):
        self._queue = queue
        self._service = service
        self._clock = clock
        self._dispatcher = dispatcher
        self._poll_seconds = poll_seconds

    def recover(self) -> None:
        """Startup pass: drain the outbox, then re-publish anything left stale."""
        if self._dispatcher is not None:
            self._dispatcher.dispatch_once()
        self._queue.enqueue(
            ReconciliationEvent(
                event_id=new_id("evt-reconcile"),
                event_type="reconciliation.requested",
                occurred_at=self._clock.now(),
            )
        )

    def step(self) -> bool:
        """Handle at most one event. False means the queue had nothing due."""
        if self._dispatcher is not None:
            self._dispatcher.dispatch_once()
        event = self._queue.claim()
        if event is None:
            return False
        try:
            self._service.handle(event)
        except Exception:
            # The message itself may quote resume or job text, so it stays in the
            # log rather than in the retry record, and the queue bounds the retries.
            logger.exception("Event %s failed; scheduling a retry.", event.event_id)
            self._queue.retry(event.event_id, "handler raised")
            return True
        self._queue.acknowledge(event.event_id)
        return True

    def run_until_idle(self, max_events: int = 1000) -> int:
        handled = 0
        while handled < max_events and self.step():
            handled += 1
        return handled

    def run_forever(  # pragma: no cover - the deployed loop
        self, should_stop: Callable[[], bool] | None = None
    ) -> None:
        stop = should_stop or (lambda: False)
        self.recover()
        while not stop():
            if not self.step():
                time.sleep(self._poll_seconds)
