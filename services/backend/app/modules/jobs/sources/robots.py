"""robots.txt interpretation. Owner: M2 (B-01).

Kept separate from fetching robots.txt itself so it is fully testable with no
network at all: feed it text, get a decision. `verify_cli.py` is what
actually fetches a live robots.txt and calls this.

This answers only what robots.txt says. It is not a substitute for reading a
source's Terms of Service -- a host can permit crawling in robots.txt while
its ToS still forbids storing or redisplaying the content, which is exactly
what this project needs to do.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.robotparser import RobotFileParser


@dataclass(frozen=True)
class RobotsDecision:
    allowed: bool
    crawl_delay: float | None


def evaluate(robots_txt: str, user_agent: str, path: str) -> RobotsDecision:
    """`robots_txt` is the file's raw text; `path` is a URL path (e.g. "/jobs/123")."""
    parser = RobotFileParser()
    parser.parse(robots_txt.splitlines())
    return RobotsDecision(
        allowed=parser.can_fetch(user_agent, path),
        crawl_delay=parser.crawl_delay(user_agent),
    )
