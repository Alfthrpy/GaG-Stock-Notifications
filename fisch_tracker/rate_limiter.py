"""Paces requests to Roblox's public server-list API.

That endpoint publishes no official rate limit, but live responses were
observed carrying `x-ratelimit-remaining` / `x-ratelimit-reset` headers
(observed live: `x-ratelimit-limit: 3, 3;w=60`, i.e. ~3 requests per 60s
sliding window). Rather than hardcoding that number -- which may differ
by IP/deployment -- this reads the real headers on every response and
paces the next request accordingly.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Mapping


@dataclass(frozen=True)
class RateLimitStatus:
    remaining: int
    reset_seconds: float


def parse_rate_limit_headers(headers: Mapping[str, str]) -> RateLimitStatus | None:
    remaining = headers.get("x-ratelimit-remaining")
    reset = headers.get("x-ratelimit-reset")
    if remaining is None or reset is None:
        return None
    try:
        return RateLimitStatus(remaining=int(remaining), reset_seconds=float(reset))
    except ValueError:
        return None


class AdaptiveRateLimiter:
    """Tracks the server's own rate-limit headers and tells callers how
    long to wait before the next request. One instance should be shared
    across a whole process's lifetime (not recreated per sweep), since
    the budget is global to the API key/IP, not per sweep.
    """

    def __init__(self, min_gap_seconds: float = 1.0, safety_margin: int = 0):
        self._min_gap_seconds = min_gap_seconds
        self._safety_margin = safety_margin
        self._status: RateLimitStatus | None = None
        self._status_observed_at: float | None = None
        self._last_request_at: float | None = None

    def update(self, headers: Mapping[str, str], now: float | None = None) -> None:
        status = parse_rate_limit_headers(headers)
        if status is None:
            return
        self._status = status
        self._status_observed_at = now if now is not None else time.monotonic()

    def record_request(self, now: float | None = None) -> None:
        self._last_request_at = now if now is not None else time.monotonic()

    def seconds_until_next_request(self, now: float | None = None) -> float:
        now = now if now is not None else time.monotonic()
        wait = 0.0

        if self._last_request_at is not None:
            wait = max(wait, self._min_gap_seconds - (now - self._last_request_at))

        if self._status is not None and self._status.remaining <= self._safety_margin:
            elapsed = now - self._status_observed_at
            wait = max(wait, self._status.reset_seconds - elapsed)

        return max(wait, 0.0)

    async def wait(
        self,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        delay = self.seconds_until_next_request(clock())
        if delay > 0:
            await sleep(delay)
