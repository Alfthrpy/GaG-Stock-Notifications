---
title: Fisch Sunken Treasure Tracker
emoji: 🎣
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 5.9.1
app_file: app.py
pinned: false
---

# Fisch Sunken Treasure Tracker

Polls Fisch's public Roblox server list, estimates each server's age via
first-seen tracking (Roblox never exposes real server creation time), and
ranks servers by how soon their Sunken Treasure spawn window opens.

## Setup

Set these as Space secrets (Settings -> Repository secrets):

- `FISCH_PLACE_ID` — `16732694052`
- `SUPABASE_URL`
- `SUPABASE_KEY`

Run the migration in `supabase/migrations/0001_fisch_server_sightings.sql`
against your Supabase project before starting the Space.

## How it works

See `fisch_tracker/` for the poller (`main.py`), rate limiter, tracker
(first-seen + reliability gate), and spawn prediction (`treasure.py`).
`app.py` runs the poller in a background thread and shows a
live-refreshing dashboard.
