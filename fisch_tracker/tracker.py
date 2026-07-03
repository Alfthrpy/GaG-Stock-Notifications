"""First-seen based server age tracking.

Roblox doesn't expose server creation time, so age is estimated as
`now - first_seen`, where `first_seen` is the earliest sweep that ever
observed a given job_id. Persisting first_seen (via SightingsRepository)
across process restarts is what keeps this estimate meaningful.

That estimate can still be wrong in ways is_age_reliable() only
partially covers:
1. A server already existed when this tracker's very first sweep
   ("epoch") ran, so its true creation time is unknown -- first_seen
   for anything seen in that sweep is a lower bound, not the truth.
2. Fisch's live population is far bigger than what a single sweep can
   see (~700-server API cap vs thousands of concurrent servers), so a
   server can stay outside our sample for a long time and only get
   caught once it happens to land on the pages we fetch.
3. A static playing count at first sighting turned out NOT to reliably
   signal "just born" -- confirmed by live observation, many servers
   sit at just 1-5 players for hours regardless of true age (Fisch's
   population is thin enough that low occupancy is normal, not a sign
   of youth or impending closure). What does distinguish them: growth.
   A genuinely new server keeps getting filled as matchmaking directs
   players to it, while a chronically idle or dying one stays flat or
   declines. is_age_reliable() therefore also requires the latest known
   playing count to be higher than it was at first sighting. This is
   still a soft, ranked guess, not a source of truth -- callers should
   treat it as a lower tier than a manual confirmation.

Manual confirmation (compute_confirmed_first_seen / apply_age_confirmation)
is the ground-truth override: Fisch's own UI shows a server's real age,
so a player can report what they saw and we replace the guess with an
exact first_seen. ServerSighting.age_confirmed marks a sighting as
ground truth; build_sightings() never lets a regular sweep clear it.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Protocol

from .roblox_api import ServerInstance

# Observed live: brand-new Fisch servers show up with 1-2 players.
# Anything first sighted above this was almost certainly discovered
# late, not caught at creation.
DEFAULT_RELIABILITY_PLAYING_THRESHOLD = 2

# A server must keep being seen for this long after first_seen before
# it's trusted -- filters out old/dying servers caught near closure,
# which mostly disappear within minutes rather than persisting.
DEFAULT_MIN_CONFIRMATION_SECONDS = 15 * 60


@dataclass(frozen=True)
class FirstSeenRecord:
    first_seen: datetime
    first_seen_playing: int
    age_confirmed: bool = False


@dataclass(frozen=True)
class ServerSighting:
    job_id: str
    first_seen: datetime
    first_seen_playing: int
    last_seen: datetime
    playing: int
    max_players: int
    age_confirmed: bool = False


class SightingsRepository(Protocol):
    def get_first_seen_records(self, job_ids: list[str]) -> dict[str, FirstSeenRecord]:
        """Return known first-seen records for the given job ids."""
        ...

    def get_epoch(self) -> datetime | None:
        """Return the timestamp of this tracker's very first sweep ever,
        or None if nothing has been recorded yet."""
        ...

    def list_sightings(self, since: datetime | None = None) -> list[ServerSighting]:
        """Return stored sightings for this place. If since is given, only
        rows with last_seen >= since -- the table grows unbounded (rows
        are never deleted except by delete_stale_sightings), so callers
        that only care about currently-relevant servers should always
        pass since to avoid pulling the entire history every call."""
        ...

    def upsert_sightings(self, sightings: list[ServerSighting]) -> None:
        """Persist sightings. Must not move a job's first_seen/first_seen_playing."""
        ...

    def delete_stale_sightings(self, older_than: datetime) -> None:
        """Delete rows with last_seen < older_than, to bound table growth."""
        ...

    def confirm_age(self, job_id: str, first_seen: datetime, confirmed_at: datetime) -> None:
        """Override first_seen with a ground-truth value and mark it
        age_confirmed, bypassing the heuristic reliability checks."""
        ...


def compute_age_seconds(first_seen: datetime, now: datetime) -> float:
    if now < first_seen:
        raise ValueError("now cannot be earlier than first_seen")
    return (now - first_seen).total_seconds()


def is_age_reliable(
    first_seen: datetime,
    first_seen_playing: int,
    current_playing: int,
    epoch: datetime,
    now: datetime,
    playing_threshold: int = DEFAULT_RELIABILITY_PLAYING_THRESHOLD,
    min_confirmation_seconds: float = DEFAULT_MIN_CONFIRMATION_SECONDS,
) -> bool:
    return (
        first_seen > epoch
        and first_seen_playing <= playing_threshold
        and (now - first_seen).total_seconds() >= min_confirmation_seconds
        and current_playing > first_seen_playing
    )


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
            age_confirmed = existing.age_confirmed
        else:
            first_seen = seen_at
            first_seen_playing = server.playing
            age_confirmed = False

        sightings.append(
            ServerSighting(
                job_id=server.job_id,
                first_seen=first_seen,
                first_seen_playing=first_seen_playing,
                last_seen=seen_at,
                playing=server.playing,
                max_players=server.max_players,
                age_confirmed=age_confirmed,
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


def compute_confirmed_first_seen(reported_age_seconds: float, observed_at: datetime) -> datetime:
    if reported_age_seconds < 0:
        raise ValueError("reported_age_seconds cannot be negative")
    return observed_at - timedelta(seconds=reported_age_seconds)


def apply_age_confirmation(
    repository: SightingsRepository,
    job_id: str,
    reported_age_seconds: float,
    observed_at: datetime,
) -> None:
    first_seen = compute_confirmed_first_seen(reported_age_seconds, observed_at)
    repository.confirm_age(job_id, first_seen, observed_at)
