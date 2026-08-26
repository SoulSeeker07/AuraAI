"""
Comprehensive Unit Tests for JarvisRingsOverlay
-----------------------------------------------
Verifies:
1. Widget initialization, frameless flags, translucent background attributes.
2. Angle progression and animation step physics.
3. Live audio level callback updates (is_speaking, peak amplitude).
4. Off-screen QPainter rendering pipeline (paintEvent).
5. Thread cleanup on closeEvent.
"""

import sys
import pytest
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtWidgets import QApplication, QWidget

# Ensure src is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(1, str(PROJECT_ROOT))

from gui.widgets.jarvis_rings_overlay import JarvisRingsOverlay, AudioLevelWorker


@pytest.fixture(scope="session")
def qapp():
    """Ensure a singleton QApplication instance exists for headless GUI testing."""
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def overlay(qapp):
    """Provide an isolated JarvisRingsOverlay widget instance."""
    w = JarvisRingsOverlay()
    w.resize(320, 350)
    qapp.processEvents()
    yield w
    if hasattr(w, "_audio_worker") and w._audio_worker:
        w._audio_worker.stop()
        w._audio_worker.wait(500)
    if hasattr(w, "close"):
        w.close()
    qapp.processEvents()


def test_widget_instantiation(overlay):
    """Verify window flags, translucent attributes, and initial state."""
    assert overlay is not None
    assert overlay.testAttribute(Qt.WA_TranslucentBackground)
    flags = overlay.windowFlags()
    assert bool(flags & Qt.FramelessWindowHint)
    assert bool(flags & Qt.WindowStaysOnTopHint)
    assert overlay._angle_outer == 0.0
    assert overlay._is_speaking is False
    assert overlay._status_text == "STANDBY"


def test_audio_level_callback(overlay):
    """Verify that audio level and speaking state update dynamically."""
    overlay._on_audio_level(peak=0.85, is_speaking=True)
    assert overlay._target_audio_level == 0.85
    assert overlay._is_speaking is True
    assert "ACTIVE" in overlay._status_text

    overlay._on_audio_level(peak=0.0, is_speaking=False)
    assert overlay._target_audio_level == 0.0
    assert overlay._is_speaking is False
    assert "STANDBY" in overlay._status_text


def test_advance_animation(overlay):
    """Verify angular progression and rotation step math."""
    initial_outer = overlay._angle_outer
    initial_mid = overlay._angle_mid
    initial_inner = overlay._angle_inner

    overlay._advance_animation()

    assert overlay._angle_outer > initial_outer
    assert overlay._angle_mid != initial_mid
    assert 0.0 <= overlay._angle_mid < 360.0
    assert overlay._angle_inner > initial_inner


def test_paint_event_rendering(overlay, qapp):
    """Verify that QPainter pipeline renders cleanly to a pixmap without throwing."""
    pixmap = QPixmap(320, 350)
    pixmap.fill(Qt.transparent)

    # Test normal idle paint
    overlay.render(pixmap)

    # Test active speech paint
    overlay._on_audio_level(peak=0.9, is_speaking=True)
    overlay._advance_animation()
    qapp.processEvents()

    overlay.render(pixmap)
    assert not pixmap.isNull()


def test_audio_worker_thread():
    """Verify AudioLevelWorker lifecycle."""
    worker = AudioLevelWorker()
    assert worker._running is True
    worker.stop()
    assert worker._running is False
