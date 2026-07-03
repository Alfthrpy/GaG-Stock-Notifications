"""First-seen based server age tracking.

Roblox doesn't expose server creation time, so age is estimated as
`now - first_seen`, where `first_seen` is the earliest sweep that ever
observed a given job_id. Persisting first_seen (via SightingsRepository)
across process restarts is what keeps this estimate meaningful.

That estimate can still be wrong in two ways, both handled by
is_age_reliable():
1. A server already existed when this tracker's very first sweep
   ("epoch") ran, so its true creation time is unknown -- first_seen
   for anything seen in that sweep is a lower bound, not the truth.
2. Fisch's live population is far bigger than what a single sweep can
   see (~700-server API cap vs tens of thousands of concurrent
   servers), so a server can stay outside our sample for a long time
   and only get caught once it happens to have few enough players to
   land on the pages we fetch. When that happens, its first_seen is
   also a lower bound, not the truth -- a genuinely brand-new server
   can't already have a non-trivial player count the first time we
   ever see it, so a high playing count at first sighting is itself
   evidence the "first sighting" wasn't actually its birth.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Protocol

from .roblox_api import ServerInstance

# Observed live: brand-new Fisch servers show up with 1-2 players.
# Anything first sighted above this was almost certainly discovered
# late, not caught at creation.
DEFAULT_RELIABILITY_PLAYING_THRESHOLD = 2


@dataclass(frozen=True)
class FirstSeenRecord:
    first_seen: datetime
    first_seen_playing: int


@dataclass(frozen=True)
class ServerSighting:
    job_id: str
    first_seen: datetime
    first_seen_playing: int
    last_seen: datetime
    playing: int
    max_players: int


class SightingsRepository(Protocol):
    def get_first_seen_records(self, job_ids: list[str]) -> dict[str, FirstSeenRecord]:
        """Return known first-seen records for the given job ids."""
        ...

    def get_epoch(self) -> datetime | None:
        """Return the timestamp of this tracker's very first sweep ever,
        or None if nothing has been recorded yet."""
        ...

    def upsert_sightings(self, sightings: list[ServerSighting]) -> None:
        """Persist sightings. Must not move a job's first_seen/first_seen_playing."""
        ...


def compute_age_seconds(first_seen: datetime, now: datetime) -> float:
    if now < first_seen:
        raise ValueError("now cannot be earlier than first_seen")
    return (now - first_seen).total_seconds()


def is_age_reliable(
    first_seen: datetime,
    first_seen_playing: int,
    epoch: datetime,
    playing_threshold: int = DEFAULT_RELIABILITY_PLAYING_THRESHOLD,
) -> bool:
    return first_seen > epoch and first_seen_playing <= playing_threshold


def build_sightings(
    servers: Iterable[ServerInstance],
    existing_first_seen: dict[str, FirstSeenRecord],
    seen_at: datetime,
) -> list[ServerSighting]:
    """A server keeps its original first_seen/first_seen_playing if
    already known; otherwise this sighting becomes its first record."""
    sightings = []
    for server in servers:
        existing = existing_first_seen.get(server.job_id)
        if existing is not None:
            first_seen = existing.first_seen
            first_seen_playing = existing.first_seen_playing
        else:
            first_seen = seen_at
            first_seen_playing = server.playing

        sightings.append(
            ServerSighting(
                job_id=server.job_id,
                first_seen=first_seen,
                first_seen_playing=first_seen_playing,
                last_seen=seen_at,
                playing=server.playing,
                max_players=server.max_players,
            )
        )
    return sightings


def record_sightings(
    repository: SightingsRepository,
    servers: list[ServerInstance],
    seen_at: datetime,
) -> list[ServerSighting]:
    job_ids = [server.job_id for server in servers]
    existing_first_seen = repository.get_first_seen_records(job_ids)
    sightings = build_sightings(servers, existing_first_seen, seen_at)
    repository.upsert_sightings(sightings)
    return sightings
