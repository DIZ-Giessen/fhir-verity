"""WebSocket endpoint for live validation progress."""

import json
import logging
from typing import Dict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
logger = logging.getLogger(__name__)

active_connections: Dict[str, list[WebSocket]] = {}


@router.websocket("/ws/validation/{run_id}")
async def websocket_endpoint(websocket: WebSocket, run_id: str):
    """WebSocket for live progress of a validation run."""
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
