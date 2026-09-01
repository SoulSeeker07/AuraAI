"""
Unit tests for MainWindow geometry scaling and small-display fitting.
Location: tests/unit/gui/test_window_geometry.py
"""

import os
import sys
import pytest

# Ensure headless Qt for test execution
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow, MIN_W, MIN_H


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_main_window_minimum_size_fits_small_displays(qapp):
    """
    Regression test: Ensure child layout minimumSizeHint does not bloat
    MainWindow beyond MIN_W (760px) or standard small-screen resolution (1366px).
    """
    win = MainWindow()
    min_w = win.minimumSizeHint().width()
    assert min_w <= MIN_W, (
        f"MainWindow minimumSizeHint().width() is {min_w}px, "
        f"which exceeds MIN_W ({MIN_W}px) and breaks small display scaling."
    )
    assert min_w < 1366, f"MainWindow minimum width {min_w}px exceeds 1366px laptop width."


def test_auto_fit_screen_produces_onscreen_geometry(qapp):
    """
    Ensure auto_fit_screen() dynamically resizes and centers the window
    within available screen geometry without overflowing edges.
    """
    win = MainWindow()
    screen = QApplication.primaryScreen().availableGeometry()
    win.auto_fit_screen()

    assert win.width() <= screen.width(), f"Window width {win.width()} exceeds screen {screen.width()}"
    assert win.height() <= screen.height(), f"Window height {win.height()} exceeds screen {screen.height()}"
    assert win.x() >= screen.left(), f"Window X {win.x()} overflows left edge {screen.left()}"
    assert win.y() >= screen.top(), f"Window Y {win.y()} overflows top edge {screen.top()}"
    assert win.x() + win.width() <= screen.right() + 1, "Window right edge overflows screen right"
    assert win.y() + win.height() <= screen.bottom() + 1, "Window bottom edge overflows screen bottom"


def test_hud_overlays_menu_actions(qapp):
    """
    Ensure the compact HUD Overlays dropdown menu preserves all 6 overlay toggle actions.
    """
    win = MainWindow()
    # Find the overlays button in the titlebar
    menu = None
    for child in win._titlebar_widget.findChildren(object):
        if hasattr(child, "menu") and child.menu() is not None:
            menu = child.menu()
            break

    assert menu is not None, "HUD Overlays dropdown menu not found on titlebar"
    action_texts = [a.text().strip() for a in menu.actions()]
    assert any("Chat HUD" in t for t in action_texts)
    assert any("Personal OS" in t for t in action_texts)
    assert any("Agent Tasks" in t for t in action_texts)
    assert any("System Status" in t for t in action_texts)
    assert any("System HUD" in t for t in action_texts)
    assert any("Weather HUD" in t for t in action_texts)


def test_chat_overlay_offscreen_geometry_clamped(qapp):
    """
    Ensure ChatWindowOverlay properly clamps off-screen or negative coordinates
    (e.g., from secondary monitor disconnects or minimized states) back into
    the visible primary screen area.
    """
    from PySide6.QtCore import QPoint, QSettings
    from gui.widgets.chat_window_overlay import ChatWindowOverlay

    # Artificially set an off-screen position (-1500, -3000)
    settings = QSettings("AuraAI", "ChatWindowOverlay")
    settings.setValue("pos", QPoint(-1500, -3000))

    overlay = ChatWindowOverlay()
    screen = QApplication.primaryScreen().availableGeometry()

    assert overlay.x() >= screen.left(), f"Chat HUD X {overlay.x()} is off-screen left"
    assert overlay.y() >= screen.top(), f"Chat HUD Y {overlay.y()} is off-screen top"
    assert overlay.x() + overlay.width() <= screen.right() + 1, "Chat HUD overflows screen right"
    assert overlay.y() + overlay.height() <= screen.bottom() + 1, "Chat HUD overflows screen bottom"


def test_chat_overlay_toggle_unminimizes(qapp):
    """
    Ensure toggle() unminimizes and restores a minimized ChatWindowOverlay.
    """
    from PySide6.QtCore import Qt
    from gui.widgets.chat_window_overlay import ChatWindowOverlay

    overlay = ChatWindowOverlay()
    overlay.showMinimized()
    assert overlay.isMinimized()

    # Calling toggle while minimized should unminimize and make it visible/active
    overlay.toggle()
    assert not overlay.isMinimized()
    assert overlay.isVisible()

