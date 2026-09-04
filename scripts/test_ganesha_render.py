"""
Test Live Lord Ganesha SVG Vector Drawing Render & Screenshot
============================================================
Location: scripts/test_ganesha_render.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from gui.webengine_init import ensure_webengine_flags
ensure_webengine_flags()

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from gui.widgets.chat_window_overlay import ChatWindowOverlay
from ai.fast_client import FastLLMClient

def run():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")

    overlay = ChatWindowOverlay()
    overlay.resize(1000, 850)
    overlay.show()
    overlay.raise_()
    overlay.activateWindow()

    artifacts_dir = PROJECT_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    screenshot_path = artifacts_dir / "ganesha_svg_render.png"

    def inject():
        overlay._clear_messages()
        prompt = "draw lord ganesh"
        overlay._append_card("user", prompt)

        resp = FastLLMClient.query(prompt)
        overlay._append_card("agent", resp, intent_tag="ILLUSTRATION")

        def capture():
            overlay._scroll_area.verticalScrollBar().setValue(overlay._scroll_area.verticalScrollBar().maximum())
            overlay.grab().save(str(screenshot_path), "PNG")
            print(f"[SUCCESS] Screenshot saved to {screenshot_path}")
            app.quit()

        QTimer.singleShot(4000, capture)

    QTimer.singleShot(500, inject)
    app.exec()

if __name__ == "__main__":
    run()
