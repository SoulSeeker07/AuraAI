from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from ...client import ConnectionManager
from .overlay_controller import OverlayController


class AuraOverlayApp:
    def __init__(self) -> None:
        self.app = QGuiApplication.instance() or QGuiApplication([])
        self.engine = QQmlApplicationEngine()
        self.connection_manager = ConnectionManager()
        self.controller = OverlayController(self.connection_manager)

    def run(self) -> None:
        self.engine.rootContext().setContextProperty("controller", self.controller)
        self.engine.rootContext().setContextProperty(
            "connectionManager", self.connection_manager
        )
        self.engine.load(QUrl("qrc:/aura/frontend/overlay/Overlay.qml"))
        self.connection_manager.start()
        self.controller.show()
        self.app.exec()
