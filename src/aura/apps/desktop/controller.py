from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from ...shared import AuraMessage, MessageType


class DesktopController(QObject):
    connectionChanged = Signal(str)
    messageReceived = Signal(object)
    messageSent = Signal(object)
    notification = Signal(str)
    errorOccurred = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._messages: list[dict] = [
            {"role": "assistant", "text": "Welcome to Aura\nYour AI desktop assistant."}
        ]
        self._connection_state = "Disconnected"

    @Property(str)
    def connection_state(self) -> str:
        return self._connection_state

    @Property(object)
    def messages(self) -> list[dict]:
        return self._messages

    @Slot(str)
    def send_message(self, text: str) -> None:
        if not text.strip():
            return

        self._messages.append({"role": "user", "text": text})
        self.messageSent.emit({"text": text})

        message = AuraMessage(
            type=MessageType.CHAT_MESSAGE,
            source="desktop",
            target="service",
            payload={"text": text},
        )
        self._emit_message(message)

    @Slot()
    def clear_chat(self) -> None:
        self._messages.clear()
        self._messages.append(
            {"role": "assistant", "text": "Welcome to Aura\nYour AI desktop assistant."}
        )

    def set_connection_state(self, state: str) -> None:
        if self._connection_state == state:
            return
        self._connection_state = state
        self.connectionChanged.emit(state)

    def handle_connected(self) -> None:
        self.set_connection_state("Connected")
        self.notification.emit("Desktop Connected")

    def handle_disconnected(self) -> None:
        self.set_connection_state("Offline")

    def handle_message(self, message: object) -> None:
        if isinstance(message, AuraMessage):
            payload = message.payload
            text = payload.get("text") or payload.get("message") or ""
            if text:
                self._messages.append({"role": "assistant", "text": text})
                self.messageReceived.emit({"text": text})

    def handle_error(self, exc: Exception) -> None:
        self.errorOccurred.emit(str(exc))

    def _emit_message(self, message: AuraMessage) -> None:
        self.messageSent.emit({"text": message.payload.get("text", "")})
