"""Websocket Endpoint"""

import json
from typing import Dict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

# Aktive WebSocket-Verbindungen pro Run
active_connections: Dict[str, list[WebSocket]] = {}


@router.websocket("/ws/validation/{run_id}")
async def websocket_endpoint(websocket: WebSocket, run_id: str):
    """WebSocket für Live-Progress eines Validierungs-Runs."""
    await websocket.accept()

    if run_id not in active_connections:
        active_connections[run_id] = []
    active_connections[run_id].append(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(
                    json.dumps({"status": "connected", "run_id": run_id})
                )
    except WebSocketDisconnect:
        active_connections[run_id].remove(websocket)
        if not active_connections[run_id]:
            del active_connections[run_id]


async def broadcast_progress(run_id: str, progress_data: dict):
    """Sendet Fortschritt an alle verbundenen Clients."""
    if run_id in active_connections:
        message = json.dumps(progress_data)
        for connection in active_connections[run_id]:
            try:
                await connection.send_text(message)
            except:
                pass
