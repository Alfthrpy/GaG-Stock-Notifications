from datetime import datetime, timedelta, timezone

import pytest

from fisch_tracker.roblox_api import ServerInstance
from fisch_tracker.tracker import (
    DEFAULT_MIN_CONFIRMATION_SECONDS,
    DEFAULT_RELIABILITY_PLAYING_THRESHOLD,
    FirstSeenRecord,
    ServerSighting,
    apply_age_confirmation,
    build_sightings,
    compute_age_seconds,
    compute_confirmed_first_seen,
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
        self.confirmations: list[tuple[str, datetime, datetime]] = []

    def get_first_seen_records(self, job_ids):
        return {jid: rec for jid, rec in self.existing_first_seen.items() if jid in job_ids}

    def get_epoch(self):
        return self.epoch

    def upsert_sightings(self, sightings):
        self.upserted.extend(sightings)

    def confirm_age(self, job_id, first_seen, confirmed_at):
        self.confirmations.append((job_id, first_seen, confirmed_at))


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


def test_build_sightings_new_server_is_not_age_confirmed():
    servers = [ServerInstance(job_id="job-new", playing=1, max_players=20)]

    sightings = build_sightings(servers, existing_first_seen={}, seen_at=T0)

    assert sightings[0].age_confirmed is False


def test_build_sightings_preserves_age_confirmed_flag_across_regular_sweeps():
    # a regular sweep re-observing an already player-confirmed server must
    # not silently clear the confirmation.
    original = FirstSeenRecord(
        first_seen=T0 - timedelta(hours=3), first_seen_playing=5, age_confirmed=True
    )
    servers = [ServerInstance(job_id="job-confirmed", playing=7, max_players=20)]

    sightings = build_sightings(
        servers, existing_first_seen={"job-confirmed": original}, seen_at=T0
    )

    assert sightings[0].first_seen == T0 - timedelta(hours=3)
    assert sightings[0].age_confirmed is True


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


def test_is_age_reliable_true_when_discovered_after_epoch_low_playing_confirmed_and_grown():
    first_seen = EPOCH + timedelta(seconds=1)
    assert is_age_reliable(
        first_seen=first_seen,
        first_seen_playing=1,
        current_playing=4,
        epoch=EPOCH,
        now=first_seen + timedelta(seconds=DEFAULT_MIN_CONFIRMATION_SECONDS),
        playing_threshold=2,
    ) is True


def test_is_age_reliable_false_when_discovered_in_epoch_sweep():
    assert is_age_reliable(
        first_seen=EPOCH,
        first_seen_playing=1,
        current_playing=4,
        epoch=EPOCH,
        now=EPOCH + timedelta(hours=5),
        playing_threshold=2,
    ) is False


def test_is_age_reliable_false_when_first_sighting_playing_exceeds_threshold():
    # can't genuinely be brand new if it already had a bunch of players
    # the very first time we ever saw it -- we probably just discovered
    # a pre-existing server late, not caught it being created.
    first_seen = EPOCH + timedelta(hours=5)
    assert is_age_reliable(
        first_seen=first_seen,
        first_seen_playing=8,
        current_playing=12,
        epoch=EPOCH,
        now=first_seen + timedelta(seconds=DEFAULT_MIN_CONFIRMATION_SECONDS),
        playing_threshold=2,
    ) is False


def test_is_age_reliable_false_when_not_survived_confirmation_window_yet():
    # a server that's actually old and dying can also show up with few
    # players the first time we ever see it (it was just outside our
    # sample until it happened to empty out near the end of its life).
    # Requiring it to keep being seen for a while filters most of those
    # out, since a truly-dying server tends to close within minutes.
    first_seen = EPOCH + timedelta(hours=5)
    assert is_age_reliable(
        first_seen=first_seen,
        first_seen_playing=1,
        current_playing=3,
        epoch=EPOCH,
        now=first_seen + timedelta(seconds=DEFAULT_MIN_CONFIRMATION_SECONDS - 1),
        playing_threshold=2,
    ) is False


def test_is_age_reliable_true_right_at_confirmation_window_boundary():
    first_seen = EPOCH + timedelta(hours=5)
    assert is_age_reliable(
        first_seen=first_seen,
        first_seen_playing=1,
        current_playing=3,
        epoch=EPOCH,
        now=first_seen + timedelta(seconds=DEFAULT_MIN_CONFIRMATION_SECONDS),
        playing_threshold=2,
    ) is True


def test_is_age_reliable_uses_default_thresholds_when_not_given():
    first_seen = EPOCH + timedelta(hours=5)
    confirmed_now = first_seen + timedelta(seconds=DEFAULT_MIN_CONFIRMATION_SECONDS)

    assert is_age_reliable(
        first_seen=first_seen,
        first_seen_playing=DEFAULT_RELIABILITY_PLAYING_THRESHOLD + 1,
        current_playing=DEFAULT_RELIABILITY_PLAYING_THRESHOLD + 5,
        epoch=EPOCH,
        now=confirmed_now,
    ) is False
    assert is_age_reliable(
        first_seen=first_seen,
        first_seen_playing=DEFAULT_RELIABILITY_PLAYING_THRESHOLD,
        current_playing=DEFAULT_RELIABILITY_PLAYING_THRESHOLD + 3,
        epoch=EPOCH,
        now=confirmed_now,
    ) is True


# -- growth-trend check: static low playing count alone isn't evidence of
# youth (confirmed live -- many old servers sit at 1-5 players for hours),
# but a real new server should show net growth as matchmaking fills it --


def test_is_age_reliable_false_when_population_never_grew_since_discovery():
    # chronically-idle old server: low then, still low now, no growth
    first_seen = EPOCH + timedelta(hours=5)
    assert is_age_reliable(
        first_seen=first_seen,
        first_seen_playing=1,
        current_playing=1,
        epoch=EPOCH,
        now=first_seen + timedelta(seconds=DEFAULT_MIN_CONFIRMATION_SECONDS),
        playing_threshold=2,
    ) is False


def test_is_age_reliable_false_when_population_declined_since_discovery():
    first_seen = EPOCH + timedelta(hours=5)
    assert is_age_reliable(
        first_seen=first_seen,
        first_seen_playing=2,
        current_playing=0,
        epoch=EPOCH,
        now=first_seen + timedelta(seconds=DEFAULT_MIN_CONFIRMATION_SECONDS),
        playing_threshold=2,
    ) is False


# -- manual age confirmation (ground truth reported from Fisch's in-game UI) --


def test_compute_confirmed_first_seen_subtracts_reported_age():
    observed_at = T0
    first_seen = compute_confirmed_first_seen(reported_age_seconds=2 * 3600 + 34 * 60, observed_at=observed_at)

    assert first_seen == T0 - timedelta(hours=2, minutes=34)


def test_compute_confirmed_first_seen_rejects_negative_age():
    with pytest.raises(ValueError):
        compute_confirmed_first_seen(reported_age_seconds=-1, observed_at=T0)


def test_apply_age_confirmation_writes_implied_first_seen_to_repository():
    repo = FakeRepository()

    apply_age_confirmation(repo, job_id="job-1", reported_age_seconds=3600, observed_at=T0)

    assert repo.confirmations == [("job-1", T0 - timedelta(hours=1), T0)]
