from __future__ import annotations

from typing import Callable, Optional

from loguru import logger

from .constants import ALT_SPACE, CTRL_SHIFT_K, ESC
from .windows import WindowsHotkeyBackend


class HotkeyManager:
    def __init__(self, backend: Optional[WindowsHotkeyBackend] = None) -> None:
        self.backend = backend or WindowsHotkeyBackend()
        self._enabled = False
        self._handlers: dict[str, Callable[[], None]] = {}

    def enable(self) -> None:
        self._enabled = True
        self._register_defaults()

    def disable(self) -> None:
        self._enabled = False
        for shortcut in list(self._handlers):
            self.backend.unregister(shortcut)
            self._handlers.pop(shortcut, None)

    def register(self, shortcut: str, callback: Callable[[], None]) -> bool:
        if not self._enabled:
            return False
        success = self.backend.register(shortcut, callback)
        if success:
            self._handlers[shortcut] = callback
        return success

    def unregister(self, shortcut: str) -> None:
        self.backend.unregister(shortcut)
        self._handlers.pop(shortcut, None)

    def _register_defaults(self) -> None:
        self.register(ALT_SPACE, self._default_toggle)
        self.register(CTRL_SHIFT_K, self._default_toggle)
        self.register(ESC, self._default_hide)

    def _default_toggle(self) -> None:
        logger.info("Overlay toggle requested")

    def _default_hide(self) -> None:
        logger.info("Overlay hide requested")
