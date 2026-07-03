"""Hugging Face Space entrypoint: runs the fisch_tracker poller in the
background and shows a live-refreshing dashboard of servers ranked by
how soon their Sunken Treasure window opens (or how soon it closes, if
already active).

Configure via Space secrets: FISCH_PLACE_ID, SUPABASE_URL, SUPABASE_KEY.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
from datetime import datetime, timezone

import gradio as gr

from fisch_tracker.config import get_place_id, get_supabase_client
from fisch_tracker.main import run_forever
from fisch_tracker.supabase_repository import SupabaseSightingsRepository
from fisch_tracker.treasure import PredictedSpawn, rank_upcoming_spawns

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fisch_tracker.app")

TABLE_HEADERS = ["Job ID", "Players", "Umur Server", "Status Spawn"]
MAX_ROWS_SHOWN = 30
REFRESH_SECONDS = 15


def _start_background_worker() -> None:
    def _run():
        try:
            asyncio.run(run_forever())
        except Exception:
            logger.exception("background worker crashed")

    threading.Thread(target=_run, daemon=True, name="fisch-tracker-worker").start()


def _format_countdown(seconds: float) -> str:
    seconds = max(0, int(seconds))
    minutes, secs = divmod(seconds, 60)
    return f"{minutes}m {secs}s"


def _format_row(prediction: PredictedSpawn) -> list[str]:
    status = f"AKTIF ({_format_countdown(prediction.seconds_until_end)} lagi tutup)" if prediction.is_active else f"{_format_countdown(prediction.seconds_until_start)} lagi"
    return [
        prediction.job_id,
        f"{prediction.playing}/{prediction.max_players}",
        _format_countdown(prediction.age_seconds),
        status,
    ]


def build_dashboard_rows() -> list[list[str]]:
    try:
        place_id = get_place_id()
        repository = SupabaseSightingsRepository(get_supabase_client(), place_id)
        epoch = repository.get_epoch()
        if epoch is None:
            return [["-", "-", "-", "Belum ada data, menunggu sweep pertama..."]]

        sightings = repository.list_sightings()
        now = datetime.now(timezone.utc)
        ranked = rank_upcoming_spawns(sightings, epoch=epoch, now=now)
        if not ranked:
            return [["-", "-", "-", "Belum ada server yang reliable, coba lagi nanti"]]

        return [_format_row(p) for p in ranked[:MAX_ROWS_SHOWN]]
    except Exception:
        logger.exception("failed to build dashboard")
        return [["-", "-", "-", "Error ambil data, cek log"]]


_start_background_worker()

with gr.Blocks(title="Fisch Sunken Treasure Tracker") as demo:
    gr.Markdown("# Fisch Sunken Treasure Tracker")
    gr.Markdown(
        "Server diurutkan berdasarkan seberapa dekat window Sunken Treasure "
        "(aktif duluan, lalu yang paling deket mulai). Cuma server dengan "
        "estimasi umur yang reliable yang ditampilkan."
    )
    gr.Dataframe(headers=TABLE_HEADERS, value=build_dashboard_rows, every=REFRESH_SECONDS)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 7860)))
