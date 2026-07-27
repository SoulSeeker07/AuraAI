from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from core.logger import logger
from core.screen_context import ScreenContext


class LiveScreenSession(QObject):
    state_changed = Signal(bool)
    frame_captured = Signal(str, int)

    def __init__(self, screen_context: ScreenContext, interval_ms: int = 1500, parent=None):
        super().__init__(parent)
        self.screen_context = screen_context
        self.interval_ms = interval_ms
        self.latest_frame_path: Path | None = None
        self.frame_count = 0

        self._timer = QTimer(self)
        self._timer.setInterval(self.interval_ms)
        self._timer.timeout.connect(self.capture_frame)

    @property
    def is_active(self) -> bool:
        return self._timer.isActive()

    def start(self) -> None:
        if self.is_active:
            return
        self.frame_count = 0
        self.capture_frame()
        self._timer.start()
        self.state_changed.emit(True)
        logger.info("Live screen mode started")

    def stop(self) -> None:
        if not self.is_active:
            return
        self._timer.stop()
        self.state_changed.emit(False)
        logger.info("Live screen mode stopped")

    def toggle(self) -> None:
        if self.is_active:
            self.stop()
        else:
            self.start()

    def capture_frame(self) -> None:
        path = self.screen_context.capture_live_frame()
        if path is None:
            logger.warning("Live screen frame capture failed")
            return

        self.latest_frame_path = path
        self.frame_count += 1
        self.frame_captured.emit(str(path), self.frame_count)
