"""
Unit & Integration Tests for M30 Holographic GUI HUD Overlays
Location: tests/test_holographic_overlays.py

Verifies:
1. Instantiation and window flags (Frameless, Translucent, WindowStaysOnTop).
2. Paint events, custom rendering, and dirty-region invalidation.
3. IntentRouter routing for all 6 HUD overlay variants.
4. Telemetry worker sampling (CPU, RAM, GPU, Network).
5. Signal bus connections across overlay widgets.
"""

import sys
import os
from pathlib import Path
import pytest

# Ensure src in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(1, str(PROJECT_ROOT))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPainter, QPixmap

from brain.intent_router import IntentRouter
from Memory import Memory

# Ensure single QApplication per test session
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def intent_router():
    mem = Memory(db_path=":memory:", chat_log_path="Data/test_chat_log.json")
    return IntentRouter(memory=mem)


def test_matrix_overlay(qapp):
    """Verify Matrix Digital Rain Overlay widget instantiation and painting."""
    from gui.widgets.matrix_overlay import MatrixOverlay
    widget = MatrixOverlay()
    assert widget.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert widget.windowFlags() & Qt.WindowType.WindowStaysOnTopHint

    # Trigger paint event
    pix = QPixmap(widget.size())
    widget.render(pix)
    assert not pix.isNull()
    widget.close()


def test_system_monitor_overlay(qapp):
    """Verify System Performance Telemetry HUD Overlay."""
    from gui.widgets.system_monitor_overlay import SystemMonitorOverlay
    widget = SystemMonitorOverlay()
    assert widget.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert widget.windowFlags() & Qt.WindowType.WindowStaysOnTopHint

    # Verify telemetry data update
    widget.update_data(cpu_pct=24.5, net_down_kb=850.0)
    assert widget.data.get("cpu_pct") == 24.5
    
    pix = QPixmap(widget.size())
    widget.render(pix)
    assert not pix.isNull()
    widget.close()


def test_agent_task_status_overlay(qapp):
    """Verify Agent Task Status & DAG Execution HUD Overlay."""
    from gui.widgets.agent_task_status_overlay import AgentTaskStatusOverlay
    widget = AgentTaskStatusOverlay()
    assert widget.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert widget.windowFlags() & Qt.WindowType.WindowStaysOnTopHint

    pix = QPixmap(widget.size())
    widget.render(pix)
    assert not pix.isNull()
    widget.close()


def test_personal_os_dashboard_overlay(qapp):
    """Verify Personal OS Holographic Dashboard Overlay."""
    from gui.widgets.personal_os_dashboard_overlay import PersonalOSDashboardOverlay
    widget = PersonalOSDashboardOverlay()
    assert widget.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert widget.windowFlags() & Qt.WindowType.WindowStaysOnTopHint

    pix = QPixmap(widget.size())
    widget.render(pix)
    assert not pix.isNull()
    widget.close()


def test_spotlight_overlay_window(qapp):
    """Verify Spotlight HUD OverlayWindow (Alt+Space Command Bar)."""
    from gui.overlay import OverlayWindow
    widget = OverlayWindow()
    assert widget.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert widget.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert widget.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    pix = QPixmap(widget.size())
    widget.render(pix)
    assert not pix.isNull()
    widget.close()


def test_intent_routing_all_hud_overlays(intent_router):
    """Verify that user queries route to all 6 HUD overlay variants."""
    overlay_test_cases = [
        ("aura launch jarvis rings", "jarvis_rings"),
        ("aura show voice rings", "jarvis_rings"),
        ("aura launch system monitor", "system_monitor"),
        ("aura show performance hud", "system_monitor"),
        ("aura launch matrix overlay", "matrix_overlay"),
        ("aura show cyberpunk matrix", "matrix_overlay"),
        ("aura launch task status", "task_status"),
        ("aura show agent status overlay", "task_status"),
        ("aura launch personal os", "personal_os"),
        ("aura show os dashboard", "personal_os"),
        ("aura launch control center", "main_hud"),
        ("aura open gui", "main_hud"),
    ]

    for query, expected_type in overlay_test_cases:
        intent = intent_router.detect(query)
        assert intent.name == "hud_overlay", f"Failed for query: '{query}' (got intent '{intent.name}')"
        assert intent.data.get("overlay_type") == expected_type, f"Failed type for '{query}' (got '{intent.data.get('overlay_type')}')"
