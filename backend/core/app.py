# backend/core/app.py (Milestone 1.1)
import sys

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from backend.core.config import APP_NAME, MAIN_QML, ORGANIZATION
from backend.core.logger import log


class AuraApplication:
    """Minimal Aura bootstrap for Milestone 1.1.

    Responsibilities:
    - Create QGuiApplication
    - Load frontend/Main.qml via QQmlApplicationEngine
    - Show the main window
    - Run the Qt event loop
    """

    def __init__(self) -> None:
        # Create the Qt application
        self.qt_app = QGuiApplication(sys.argv)
        self.qt_app.setApplicationName(APP_NAME)
        try:
            self.qt_app.setOrganizationName(ORGANIZATION)
        except Exception:
            # older Qt versions may not expose setOrganizationName on QGuiApplication
            pass

        self.engine = QQmlApplicationEngine()
        self.overlay_controller = None

    def run(self) -> int:
        log.info("Starting Aura AI")

        # Load the main QML
        self.engine.load(QUrl.fromLocalFile(str(MAIN_QML)))

        # Verify load
        if not self.engine.rootObjects():
            log.error("Unable to load Main.qml: %s", MAIN_QML)
            sys.exit(-1)

        # initialize overlay controller (if Overlay.qml is present)
        try:
            from backend.core.overlay_controller import OverlayController

            self.overlay_controller = OverlayController(self.engine)
        except Exception:
            self.overlay_controller = None

        log.success("Aura Started Successfully")

        # Enter Qt event loop
        return self.qt_app.exec()
