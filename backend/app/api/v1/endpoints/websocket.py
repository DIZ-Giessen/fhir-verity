"""WebSocket endpoint for live validation progress."""

import json
import logging
import uuid
from typing import Dict

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.security import load_server_scoped
from app.models.user import User
from app.models.validation_run import ValidationRun

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()

active_connections: Dict[str, list[WebSocket]] = {}


@router.websocket("/ws/validation/{run_id}")
async def websocket_endpoint(websocket: WebSocket, run_id: str):
    """WebSocket for live progress of a validation run.

    Same access rules as GET /validation/runs/{run_id}: the session cookie
    must belong to a user who can see the run's server.
    """
    if not await _may_watch(websocket, run_id):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()

    if run_id not in active_connections:
        active_connections[run_id] = []
    active_connections[run_id].append(websocket)
    logger.debug(
        "WebSocket connected for run %s. Total clients: %d",
        run_id,
        len(active_connections[run_id]),
    )

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(
                    json.dumps({"type": "pong", "run_id": run_id})
                )
    except WebSocketDisconnect:
        _remove_connection(run_id, websocket)
        logger.debug("WebSocket disconnected for run %s", run_id)


def _allowed_origins() -> set[str]:
    origins = {o.rstrip("/") for o in settings.cors_origins_list}
    origins.add(settings.FRONTEND_BASE_URL.rstrip("/"))
    return origins


async def _may_watch(websocket: WebSocket, run_id: str) -> bool:
    """True if the connecting session may follow this run."""
    # Browsers send the session cookie along with cross-site WebSocket
    # handshakes from the same site, so only accept Verity's own pages.
    origin = websocket.headers.get("origin")
    if origin and origin.rstrip("/") not in _allowed_origins():
        return False
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        return False
    if not settings.AUTH_ENABLED:
        return True

    user_id = websocket.session.get("user_id")
    if not user_id:
        return False

    async with AsyncSessionLocal() as db:
        try:
            user = (
                await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
            ).scalar_one_or_none()
        except ValueError:
            return False
        server_id = (
            await db.execute(
                select(ValidationRun.server_id).where(ValidationRun.id == run_uuid)
            )
        ).scalar_one_or_none()
        if user is None or server_id is None:
            return False
        try:
            await load_server_scoped(server_id, user, db)
        except HTTPException:
            return False
    return True


def _remove_connection(run_id: str, websocket: WebSocket):
    """Remove a single connection and clean up if no more clients."""
    if run_id in active_connections:
        try:
            active_connections[run_id].remove(websocket)
        except ValueError:
            pass
        if not active_connections[run_id]:
            del active_connections[run_id]


async def broadcast_progress(run_id: str, progress_data: dict):
    """
    Send progress data to all connected clients for a run.
    Dead connections are removed silently.
    """
    if run_id not in active_connections:
        return

    message = json.dumps(progress_data, default=str)
    dead: list[WebSocket] = []

    for connection in active_connections[run_id]:
        try:
            await connection.send_text(message)
        except Exception:
            dead.append(connection)

    for conn in dead:
        _remove_connection(run_id, conn)
