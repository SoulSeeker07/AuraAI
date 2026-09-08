"""
Tests for ThoughtBlockWidget & Collapsible Thought Parsing
==========================================================
Location: tests/test_thought_block_widget.py
"""

import pytest
from PySide6.QtWidgets import QApplication

from gui.widgets.message_parser import parse_message_segments, SegmentType
from gui.widgets.thought_block_widget import ThoughtBlockWidget


@pytest.fixture(scope="session")
def qapp():
    """Ensure a QApplication instance exists for widget testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["--platform", "offscreen"])
    return app


def test_parse_message_segments_with_thought():
    raw = """<think>
Inspecting user memory.
Found favorite IDE is VS Code.
</think>
Your favorite editor is VS Code. Here is a sample:
```python
print("Hello Aura")
```
Subsystems nominal."""

    segments = parse_message_segments(raw)
    assert len(segments) == 4

    # 1. Thought block
    assert segments[0].type == SegmentType.THOUGHT
    assert "Found favorite IDE is VS Code" in segments[0].content

    # 2. Text
    assert segments[1].type == SegmentType.TEXT
    assert "Your favorite editor is VS Code" in segments[1].content

    # 3. Code
    assert segments[2].type == SegmentType.CODE
    assert "print(\"Hello Aura\")" in segments[2].content
    assert segments[2].language == "python"

    # 4. Trailing text
    assert segments[3].type == SegmentType.TEXT
    assert "Subsystems nominal" in segments[3].content


def test_parse_message_segments_thinking_variants():
    # Test <thinking> tag
    raw1 = "<thinking>Claude style reasoning</thinking>Final answer."
    segs1 = parse_message_segments(raw1)
    assert len(segs1) == 2
    assert segs1[0].type == SegmentType.THOUGHT
    assert segs1[0].content == "Claude style reasoning"
    assert segs1[1].type == SegmentType.TEXT
    assert segs1[1].content == "Final answer."

    # Test unclosed <think> during streaming
    raw2 = "<think>Still thinking in progress..."
    segs2 = parse_message_segments(raw2)
    assert len(segs2) == 1
    assert segs2[0].type == SegmentType.THOUGHT
    assert "Still thinking in progress..." in segs2[0].content


def test_thought_block_widget_behavior(qapp):
    widget = ThoughtBlockWidget("Evaluating system parameters...", title="Reasoning", is_expanded=False)
    widget.show()

    # 1. Default collapsed
    assert widget.is_expanded is False
    assert widget._chevron.text() == "▶"
    assert widget._body_container.isVisible() is False
    assert "Evaluating system parameters" in widget._body_lbl.text()

    # 2. Toggle to expanded
    received_signals = []
    widget.toggled.connect(received_signals.append)

    widget.toggle()
    assert widget.is_expanded is True
    assert widget._chevron.text() == "▼"
    assert widget._body_container.isVisible() is True
    assert received_signals == [True]

    # 3. Toggle back to collapsed
    widget.toggle()
    assert widget.is_expanded is False
    assert widget._chevron.text() == "▶"
    assert widget._body_container.isVisible() is False
    assert received_signals == [True, False]
