from __future__ import annotations

from collections.abc import Callable

from loguru import logger


class WindowsHotkeyBackend:
    def __init__(self) -> None:
        self._registered: dict[str, Callable[[], None]] = {}

    def register(self, shortcut: str, callback: Callable[[], None]) -> bool:
        try:
            self._registered[shortcut] = callback
            logger.info("Hotkey registered: {}", shortcut)
            return True
        except Exception as exc:
            logger.warning("Hotkey registration failed: {}", exc)
            return False

    def unregister(self, shortcut: str) -> None:
        self._registered.pop(shortcut, None)

    def trigger(self, shortcut: str) -> None:
        callback = self._registered.get(shortcut)
        if callback is not None:
            callback()
