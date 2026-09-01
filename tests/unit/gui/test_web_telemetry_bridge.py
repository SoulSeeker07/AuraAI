"""
Tests for WebEngine Telemetry Bridge
====================================
Location: tests/unit/gui/test_web_telemetry_bridge.py
"""

import pytest
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWidgets import QApplication

from gui.bridge.web_telemetry_bridge import WebTelemetryBridge
from gui.signals import app_signals


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_web_telemetry_bridge_console_forwarding(qapp):
    bridge = WebTelemetryBridge()
    captured_signals = []
    captured_app_logs = []

    def on_console_logged(level, msg, line, src):
        captured_signals.append((level, msg, line, src))

    def on_app_log(msg, level):
        captured_app_logs.append((msg, level))

    bridge.console_logged.connect(on_console_logged)
    app_signals.log_message.connect(on_app_log)

    # Simulate info console message
    bridge.javaScriptConsoleMessage(
        QWebEnginePage.JavaScriptConsoleMessageLevel.InfoMessageLevel,
        "Aura preview active",
        42,
        "http://127.0.0.1:8765/app.js",
    )

    assert len(captured_signals) == 1
    assert captured_signals[0] == ("INFO", "Aura preview active", 42, "http://127.0.0.1:8765/app.js")

    assert len(captured_app_logs) >= 1
    assert any("[WebEngine:Console]" in log[0] and "Aura preview active" in log[0] for log in captured_app_logs)

    # Simulate error console message
    bridge.javaScriptConsoleMessage(
        QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel,
        "Uncaught TypeError: Cannot read properties of undefined",
        99,
        "http://127.0.0.1:8765/bundle.js",
    )

    assert captured_signals[-1][0] == "ERROR"
    assert any("[WebEngine:Error]" in log[0] and "Uncaught TypeError" in log[0] for log in captured_app_logs)
