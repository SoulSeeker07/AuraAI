import asyncio
import json
import sys
import threading
import time
from pathlib import Path

import websockets
from PySide6.QtCore import QCoreApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.aura.client.connection_manager import ConnectionManager
from src.aura.shared import AuraMessage, MessageType

PORT = 8765
PATH = "/ws"


async def _service_handler(websocket):
    async for message in websocket:
        try:
            data = json.loads(message)
        except Exception:
            data = {"type": "raw", "raw": message}

        if isinstance(data, dict) and data.get("type") == "heartbeat":
            await websocket.send(json.dumps({"type": "heartbeat_ack"}))
        elif isinstance(data, dict) and data.get("type") == "chat.message":
            await websocket.send(
                json.dumps({"type": "chat.response", "payload": {"ok": True}})
            )
        else:
            await websocket.send(
                json.dumps(
                    {"type": "welcome", "payload": {"message": "Welcome to Aura"}}
                )
            )


async def _run_server():
    async with websockets.serve(
        _service_handler, "127.0.0.1", PORT, ping_interval=None
    ):
        await asyncio.Future()


def main():
    app = QCoreApplication.instance() or QCoreApplication([])

    server_thread = threading.Thread(
        target=lambda: asyncio.run(_run_server()), daemon=True
    )
    server_thread.start()
    time.sleep(1)

    manager = ConnectionManager(url=f"ws://127.0.0.1:{PORT}{PATH}")
    received = []

    def on_connected():
        print("Connected!")

    def on_disconnected():
        print("Disconnected")

    def on_message(message):
        received.append(message)
        print("Welcome Received")

    manager.on_connected(on_connected)
    manager.on_disconnected(on_disconnected)
    manager.on_message(on_message)

    manager.start()
    app.processEvents()
    time.sleep(2)

    message = AuraMessage(
        type=MessageType.CHAT_MESSAGE,
        source="desktop",
        target="service",
        payload={"text": "Hello"},
    )
    manager.send(message)
    app.processEvents()
    time.sleep(2)

    print("Heartbeat OK")
    manager.stop()
    app.processEvents()


if __name__ == "__main__":
    main()
