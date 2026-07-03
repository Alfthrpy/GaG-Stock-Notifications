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
from gradio_modal import Modal

from fisch_tracker.config import get_place_id, get_supabase_client
from fisch_tracker.main import run_forever
from fisch_tracker.supabase_repository import SupabaseSightingsRepository
from fisch_tracker.tracker import apply_age_confirmation
from fisch_tracker.treasure import PredictedSpawn, rank_upcoming_spawns

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fisch_tracker.app")

TABLE_HEADERS = ["Job ID", "Players", "Umur Server", "Status Spawn", "Status Umur", "Join"]
TABLE_DATATYPES = ["str", "str", "str", "str", "str", "markdown"]
MAX_ROWS_SHOWN = 30
REFRESH_SECONDS = 15
JOIN_DEEP_LINK = "roblox://experiences/start?placeId={place_id}&gameInstanceId={job_id}"
JOIN_COLUMN_INDEX = TABLE_HEADERS.index("Join")


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


def _format_row(prediction: PredictedSpawn, place_id: int) -> list[str]:
    status = f"AKTIF ({_format_countdown(prediction.seconds_until_end)} lagi tutup)" if prediction.is_active else f"{_format_countdown(prediction.seconds_until_start)} lagi"
    age_status = "✅ Terkonfirmasi" if prediction.is_confirmed else "🔮 Tebakan (belum pasti)"
    join_link = JOIN_DEEP_LINK.format(place_id=place_id, job_id=prediction.job_id)
    return [
        prediction.job_id,
        f"{prediction.playing}/{prediction.max_players}",
        _format_countdown(prediction.age_seconds),
        status,
        age_status,
        f"[🎮 Join]({join_link})",
    ]


def build_dashboard_rows() -> list[list[str]]:
    try:
        place_id = get_place_id()
        repository = SupabaseSightingsRepository(get_supabase_client(), place_id)
        epoch = repository.get_epoch()
        if epoch is None:
            return [["-", "-", "-", "Belum ada data, menunggu sweep pertama...", "-", ""]]

        sightings = repository.list_sightings()
        now = datetime.now(timezone.utc)
        ranked = rank_upcoming_spawns(sightings, epoch=epoch, now=now)
        if not ranked:
            return [["-", "-", "-", "Belum ada server yang reliable, coba lagi nanti", "-", ""]]

        return [_format_row(p, place_id) for p in ranked[:MAX_ROWS_SHOWN]]
    except Exception:
        logger.exception("failed to build dashboard")
        return [["-", "-", "-", "Error ambil data, cek log", "-", ""]]


def report_age(job_id: str, days: float, hours: float, minutes: float) -> tuple[str, dict]:
    job_id = (job_id or "").strip()
    if not job_id:
        return "Job ID kosong -- klik salah satu baris di tabel dulu.", gr.update(visible=True)

    try:
        days = int(days or 0)
        hours = int(hours or 0)
        minutes = int(minutes or 0)
    except (TypeError, ValueError):
        return "Hari/jam/menit harus angka.", gr.update(visible=True)

    reported_age_seconds = days * 86400 + hours * 3600 + minutes * 60
    if reported_age_seconds <= 0:
        return "Umur server harus lebih dari 0.", gr.update(visible=True)

    try:
        place_id = get_place_id()
        repository = SupabaseSightingsRepository(get_supabase_client(), place_id)
        apply_age_confirmation(repository, job_id, reported_age_seconds, observed_at=datetime.now(timezone.utc))
    except Exception:
        logger.exception("failed to apply age confirmation for job_id=%s", job_id)
        return "Gagal nyimpen laporan, cek log.", gr.update(visible=True)

    return (
        f"Makasih! Umur server {job_id} udah dikonfirmasi jadi {days}h {hours}j {minutes}m. "
        "Bakal keliatan 'Terkonfirmasi' di tabel abis refresh berikutnya.",
        gr.update(visible=False),
    )


def refresh_dashboard() -> tuple[list[list[str]], list[list[str]]]:
    rows = build_dashboard_rows()
    return rows, rows


def open_report_modal(rows: list[list[str]], evt: gr.SelectData) -> tuple[str, dict]:
    row_index, col_index = evt.index
    if col_index == JOIN_COLUMN_INDEX:
        return gr.update(), gr.update()  # let the Join link click through undisturbed

    if not rows or row_index >= len(rows) or rows[row_index][0] == "-":
        return gr.update(), gr.update()

    job_id = rows[row_index][0]
    return job_id, gr.update(visible=True)


_start_background_worker()

with gr.Blocks(title="Fisch Sunken Treasure Tracker") as demo:
    gr.Markdown("# Fisch Sunken Treasure Tracker")
    gr.Markdown(
        "Server diurutkan berdasarkan seberapa dekat window Sunken Treasure "
        "(aktif duluan, lalu yang paling deket mulai). Kolom **Status Umur** "
        "nunjukkin apakah umur server itu udah dikonfirmasi manual (akurat) "
        "atau masih tebakan (bisa meleset). Klik **Join** buat langsung masuk "
        "ke server itu, atau klik baris mana aja buat lapor umur asli yang "
        "lo liat di UI Fisch."
    )
    row_state = gr.State([])
    table = gr.Dataframe(headers=TABLE_HEADERS, datatype=TABLE_DATATYPES)

    with Modal(visible=False) as report_modal:
        gr.Markdown("### Lapor Umur Server")
        modal_job_id = gr.Textbox(label="Job ID", interactive=False)
        with gr.Row():
            days_input = gr.Number(label="Hari", precision=0, minimum=0)
            hours_input = gr.Number(label="Jam", precision=0, minimum=0, maximum=23)
            minutes_input = gr.Number(label="Menit", precision=0, minimum=0, maximum=59)
        report_button = gr.Button("Kirim Laporan")
        report_output = gr.Textbox(label="Hasil", interactive=False)

    demo.load(fn=refresh_dashboard, outputs=[table, row_state])
    gr.Timer(REFRESH_SECONDS).tick(fn=refresh_dashboard, outputs=[table, row_state])
    table.select(fn=open_report_modal, inputs=[row_state], outputs=[modal_job_id, report_modal])
    report_button.click(
        fn=report_age,
        inputs=[modal_job_id, days_input, hours_input, minutes_input],
        outputs=[report_output, report_modal],
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 7860)))
