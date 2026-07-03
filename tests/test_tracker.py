from datetime import datetime, timedelta, timezone

import pytest

from fisch_tracker.roblox_api import ServerInstance
from fisch_tracker.tracker import (
    DEFAULT_RELIABILITY_PLAYING_THRESHOLD,
    FirstSeenRecord,
    ServerSighting,
    build_sightings,
    compute_age_seconds,
    is_age_reliable,
    record_sightings,
)

T0 = datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)
EPOCH = T0 - timedelta(days=1)


class FakeRepository:
    """In-memory double for SightingsRepository, used to test orchestration."""

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


def test_compute_age_seconds():
    first_seen = T0
    now = T0 + timedelta(seconds=90)

    assert compute_age_seconds(first_seen, now) == 90.0


def test_compute_age_seconds_rejects_now_before_first_seen():
    with pytest.raises(ValueError):
        compute_age_seconds(T0, T0 - timedelta(seconds=1))


def test_build_sightings_assigns_seen_at_and_playing_to_brand_new_server():
    servers = [ServerInstance(job_id="job-new", playing=2, max_players=20)]

    sightings = build_sightings(servers, existing_first_seen={}, seen_at=T0)

    assert sightings == [
        ServerSighting(
            job_id="job-new",
            first_seen=T0,
            first_seen_playing=2,
            last_seen=T0,
            playing=2,
            max_players=20,
        )
    ]


def test_build_sightings_keeps_original_first_seen_and_playing_for_known_server():
    # server was first recorded with 1 player 2 hours ago; now it's got 15
    original = FirstSeenRecord(first_seen=T0 - timedelta(hours=2), first_seen_playing=1)
    servers = [ServerInstance(job_id="job-old", playing=15, max_players=20)]

    sightings = build_sightings(
        servers, existing_first_seen={"job-old": original}, seen_at=T0
    )

    assert sightings[0].first_seen == T0 - timedelta(hours=2)
    assert sightings[0].first_seen_playing == 1
    assert sightings[0].last_seen == T0
    assert sightings[0].playing == 15


def test_record_sightings_queries_repository_and_persists_result():
    repo = FakeRepository(
        existing_first_seen={
            "job-old": FirstSeenRecord(first_seen=T0 - timedelta(hours=1), first_seen_playing=3)
        }
    )
    servers = [
        ServerInstance(job_id="job-old", playing=10, max_players=20),
        ServerInstance(job_id="job-new", playing=1, max_players=20),
    ]

    result = record_sightings(repo, servers, seen_at=T0)

    assert {s.job_id: (s.first_seen, s.first_seen_playing) for s in result} == {
        "job-old": (T0 - timedelta(hours=1), 3),
        "job-new": (T0, 1),
    }
    assert repo.upserted == result


# -- reliability gate --


def test_is_age_reliable_true_when_discovered_after_epoch_with_low_playing():
    assert is_age_reliable(
        first_seen=EPOCH + timedelta(seconds=1),
        first_seen_playing=2,
        epoch=EPOCH,
        playing_threshold=2,
    ) is True


def test_is_age_reliable_false_when_discovered_in_epoch_sweep():
    assert is_age_reliable(
        first_seen=EPOCH,
        first_seen_playing=1,
        epoch=EPOCH,
        playing_threshold=2,
    ) is False


def test_is_age_reliable_false_when_first_sighting_playing_exceeds_threshold():
    # can't genuinely be brand new if it already had a bunch of players
    # the very first time we ever saw it -- we probably just discovered
    # a pre-existing server late, not caught it being created.
    assert is_age_reliable(
        first_seen=EPOCH + timedelta(hours=5),
        first_seen_playing=8,
        epoch=EPOCH,
        playing_threshold=2,
    ) is False


def test_is_age_reliable_uses_default_threshold_when_not_given():
    assert is_age_reliable(
        first_seen=EPOCH + timedelta(hours=5),
        first_seen_playing=DEFAULT_RELIABILITY_PLAYING_THRESHOLD + 1,
        epoch=EPOCH,
    ) is False
    assert is_age_reliable(
        first_seen=EPOCH + timedelta(hours=5),
        first_seen_playing=DEFAULT_RELIABILITY_PLAYING_THRESHOLD,
        epoch=EPOCH,
    ) is True
