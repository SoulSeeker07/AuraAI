"""
AuraAI — Jarvis Voice-Reactive HUD Rings Launcher
Usage:
    python run_jarvis_hud.py
"""

import sys
from pathlib import Path

# Ensure UTF-8 output
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Configure import paths
PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(1, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication
from gui.widgets.jarvis_rings_overlay import JarvisRingsOverlay


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AuraAI_Jarvis_HUD")
    overlay = JarvisRingsOverlay()
    overlay.show()
    print("🔮 AuraAI Jarvis HUD Rings Overlay launched. Press Ctrl+C in terminal or close to exit.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
