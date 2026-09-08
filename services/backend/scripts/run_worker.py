"""The worker service entry point. Owner: M3 (C-01/C-06).

Deployment runs `python -m scripts.run_worker`. It builds the container, drains
M2's job-change outbox into the durable queue, and consumes events until it is
stopped. There is no cron and no scheduler: this process is the consumer, so a
sleeping worker means pending work simply waits.

The matcher is M2's (B-04/B-06). Until it exists this entry point refuses to
start rather than substituting a fixture scorer, because a worker that silently
published synthetic scores would be worse than one that does not run.
"""

from __future__ import annotations

import logging
import signal
import sys

from app.core.container import Container
from app.core.settings import Settings
from app.orchestration.worker import MatchWorker

logger = logging.getLogger("worker")


def load_matcher():
    """Import M2's matcher, or explain precisely what is missing."""
    try:
        from app.modules.matching.scoring import Matcher  # type: ignore[attr-defined]
    except ImportError as error:
        raise SystemExit(
            "No matcher is available: app.modules.matching.scoring.Matcher is not "
            "implemented yet (B-04/B-06). The worker will not start with a fixture "
            "scorer, because published scores must not be synthetic.\n"
            f"Import error: {error}"
        ) from error
    return Matcher()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings()
    settings.validate_for_runtime()
    container = Container(settings=settings)
    worker = MatchWorker(
        container.match_queue,
        container.match_service(load_matcher()),
        container.clock,
        container.dispatcher,
    )

    stopping = False

    def stop(signum, _frame):
        nonlocal stopping
        logger.info("Signal %s received; finishing the current event.", signum)
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    logger.info("Worker started in %s mode.", settings.app_mode)
    worker.run_forever(should_stop=lambda: stopping)
    logger.info("Worker stopped cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
