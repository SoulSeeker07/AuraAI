from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from ...client import ConnectionManager
from ...shared import AuraMessage, MessageType


class OverlayController(QObject):
    visibilityChanged = Signal(bool)
    messageSent = Signal(object)
    messageReceived = Signal(object)
    connectionChanged = Signal(str)
    errorOccurred = Signal(str)

    def __init__(self, connection_manager: ConnectionManager | None = None) -> None:
        super().__init__()
        self._visible = False
        self._connection_state = "Offline"
        self._connection_manager = connection_manager or ConnectionManager()
        self._input_text = ""
        self._messages: list[dict] = []
        self._setup_connection_handlers()

    @Property(bool)
    def visible(self) -> bool:
        return self._visible

    @Property(str)
    def connection_state(self) -> str:
        return self._connection_state

    @Property(object)
    def messages(self) -> list[dict]:
        return self._messages

    @Slot()
    def show(self) -> None:
        self._visible = True
        self.visibilityChanged.emit(True)

    @Slot()
    def hide(self) -> None:
        self._visible = False
        self.visibilityChanged.emit(False)

    @Slot()
    def toggle(self) -> None:
        self.show() if not self._visible else self.hide()

    @Slot(str)
    def send_message(self, text: str) -> None:
        if not text.strip():
            return

        self._input_text = ""
        self._messages.append({"role": "user", "text": text})
        self.messageSent.emit({"text": text})

        message = AuraMessage(
            type=MessageType.CHAT_MESSAGE,
            source="overlay",
            target="service",
            payload={"text": text},
        )
        if self._connection_manager.is_connected():
            self._connection_manager.send(message)
        else:
            self._messages.append({"role": "assistant", "text": "Offline"})
            self.messageReceived.emit({"text": "Offline"})

    @Slot()
    def focus_input(self) -> None:
        self.visibilityChanged.emit(True)

    def handle_connected(self) -> None:
        self._connection_state = "Connected"
        self.connectionChanged.emit(self._connection_state)

    def handle_disconnected(self) -> None:
        self._connection_state = "Offline"
        self.connectionChanged.emit(self._connection_state)

    def handle_message(self, message: object) -> None:
        if isinstance(message, AuraMessage):
            payload = message.payload
            text = payload.get("text") or payload.get("message") or ""
            if text:
                self._messages.append({"role": "assistant", "text": text})
                self.messageReceived.emit({"text": text})
        elif isinstance(message, dict):
            text = message.get("text") or message.get("message") or ""
            if text:
                self._messages.append({"role": "assistant", "text": text})
                self.messageReceived.emit({"text": text})

    def handle_error(self, exc: Exception) -> None:
        self.errorOccurred.emit(str(exc))

    def _setup_connection_handlers(self) -> None:
        self._connection_manager.on_connected(self.handle_connected)
        self._connection_manager.on_disconnected(self.handle_disconnected)
        self._connection_manager.on_message(self.handle_message)
        self._connection_manager.on_error(self.handle_error)
