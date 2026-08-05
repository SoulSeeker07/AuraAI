from PySide6.QtCore import QObject
from PySide6.QtGui import QCursor

from backend.core.event_bus import EventBus
from backend.core.logger import get_logger

logger = get_logger("window_manager")


class WindowManager:
    def __init__(self, engine, event_bus: EventBus):
        self.engine = engine
        self.event_bus = event_bus
        self.root = engine.rootObjects()[0] if engine.rootObjects() else None
        self.overlay = None
        self._resolve_overlay()

        self.event_bus.subscribe("overlay.show", self._on_show_overlay)
        self.event_bus.subscribe("overlay.toggle", self._on_toggle_overlay)
        self.event_bus.subscribe("overlay.hide", self._on_hide_overlay)

    def _resolve_overlay(self):
        if not self.root:
            return
        try:
            # overlayWindow is the objectName set inside Overlay.qml
            self.overlay = self.root.findChild(QObject, "overlayWindow")
        except Exception:
            self.overlay = None

    def _place_next_to_cursor(self):
        # Determine cursor position and set overlay x/y accordingly
        pos = QCursor.pos()  # global screen coords
        # convert to top-left so overlay appears slightly below/right of cursor
        x = pos.x() + 12
        y = pos.y() + 12
        return x, y

    def show_overlay_at_cursor(self):
        if not self.overlay:
            self._resolve_overlay()
        if not self.overlay:
            logger.warning("No overlay object to show")
            return
        x, y = self._place_next_to_cursor()
        try:
            self.overlay.setProperty("x", x)
            self.overlay.setProperty("y", y)
            self.overlay.setProperty("visible", True)
            # attempt to call QML function to focus input
            try:
                self.overlay.callMethod("showOverlay")
            except Exception:
                pass
        except Exception:
            logger.exception("Failed to show overlay at cursor")

    def _on_show_overlay(self, event):
        self.show_overlay_at_cursor()

    def _on_toggle_overlay(self, event):
        if not self.overlay:
            self._resolve_overlay()
        try:
            vis = bool(self.overlay.property("visible"))
        except Exception:
            vis = False
        if vis:
            self.event_bus.publish("overlay.hide")
        else:
            self.event_bus.publish("overlay.show")

    def _on_hide_overlay(self, event):
        if not self.overlay:
            self._resolve_overlay()
        try:
            self.overlay.setProperty("visible", False)
        except Exception:
            pass
