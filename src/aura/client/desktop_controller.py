from __future__ import annotations

import json
import os
from typing import Any

from loguru import logger
from PySide6.QtCore import QObject, Signal, Slot

from .connection_manager import ConnectionManager
from .protocol import build_message


class DesktopController(QObject):
    connected = Signal(bool)
    status = Signal(str)
    messageReceived = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        host = os.getenv("AURA_HOST", "127.0.0.1")
        port = int(os.getenv("AURA_PORT", "8765"))
        path = os.getenv("AURA_WS_PATH", "/ws")

        self._mgr = ConnectionManager(host=host, port=port, path=path)
        self._mgr.on_connected(self._on_connected)
        self._mgr.on_disconnected(self._on_disconnected)
        self._mgr.on_message(self._on_message)
        self._mgr.on_error(self._on_error)

    @Slot()
    def start(self):
        logger.debug("DesktopController.start() called")
        self.status.emit("Connecting...")
        self._mgr.start()

    @Slot()
    def stop(self):
        logger.debug("DesktopController.stop() called")
        self._mgr.stop()
        self.status.emit("Stopped")

    @Slot(str)
    def send(self, text: str):
        try:
            payload = {"text": text}
            msg = build_message(
                "chat.message", payload, source="desktop", target="service"
            )
            self._mgr.send(msg)
            self.status.emit("Sent")
        except Exception as e:
            self._on_error(e)

    # internal callbacks
    def _on_connected(self):
        logger.info("DesktopController connected callback")
        self.status.emit("Connected")
        self.connected.emit(True)

    def _on_disconnected(self):
        logger.info("DesktopController disconnected callback")
        self.status.emit("Disconnected")
        self.connected.emit(False)

    def _on_message(self, message: dict[str, Any]):
        # forward JSON string to QML
        try:
            s = json.dumps(message)
        except Exception:
            s = str(message)
        logger.debug("DesktopController received message: {}", s)
        self.messageReceived.emit(s)

    def _on_error(self, exc: Exception):
        logger.warning("DesktopController error: {}", exc)
        self.status.emit(f"Error: {exc}")
