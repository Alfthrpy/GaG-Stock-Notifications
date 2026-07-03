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


def rank_upcoming_spawns(
    sightings: list[ServerSighting],
    epoch: datetime,
    now: datetime,
    recency_threshold_seconds: float = DEFAULT_RECENCY_THRESHOLD_SECONDS,
    playing_threshold: int = DEFAULT_RELIABILITY_PLAYING_THRESHOLD,
) -> list[PredictedSpawn]:
    """Reliable, still-live servers ranked by treasure-spawn urgency:
    active servers first (soonest to end), then upcoming (soonest to start)."""
    predictions = []
    for sighting in sightings:
        if not is_age_reliable(sighting.first_seen, sighting.first_seen_playing, epoch, playing_threshold):
            continue
        if (now - sighting.last_seen).total_seconds() > recency_threshold_seconds:
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
            )
        )

    predictions.sort(
        key=lambda p: (0 if p.is_active else 1, p.seconds_until_end if p.is_active else p.seconds_until_start)
    )
    return predictions
