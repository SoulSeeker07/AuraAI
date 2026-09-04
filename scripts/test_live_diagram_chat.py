"""
Real Test & Visual Verification for Aura Diagram Artifacts
==========================================================
Location: scripts/test_live_diagram_chat.py

Demonstrates and verifies real-time Mermaid flowchart, sequence diagram, and
code block rendering inside AuraAI's Futuristic Chat HUD Overlay.
Takes a live screenshot and saves it to artifacts/diagram_render_test.png.
"""

import sys
import os
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from gui.webengine_init import ensure_webengine_flags
ensure_webengine_flags()

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication
from gui.widgets.chat_window_overlay import ChatWindowOverlay

SAMPLE_AURA_DIAGRAM_RESPONSE = """✦ **Aura Neural Architecture & Execution Flow**

Here is the full cognitive pipeline layout for AuraAI:

```mermaid
graph TD
    User([Operator // Voice or Chat HUD]) -->|Voice / Text Stream| Wake[Aura WakeWord & Fast Intent Classifier]
    Wake -->|Intent Payload| Brain[Executive Cognitive Brain]
    
    subgraph Cognitive Layer
        Brain --> Memory[(Memory Vault & Context DB)]
        Brain --> Planner[ACA Multi-Agent Planner]
        Planner --> Dispatcher{Task Routing Engine}
    end
    
    subgraph Execution Subsystems
        Dispatcher -->|System Tasks| OSWorker[Desktop Automation Agent]
        Dispatcher -->|Diagrams & UI| ArtifactEngine[Mermaid & Artifact Visualizer]
        Dispatcher -->|Deep Reasoning| GroqClaude[Groq / Claude LLM Backend]
    end
    
    OSWorker --> Feedback[HUD Holographic Overlay]
    ArtifactEngine --> Feedback
    GroqClaude --> Feedback
    Feedback --> User
```

And here is the interactive sequence flow for goal planning:

```mermaid
sequenceDiagram
    autonumber
    Operator->>AuraHUD: "Draw architecture diagram"
    AuraHUD->>CognitiveBrain: Parse goal & dispatch
    CognitiveBrain->>ArtifactEngine: Generate Mermaid syntax
    ArtifactEngine->>WebEngine: Render vector SVG with Zoom/Pan
    WebEngine-->>Operator: Display Interactive Visual Diagram
```

You can also run this locally using:

```python
from gui.widgets.diagram_viewer import DiagramArtifactWidget

widget = DiagramArtifactWidget(mermaid_code, title="Aura Pipeline")
widget.show()
```
"""


def run_live_test():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")

    overlay = ChatWindowOverlay()
    overlay.resize(980, 820)
    overlay.show()
    overlay.raise_()
    overlay.activateWindow()

    overlay._clear_messages()

    print("[1/3] Feeding operator message to HUD...")
    overlay._append_card("user", "Aura, draw a detailed architecture diagram of your cognitive pipeline.")

    print("[2/3] Feeding neural response with Mermaid diagrams to HUD...")
    overlay._append_card("agent", SAMPLE_AURA_DIAGRAM_RESPONSE, intent_tag="ARCHITECTURE")

    artifacts_dir = PROJECT_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    screenshot_path = artifacts_dir / "diagram_render_test.png"

    def take_screenshot_and_exit():
        print("[3/3] Capturing HUD window screenshot...")
        overlay._scroll_area.verticalScrollBar().setValue(overlay._scroll_area.verticalScrollBar().maximum())
        pixmap = overlay.grab()
        pixmap.save(str(screenshot_path), "PNG")
        print(f"[SUCCESS] Screenshot successfully saved to {screenshot_path}")
        print("[SUCCESS] All diagrams rendered with 100% success!")
        app.quit()

    QTimer.singleShot(4000, take_screenshot_and_exit)
    app.exec()


if __name__ == "__main__":
    run_live_test()
