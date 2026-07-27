from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QApplication

from core.config import SCREENSHOT_DIR


class ScreenContext:
    def __init__(self, capture_dir: Path = SCREENSHOT_DIR):
        self.capture_dir = capture_dir
        self.capture_dir.mkdir(parents=True, exist_ok=True)

    def capture_primary_screen(self, filename: str | None = None) -> Path | None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return None

        pixmap = screen.grabWindow(0)
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            filename = f"screen-{timestamp}.png"
        path = self.capture_dir / filename
        if not pixmap.save(str(path), "PNG"):
            return None
        return path

    def capture_live_frame(self) -> Path | None:
        return self.capture_primary_screen("live-screen-latest.png")
