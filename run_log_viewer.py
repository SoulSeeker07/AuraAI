"""
Launcher for Dedicated AuraAI Live System Logs Overlay.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from PySide6.QtWidgets import QApplication
from gui.widgets.live_log_viewer_overlay import LiveLogViewerOverlay

if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    viewer = LiveLogViewerOverlay()
    viewer.show()
    viewer.raise_()
    viewer.activateWindow()
    sys.exit(app.exec())
