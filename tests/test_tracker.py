from datetime import datetime, timedelta, timezone

import pytest

from fisch_tracker.roblox_api import ServerInstance
from fisch_tracker.tracker import (
    ServerSighting,
    build_sightings,
    compute_age_seconds,
    record_sightings,
)

T0 = datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)


class FakeRepository:
    """In-memory double for SightingsRepository, used to test orchestration."""

    def __init__(self, existing_first_seen=None):
        self.existing_first_seen = dict(existing_first_seen or {})
        self.upserted: list[ServerSighting] = []

    def get_first_seen_map(self, job_ids):
        return {jid: ts for jid, ts in self.existing_first_seen.items() if jid in job_ids}

    def upsert_sightings(self, sightings):
        self.upserted.extend(sightings)


def test_compute_age_seconds():
    first_seen = T0
    now = T0 + timedelta(seconds=90)

    assert compute_age_seconds(first_seen, now) == 90.0


def test_compute_age_seconds_rejects_now_before_first_seen():
    with pytest.raises(ValueError):
        compute_age_seconds(T0, T0 - timedelta(seconds=1))


def test_build_sightings_assigns_seen_at_to_brand_new_server():
    servers = [ServerInstance(job_id="job-new", playing=1, max_players=8)]

    sightings = build_sightings(servers, existing_first_seen={}, seen_at=T0)

    assert sightings == [
        ServerSighting(job_id="job-new", first_seen=T0, last_seen=T0, playing=1, max_players=8)
    ]


def test_build_sightings_keeps_original_first_seen_for_known_server():
    original_first_seen = T0 - timedelta(hours=2)
    servers = [ServerInstance(job_id="job-old", playing=4, max_players=8)]
    seen_at = T0

    sightings = build_sightings(
        servers, existing_first_seen={"job-old": original_first_seen}, seen_at=seen_at
    )

    assert sightings[0].first_seen == original_first_seen
    assert sightings[0].last_seen == seen_at


def test_record_sightings_queries_repository_and_persists_result():
    repo = FakeRepository(existing_first_seen={"job-old": T0 - timedelta(hours=1)})
    servers = [
        ServerInstance(job_id="job-old", playing=2, max_players=8),
        ServerInstance(job_id="job-new", playing=1, max_players=8),
    ]

    result = record_sightings(repo, servers, seen_at=T0)

    assert {s.job_id: s.first_seen for s in result} == {
        "job-old": T0 - timedelta(hours=1),
        "job-new": T0,
    }
    assert repo.upserted == result
