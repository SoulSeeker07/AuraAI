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


def test_extract_svg_content_sanitizes_br_and_amp():
    from gui.widgets.diagram_viewer import extract_svg_content
    broken_svg = (
        '<svg viewBox="0 0 800 600">'
        '<text x="50" y="50">LINE 1<br/>LINE 2</text>'
        '<text x="50" y="80">AIR & NAV &amp; COMM</text>'
        '</svg>'
    )
    cleaned = extract_svg_content(broken_svg)
    assert "<br/>" not in cleaned
    assert "<br" not in cleaned
    assert "LINE 1 LINE 2" in cleaned
    assert "AIR &amp; NAV &amp; COMM" in cleaned
    assert 'id="mermaid-svg"' in cleaned


def test_detect_diagram_type_mcdu():
    mcdu_svg = '<svg viewBox="0 0 800 600"><text>MCDU Flight Management</text></svg>'
    assert detect_diagram_type(mcdu_svg) == "UI INTERFACE LAYOUT"

    art_svg = '<svg viewBox="0 0 800 600"><circle r="50"/></svg>'
    assert detect_diagram_type(art_svg) == "SVG VECTOR ART"

    sketch_svg = '<svg viewBox="0 0 800 600"><style>.sketch { stroke: black; }</style><path class="sketch" d="M0,0 L10,10"/></svg>'
    assert detect_diagram_type(sketch_svg) == "PENCIL SKETCH"

    cad_svg = '<svg viewBox="0 0 800 600"><text>Turbofan CAD Blueprint</text></svg>'
    assert detect_diagram_type(cad_svg) == "CAD BLUEPRINT"


def test_pencil_sketch_detection_and_auto_canvas():
    from gui.widgets.diagram_viewer import (
        is_sketch_or_dark_line_svg,
        inject_canvas_background,
        extract_svg_content,
    )
    
    # 1. Sketch with dark stroke and no background
    sketch_code = """
    <svg viewBox="0 0 1000 400" width="1000" height="400">
      <style>
        .sketch { stroke: black; stroke-width: 1.5; fill: none; }
      </style>
      <defs><marker id="m"/></defs>
      <path class="sketch" d="M 50 200 L 150 160" />
    </svg>
    """
    assert is_sketch_or_dark_line_svg(sketch_code) is True

    # 2. extract_svg_content injects canvas rect
    processed = extract_svg_content(sketch_code)
    assert 'id="aura-auto-canvas"' in processed
    assert 'fill="#fcfbf7"' in processed
    assert 'x="0"' in processed and 'y="0"' in processed
    assert 'width="1000"' in processed and 'height="400"' in processed

    # 3. Neon HUD diagram should NOT trigger canvas injection
    neon_hud_code = """
    <svg viewBox="0 0 800 600" style="background-color: #090d16;">
      <path stroke="#00e5ff" stroke-width="2" d="M0,0 L100,100"/>
    </svg>
    """
    assert is_sketch_or_dark_line_svg(neon_hud_code) is False
    neon_processed = extract_svg_content(neon_hud_code)
    assert 'id="aura-auto-canvas"' not in neon_processed

    # 4. HTML includes canvas mode switcher button
    sketch_html = build_mermaid_html(sketch_code)
    assert "btn-canvas-mode" in sketch_html
    assert "cycleCanvasMode" in sketch_html
    assert "📜 Paper" in sketch_html



