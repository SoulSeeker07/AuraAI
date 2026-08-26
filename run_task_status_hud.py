"""
Launcher for Next-Gen AuraAI Agent Task Status HUD Overlay.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from PySide6.QtWidgets import QApplication
from gui.widgets.agent_task_status_overlay import AgentTaskStatusOverlay

if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    overlay = AgentTaskStatusOverlay()
    overlay.show()
    sys.exit(app.exec())
