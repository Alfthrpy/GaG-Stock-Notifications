"""First-seen based server age tracking.

Roblox doesn't expose server creation time, so age is estimated as
`now - first_seen`, where `first_seen` is the earliest sweep that ever
observed a given job_id. Persisting first_seen (via SightingsRepository)
across process restarts is what keeps this estimate meaningful.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Protocol

from .roblox_api import ServerInstance


@dataclass(frozen=True)
class ServerSighting:
    job_id: str
    first_seen: datetime
    last_seen: datetime
    playing: int
    max_players: int


class SightingsRepository(Protocol):
    def get_first_seen_map(self, job_ids: list[str]) -> dict[str, datetime]:
        """Return known first_seen timestamps for the given job ids."""
        ...

    def upsert_sightings(self, sightings: list[ServerSighting]) -> None:
        """Persist sightings. Must not move a job's first_seen later."""
        ...


def compute_age_seconds(first_seen: datetime, now: datetime) -> float:
    if now < first_seen:
        raise ValueError("now cannot be earlier than first_seen")
    return (now - first_seen).total_seconds()


def build_sightings(
    servers: Iterable[ServerInstance],
    existing_first_seen: dict[str, datetime],
    seen_at: datetime,
) -> list[ServerSighting]:
    """A server keeps its original first_seen if already known; otherwise
    seen_at becomes its first_seen."""
    return [
        ServerSighting(
            job_id=server.job_id,
            first_seen=existing_first_seen.get(server.job_id, seen_at),
            last_seen=seen_at,
            playing=server.playing,
            max_players=server.max_players,
        )
        for server in servers
    ]


def record_sightings(
    repository: SightingsRepository,
    servers: list[ServerInstance],
    seen_at: datetime,
) -> list[ServerSighting]:
    job_ids = [server.job_id for server in servers]
    existing_first_seen = repository.get_first_seen_map(job_ids)
    sightings = build_sightings(servers, existing_first_seen, seen_at)
    repository.upsert_sightings(sightings)
    return sightings
