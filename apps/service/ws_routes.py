import json
from datetime import UTC, datetime
from uuid import uuid4

from Chatbot import get_default_bot
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .config import settings
from .logger import get_logger
from .ws_manager import WebSocketManager

router = APIRouter()
log = get_logger("ws")

# single manager instance for the app (will be assigned by app factory)
_manager: WebSocketManager | None = None


def get_manager() -> WebSocketManager:
    if _manager is None:
        raise RuntimeError("WebSocketManager not initialized")
    return _manager


@router.websocket(settings.ws_path)
async def websocket_endpoint(websocket: WebSocket):
    manager = get_manager()
    chatbot = get_default_bot()
    await manager.connect(websocket)
    log.info("WebSocket connected")
    try:
        while True:
            data = await websocket.receive_text()
            prompt = _extract_prompt(data)
            response = (
                chatbot.ask(prompt)
                if prompt
                else "I did not receive any text to answer."
            )
            await manager.send_personal_message(_chat_response(response), websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        log.info("WebSocket disconnected")


# helper to set manager from app
def set_manager(mgr: WebSocketManager):
    global _manager
    _manager = mgr


def _extract_prompt(data: str) -> str:
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return data.strip()

    if isinstance(payload, dict):
        nested = payload.get("payload")
        if isinstance(nested, dict):
            return str(nested.get("text") or nested.get("message") or "").strip()
        return str(payload.get("text") or payload.get("message") or "").strip()
    return str(payload).strip()


def _chat_response(text: str) -> str:
    return json.dumps(
        {
            "id": str(uuid4()),
            "type": "chat.response",
            "timestamp": datetime.now(UTC).isoformat(),
            "source": "service",
            "target": "desktop",
            "payload": {"text": text},
        }
    )
