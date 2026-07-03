import asyncio
from datetime import datetime, timedelta, timezone

from tests.test_roblox_api import FakeRateLimiter, FakeResponse, FakeSession

from fisch_tracker.sweep import run_sweep
from fisch_tracker.tracker import FirstSeenRecord, ServerSighting

T0 = datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)


class FakeRepository:
    def __init__(self, existing_first_seen=None, epoch=None):
        self.existing_first_seen = dict(existing_first_seen or {})
        self.epoch = epoch
        self.upserted: list[ServerSighting] = []

    def get_first_seen_records(self, job_ids):
        return {jid: rec for jid, rec in self.existing_first_seen.items() if jid in job_ids}

    def get_epoch(self):
        return self.epoch

    def upsert_sightings(self, sightings):
        self.upserted.extend(sightings)


def test_run_sweep_fetches_all_pages_and_records_sightings():
    page1 = {"data": [{"id": "job-1", "playing": 1, "maxPlayers": 8}], "nextPageCursor": "page-2"}
    page2 = {"data": [{"id": "job-2", "playing": 2, "maxPlayers": 8}], "nextPageCursor": None}
    session = FakeSession([FakeResponse(200, page1), FakeResponse(200, page2)])
    repo = FakeRepository(
        existing_first_seen={"job-1": FirstSeenRecord(first_seen=T0 - timedelta(hours=3), first_seen_playing=1)}
    )

    result = asyncio.run(run_sweep(session, repo, place_id=999))

    assert result.server_count == 2
    assert {s.job_id for s in repo.upserted} == {"job-1", "job-2"}
    assert result.sightings == repo.upserted

    job1 = next(s for s in repo.upserted if s.job_id == "job-1")
    job2 = next(s for s in repo.upserted if s.job_id == "job-2")
    assert job1.first_seen == T0 - timedelta(hours=3)
    assert job2.first_seen == job2.last_seen


def test_run_sweep_reports_duration():
    page = {"data": [], "nextPageCursor": None}
    session = FakeSession([FakeResponse(200, page)])
    repo = FakeRepository()

    result = asyncio.run(run_sweep(session, repo, place_id=999))

    assert result.server_count == 0
    assert result.duration_seconds >= 0
    assert result.finished_at >= result.started_at


def test_run_sweep_respects_max_pages():
    page = {"data": [{"id": "job-x", "playing": 1, "maxPlayers": 8}], "nextPageCursor": "keeps-going"}
    session = FakeSession([FakeResponse(200, page)] * 2)
    repo = FakeRepository()

    result = asyncio.run(run_sweep(session, repo, place_id=999, max_pages=2))

    assert result.server_count == 2
    assert len(session.calls) == 2


def test_run_sweep_passes_rate_limiter_through():
    page = {"data": [], "nextPageCursor": None}
    session = FakeSession([FakeResponse(200, page)])
    repo = FakeRepository()
    limiter = FakeRateLimiter()

    asyncio.run(run_sweep(session, repo, place_id=999, rate_limiter=limiter))

    assert limiter.waited is True
    assert limiter.recorded is True
