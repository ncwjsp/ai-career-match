"""robots.txt interpretation (B-01). Text fed in directly; no network."""

from app.modules.jobs.sources.robots import evaluate


def test_an_explicit_disallow_for_the_path_is_not_allowed():
    robots_txt = "User-agent: *\nDisallow: /jobs/\n"

    decision = evaluate(robots_txt, "ai-career-match-job-source/0.1", "/jobs/123")

    assert decision.allowed is False


def test_a_path_outside_any_disallow_rule_is_allowed():
    robots_txt = "User-agent: *\nDisallow: /admin/\n"

    decision = evaluate(robots_txt, "ai-career-match-job-source/0.1", "/jobs/123")

    assert decision.allowed is True


def test_an_empty_robots_txt_allows_everything():
    decision = evaluate("", "ai-career-match-job-source/0.1", "/jobs/123")

    assert decision.allowed is True


def test_disallow_all_blocks_everything():
    robots_txt = "User-agent: *\nDisallow: /\n"

    decision = evaluate(robots_txt, "ai-career-match-job-source/0.1", "/jobs/123")

    assert decision.allowed is False


def test_a_rule_scoped_to_a_different_user_agent_does_not_apply():
    robots_txt = "User-agent: SomeOtherBot\nDisallow: /jobs/\nUser-agent: *\nAllow: /\n"

    decision = evaluate(robots_txt, "ai-career-match-job-source/0.1", "/jobs/123")

    assert decision.allowed is True


def test_crawl_delay_is_reported_when_declared():
    robots_txt = "User-agent: *\nCrawl-delay: 5\nDisallow:\n"

    decision = evaluate(robots_txt, "ai-career-match-job-source/0.1", "/jobs/123")

    assert decision.crawl_delay == 5


def test_crawl_delay_is_none_when_not_declared():
    robots_txt = "User-agent: *\nDisallow:\n"

    decision = evaluate(robots_txt, "ai-career-match-job-source/0.1", "/jobs/123")

    assert decision.crawl_delay is None
