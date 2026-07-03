-- Incremental migration for existing deployments (0001 already applied).
-- See fisch_tracker/tracker.py for why manual age confirmation exists.
alter table fisch_server_sightings
  add column if not exists age_confirmed boolean not null default false;
