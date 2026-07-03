---
title: Fisch Sunken Treasure Tracker API
emoji: 🎣
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Fisch Sunken Treasure Tracker API

Polls Fisch's public Roblox server list, estimates each server's age via
first-seen tracking (Roblox never exposes real server creation time), and
ranks servers by how soon their Sunken Treasure spawn window opens.

This is the backend only: a FastAPI service (`api.py`) with REST + a
WebSocket for realtime updates. The frontend lives separately in
`frontend/` (Vite + React).

## Setup

Set these as Space secrets (Settings -> Repository secrets):

- `FISCH_PLACE_ID` — `16732694052`
- `SUPABASE_URL`
- `SUPABASE_KEY`

Run the migrations in `supabase/migrations/` against your Supabase project
before starting the Space.

## API

- `GET /api/health`
- `GET /api/servers` — ranked list (confirmed servers first, then
  growth-verified guesses), each with a `join_link` deep link
- `POST /api/servers/{job_id}/confirm-age` — body `{days, hours, minutes}`,
  overrides the guessed age with a ground-truth value reported from
  Fisch's own in-game UI
- `WS /ws/servers` — pushes the same payload as `GET /api/servers` every
  5s, and immediately after a confirmation is submitted

## How it works

See `fisch_tracker/` for the poller (`main.py`), rate limiter, tracker
(first-seen + reliability gate + manual confirmation), and spawn
prediction (`treasure.py`). `api.py` runs the poller in a background
thread and serves the API.
