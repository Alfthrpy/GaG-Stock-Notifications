"""One full poll cycle: fetch every public server, then record sightings."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .roblox_api import fetch_all_public_servers
from .tracker import ServerSighting, SightingsRepository, record_sightings


@dataclass(frozen=True)
class SweepResult:
    server_count: int
    sightings: list[ServerSighting]
    started_at: datetime
    finished_at: datetime

    @property
    def duration_seconds(self) -> float:
        return (self.finished_at - self.started_at).total_seconds()


async def run_sweep(session: Any, repository: SightingsRepository, place_id: int) -> SweepResult:
    started_at = datetime.now(timezone.utc)
    servers = await fetch_all_public_servers(session, place_id)
    seen_at = datetime.now(timezone.utc)
    sightings = record_sightings(repository, servers, seen_at)
    finished_at = datetime.now(timezone.utc)
    return SweepResult(
        server_count=len(servers),
        sightings=sightings,
        started_at=started_at,
        finished_at=finished_at,
    )
