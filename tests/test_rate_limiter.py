import asyncio

import pytest

from fisch_tracker.rate_limiter import AdaptiveRateLimiter, parse_rate_limit_headers


def test_parse_rate_limit_headers_reads_remaining_and_reset():
    headers = {"x-ratelimit-limit": "3, 3;w=60", "x-ratelimit-remaining": "2", "x-ratelimit-reset": "36"}

    status = parse_rate_limit_headers(headers)

    assert status.remaining == 2
    assert status.reset_seconds == 36.0


def test_parse_rate_limit_headers_returns_none_when_missing():
    assert parse_rate_limit_headers({}) is None


def test_parse_rate_limit_headers_returns_none_when_not_numeric():
    headers = {"x-ratelimit-remaining": "not-a-number", "x-ratelimit-reset": "36"}

    assert parse_rate_limit_headers(headers) is None


def test_first_request_has_no_wait():
    limiter = AdaptiveRateLimiter(min_gap_seconds=1.0)

    assert limiter.seconds_until_next_request(now=100.0) == 0.0


def test_min_gap_enforced_between_requests_even_without_headers():
    limiter = AdaptiveRateLimiter(min_gap_seconds=1.0)
    limiter.record_request(now=100.0)

    assert limiter.seconds_until_next_request(now=100.4) == pytest.approx(0.6)


def test_waits_out_the_reset_window_when_budget_exhausted():
    limiter = AdaptiveRateLimiter(min_gap_seconds=0.0, safety_margin=0)
    limiter.update({"x-ratelimit-remaining": "0", "x-ratelimit-reset": "30"}, now=100.0)

    assert limiter.seconds_until_next_request(now=105.0) == 25.0


def test_no_wait_when_remaining_above_safety_margin():
    limiter = AdaptiveRateLimiter(min_gap_seconds=0.0, safety_margin=0)
    limiter.update({"x-ratelimit-remaining": "2", "x-ratelimit-reset": "30"}, now=100.0)

    assert limiter.seconds_until_next_request(now=101.0) == 0.0


def test_update_ignores_headers_without_rate_limit_info():
    limiter = AdaptiveRateLimiter(min_gap_seconds=0.0, safety_margin=0)
    limiter.update({"x-ratelimit-remaining": "0", "x-ratelimit-reset": "30"}, now=100.0)
    limiter.update({}, now=101.0)

    # still governed by the last known real status, not reset by the empty update
    assert limiter.seconds_until_next_request(now=105.0) == 25.0


def test_wait_sleeps_for_the_computed_delay():
    limiter = AdaptiveRateLimiter(min_gap_seconds=0.0, safety_margin=0)
    limiter.update({"x-ratelimit-remaining": "0", "x-ratelimit-reset": "10"}, now=100.0)

    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    asyncio.run(limiter.wait(sleep=fake_sleep, clock=lambda: 100.0))

    assert sleeps == [10.0]


def test_wait_does_not_sleep_when_no_delay_needed():
    limiter = AdaptiveRateLimiter(min_gap_seconds=0.0)

    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    asyncio.run(limiter.wait(sleep=fake_sleep, clock=lambda: 100.0))

    assert sleeps == []
