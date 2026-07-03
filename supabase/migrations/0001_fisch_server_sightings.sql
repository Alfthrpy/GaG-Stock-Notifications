-- Tracks first/last time each Fisch public server job_id was observed by
-- the poller (fisch_tracker), so server age can be estimated as
-- now() - first_seen. Roblox does not expose true server creation time.

-- first_seen_playing: player count recorded at the moment first_seen was
-- set. A genuinely brand-new server can't already have many players, so
-- this doubles as a reliability gate alongside the epoch (this tracker's
-- very first-ever sweep, i.e. MIN(first_seen)): a server is only trusted
-- as truly age-tracked if first_seen > epoch AND first_seen_playing is
-- low -- otherwise it was likely discovered late, not caught at birth.
-- age_confirmed: set when a player reports the server's real age as
-- shown in Fisch's own in-game UI. Ground truth overrides the
-- first_seen_playing heuristic entirely -- see confirm_age() /
-- apply_age_confirmation() in fisch_tracker/tracker.py.
create table if not exists fisch_server_sightings (
    place_id bigint not null,
    job_id text not null,
    first_seen timestamptz not null,
    first_seen_playing integer not null default 0,
    last_seen timestamptz not null,
    playing integer not null default 0,
    max_players integer not null default 0,
    age_confirmed boolean not null default false,
    primary key (place_id, job_id)
);

create index if not exists fisch_server_sightings_last_seen_idx
    on fisch_server_sightings (last_seen);

create index if not exists fisch_server_sightings_first_seen_idx
    on fisch_server_sightings (place_id, first_seen);
