"""Sunken Treasure spawn prediction and ranking.

Observed pattern: the first spawn window opens at server age 60:00,
stays active for 10:00, then a 60:00 gap, repeating every 70:00 after
the first spawn (spawn N starts at 60:00 + (N-1)*70:00).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .tracker import DEFAULT_RELIABILITY_PLAYING_THRESHOLD, ServerSighting, compute_age_seconds, is_age_reliable

FIRST_SPAWN_SECONDS = 60 * 60
SPAWN_DURATION_SECONDS = 10 * 60
CYCLE_SECONDS = 70 * 60

DEFAULT_RECENCY_THRESHOLD_SECONDS = 300

# Regular sweeps sample low-population servers first, so a confirmed
# server with moderate/high population may not get re-swept (and its
# last_seen refreshed) for a long time even while still alive. Use a
# far more generous window for confirmed sightings so they don't
# vanish from the list just because our sampling missed them.
DEFAULT_CONFIRMED_RECENCY_THRESHOLD_SECONDS = 6 * 3600


@dataclass(frozen=True)
class SpawnWindow:
    is_active: bool
    seconds_until_start: float
    seconds_until_end: float


def predict_next_spawn(age_seconds: float) -> SpawnWindow:
    if age_seconds < 0:
        raise ValueError("age_seconds cannot be negative")

    if age_seconds < FIRST_SPAWN_SECONDS:
        seconds_until_start = FIRST_SPAWN_SECONDS - age_seconds
        return SpawnWindow(
            is_active=False,
            seconds_until_start=seconds_until_start,
            seconds_until_end=seconds_until_start + SPAWN_DURATION_SECONDS,
        )

    phase = (age_seconds - FIRST_SPAWN_SECONDS) % CYCLE_SECONDS
    if phase < SPAWN_DURATION_SECONDS:
        return SpawnWindow(is_active=True, seconds_until_start=0, seconds_until_end=SPAWN_DURATION_SECONDS - phase)

    seconds_until_start = CYCLE_SECONDS - phase
    return SpawnWindow(
        is_active=False,
        seconds_until_start=seconds_until_start,
        seconds_until_end=seconds_until_start + SPAWN_DURATION_SECONDS,
    )


@dataclass(frozen=True)
class PredictedSpawn:
    job_id: str
    age_seconds: float
    is_active: bool
    seconds_until_start: float
    seconds_until_end: float
    playing: int
    max_players: int
    is_confirmed: bool


def rank_upcoming_spawns(
    sightings: list[ServerSighting],
    epoch: datetime,
    now: datetime,
    recency_threshold_seconds: float = DEFAULT_RECENCY_THRESHOLD_SECONDS,
    confirmed_recency_threshold_seconds: float = DEFAULT_CONFIRMED_RECENCY_THRESHOLD_SECONDS,
    playing_threshold: int = DEFAULT_RELIABILITY_PLAYING_THRESHOLD,
) -> list[PredictedSpawn]:
    """Servers ranked by treasure-spawn urgency (active first, soonest to
    end; then upcoming, soonest to start). Includes both age-confirmed
    (ground truth, ranked_upcoming_spawns trusts these unconditionally)
    and heuristic-passed (unconfirmed guess) servers -- callers should
    use PredictedSpawn.is_confirmed to tell them apart."""
    predictions = []
    for sighting in sightings:
        if not (
            sighting.age_confirmed
            or is_age_reliable(sighting.first_seen, sighting.first_seen_playing, epoch, now, playing_threshold)
        ):
            continue
        effective_recency_threshold = (
            confirmed_recency_threshold_seconds if sighting.age_confirmed else recency_threshold_seconds
        )
        if (now - sighting.last_seen).total_seconds() > effective_recency_threshold:
            continue

        age = compute_age_seconds(sighting.first_seen, now)
        window = predict_next_spawn(age)
        predictions.append(
            PredictedSpawn(
                job_id=sighting.job_id,
                age_seconds=age,
                is_active=window.is_active,
                seconds_until_start=window.seconds_until_start,
                seconds_until_end=window.seconds_until_end,
                playing=sighting.playing,
                max_players=sighting.max_players,
                is_confirmed=sighting.age_confirmed,
            )
        )

    predictions.sort(
        key=lambda p: (0 if p.is_active else 1, p.seconds_until_end if p.is_active else p.seconds_until_start)
    )
    return predictions
