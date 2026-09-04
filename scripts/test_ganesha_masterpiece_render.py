"""
Test Masterpiece Lord Ganesha SVG Render & Screenshot
=====================================================
Location: scripts/test_ganesha_masterpiece_render.py
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

def run():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")

    overlay = ChatWindowOverlay()
    overlay.resize(1000, 880)
    overlay.show()
    overlay.raise_()
    overlay.activateWindow()

    svg_file = PROJECT_ROOT / "artifacts" / "ganesha_masterpiece.svg"
    svg_content = svg_file.read_text(encoding="utf-8")

    def inject():
        overlay._clear_messages()
        prompt = "draw lord ganesh"
        overlay._append_card("user", prompt)

        card_text = f"Here is a master-grade, ornate vector illustration of **Lord Ganesha** featuring golden gradients, sacred tilak, and divine aura:\n\n```svg\n{svg_content}\n```"
        overlay._append_card("agent", card_text, intent_tag="ILLUSTRATION")

        screenshot_path = PROJECT_ROOT / "artifacts" / "ganesha_masterpiece_render.png"

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
