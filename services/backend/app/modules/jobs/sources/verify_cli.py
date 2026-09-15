"""One-command job-source verification helper. Owner: M2 (B-01).

This sandboxed session's network egress to external job/career sites is
blocked by organization policy (see docs/job-sources/REGISTER.md for how that
was confirmed) -- so B-01's live checks could not be completed here. Run this
from a machine with normal network access to do them in one command instead
of by hand:

    uv run python -m app.modules.jobs.sources.verify_cli https://boards.greenhouse.io \
        --path /some-company/jobs/123 \
        --fetch-sample https://boards.greenhouse.io/some-company/jobs/123

It fetches and prints the host's live robots.txt, evaluates it for one path
via robots.py, and (with --fetch-sample) attempts the one real retrieval
plan.md's B-01 acceptance bar asks for. It does **not** read Terms of
Service or decide policy -- robots.txt allowing a fetch is necessary, not
sufficient, and a human still has to read the current ToS before recording a
source as approved in docs/job-sources/REGISTER.md.

Not in services/backend/scripts/ (M3's owned path per
docs/integration/OWNERSHIP.md) -- this lives with the rest of B-01's source
code and runs as a module instead.
"""

from __future__ import annotations

import argparse
import sys
from urllib.parse import urlparse

from app.modules.jobs.sources.fetch import SourceFetchError, UrllibTransport, fetch_single_posting
from app.modules.jobs.sources.robots import evaluate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", help="e.g. https://boards.greenhouse.io")
    parser.add_argument("--path", default="/", help="path to check robots.txt permission for")
    parser.add_argument("--user-agent", default="ai-career-match-job-source/0.1")
    parser.add_argument(
        "--fetch-sample",
        metavar="URL",
        help="also try fetching this exact posting URL as the real-retrieval evidence",
    )
    args = parser.parse_args(argv)

    host = urlparse(args.base_url).hostname
    if not host:
        print(f"Could not parse a host from {args.base_url!r}", file=sys.stderr)
        return 2

    transport = UrllibTransport()
    robots_url = f"https://{host}/robots.txt"
    print(f"Fetching {robots_url} ...")
    try:
        status, _content_type, body = transport.get(robots_url, timeout=10.0)
    except SourceFetchError as error:
        print(f"FAILED to fetch robots.txt: {error}", file=sys.stderr)
        return 1

    if status >= 400:
        print(
            f"robots.txt returned HTTP {status}; treated as no crawl rules declared. "
            "That is NOT the same as the Terms of Service permitting automated retrieval "
            "-- read the ToS by hand regardless."
        )
        robots_text = ""
    else:
        robots_text = body.decode("utf-8", errors="replace")
        print(f"--- {robots_url} ---\n{robots_text}--- end robots.txt ---")

    decision = evaluate(robots_text, args.user_agent, args.path)
    print(f"\ncan_fetch({args.user_agent!r}, {args.path!r}) = {decision.allowed}")
    if decision.crawl_delay is not None:
        print(f"Declared crawl-delay: {decision.crawl_delay}s")

    if args.fetch_sample:
        print(f"\nFetching sample posting {args.fetch_sample} ...")
        try:
            page = fetch_single_posting(args.fetch_sample, frozenset({host}), transport=transport)
        except SourceFetchError as error:
            print(f"FAILED: {error}", file=sys.stderr)
            return 1
        print(f"HTTP {page.status_code}, {page.content_type}, {len(page.body)} chars")
        print("^ this is the 'one successful real retrieval' evidence for the register.")

    print(
        "\nReminder: this checked robots.txt and reachability only. Read the source's "
        "current Terms of Service before recording it as approved in "
        "docs/job-sources/REGISTER.md."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
