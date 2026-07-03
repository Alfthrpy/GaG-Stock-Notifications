"""Async client for Roblox's public game-server list API.

Roblox never exposes a server's creation time, so this module only
handles fetching the live list of public servers for a place. Age
estimation (via first-seen tracking) lives in `tracker.py`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

SERVERS_URL = "https://games.roblox.com/v1/games/{place_id}/servers/Public"


class RobloxApiError(Exception):
    def __init__(self, status: int, body: str):
        super().__init__(f"Roblox API returned status {status}: {body}")
        self.status = status


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


@retry(
    retry=retry_if_exception_type((RobloxApiError, ConnectionError, TimeoutError)),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=0.5, max=8),
    reraise=True,
)
async def fetch_servers_page(
    session: Any, place_id: int, cursor: str | None = None, limit: int = 100
) -> tuple[list[ServerInstance], str | None]:
    """Fetch a single page of public servers. Returns (servers, next_cursor)."""
    url = SERVERS_URL.format(place_id=place_id)
    params: dict[str, Any] = {"sortOrder": "Asc", "limit": limit}
    if cursor:
        params["cursor"] = cursor

    async with session.get(url, params=params) as resp:
        if resp.status != 200:
            body = await resp.text()
            raise RobloxApiError(resp.status, body)
        payload = await resp.json()

    servers = [_parse_server(item) for item in payload.get("data", [])]
    next_cursor = payload.get("nextPageCursor") or None
    return servers, next_cursor


async def fetch_all_public_servers(
    session: Any, place_id: int, limit: int = 100, max_pages: int = 500
) -> list[ServerInstance]:
    """Walk the full cursor chain and return every public server instance.

    Cursor pagination is inherently sequential (each page's cursor is only
    known after the previous page's response), so pages cannot be fetched
    concurrently for a single place.
    """
    servers: list[ServerInstance] = []
    cursor: str | None = None

    for _ in range(max_pages):
        page_servers, cursor = await fetch_servers_page(session, place_id, cursor=cursor, limit=limit)
        servers.extend(page_servers)
        if not cursor:
            break

    return servers
