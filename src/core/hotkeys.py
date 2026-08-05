from PySide6.QtCore import QObject, Signal

from core.logger import logger


class GlobalHotkeyManager(QObject):
    activated = Signal()

    def __init__(self, sequence: str = "alt+space", parent=None):
        super().__init__(parent)
        self.sequence = sequence
        self._keyboard = None
        self._hook = None

    def start(self) -> None:
        try:
            import keyboard

            self._keyboard = keyboard
            self._hook = keyboard.add_hotkey(self.sequence, self.activated.emit)
            logger.info("Registered global hotkey: %s", self.sequence)
        except Exception as exc:
            logger.warning(
                "Global hotkey unavailable; Qt shortcut fallback remains active: %s",
                exc,
            )

    def stop(self) -> None:
        if self._keyboard is None or self._hook is None:
            return
        try:
            self._keyboard.remove_hotkey(self._hook)
        except Exception as exc:
            logger.debug("Could not remove global hotkey cleanly: %s", exc)
        finally:
            self._hook = None
            self._keyboard = None
