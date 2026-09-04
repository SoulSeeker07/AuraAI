"""
Tests for AuraAI Interactive Diagram & Artifact Viewer
=====================================================
Location: tests/test_diagram_viewer.py
"""

import pytest
from PySide6.QtWidgets import QApplication

from gui.widgets.diagram_viewer import (
    build_mermaid_html,
    detect_diagram_type,
    DiagramArtifactWidget,
)
from gui.widgets.message_parser import parse_message_segments, SegmentType
from gui.widgets.code_block_widget import CodeBlockWidget
from gui.widgets.chat_bubble import ChatBubble
from gui.widgets.chat_window_overlay import ChatOverlayMessageCard


@pytest.fixture(scope="session")
def qapp():
    """Ensure a QApplication instance exists for widget testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["--platform", "offscreen"])
    return app


def test_detect_diagram_type():
    flowchart_code = """
    graph TD
        A[User Prompt] --> B(Aura Cognitive Brain)
        B --> C{Decision Engine}
        C -->|Action| D[Tool Execution]
        C -->|Answer| E[Neural Response]
    """
    assert detect_diagram_type(flowchart_code) == "FLOWCHART"

    sequence_code = """
    sequenceDiagram
        autonumber
        Operator->>AuraCore: "Spawn Weather HUD"
        AuraCore->>Telemetry: Query sensors
        Telemetry-->>AuraCore: Sensor snapshot
        AuraCore-->>Operator: Display Holographic HUD
    """
    assert detect_diagram_type(sequence_code) == "SEQUENCE"

    state_code = """
    stateDiagram-v2
        [*] --> IDLE
        IDLE --> LISTENING : WakeWord 'Aura'
        LISTENING --> REASONING : Audio captured
        REASONING --> EXECUTING : Goal planned
        EXECUTING --> IDLE : Complete
    """
    assert detect_diagram_type(state_code) == "STATE MACHINE"


def test_build_mermaid_html():
    code = "graph LR\n  A --> B"
    html_output = build_mermaid_html(code)
    assert "<!DOCTYPE html>" in html_output
    assert "mermaid@10" in html_output
    assert "svg-pan-zoom" in html_output
    assert "graph LR" in html_output
    assert "#00e5ff" in html_output  # Aura cyan theme


def test_parse_message_segments():
    raw_message = """
Here is the system architecture for Aura:

```mermaid
graph TD
    Client[Floating HUD] --> Gateway[Aura WebSocket Bridge]
    Gateway --> Brain[Executive Core]
    Brain --> LLM[Groq / Claude Engine]
```

And here is the startup command:

```bash
python run_chat_window.py --hologram
```

All subsystems are nominal.
    """

    segments = parse_message_segments(raw_message)
    assert len(segments) == 5

    assert segments[0].type == SegmentType.TEXT
    assert "Here is the system architecture" in segments[0].content

    assert segments[1].type == SegmentType.DIAGRAM
    assert "graph TD" in segments[1].content
    assert segments[1].language == "mermaid"

    assert segments[2].type == SegmentType.TEXT
    assert "startup command" in segments[2].content

    assert segments[3].type == SegmentType.CODE
    assert "run_chat_window.py" in segments[3].content
    assert segments[3].language == "bash"

    assert segments[4].type == SegmentType.TEXT
    assert "nominal" in segments[4].content


def test_widgets_instantiation(qapp):
    mermaid_code = "graph TD; A-->B;"
    
    # 1. DiagramArtifactWidget
    diag_widget = DiagramArtifactWidget(mermaid_code, title="Test Architecture")
    assert diag_widget.diagram_type == "FLOWCHART"
    assert diag_widget.btn_diagram.isChecked()
    assert diag_widget.stack.currentIndex() == 0

    # 2. CodeBlockWidget
    code_widget = CodeBlockWidget("print('Aura online')", language="python")
    assert code_widget.language == "python"

    # 3. ChatOverlayMessageCard with diagram
    msg = f"Architecture layout:\n```mermaid\n{mermaid_code}\n```"
    overlay_card = ChatOverlayMessageCard(sender="agent", text=msg, intent_tag="DESIGN")
    assert overlay_card is not None

    # 4. ChatBubble with diagram
    chat_bubble = ChatBubble(sender="agent", content=msg)
    assert chat_bubble is not None


def test_sanitize_mermaid_code():
    from gui.widgets.diagram_viewer import sanitize_mermaid_code
    broken_code = """flowchart LR
    subgraph Power[Power & Energy]
    AR[Arc Reactor Core]
    EP[Energy Storage (Capacitors/Ultra‑Superconductors)]
    EM[Energy Management Unit (EMU)]
    PD[Power Distribution Bus]
    end
    F -->|Reg (50%)| G[Output]
    """
    sanitized = sanitize_mermaid_code(broken_code)
    assert '["Energy Storage (Capacitors/Ultra-Superconductors)"]' in sanitized
    assert '["Energy Management Unit (EMU)"]' in sanitized
    assert '|"Reg (50%)"|' in sanitized
    assert '\u2011' not in sanitized


def test_unclosed_fence_repair():
    raw_unclosed = "Here is the diagram:\n```mermaid\nflowchart TD\nA[Start] --> B[End]"
    segments = parse_message_segments(raw_unclosed)
    assert len(segments) == 2
    assert segments[0].type == SegmentType.TEXT
    assert segments[1].type == SegmentType.DIAGRAM
    assert "flowchart TD" in segments[1].content

