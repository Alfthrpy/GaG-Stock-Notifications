"""Supabase-backed implementation of SightingsRepository.

Requires the `fisch_server_sightings` table from
supabase/migrations/0001_fisch_server_sightings.sql.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .tracker import ServerSighting

TABLE = "fisch_server_sightings"


class SupabaseSightingsRepository:
    def __init__(self, supabase_client: Any, place_id: int):
        self._client = supabase_client
        self._place_id = place_id

    def get_first_seen_map(self, job_ids: list[str]) -> dict[str, datetime]:
        if not job_ids:
            return {}
        response = (
            self._client.table(TABLE)
            .select("job_id, first_seen")
            .eq("place_id", self._place_id)
            .in_("job_id", job_ids)
            .execute()
        )
        return {
            row["job_id"]: datetime.fromisoformat(row["first_seen"]).astimezone(timezone.utc)
            for row in response.data
        }

    def upsert_sightings(self, sightings: list[ServerSighting]) -> None:
        if not sightings:
            return
        rows = [
            {
                "place_id": self._place_id,
                "job_id": s.job_id,
                "first_seen": s.first_seen.isoformat(),
                "last_seen": s.last_seen.isoformat(),
                "playing": s.playing,
                "max_players": s.max_players,
            }
            for s in sightings
        ]
        self._client.table(TABLE).upsert(rows, on_conflict="place_id,job_id").execute()
