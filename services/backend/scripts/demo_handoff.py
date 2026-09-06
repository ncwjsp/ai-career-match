"""Run both matching triggers using fixed fixtures; never reads a resume or network."""

import json
from datetime import UTC, datetime

from app.testing.adapters import FixtureMatcher
from app.testing.fixtures import load_fixtures
from app.testing.harness import FixtureMatchHarness
from app.testing.memory import MemoryJobs, MemoryMatches, MemoryProfiles


def main() -> None:
    fixtures = load_fixtures()
    profiles = MemoryProfiles(fixtures.profiles)
    jobs = MemoryJobs(fixtures.jobs[:1])
    matches = MemoryMatches()
    harness = FixtureMatchHarness(
        profiles, jobs, matches, FixtureMatcher(fixtures), datetime(2026, 9, 5, tzinfo=UTC)
    )
    first = harness.handle(fixtures.events[0])
    jobs.save_with_event(fixtures.jobs[1], fixtures.events[1])
    second = harness.handle(jobs.pending()[0])
    print(
        json.dumps(
            {
                "mode": "fixture",
                "clock": "2026-09-05T00:00:00Z (fixed for repeatability)",
                "profile_ready_jobs": [match.job_id for match in first],
                "new_job_matches": [match.job_id for match in second],
                "stored_pair_scores": {
                    result.job_id: result.score
                    for result in matches.list_for_candidate("candidate-demo", 1)
                },
                "retained_profile_unchanged": profiles.get("candidate-demo")
                == fixtures.profiles[0],
                "resume_uploads": 0,
                "warning": (
                    "Scores are fixture lookups. No NLP, ranking or durable worker is implemented."
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
