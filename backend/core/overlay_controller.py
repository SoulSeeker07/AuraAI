from typing import Optional
from PySide6.QtCore import QObject
from PySide6.QtGui import QCursor

from backend.core.logger import log


class OverlayController:
    """Controls the Overlay QML window.

    Usage:
        controller = OverlayController(engine)
        controller.show()
        controller.hide()
        controller.center_on_cursor()
    """

    def __init__(self, engine):
        self.engine = engine
        self.root = engine.rootObjects()[0] if engine.rootObjects() else None
        self.overlay = None
        self._resolve_overlay()

    def _resolve_overlay(self):
        if not self.root:
            return
        try:
            self.overlay = self.root.findChild(QObject, "overlayWindow")
        except Exception:
            self.overlay = None

    def show(self):
        if not self.overlay:
            self._resolve_overlay()
        if not self.overlay:
            log.warning("Overlay object not found to show")
            return
        try:
            # center near cursor before requesting open
            self.center_on_cursor()
            # set the openRequest flag which QML listens to
            self.overlay.setProperty("openRequest", True)
            log.debug("Overlay show requested")
        except Exception:
            log.exception("Failed to show overlay")

    def hide(self):
        if not self.overlay:
            self._resolve_overlay()
        if not self.overlay:
            return
        try:
            self.overlay.setProperty("visible", False)
        except Exception:
            log.exception("Failed to hide overlay")

    def toggle(self):
        if not self.overlay:
            self._resolve_overlay()
        if not self.overlay:
            return
        try:
            vis = bool(self.overlay.property("visible"))
            if vis:
                self.hide()
            else:
                self.show()
        except Exception:
            self.show()

    def center_on_cursor(self):
        """Place the overlay panel near the current cursor position."""
        if not self.overlay:
            self._resolve_overlay()
        if not self.overlay:
            return
        try:
            pos = QCursor.pos()
            # compute coordinates to put overlay with some offset
            x = pos.x() + 12
            y = pos.y() + 12
            # set overlay x,y so Window moves to cursor area; overlay QML uses anchors from top
            self.overlay.setProperty("x", x)
            self.overlay.setProperty("y", y)
        except Exception:
            log.exception("Failed to center overlay on cursor")
