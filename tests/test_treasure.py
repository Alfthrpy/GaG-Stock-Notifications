from datetime import datetime, timedelta, timezone

import pytest

from fisch_tracker.treasure import predict_next_spawn, rank_upcoming_spawns
from fisch_tracker.tracker import ServerSighting

EPOCH = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)


# -- predict_next_spawn: first spawn at 60:00, active for 10:00, then every 70:00 --


def test_before_first_spawn():
    window = predict_next_spawn(age_seconds=0)

    assert window.is_active is False
    assert window.seconds_until_start == 3600
    assert window.seconds_until_end == 3600 + 600


def test_one_second_before_first_spawn():
    window = predict_next_spawn(age_seconds=3599)

    assert window.is_active is False
    assert window.seconds_until_start == 1


def test_exactly_at_first_spawn_start():
    window = predict_next_spawn(age_seconds=3600)

    assert window.is_active is True
    assert window.seconds_until_start == 0
    assert window.seconds_until_end == 600


def test_one_second_before_first_spawn_ends():
    window = predict_next_spawn(age_seconds=3600 + 599)

    assert window.is_active is True
    assert window.seconds_until_end == 1


def test_right_after_first_spawn_ends_waits_for_second_spawn():
    # spawn 2 starts at 2h10m = 7800s absolute age
    window = predict_next_spawn(age_seconds=3600 + 600)

    assert window.is_active is False
    assert window.seconds_until_start == 7800 - (3600 + 600)


def test_exactly_at_second_spawn_start():
    window = predict_next_spawn(age_seconds=7800)

    assert window.is_active is True
    assert window.seconds_until_start == 0
    assert window.seconds_until_end == 600


def test_third_spawn_matches_70_minute_cycle():
    # spawn 3 should start at 3h20m = 12000s
    window = predict_next_spawn(age_seconds=12000)

    assert window.is_active is True


def test_negative_age_rejected():
    with pytest.raises(ValueError):
        predict_next_spawn(age_seconds=-1)


# -- rank_upcoming_spawns --


def _sighting(job_id, first_seen, first_seen_playing=1, last_seen=None, playing=1, max_players=20):
    return ServerSighting(
        job_id=job_id,
        first_seen=first_seen,
        first_seen_playing=first_seen_playing,
        last_seen=last_seen or first_seen,
        playing=playing,
        max_players=max_players,
    )


def test_rank_excludes_unreliable_epoch_servers():
    now = EPOCH + timedelta(hours=5)
    sightings = [
        _sighting("job-epoch", first_seen=EPOCH, last_seen=now),
        _sighting("job-real", first_seen=EPOCH + timedelta(minutes=10), last_seen=now),
    ]

    ranked = rank_upcoming_spawns(sightings, epoch=EPOCH, now=now)

    assert [p.job_id for p in ranked] == ["job-real"]


def test_rank_excludes_servers_discovered_with_high_playing():
    now = EPOCH + timedelta(hours=5)
    sightings = [
        _sighting("job-late-discovery", first_seen=EPOCH + timedelta(minutes=10), first_seen_playing=9, last_seen=now),
    ]

    ranked = rank_upcoming_spawns(sightings, epoch=EPOCH, now=now)

    assert ranked == []


def test_rank_excludes_stale_servers_not_seen_recently():
    now = EPOCH + timedelta(hours=5)
    sightings = [
        _sighting(
            "job-gone",
            first_seen=EPOCH + timedelta(minutes=10),
            last_seen=now - timedelta(minutes=20),
        ),
    ]

    ranked = rank_upcoming_spawns(sightings, epoch=EPOCH, now=now, recency_threshold_seconds=300)

    assert ranked == []


def test_rank_orders_active_servers_before_upcoming_by_urgency():
    # job-A: about to end soon (more urgent than job-B which just started)
    # job-B: active, ends later
    # job-C: not active yet, starts soonest among the "waiting" group
    # job-D: not active, starts later than job-C
    now = EPOCH + timedelta(hours=5)

    def age_for(job_id, seconds_old):
        return _sighting(job_id, first_seen=now - timedelta(seconds=seconds_old), last_seen=now)

    sightings = [
        age_for("job-B", 3601),  # just started its active window (599s left)... wait compute below
        age_for("job-A", 3600 + 590),  # 10s left in active window
        age_for("job-D", 100),  # far from first spawn
        age_for("job-C", 3500),  # 100s until first spawn starts
    ]

    ranked = rank_upcoming_spawns(sightings, epoch=EPOCH, now=now)

    assert [p.job_id for p in ranked] == ["job-A", "job-B", "job-C", "job-D"]


def test_rank_returns_predicted_spawn_metadata():
    now = EPOCH + timedelta(hours=5)
    sightings = [_sighting("job-real", first_seen=now - timedelta(seconds=100), playing=4, max_players=20, last_seen=now)]

    ranked = rank_upcoming_spawns(sightings, epoch=EPOCH, now=now)

    assert len(ranked) == 1
    p = ranked[0]
    assert p.job_id == "job-real"
    assert p.age_seconds == 100
    assert p.playing == 4
    assert p.max_players == 20
    assert p.is_active is False
    assert p.seconds_until_start == 3500
