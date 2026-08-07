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
from src.gui.signals import app_signals, ExecutionStep, StepStatus
from src.gui.main_window import MainWindow
from src.gui.overlay import OverlayWindow
from src.gui.widgets import NavigationRail, StatusPill, StepCard, VoiceWaveform, ChatStreamWidget, DagVisualizer, InspectorDrawer


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
    
    step = ExecutionStep(index=0, title="Test Step", description="Details", status=StepStatus.RUNNING, timestamp=1.0)
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
    assert window.windowTitle() == "AuraAI Control Center"
    assert window._center_stack.count() == 5


def test_overlay_window_instantiation(qapp):
    overlay = OverlayWindow()
    assert overlay.objectName() == "OverlayWindow"
    assert not overlay.isVisible()
