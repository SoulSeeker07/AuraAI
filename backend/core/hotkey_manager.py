import logging

import keyboard

from backend.core.config import DEFAULT_HOTKEYS
from backend.core.event_bus import EventBus

logger = logging.getLogger("aura.hotkey")


class HotkeyManager:
    def __init__(self, event_bus: EventBus, overlay_hotkey: str | None = None):
        self.event_bus = event_bus
        self.overlay_hotkey = overlay_hotkey or DEFAULT_HOTKEYS["overlay"]
        self._handles = []

    def start(self) -> None:
        try:
            h = keyboard.add_hotkey(
                self.overlay_hotkey, lambda: self.event_bus.publish("overlay.toggle")
            )
            self._handles.append(h)
            logger.info("Registered global hotkey: %s", self.overlay_hotkey)
        except Exception as exc:
            logger.warning("Could not register global hotkey: %s", exc)

    def stop(self) -> None:
        try:
            for h in self._handles:
                keyboard.remove_hotkey(h)
        except Exception:
            pass
        finally:
            self._handles.clear()
