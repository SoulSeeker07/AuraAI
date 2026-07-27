import sys

from PySide6.QtWidgets import QApplication

from core.config import APP_NAME, ORGANIZATION_NAME, ensure_runtime_dirs
from core.event_bus import Event, EventBus
from core.hotkeys import GlobalHotkeyManager
from core.live_screen import LiveScreenSession
from core.local_responder import LocalResponder
from core.logger import logger
from core.overlay_manager import OverlayManager
from core.plugin_manager import PluginManager
from core.screen_context import ScreenContext
from core.settings import Settings
from core.window_manager import WindowManager
from gui.theme import apply_theme


class AuraApplication:
    def __init__(self):
        ensure_runtime_dirs()
        self.settings = Settings()
        self.event_bus = EventBus()

        self.qt_app = QApplication(sys.argv)
        self.qt_app.setApplicationName(APP_NAME)
        self.qt_app.setOrganizationName(ORGANIZATION_NAME)
        self.qt_app.setQuitOnLastWindowClosed(False)
        self.qt_app.setProperty("force_quit", False)
        apply_theme(self.qt_app)

        self.plugin_manager = PluginManager(self.event_bus)
        self.screen_context = ScreenContext()
        self.live_screen = LiveScreenSession(
            self.screen_context,
            interval_ms=self.settings.live_screen_interval_ms,
            parent=self.qt_app,
        )
        self.local_responder = LocalResponder(self.screen_context, self.live_screen)
        self.window_manager = WindowManager(self.qt_app, self.event_bus)
        self.overlay_manager = OverlayManager(self.event_bus, self.local_responder)
        self.hotkeys = GlobalHotkeyManager(self.settings.overlay_hotkey, parent=self.qt_app)

        self._subscribe_events()
        self._connect_lifecycle()

    def run(self) -> int:
        logger.info("Starting %s", APP_NAME)
        self.plugin_manager.load_plugins()
        self.hotkeys.start()
        self.window_manager.start()
        return self.qt_app.exec()

    def _subscribe_events(self) -> None:
        self.event_bus.subscribe("history.prompt", self._record_prompt)
        self.event_bus.subscribe("live_screen.set_enabled", self._set_live_screen_enabled)

    def _connect_lifecycle(self) -> None:
        self.hotkeys.activated.connect(lambda: self.event_bus.publish("overlay.toggle"))
        self.live_screen.state_changed.connect(self._publish_live_screen_state)
        self.live_screen.frame_captured.connect(self._publish_live_screen_frame)
        self.qt_app.aboutToQuit.connect(self.live_screen.stop)
        self.qt_app.aboutToQuit.connect(self.hotkeys.stop)

    def _record_prompt(self, event: Event) -> None:
        prompt = str(event.payload.get("prompt", ""))
        self.window_manager.main_window.add_history_entry(prompt)

    def _set_live_screen_enabled(self, event: Event) -> None:
        enabled = bool(event.payload.get("enabled", False))
        if enabled:
            self.live_screen.start()
        else:
            self.live_screen.stop()

    def _publish_live_screen_state(self, is_active: bool) -> None:
        self.event_bus.publish(
            "live_screen.state_changed",
            is_active=is_active,
            frame_count=self.live_screen.frame_count,
            frame_path=str(self.live_screen.latest_frame_path) if self.live_screen.latest_frame_path else None,
        )

    def _publish_live_screen_frame(self, frame_path: str, frame_count: int) -> None:
        self.event_bus.publish(
            "live_screen.frame_captured",
            frame_path=frame_path,
            frame_count=frame_count,
        )


def create_app() -> AuraApplication:
    return AuraApplication()
