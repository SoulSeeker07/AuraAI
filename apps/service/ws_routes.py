from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from .ws_manager import WebSocketManager
from .logger import get_logger
from .config import settings

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
    await manager.connect(websocket)
    log.info("WebSocket connected")
    try:
        while True:
            data = await websocket.receive_text()
            # Echo for now
            await manager.send_personal_message(f"echo: {data}", websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        log.info("WebSocket disconnected")


# helper to set manager from app
def set_manager(mgr: WebSocketManager):
    global _manager
    _manager = mgr
