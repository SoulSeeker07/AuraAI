import asyncio
import json
import threading
import time

import pytest
import websockets

from src.aura.client.connection_manager import ConnectionManager

PORT = 8766
PATH = "/ws"


async def _echo_ws_handler(websocket, path):
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
            # echo with a small wrapper
            await websocket.send(json.dumps({"type": "echo", "original": data}))


def _start_server(loop):
    asyncio.set_event_loop(loop)
    server = websockets.serve(_echo_ws_handler, "127.0.0.1", PORT)
    loop.run_until_complete(server)
    loop.run_forever()


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
    mgr = ConnectionManager(host="127.0.0.1", port=PORT, path=PATH)

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
    ok = connected_ev.wait(timeout=5)
    assert ok, "Did not connect in time"

    # send a test message
    mgr.send({"type": "test", "payload": {"hello": "world"}})

    ok2 = msg_ev.wait(timeout=5)
    assert ok2, "Did not receive echoed message"

    assert "msg" in received
    assert received["msg"].get("type") == "echo"

    mgr.stop()
