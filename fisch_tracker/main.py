"""Standalone worker: polls Fisch's public server list on a loop and
persists first-seen/last-seen sightings to Supabase.

Run with:
    FISCH_PLACE_ID=... SUPABASE_URL=... SUPABASE_KEY=... python -m fisch_tracker.main
"""
from __future__ import annotations

import asyncio
import logging

import aiohttp

from .config import get_place_id, get_supabase_client
from .supabase_repository import SupabaseSightingsRepository
from .sweep import run_sweep

logger = logging.getLogger("fisch_tracker")

# Full sweeps are sequential (cursor pagination), so this bounds worst-case
# detection lag for a newly created server to roughly this many seconds.
POLL_INTERVAL_SECONDS = 12


async def run_forever() -> None:
    place_id = get_place_id()
    repository = SupabaseSightingsRepository(get_supabase_client(), place_id)

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                result = await run_sweep(session, repository, place_id)
                logger.info(
                    "sweep done: %d servers in %.2fs", result.server_count, result.duration_seconds
                )
            except Exception:
                logger.exception("sweep failed")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_forever())
