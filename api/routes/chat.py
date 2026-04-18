"""WebSocket chat endpoint streaming Sidekick.run_superstep yields as JSON frames."""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.deps import sidekick_registry

router = APIRouter(tags=["chat"])

log = logging.getLogger(__name__)


@router.websocket("/api/ws/chat/{session_id}")
async def chat_ws(websocket: WebSocket, session_id: str):
    """
    Protocol — the client sends one JSON object per turn:

        {"message": "...", "success_criteria": "...", "history": [...]}

    The server streams back frames:

        {"type": "history", "history": [...]}      — repeated, latest snapshot
        {"type": "done"}                           — turn finished
        {"type": "error", "error": "..."}          — something blew up

    The connection stays open between turns; the next client message starts
    another superstep against the same Sidekick.
    """
    await websocket.accept()

    try:
        sidekick = await sidekick_registry.get(session_id)
    except Exception as e:
        log.exception("Failed to bring up Sidekick for %s", session_id)
        await websocket.send_text(json.dumps({"type": "error", "error": str(e)}))
        await websocket.close()
        return

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
                message = payload["message"]
                success_criteria = payload.get("success_criteria") or ""
                history = payload.get("history") or []
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                await websocket.send_text(
                    json.dumps({"type": "error", "error": f"bad payload: {e}"})
                )
                continue

            try:
                async for updated in sidekick.run_superstep(
                    message, success_criteria, history
                ):
                    await websocket.send_text(
                        json.dumps({"type": "history", "history": updated})
                    )
                await websocket.send_text(json.dumps({"type": "done"}))
            except Exception as e:
                log.exception("Superstep failed for session %s", session_id)
                await websocket.send_text(
                    json.dumps({"type": "error", "error": str(e)})
                )

    except WebSocketDisconnect:
        log.info("Chat WS disconnected for session %s", session_id)
