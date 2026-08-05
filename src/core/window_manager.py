from PySide6.QtWidgets import QApplication

from core.event_bus import Event, EventBus
from core.logger import get_logger
from core.settings import Settings
from gui.main_window import MainWindow
from gui.overlay import OverlayWindow
from gui.tray import AuraTrayIcon

logger = get_logger("window_manager")


class WindowManager:
    def __init__(self, app: QApplication, event_bus: EventBus, settings: Settings):
        self.app = app
        self.event_bus = event_bus
        self.settings = settings
        self.main_window = MainWindow()
        self.overlay_window = OverlayWindow()
        self.tray_icon = AuraTrayIcon(
            self.main_window, self.overlay_window, self.app, self.settings
        )
        self._connect_qt_signals()
        self._subscribe_events()

    def start(self) -> None:
        self.tray_icon.show()
        self.main_window.show()
        logger.info("Window manager started")

    def _connect_qt_signals(self) -> None:
        self.main_window.show_overlay_requested.connect(
            lambda: self.event_bus.publish("overlay.show")
        )
        self.overlay_window.submitted.connect(
            lambda prompt: self.event_bus.publish(
                "overlay.prompt_submitted", prompt=prompt
            )
        )
        self.overlay_window.live_screen_toggled.connect(
            lambda enabled: self.event_bus.publish(
                "live_screen.set_enabled", enabled=enabled
            )
        )
        self.tray_icon.live_screen_toggled.connect(
            lambda enabled: self.event_bus.publish(
                "live_screen.set_enabled", enabled=enabled
            )
        )
        self.tray_icon.show_overlay_requested.connect(
            lambda: self.event_bus.publish("overlay.show")
        )
        self.main_window.hidden_to_tray.connect(self.tray_icon.sync_visibility_actions)

    def _subscribe_events(self) -> None:
        self.event_bus.subscribe("overlay.show", self._show_overlay)
        self.event_bus.subscribe("overlay.toggle", self._toggle_overlay)
        self.event_bus.subscribe("overlay.response", self._set_overlay_response)
        self.event_bus.subscribe(
            "live_screen.state_changed", self._set_live_screen_state
        )
        self.event_bus.subscribe(
            "live_screen.frame_captured", self._set_live_screen_frame
        )

    def _show_overlay(self, event: Event) -> None:
        self.overlay_window.show_overlay()
        logger.info("Overlay opened")

    def _toggle_overlay(self, event: Event) -> None:
        self.overlay_window.toggle()

    def _set_overlay_response(self, event: Event) -> None:
        response = str(event.payload.get("response", ""))
        self.overlay_window.set_response(response)
        self.main_window.add_response_entry(response)

    def _set_live_screen_state(self, event: Event) -> None:
        is_active = bool(event.payload.get("is_active", False))
        frame_count = int(event.payload.get("frame_count", 0))
        frame_path = event.payload.get("frame_path")
        self.overlay_window.set_live_screen_state(is_active, frame_count, frame_path)
        self.tray_icon.set_live_screen_state(is_active)
        self.main_window.set_live_screen_status(is_active, frame_count)

    def _set_live_screen_frame(self, event: Event) -> None:
        frame_path = str(event.payload.get("frame_path", ""))
        frame_count = int(event.payload.get("frame_count", 0))
        self.overlay_window.set_live_screen_state(True, frame_count, frame_path)
        self.main_window.set_live_screen_status(True, frame_count)
