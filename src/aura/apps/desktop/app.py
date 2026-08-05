from __future__ import annotations

from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from ...client import ConnectionManager
from .controller import DesktopController


class AuraDesktopApp(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.app = QGuiApplication.instance() or QGuiApplication([])
        self.engine = QQmlApplicationEngine()
        self.controller = DesktopController()
        self.connection_manager = ConnectionManager()
        self._attach_controller()

    def _attach_controller(self) -> None:
        self.controller.connectionChanged.connect(self._on_connection_changed)
        self.controller.messageReceived.connect(self._on_message_received)
        self.connection_manager.on_connected(self.controller.handle_connected)
        self.connection_manager.on_disconnected(self.controller.handle_disconnected)
        self.connection_manager.on_message(self.controller.handle_message)
        self.connection_manager.on_error(self.controller.handle_error)

    def run(self) -> None:
        self.engine.rootContext().setContextProperty("controller", self.controller)
        self.engine.rootContext().setContextProperty(
            "connectionManager", self.connection_manager
        )
        self.engine.load(QUrl("qrc:/aura/frontend/desktop/Main.qml"))
        self.connection_manager.start()
        self.controller.set_connection_state("Connecting")
        self.app.exec()

    def _on_connection_changed(self, state: str) -> None:
        self.controller.set_connection_state(state)

    def _on_message_received(self, message: object) -> None:
        self.connection_manager.send(message)
