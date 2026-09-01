"""
Unit tests for AuraAI GUI Framework
===================================
Tests instantiation and signal wiring for MainWindow, OverlayWindow, NavigationRail, and AppSignals.
"""

import os
import sys

import pytest

# Ensure headless Qt for test execution
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow
from gui.overlay import OverlayWindow
from gui.signals import ExecutionStep, StepStatus, app_signals
from gui.widgets import (
    ChatBubble,
    ChatStreamWidget,
    ChatWindowOverlay,
    DagVisualizer,
    InspectorDrawer,
    NavigationRail,
    StatusPill,
    StepCard,
    SystemStatusOverlay,
    VoiceWaveform,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_app_signals():
    received_steps = []

    def on_step(step):
        received_steps.append(step)

    app_signals.step_updated.connect(on_step)

    step = ExecutionStep(
        index=0,
        title="Test Step",
        description="Details",
        status=StepStatus.RUNNING,
        timestamp=1.0,
    )
    app_signals.step_updated.emit(step)

    assert len(received_steps) == 1
    assert received_steps[0].title == "Test Step"
    app_signals.step_updated.disconnect(on_step)


def test_navigation_rail_instantiation(qapp):
    nav = NavigationRail()
    assert nav.objectName() == "NavRail"

    toggled_index = []
    nav.tab_changed.connect(lambda idx: toggled_index.append(idx))

    nav._on_tab_clicked(2)
    assert toggled_index == [2]


def test_main_window_instantiation(qapp):
    window = MainWindow()
    assert "AuraAI" in window.windowTitle()
    assert window._center_stack.count() == 4



def test_main_window_chat_overlay_toggle(qapp):
    window = MainWindow()
    assert window._chat_overlay is None

    # First toggle -> instantiated & shown
    window.toggle_chat_overlay()
    assert window._chat_overlay is not None
    assert isinstance(window._chat_overlay, ChatWindowOverlay)
    assert window._chat_overlay.isVisible()

    # Second toggle -> hidden
    window.toggle_chat_overlay()
    assert not window._chat_overlay.isVisible()


def test_overlay_window_instantiation(qapp):
    overlay = OverlayWindow()
    assert overlay.objectName() == "OverlayWindow"
    assert not overlay.isVisible()


def test_chat_window_overlay_instantiation(qapp):
    overlay = ChatWindowOverlay()
    assert overlay.objectName() == "ChatWindowOverlay"
    assert overlay.windowTitle() == "AuraAI Neural Chat HUD"
    assert not overlay.isVisible()

    # Test toggle
    overlay.toggle()
    assert overlay.isVisible()
    overlay.toggle()
    assert not overlay.isVisible()

    # Test submitting prompt
    submitted_texts = []
    overlay.command_submitted.connect(lambda t: submitted_texts.append(t))
    overlay._input_field.setText("Test Command Prompt")
    overlay._on_submit()
    assert "Test Command Prompt" in submitted_texts
    assert overlay._input_field.text() == ""


def test_system_status_overlay_instantiation(qapp):
    overlay = SystemStatusOverlay()
    assert overlay.objectName() == "SystemStatusOverlay"
    assert overlay.windowTitle() == "AuraAI System Status"
    assert not overlay.isVisible()

    # Test toggle
    overlay.toggle()
    assert overlay.isVisible()
    overlay.toggle()
    assert not overlay.isVisible()


