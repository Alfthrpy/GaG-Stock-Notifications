"""Standalone worker: polls Fisch's public server list and persists
first-seen/last-seen sightings to Supabase.

Run with:
    FISCH_PLACE_ID=... SUPABASE_URL=... SUPABASE_KEY=... python -m fisch_tracker.main

Live testing against the real endpoint (placeId 16732694052) showed:
- Rate limit ~3 requests/60s (sliding window), signaled via
  x-ratelimit-remaining/x-ratelimit-reset response headers -- see
  rate_limiter.AdaptiveRateLimiter, which paces requests off the real
  headers instead of a hardcoded guess.
- Cursor pagination hard-caps around 700 servers (7 pages of 100).
- sortOrder=Asc empirically sorts by ascending player count, so newly
  created (low-population) servers tend to surface on page 1.

Given that budget, walking all ~7 pages every tick is unsustainable
(it alone would take minutes). Instead: most ticks fetch page 1 only
(cheap, catches new servers fast per the sort behavior above); every
Nth tick does a deeper sweep for broader coverage.
"""
from __future__ import annotations

import asyncio
import logging

import aiohttp

from .config import get_place_id, get_supabase_client
from .rate_limiter import AdaptiveRateLimiter
from .roblox_api import DEFAULT_MAX_PAGES
from .supabase_repository import SupabaseSightingsRepository
from .sweep import run_sweep

logger = logging.getLogger("fisch_tracker")

SHALLOW_PAGES = 1
DEEP_SWEEP_EVERY_N_TICKS = 5
# Floor gap between ticks so an all-empty/instant response doesn't tight-loop;
# the rate limiter is what actually paces real requests.
MIN_TICK_GAP_SECONDS = 1


def pages_for_tick(
    tick_number: int,
    deep_sweep_every: int = DEEP_SWEEP_EVERY_N_TICKS,
    shallow_pages: int = SHALLOW_PAGES,
    deep_pages: int = DEFAULT_MAX_PAGES,
) -> int:
    """Tick 0 (the process's first-ever sweep) is deep too, since 0 % N == 0."""
    if tick_number % deep_sweep_every == 0:
        return deep_pages
    return shallow_pages


async def run_forever() -> None:
    place_id = get_place_id()
    repository = SupabaseSightingsRepository(get_supabase_client(), place_id)
    rate_limiter = AdaptiveRateLimiter()

    tick = 0
    async with aiohttp.ClientSession() as session:
        while True:
            max_pages = pages_for_tick(tick)
            logger.info("tick %d (max_pages=%d): sweep starting", tick, max_pages)
            try:
                result = await run_sweep(session, repository, place_id, rate_limiter=rate_limiter, max_pages=max_pages)
                logger.info(
                    "tick %d (max_pages=%d): %d servers in %.2fs",
                    tick,
                    max_pages,
                    result.server_count,
                    result.duration_seconds,
                )
            except Exception:
                logger.exception("sweep failed on tick %d", tick)
            tick += 1
            await asyncio.sleep(MIN_TICK_GAP_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_forever())
