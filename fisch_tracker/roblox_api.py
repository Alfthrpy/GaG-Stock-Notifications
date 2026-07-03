"""Async client for Roblox's public game-server list API.

Roblox never exposes a server's creation time, so this module only
handles fetching the live list of public servers for a place. Age
estimation (via first-seen tracking) lives in `tracker.py`.

Two undocumented constraints observed live against this endpoint:
- Rate limit: `x-ratelimit-limit: 3, 3;w=60` (~3 requests/60s sliding
  window), signaled via x-ratelimit-remaining/x-ratelimit-reset
  response headers. See rate_limiter.AdaptiveRateLimiter, which reads
  these headers instead of hardcoding the number.
- Hard population cap: cursor pagination stops (nextPageCursor: null)
  after ~700 servers (7 pages of 100), even when more servers exist.
  max_pages defaults just above that cap.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .rate_limiter import AdaptiveRateLimiter, parse_rate_limit_headers

_logger = logging.getLogger(__name__)

SERVERS_URL = "https://games.roblox.com/v1/games/{place_id}/servers/Public"

# Observed hard cap is ~700 servers / 7 pages; a small buffer above that
# is enough since the API refuses to paginate further regardless.
DEFAULT_MAX_PAGES = 10

_DEFAULT_RETRY_AFTER_SECONDS = 65.0


class RobloxApiError(Exception):
    def __init__(self, status: int, body: str):
        super().__init__(f"Roblox API returned status {status}: {body}")
        self.status = status


class RobloxRateLimitedError(RobloxApiError):
    def __init__(self, status: int, body: str, retry_after: float):
        super().__init__(status, body)
        self.retry_after = retry_after


@dataclass(frozen=True)
class ServerInstance:
    job_id: str
    playing: int
    max_players: int
    fps: float | None = None
    ping: float | None = None


def _parse_server(raw: dict[str, Any]) -> ServerInstance:
    return ServerInstance(
        job_id=raw["id"],
        playing=raw.get("playing", 0),
        max_players=raw.get("maxPlayers", 0),
        fps=raw.get("fps"),
        ping=raw.get("ping"),
    )


def _header_get(headers: Mapping[str, str], name: str) -> str | None:
    if name in headers:
        return headers[name]
    lower = name.lower()
    for key, value in headers.items():
        if key.lower() == lower:
            return value
    return None


def _parse_retry_after(headers: Mapping[str, str]) -> float:
    raw = _header_get(headers, "Retry-After")
    if raw is not None:
        try:
            return float(raw)
        except ValueError:
            pass

    status = parse_rate_limit_headers(headers)
    if status is not None:
        return status.reset_seconds

    return _DEFAULT_RETRY_AFTER_SECONDS


def _wait_strategy(retry_state):
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if isinstance(exc, RobloxRateLimitedError):
        return exc.retry_after
    return wait_exponential(multiplier=0.5, max=8)(retry_state)


@retry(
    retry=retry_if_exception_type((RobloxApiError, ConnectionError, TimeoutError)),
    stop=stop_after_attempt(4),
    wait=_wait_strategy,
    reraise=True,
)
async def fetch_servers_page(
    session: Any,
    place_id: int,
    cursor: str | None = None,
    limit: int = 100,
    rate_limiter: AdaptiveRateLimiter | None = None,
) -> tuple[list[ServerInstance], str | None]:
    """Fetch a single page of public servers. Returns (servers, next_cursor)."""
    if rate_limiter is not None:
        await rate_limiter.wait()

    url = SERVERS_URL.format(place_id=place_id)
    params: dict[str, Any] = {"sortOrder": "Asc", "limit": limit}
    if cursor:
        params["cursor"] = cursor

    async with session.get(url, params=params) as resp:
        headers = getattr(resp, "headers", {})
        if rate_limiter is not None:
            rate_limiter.update(headers)
            rate_limiter.record_request()

        if resp.status == 429:
            body = await resp.text()
            raise RobloxRateLimitedError(resp.status, body, _parse_retry_after(headers))
        if resp.status != 200:
            body = await resp.text()
            raise RobloxApiError(resp.status, body)
        payload = await resp.json()

    servers = [_parse_server(item) for item in payload.get("data", [])]
    next_cursor = payload.get("nextPageCursor") or None
    return servers, next_cursor


async def fetch_all_public_servers(
    session: Any,
    place_id: int,
    rate_limiter: AdaptiveRateLimiter | None = None,
    limit: int = 100,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> list[ServerInstance]:
    """Walk the cursor chain and return every public server instance seen
    (bounded by max_pages, since Roblox caps pagination around 700
    servers / 7 pages anyway).

    Cursor pagination is inherently sequential (each page's cursor is only
    known after the previous page's response), so pages cannot be fetched
    concurrently for a single place.
    """
    servers: list[ServerInstance] = []
    cursor: str | None = None

    for page_number in range(1, max_pages + 1):
        page_servers, cursor = await fetch_servers_page(
            session, place_id, cursor=cursor, limit=limit, rate_limiter=rate_limiter
        )
        servers.extend(page_servers)
        if max_pages > 1:
            _logger.info("page %d: +%d servers (%d so far)", page_number, len(page_servers), len(servers))
        if not cursor:
            break

    return servers
