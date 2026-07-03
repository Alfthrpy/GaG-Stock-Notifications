"""FastAPI backend for the Fisch Sunken Treasure Tracker.

Replaces the old Gradio dashboard. Runs the poller
(fisch_tracker.main.run_forever) in a dedicated background thread with its
own event loop -- same pattern the old Gradio app used, since the poller's
repository calls are synchronous (blocking) and would otherwise stall this
process's main event loop, which now also has to serve HTTP/WebSocket
traffic. The API's own repository reads/writes are dispatched via
asyncio.to_thread for the same reason.

Configure via env vars: FISCH_PLACE_ID, SUPABASE_URL, SUPABASE_KEY.
Run with: uvicorn api:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import asyncio
import logging
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from fisch_tracker.config import get_place_id, get_supabase_client
from fisch_tracker.main import run_forever
from fisch_tracker.supabase_repository import SupabaseSightingsRepository
from fisch_tracker.tracker import apply_age_confirmation
from fisch_tracker.treasure import PredictedSpawn, rank_upcoming_spawns

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fisch_tracker.api")

# treasure.rank_upcoming_spawns never keeps a row past a 6h recency
# window, so anything older than that can never make the ranked list --
# fetching it from Supabase (and paginating through it) would be pure
# waste. Buffer by 1h over that ceiling, not more.
DASHBOARD_LOOKBACK_HOURS = 7
BROADCAST_INTERVAL_SECONDS = 5
JOIN_DEEP_LINK = "roblox://experiences/start?placeId={place_id}&gameInstanceId={job_id}"


def _start_background_poller() -> None:
    def _run() -> None:
        try:
            asyncio.run(run_forever())
        except Exception:
            logger.exception("background poller crashed")

    threading.Thread(target=_run, daemon=True, name="fisch-tracker-poller").start()


def _get_repository() -> SupabaseSightingsRepository:
    place_id = get_place_id()
    return SupabaseSightingsRepository(get_supabase_client(), place_id)


def _serialize(prediction: PredictedSpawn, place_id: int) -> dict[str, Any]:
    return {
        "job_id": prediction.job_id,
        "playing": prediction.playing,
        "max_players": prediction.max_players,
        "age_seconds": prediction.age_seconds,
        "is_active": prediction.is_active,
        "seconds_until_start": prediction.seconds_until_start,
        "seconds_until_end": prediction.seconds_until_end,
        "is_confirmed": prediction.is_confirmed,
        "join_link": JOIN_DEEP_LINK.format(place_id=place_id, job_id=prediction.job_id),
    }


def get_ranked_servers_sync() -> dict[str, Any]:
    """Fetch + rank synchronously (blocking network calls) -- callers in
    async context should dispatch this via asyncio.to_thread. Returns a
    JSON-serializable payload with a server_time anchor so clients can
    tick countdowns locally between broadcasts."""
    place_id = get_place_id()
    repository = _get_repository()
    now = datetime.now(timezone.utc)
    epoch = repository.get_epoch()
    if epoch is None:
        return {"servers": [], "server_time": now.isoformat(), "status": "waiting_for_first_sweep"}

    sightings = repository.list_sightings(since=now - timedelta(hours=DASHBOARD_LOOKBACK_HOURS))
    ranked = rank_upcoming_spawns(sightings, epoch=epoch, now=now)
    return {
        "servers": [_serialize(p, place_id) for p in ranked],
        "server_time": now.isoformat(),
        "status": "ok",
    }


class ConfirmAgeRequest(BaseModel):
    days: int = Field(default=0, ge=0)
    hours: int = Field(default=0, ge=0, le=23)
    minutes: int = Field(default=0, ge=0, le=59)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        dead = []
        for connection in list(self._connections):
            try:
                await connection.send_json(payload)
            except Exception:
                dead.append(connection)
        for connection in dead:
            self.disconnect(connection)


manager = ConnectionManager()


async def _broadcast_loop() -> None:
    while True:
        await asyncio.sleep(BROADCAST_INTERVAL_SECONDS)
        try:
            payload = await asyncio.to_thread(get_ranked_servers_sync)
            await manager.broadcast(payload)
        except Exception:
            logger.exception("broadcast loop failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _start_background_poller()
    broadcast_task = asyncio.create_task(_broadcast_loop())
    yield
    broadcast_task.cancel()


app = FastAPI(title="Fisch Sunken Treasure Tracker API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to the real frontend origin once deployed
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/servers")
async def list_servers() -> dict[str, Any]:
    try:
        return await asyncio.to_thread(get_ranked_servers_sync)
    except Exception:
        logger.exception("failed to list servers")
        raise HTTPException(status_code=500, detail="failed to fetch servers")


@app.post("/api/servers/{job_id}/confirm-age")
async def confirm_age(job_id: str, body: ConfirmAgeRequest) -> dict[str, Any]:
    reported_age_seconds = body.days * 86400 + body.hours * 3600 + body.minutes * 60
    if reported_age_seconds <= 0:
        raise HTTPException(status_code=400, detail="reported age must be greater than 0")

    def _confirm() -> None:
        repository = _get_repository()
        apply_age_confirmation(repository, job_id, reported_age_seconds, observed_at=datetime.now(timezone.utc))

    try:
        await asyncio.to_thread(_confirm)
    except Exception:
        logger.exception("failed to confirm age for job_id=%s", job_id)
        raise HTTPException(status_code=500, detail="failed to save confirmation")

    # push the update immediately instead of waiting for the next periodic tick
    try:
        payload = await asyncio.to_thread(get_ranked_servers_sync)
        await manager.broadcast(payload)
    except Exception:
        logger.exception("failed to broadcast after confirmation")

    return {"status": "ok", "job_id": job_id}


@app.post("/api/servers/{job_id}/mark-dead")
async def mark_dead(job_id: str) -> dict[str, Any]:
    def _delete() -> None:
        repository = _get_repository()
        repository.delete_sighting(job_id)

    try:
        await asyncio.to_thread(_delete)
    except Exception:
        logger.exception("failed to mark job_id=%s as dead", job_id)
        raise HTTPException(status_code=500, detail="failed to delete server")

    # push the update immediately instead of waiting for the next periodic tick
    try:
        payload = await asyncio.to_thread(get_ranked_servers_sync)
        await manager.broadcast(payload)
    except Exception:
        logger.exception("failed to broadcast after mark-dead")

    return {"status": "ok", "job_id": job_id}


@app.websocket("/ws/servers")
async def servers_websocket(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        payload = await asyncio.to_thread(get_ranked_servers_sync)
        await websocket.send_json(payload)
        while True:
            # no messages expected from the client; awaiting is what lets
            # us detect disconnects without polling the socket manually
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
