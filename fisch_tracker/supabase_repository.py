"""Supabase-backed implementation of SightingsRepository.

Requires the `fisch_server_sightings` table from
supabase/migrations/0001_fisch_server_sightings.sql.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .tracker import FirstSeenRecord, ServerSighting

TABLE = "fisch_server_sightings"


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


class SupabaseSightingsRepository:
    def __init__(self, supabase_client: Any, place_id: int):
        self._client = supabase_client
        self._place_id = place_id

    def get_first_seen_records(self, job_ids: list[str]) -> dict[str, FirstSeenRecord]:
        if not job_ids:
            return {}
        response = (
            self._client.table(TABLE)
            .select("job_id, first_seen, first_seen_playing")
            .eq("place_id", self._place_id)
            .in_("job_id", job_ids)
            .execute()
        )
        return {
            row["job_id"]: FirstSeenRecord(
                first_seen=_parse_utc(row["first_seen"]),
                first_seen_playing=row["first_seen_playing"],
            )
            for row in response.data
        }

    def list_sightings(self) -> list[ServerSighting]:
        response = self._client.table(TABLE).select("*").eq("place_id", self._place_id).execute()
        return [
            ServerSighting(
                job_id=row["job_id"],
                first_seen=_parse_utc(row["first_seen"]),
                first_seen_playing=row["first_seen_playing"],
                last_seen=_parse_utc(row["last_seen"]),
                playing=row["playing"],
                max_players=row["max_players"],
            )
            for row in response.data
        ]

    def get_epoch(self) -> datetime | None:
        response = (
            self._client.table(TABLE)
            .select("first_seen")
            .eq("place_id", self._place_id)
            .order("first_seen")
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        return _parse_utc(response.data[0]["first_seen"])

    def upsert_sightings(self, sightings: list[ServerSighting]) -> None:
        if not sightings:
            return
        rows = [
            {
                "place_id": self._place_id,
                "job_id": s.job_id,
                "first_seen": s.first_seen.isoformat(),
                "first_seen_playing": s.first_seen_playing,
                "last_seen": s.last_seen.isoformat(),
                "playing": s.playing,
                "max_players": s.max_players,
            }
            for s in sightings
        ]
        self._client.table(TABLE).upsert(rows, on_conflict="place_id,job_id").execute()
