"""Small console test for the ConnectionManager & AsyncWebSocketClient.

Usage: python test_client.py

This test attempts to connect to the local Aura Service, prints status,
and sends a test message. It demonstrates heartbeat/echo behavior.
"""
import time
import json

from src.aura.client.connection_manager import ConnectionManager
from src.aura.client.api_client import ApiClient


def main():
    print("Starting console test for Aura networking")

    api = ApiClient()
    try:
        print("Health:", api.health())
    except Exception as e:
        print("Health check failed:", e)

    mgr = ConnectionManager()

    def on_conn():
        print("Connected!")

    def on_disc():
        print("Disconnected")

    def on_msg(msg):
        print("RECV:", json.dumps(msg))

    def on_err(e):
        print("ERROR:", e)

    mgr.on_connected(on_conn)
    mgr.on_disconnected(on_disc)
    mgr.on_message(on_msg)
    mgr.on_error(on_err)

    mgr.start()

    # run for a short period and then send a message
    time.sleep(2)
    if mgr.is_connected():
        mgr.send({"type": "test", "payload": {"hello": "world"}})

    # keep running to see heartbeats and messages
    try:
        for _ in range(30):
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    mgr.stop()
    api.close()
    print("Test finished")


if __name__ == "__main__":
    main()
