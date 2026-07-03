import asyncio

import pytest

from fisch_tracker.roblox_api import (
    RobloxApiError,
    RobloxRateLimitedError,
    _parse_retry_after,
    _wait_strategy,
    fetch_all_public_servers,
    fetch_servers_page,
)


class FakeResponse:
    def __init__(self, status: int, payload: dict | None = None, text: str = "", headers: dict | None = None):
        self.status = status
        self._payload = payload or {}
        self._text = text
        self.headers = headers or {}

    async def json(self):
        return self._payload

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


class FakeSession:
    """Test double for aiohttp.ClientSession.get, returns queued responses in order."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def get(self, url, params=None):
        self.calls.append({"url": url, "params": params})
        return self._responses.pop(0)


class FakeRateLimiter:
    def __init__(self):
        self.waited = False
        self.updated_with = None
        self.recorded = False

    async def wait(self):
        self.waited = True

    def update(self, headers):
        self.updated_with = headers

    def record_request(self):
        self.recorded = True


class FakeOutcome:
    def __init__(self, exc):
        self._exc = exc

    def exception(self):
        return self._exc


class FakeRetryState:
    def __init__(self, exc, attempt_number=1):
        self.outcome = FakeOutcome(exc)
        self.attempt_number = attempt_number


def test_fetch_servers_page_parses_data_and_next_cursor():
    payload = {
        "data": [
            {"id": "job-1", "playing": 3, "maxPlayers": 8, "fps": 60.0, "ping": 45},
            {"id": "job-2", "playing": 1, "maxPlayers": 8, "fps": 59.5, "ping": 80},
        ],
        "nextPageCursor": "cursor-abc",
    }
    session = FakeSession([FakeResponse(200, payload)])

    servers, next_cursor = asyncio.run(fetch_servers_page(session, place_id=123))

    assert next_cursor == "cursor-abc"
    assert [s.job_id for s in servers] == ["job-1", "job-2"]
    assert servers[0].playing == 3
    assert servers[0].max_players == 8
    assert servers[0].fps == 60.0
    assert servers[0].ping == 45

    call = session.calls[0]
    assert call["url"] == "https://games.roblox.com/v1/games/123/servers/Public"
    assert call["params"]["sortOrder"] == "Asc"


def test_fetch_servers_page_sends_cursor_when_given():
    payload = {"data": [], "nextPageCursor": None}
    session = FakeSession([FakeResponse(200, payload)])

    asyncio.run(fetch_servers_page(session, place_id=123, cursor="cursor-xyz"))

    assert session.calls[0]["params"]["cursor"] == "cursor-xyz"


def test_fetch_servers_page_raises_on_non_200_after_exhausting_retries():
    session = FakeSession([FakeResponse(500, {}, "server error")] * 4)

    with pytest.raises(RobloxApiError):
        asyncio.run(fetch_servers_page(session, place_id=123))

    assert len(session.calls) == 4


def test_fetch_servers_page_retries_and_recovers():
    payload = {"data": [{"id": "job-1", "playing": 1, "maxPlayers": 8}], "nextPageCursor": None}
    session = FakeSession(
        [
            FakeResponse(500, {}, "boom"),
            FakeResponse(200, payload),
        ]
    )

    servers, next_cursor = asyncio.run(fetch_servers_page(session, place_id=123))

    assert len(session.calls) == 2
    assert servers[0].job_id == "job-1"
    assert next_cursor is None


def test_fetch_all_public_servers_walks_every_page():
    page1 = {
        "data": [{"id": "job-1", "playing": 1, "maxPlayers": 8}],
        "nextPageCursor": "page-2",
    }
    page2 = {
        "data": [{"id": "job-2", "playing": 2, "maxPlayers": 8}],
        "nextPageCursor": None,
    }
    session = FakeSession([FakeResponse(200, page1), FakeResponse(200, page2)])

    servers = asyncio.run(fetch_all_public_servers(session, place_id=123))

    assert [s.job_id for s in servers] == ["job-1", "job-2"]
    assert len(session.calls) == 2
    assert session.calls[1]["params"]["cursor"] == "page-2"


def test_fetch_all_public_servers_stops_when_no_more_pages():
    page1 = {"data": [], "nextPageCursor": None}
    session = FakeSession([FakeResponse(200, page1)])

    servers = asyncio.run(fetch_all_public_servers(session, place_id=123))

    assert servers == []
    assert len(session.calls) == 1


def test_fetch_all_public_servers_stops_at_max_pages_even_if_cursor_continues():
    page = {"data": [{"id": "job-x", "playing": 1, "maxPlayers": 8}], "nextPageCursor": "keeps-going"}
    session = FakeSession([FakeResponse(200, page)] * 3)

    servers = asyncio.run(fetch_all_public_servers(session, place_id=123, max_pages=3))

    assert len(servers) == 3
    assert len(session.calls) == 3


# -- rate limiter wiring --


def test_fetch_servers_page_waits_on_rate_limiter_before_request():
    payload = {"data": [], "nextPageCursor": None}
    session = FakeSession([FakeResponse(200, payload, headers={"x-ratelimit-remaining": "2", "x-ratelimit-reset": "10"})])
    limiter = FakeRateLimiter()

    asyncio.run(fetch_servers_page(session, place_id=123, rate_limiter=limiter))

    assert limiter.waited is True
    assert limiter.recorded is True
    assert limiter.updated_with == {"x-ratelimit-remaining": "2", "x-ratelimit-reset": "10"}


def test_fetch_servers_page_updates_rate_limiter_even_on_error_response():
    session = FakeSession([FakeResponse(500, {}, "boom", headers={"x-ratelimit-remaining": "1", "x-ratelimit-reset": "5"})] * 4)
    limiter = FakeRateLimiter()

    with pytest.raises(RobloxApiError):
        asyncio.run(fetch_servers_page(session, place_id=123, rate_limiter=limiter))

    assert limiter.recorded is True


# -- 429 / Retry-After handling --


def test_parse_retry_after_reads_retry_after_header():
    assert _parse_retry_after({"Retry-After": "12"}) == 12.0


def test_parse_retry_after_falls_back_to_ratelimit_reset():
    assert _parse_retry_after({"x-ratelimit-remaining": "0", "x-ratelimit-reset": "30"}) == 30.0


def test_parse_retry_after_falls_back_to_default_when_nothing_present():
    assert _parse_retry_after({}) == 65.0


def test_fetch_servers_page_raises_rate_limited_error_with_retry_after():
    session = FakeSession([FakeResponse(429, {}, "slow down", headers={"Retry-After": "0.001"})] * 4)

    with pytest.raises(RobloxRateLimitedError) as excinfo:
        asyncio.run(fetch_servers_page(session, place_id=123))

    assert excinfo.value.retry_after == 0.001


def test_wait_strategy_uses_retry_after_for_rate_limited_error():
    exc = RobloxRateLimitedError(429, "", retry_after=12.0)
    assert _wait_strategy(FakeRetryState(exc)) == 12.0


def test_wait_strategy_falls_back_to_exponential_for_other_errors():
    exc = RobloxApiError(500, "boom")
    delay = _wait_strategy(FakeRetryState(exc, attempt_number=1))
    assert delay >= 0
