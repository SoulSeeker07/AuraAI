"""Qt-based websocket client for Aura.

This client owns a single QWebSocket instance, exposes Qt signals for the UI,
and keeps the transport logic off the main thread. It does not implement
reconnection by itself; the ConnectionManager is responsible for that.
"""

from __future__ import annotations

from loguru import logger
from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QAbstractSocket
from PySide6.QtWebSockets import QWebSocket

from ..shared import AuraMessage, MessageType, deserialize, serialize
from .constants import HEARTBEAT_INTERVAL


class AuraWebSocketClient(QObject):
    connected = Signal()
    disconnected = Signal()
    messageReceived = Signal(object)
    errorOccurred = Signal(str)

    def __init__(self, url: str = "ws://127.0.0.1:8765/ws") -> None:
        super().__init__()
        self.url = url
        self._socket: QWebSocket | None = None
        self._heartbeatTimer: QTimer | None = None
        self._connected = False

    def connect(self) -> None:
        if self._connected and self._socket is not None:
            return

        logger.info("Connecting to {}", self.url)
        self._socket = QWebSocket("AuraClient", parent=None)
        self._socket.connected.connect(self._on_connected)
        self._socket.disconnected.connect(self._on_disconnected)
        self._socket.textMessageReceived.connect(self._on_text_message)
        self._socket.error.connect(self._on_socket_error)
        self._socket.open(QUrl(self.url))

    def disconnect(self) -> None:
        if self._heartbeatTimer is not None:
            self._heartbeatTimer.stop()
            self._heartbeatTimer.deleteLater()
            self._heartbeatTimer = None

        if self._socket is not None:
            self._socket.close()
            self._socket.deleteLater()
            self._socket = None

        self._connected = False

    def send(self, message: AuraMessage) -> None:
        if self._socket is None or not self._connected:
            raise RuntimeError("WebSocket is not connected")

        payload = serialize(message)
        self._socket.sendTextMessage(payload)

    def is_connected(self) -> bool:
        return self._connected

    def _start_heartbeat(self) -> None:
        if self._heartbeatTimer is None:
            self._heartbeatTimer = QTimer(self)
            self._heartbeatTimer.timeout.connect(self._send_heartbeat)
        self._heartbeatTimer.start(HEARTBEAT_INTERVAL)

    def _stop_heartbeat(self) -> None:
        if self._heartbeatTimer is not None:
            self._heartbeatTimer.stop()

    def _send_heartbeat(self) -> None:
        if not self._connected or self._socket is None:
            return

        heartbeat = AuraMessage(
            type=MessageType.HEARTBEAT,
            source="desktop",
            target="service",
            payload={},
        )
        try:
            self.send(heartbeat)
            logger.info("Heartbeat OK")
        except Exception as exc:
            logger.warning("Heartbeat failed: {}", exc)
            self._on_disconnected()

    def _on_connected(self) -> None:
        self._connected = True
        self._start_heartbeat()
        logger.info("Connected")
        self.connected.emit()

    def _on_disconnected(self) -> None:
        self._stop_heartbeat()
        self._connected = False
        logger.warning("Connection Lost")
        self.disconnected.emit()

    def _on_text_message(self, message: str) -> None:
        try:
            decoded = deserialize(message)
            self.messageReceived.emit(decoded)
        except Exception as exc:
            logger.warning("Failed to deserialize message: {}", exc)
            self.errorOccurred.emit(str(exc))

    def _on_socket_error(self, error: QAbstractSocket.SocketError) -> None:
        logger.warning("Socket error: {}", error)
        self.errorOccurred.emit(str(error))
