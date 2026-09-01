"""
WebEngine Telemetry & Console Bridge
====================================
Location: src/gui/bridge/web_telemetry_bridge.py

Connects Chromium JavaScript console output, network warnings, and unhandled errors
directly into Aura's global signal bus and Live Log Viewer HUD.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtWebEngineCore import QWebEnginePage

from gui.signals import app_signals

logger = logging.getLogger(__name__)


class WebTelemetryBridge(QWebEnginePage):
    """
    Custom QWebEnginePage that intercepts browser JavaScript console messages,
    errors, and telemetry, streaming them to Qt signals and Aura's Live Log HUD.
    """

    # Custom signals for granular UI telemetry listeners
    console_logged = Signal(str, str, int, str)  # level, message, line, source_id
    page_title_changed = Signal(str)
    load_state_changed = Signal(str, int)  # status ("loading"|"finished"|"failed"), progress

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._setup_page_signals()

    def _setup_page_signals(self) -> None:
        self.loadStarted.connect(lambda: self.load_state_changed.emit("loading", 0))
        self.loadProgress.connect(lambda p: self.load_state_changed.emit("loading", p))
        self.loadFinished.connect(self._on_load_finished)
        self.titleChanged.connect(self.page_title_changed.emit)

    def _on_load_finished(self, success: bool) -> None:
        status = "finished" if success else "failed"
        self.load_state_changed.emit(status, 100)
        if success:
            app_signals.log_message.emit(
                f"[WebPreview] Loaded page: {self.url().toString()}",
                "INFO",
            )
        else:
            app_signals.log_message.emit(
                f"[WebPreview:Error] Failed to load URL: {self.url().toString()}",
                "ERROR",
            )

    def javaScriptConsoleMessage(
        self,
        level: QWebEnginePage.JavaScriptConsoleMessageLevel,
        message: str,
        line_number: int,
        source_id: str,
    ) -> None:
        """
        Intercepts all console.log, console.warn, and console.error messages from page JavaScript.
        """
        level_map = {
            QWebEnginePage.JavaScriptConsoleMessageLevel.InfoMessageLevel: "INFO",
            QWebEnginePage.JavaScriptConsoleMessageLevel.WarningMessageLevel: "WARNING",
            QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel: "ERROR",
        }
        level_str = level_map.get(level, "INFO")
        source_name = source_id.split("/")[-1] if source_id else "inline"

        # Emit Qt signal
        self.console_logged.emit(level_str, message, line_number, source_id)

        # Route to Aura's Live Log HUD
        log_tag = "WebEngine:Error" if level_str == "ERROR" else "WebEngine:Console"
        formatted_msg = f"[{log_tag}] ({source_name}:{line_number}) {message}"
        app_signals.log_message.emit(formatted_msg, level_str)
        logger.debug(f"[TelemetryBridge] {formatted_msg}")
