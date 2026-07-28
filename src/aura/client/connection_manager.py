"""Qt-powered connection manager for Aura.

This class owns a single websocket client, manages connection state transitions,
and handles reconnect/backoff without blocking the UI thread.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QObject, QTimer, Signal
from loguru import logger

from .constants import RECONNECT_DELAY
from .websocket_client import AuraWebSocketClient
from ..shared import AuraMessage


class ConnectionManager(QObject):
    stateChanged = Signal(str)

    def __init__(self, url: str = "ws://127.0.0.1:8765/ws") -> None:
        super().__init__()
        self.url = url
        self._client: Optional[AuraWebSocketClient] = None
        self._reconnect_timer: Optional[QTimer] = None
        self._running = False
        self._state = "Disconnected"
        self._backoff_index = 0

        self._on_connected: Optional[Callable[[], None]] = None
        self._on_disconnected: Optional[Callable[[], None]] = None
        self._on_message: Optional[Callable[[object], None]] = None
        self._on_error: Optional[Callable[[Exception], None]] = None

    def on_connected(self, cb: Callable[[], None]) -> None:
        self._on_connected = cb

    def on_disconnected(self, cb: Callable[[], None]) -> None:
        self._on_disconnected = cb

    def on_message(self, cb: Callable[[object], None]) -> None:
        self._on_message = cb

    def on_error(self, cb: Callable[[Exception], None]) -> None:
        self._on_error = cb

    def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._setup_reconnect_timer()
        self._connect()

    def stop(self) -> None:
        self._running = False
        self._set_state("Disconnected")
        if self._reconnect_timer is not None:
            self._reconnect_timer.stop()
        if self._client is not None:
            self._client.disconnect()
            self._client = None

    def send(self, message: AuraMessage) -> None:
        if self._client is None or not self._client.is_connected():
            raise RuntimeError("ConnectionManager is not running")
        self._client.send(message)

    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected()

    def _set_state(self, state: str) -> None:
        self._state = state
        self.stateChanged.emit(state)

    def _setup_reconnect_timer(self) -> None:
        if self._reconnect_timer is None:
            self._reconnect_timer = QTimer(self)
            self._reconnect_timer.setSingleShot(True)
            self._reconnect_timer.timeout.connect(self._connect)

    def _connect(self) -> None:
        if not self._running:
            return

        if self._client is not None:
            self._client.disconnect()

        self._set_state("Connecting")
        logger.info("Connecting...")
        self._client = AuraWebSocketClient(self.url)
        self._client.connected.connect(self._handle_connected)
        self._client.disconnected.connect(self._handle_disconnected)
        self._client.messageReceived.connect(self._handle_message)
        self._client.errorOccurred.connect(self._handle_error)
        self._client.connect()

    def _schedule_reconnect(self) -> None:
        if not self._running:
            return

        delay = self._next_delay()
        self._set_state("Reconnecting")
        logger.info("Reconnect in {} sec", delay / 1000)
        self._reconnect_timer.start(delay)

    def _next_delay(self) -> int:
        delays = [1000, 2000, 5000, 10000, 30000]
        delay = delays[min(self._backoff_index, len(delays) - 1)]
        self._backoff_index += 1
        return delay

    def _handle_connected(self) -> None:
        self._backoff_index = 0
        self._set_state("Connected")
        logger.info("Connected")
        if self._on_connected is not None:
            self._on_connected()

    def _handle_disconnected(self) -> None:
        self._set_state("Disconnected")
        logger.warning("Disconnected")
        if self._on_disconnected is not None:
            self._on_disconnected()
        self._schedule_reconnect()

    def _handle_message(self, message: object) -> None:
        if self._on_message is not None:
            self._on_message(message)

    def _handle_error(self, exc: Exception) -> None:
        logger.warning("Connection error: {}", exc)
        if self._on_error is not None:
            self._on_error(exc)
        if self._running:
            self._schedule_reconnect()
