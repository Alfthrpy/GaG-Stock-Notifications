-- Tracks first/last time each Fisch public server job_id was observed by
-- the poller (fisch_tracker), so server age can be estimated as
-- now() - first_seen. Roblox does not expose true server creation time.

create table if not exists fisch_server_sightings (
    place_id bigint not null,
    job_id text not null,
    first_seen timestamptz not null,
    last_seen timestamptz not null,
    playing integer not null default 0,
    max_players integer not null default 0,
    primary key (place_id, job_id)
);

create index if not exists fisch_server_sightings_last_seen_idx
    on fisch_server_sightings (last_seen);
