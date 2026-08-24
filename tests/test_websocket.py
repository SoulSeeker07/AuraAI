import asyncio
import json
import threading
import time

import pytest
import websockets

from aura.client.connection_manager import ConnectionManager
from aura.shared.enums import MessageType
from aura.shared.message import AuraMessage

PORT = 8766
PATH = "/ws"


async def _echo_ws_handler(websocket, *args, **kwargs):
    # simple handler: echo back and respond to heartbeat
    async for message in websocket:
        try:
            data = json.loads(message)
        except Exception:
            data = {"type": "raw", "raw": message}
        # respond to heartbeat
        if isinstance(data, dict) and data.get("type") == "heartbeat":
            await websocket.send(json.dumps({"type": "heartbeat_ack"}))
        else:
            # echo with a valid AuraMessage schema
            echo_msg = {
                "id": data.get("id", "1"),
                "type": "chat.response",
                "source": "server",
                "target": "client",
                "payload": data.get("payload", {}),
            }
            await websocket.send(json.dumps(echo_msg))


def _start_server(loop):
    asyncio.set_event_loop(loop)
    async def serve():
        async with websockets.serve(_echo_ws_handler, "127.0.0.1", PORT):
            await asyncio.Future()
    loop.run_until_complete(serve())


@pytest.fixture(scope="module")
def ws_server():
    loop = asyncio.new_event_loop()
    t = threading.Thread(target=_start_server, args=(loop,), daemon=True)
    t.start()
    # give server a moment
    time.sleep(0.5)
    yield
    loop.call_soon_threadsafe(loop.stop)
    t.join(timeout=2)


def test_connection_and_echo(ws_server):
    from PySide6.QtCore import QCoreApplication
    app = QCoreApplication.instance() or QCoreApplication([])
    mgr = ConnectionManager(url=f"ws://127.0.0.1:{PORT}{PATH}")

    connected_ev = threading.Event()
    msg_ev = threading.Event()
    received = {}

    def on_conn():
        connected_ev.set()

    def on_msg(m):
        received["msg"] = m
        msg_ev.set()

    def on_err(e):
        pytest.fail(f"ConnectionManager error: {e}")

    mgr.on_connected(on_conn)
    mgr.on_message(on_msg)
    mgr.on_error(on_err)

    mgr.start()

    # wait for connection
    t_end = time.monotonic() + 5.0
    while time.monotonic() < t_end and not connected_ev.is_set():
        app.processEvents()
        time.sleep(0.05)
    assert connected_ev.is_set(), "Did not connect in time"

    # send a test message
    test_msg = AuraMessage(
        type=MessageType.CHAT_MESSAGE,
        source="client",
        target="server",
        payload={"hello": "world"},
    )
    mgr.send(test_msg)

    t_end2 = time.monotonic() + 5.0
    while time.monotonic() < t_end2 and not msg_ev.is_set():
        app.processEvents()
        time.sleep(0.05)
    assert msg_ev.is_set(), "Did not receive echoed message"

    assert "msg" in received
    assert received["msg"].type == MessageType.CHAT_RESPONSE
    assert received["msg"].payload == {"hello": "world"}

    mgr.stop()
