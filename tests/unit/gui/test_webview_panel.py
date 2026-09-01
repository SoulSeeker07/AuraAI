"""
Tests for In-GUI Webview Preview Panel
======================================
Location: tests/unit/gui/test_webview_panel.py
"""

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

from gui.webengine_init import ensure_webengine_flags
ensure_webengine_flags()

from gui.widgets.webview_panel import WebViewPanel


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_webview_panel_instantiation_and_viewport_modes(qapp):
    panel = WebViewPanel()
    assert panel is not None
    assert panel.get_viewport_mode() == "desktop"

    # Test Mobile Viewport
    panel.set_viewport_mode("mobile")
    assert panel.get_viewport_mode() == "mobile"
    assert panel.view_wrapper.width() == 375
    assert panel.btn_mobile.isChecked()

    # Test Tablet Viewport
    panel.set_viewport_mode("tablet")
    assert panel.get_viewport_mode() == "tablet"
    assert panel.view_wrapper.width() == 768
    assert panel.btn_tablet.isChecked()

    # Test Desktop / Responsive Viewport
    panel.set_viewport_mode("desktop")
    assert panel.get_viewport_mode() == "desktop"
    assert panel.btn_desktop.isChecked()


def test_webview_panel_zoom_controls(qapp):
    panel = WebViewPanel()
    assert panel.get_zoom_factor() == 1.0

    panel.zoom_in()
    assert round(panel.get_zoom_factor(), 2) == 1.1

    panel.zoom_out()
    assert round(panel.get_zoom_factor(), 2) == 1.0

    # Test clamp boundaries
    panel.set_zoom_factor(0.1)
    assert panel.get_zoom_factor() == 0.5

    panel.set_zoom_factor(5.0)
    assert panel.get_zoom_factor() == 3.0


def test_webview_panel_url_loading(qapp):
    panel = WebViewPanel()
    panel.load_url("http://127.0.0.1:8765/test.html")
    assert panel.url_display.text() == "http://127.0.0.1:8765/test.html"
