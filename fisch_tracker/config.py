"""Environment-based configuration for the standalone poller process.

This runs outside Streamlit (cron/systemd/etc.), so it reads plain env
vars rather than st.secrets.
"""
from __future__ import annotations

import os

FISCH_PLACE_ID_ENV = "FISCH_PLACE_ID"


def get_place_id() -> int:
    value = os.environ.get(FISCH_PLACE_ID_ENV)
    if not value:
        raise RuntimeError(f"{FISCH_PLACE_ID_ENV} env var is not set")
    return int(value)


def get_supabase_client():
    from supabase import create_client

    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)
