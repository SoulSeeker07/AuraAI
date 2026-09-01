"""
Interactive Webview Preview Panel
=================================
Location: src/gui/widgets/webview_panel.py

Claude-Artifacts-style live webview preview widget embedded directly in Aura's
developer workspace. Features viewport switching (Mobile/Tablet/Desktop), zoom controls,
auto-reloading, and Live Log Viewer telemetry streaming.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.bridge.web_telemetry_bridge import WebTelemetryBridge
from gui.theme import Colors, Typography

logger = logging.getLogger(__name__)


class WebViewPanel(QWidget):
    """
    In-GUI Live Webview Preview Panel with viewport controls and telemetry routing.
    """

    # Signals
    url_changed = Signal(str)
    viewport_changed = Signal(str)  # "mobile", "tablet", "desktop"

    VIEWPORT_WIDTHS = {
        "mobile": 375,
        "tablet": 768,
        "desktop": None,  # 100% responsive
    }

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._current_viewport_mode = "desktop"
        self._current_zoom = 1.0

        self._setup_ui()
        self._setup_webengine()
        self._apply_styling()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Top Control Bar / Toolbar
        self.toolbar = QFrame()
        self.toolbar.setObjectName("PreviewToolbar")
        self.toolbar.setFixedHeight(40)
        tb_layout = QHBoxLayout(self.toolbar)
        tb_layout.setContentsMargins(8, 4, 8, 4)
        tb_layout.setSpacing(6)

        # Viewport Mode Buttons
        self.btn_mobile = QPushButton("📱 375")
        self.btn_mobile.setToolTip("Mobile Viewport (375px)")
        self.btn_mobile.setCheckable(True)
        self.btn_mobile.clicked.connect(lambda: self.set_viewport_mode("mobile"))

        self.btn_tablet = QPushButton("💻 768")
        self.btn_tablet.setToolTip("Tablet Viewport (768px)")
        self.btn_tablet.setCheckable(True)
        self.btn_tablet.clicked.connect(lambda: self.set_viewport_mode("tablet"))

        self.btn_desktop = QPushButton("🖥️ 100%")
        self.btn_desktop.setToolTip("Desktop Responsive (100%)")
        self.btn_desktop.setCheckable(True)
        self.btn_desktop.setChecked(True)
        self.btn_desktop.clicked.connect(lambda: self.set_viewport_mode("desktop"))

        # URL / Status Bar
        self.url_display = QLineEdit()
        self.url_display.setPlaceholderText("http://127.0.0.1:8765/index.html")
        self.url_display.setReadOnly(True)
        self.url_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # Zoom Controls
        self.btn_zoom_out = QPushButton("➖")
        self.btn_zoom_out.setToolTip("Zoom Out")
        self.btn_zoom_out.setFixedWidth(28)
        self.btn_zoom_out.clicked.connect(self.zoom_out)

        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setObjectName("ZoomLabel")
        self.lbl_zoom.setAlignment(Qt.AlignCenter)
        self.lbl_zoom.setFixedWidth(42)

        self.btn_zoom_in = QPushButton("➕")
        self.btn_zoom_in.setToolTip("Zoom In")
        self.btn_zoom_in.setFixedWidth(28)
        self.btn_zoom_in.clicked.connect(self.zoom_in)

        # Action Buttons
        self.btn_reload = QPushButton("🔄")
        self.btn_reload.setToolTip("Hard Reload Preview")
        self.btn_reload.setFixedWidth(32)
        self.btn_reload.clicked.connect(self.reload_page)

        self.btn_external = QPushButton("↗")
        self.btn_external.setToolTip("Open in External Browser")
        self.btn_external.setFixedWidth(32)
        self.btn_external.clicked.connect(self.open_external)

        # Assemble Toolbar
        tb_layout.addWidget(self.btn_mobile)
        tb_layout.addWidget(self.btn_tablet)
        tb_layout.addWidget(self.btn_desktop)
        tb_layout.addWidget(self.url_display)
        tb_layout.addWidget(self.btn_zoom_out)
        tb_layout.addWidget(self.lbl_zoom)
        tb_layout.addWidget(self.btn_zoom_in)
        tb_layout.addWidget(self.btn_reload)
        tb_layout.addWidget(self.btn_external)

        main_layout.addWidget(self.toolbar)

        # 2. Viewport Area (Container supporting fixed width centering)
        self.viewport_scroll = QScrollArea()
        self.viewport_scroll.setObjectName("ViewportScroll")
        self.viewport_scroll.setWidgetResizable(True)
        self.viewport_scroll.setFrameShape(QFrame.NoFrame)
        self.viewport_scroll.setAlignment(Qt.AlignCenter)

        self.viewport_container = QWidget()
        self.viewport_container.setObjectName("ViewportContainer")
        self.container_layout = QHBoxLayout(self.viewport_container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(0)
        self.container_layout.setAlignment(Qt.AlignCenter)

        self.viewport_scroll.setWidget(self.viewport_container)
        main_layout.addWidget(self.viewport_scroll)

    def _setup_webengine(self) -> None:
        # Create WebEngineView and Telemetry Page Bridge
        self.web_view = QWebEngineView()
        self.web_view.setObjectName("PreviewWebEngineView")
        self.page_bridge = WebTelemetryBridge(self.web_view)
        self.web_view.setPage(self.page_bridge)

        # Connect signals
        self.web_view.urlChanged.connect(self._on_url_changed)

        # Frame wrapper to render clean bezels when constrained to mobile/tablet
        self.view_wrapper = QFrame()
        self.view_wrapper.setObjectName("ViewWrapper")
        wrapper_layout = QVBoxLayout(self.view_wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(0)
        wrapper_layout.addWidget(self.web_view)

        self.container_layout.addWidget(self.view_wrapper)

    def _apply_styling(self) -> None:
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {Colors.BG_DEEP};
                color: {Colors.TEXT_PRIMARY};
                font-family: {Typography.FAMILY};
            }}
            #PreviewToolbar {{
                background-color: {Colors.BG_SLATE};
                border-bottom: 1px solid {Colors.BORDER_SUBTLE};
            }}
            #PreviewToolbar QPushButton {{
                background-color: {Colors.BG_SURFACE};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }}
            #PreviewToolbar QPushButton:hover {{
                border-color: {Colors.CYAN};
                color: {Colors.CYAN};
            }}
            #PreviewToolbar QPushButton:checked {{
                background-color: {Colors.CYAN_DIM};
                border-color: {Colors.CYAN};
                color: {Colors.CYAN};
                font-weight: bold;
            }}
            QLineEdit {{
                background-color: {Colors.BG_DEEP};
                color: {Colors.TEXT_MUTED};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: 4px;
                padding: 2px 8px;
                font-family: Consolas, monospace;
                font-size: 11px;
            }}
            #ZoomLabel {{
                color: {Colors.TEXT_MUTED};
                font-family: Consolas, monospace;
                font-size: 11px;
            }}
            #ViewWrapper {{
                background-color: transparent;
            }}
        """)

    def _on_url_changed(self, url: QUrl) -> None:
        url_str = url.toString()
        self.url_display.setText(url_str)
        self.url_changed.emit(url_str)

    # ─────────────────────────────────────────────────────────────────────────
    # Public Control API
    # ─────────────────────────────────────────────────────────────────────────
    def load_url(self, url: str) -> None:
        """Navigates webview to specified URL."""
        if not url.startswith("http://") and not url.startswith("https://") and not url.startswith("file://"):
            url = f"http://{url}"
        self.url_display.setText(url)
        self.web_view.setUrl(QUrl(url))

    def load_html(self, html_content: str, base_url: str = "") -> None:
        """Renders raw HTML string directly."""
        self.web_view.setHtml(html_content, QUrl(base_url))

    def reload_page(self) -> None:
        """Forces hard refresh of current preview."""
        self.web_view.reload()

    def open_external(self) -> None:
        """Opens current URL in default system web browser."""
        current_url = self.web_view.url()
        if current_url.isValid() and not current_url.isEmpty():
            QDesktopServices.openUrl(current_url)

    def set_viewport_mode(self, mode: str) -> None:
        """
        Switches viewport constraint mode ('mobile', 'tablet', 'desktop').
        """
        mode = mode.lower()
        if mode not in self.VIEWPORT_WIDTHS:
            mode = "desktop"

        self._current_viewport_mode = mode

        # Update button checks
        self.btn_mobile.setChecked(mode == "mobile")
        self.btn_tablet.setChecked(mode == "tablet")
        self.btn_desktop.setChecked(mode == "desktop")

        target_width = self.VIEWPORT_WIDTHS[mode]

        if target_width is None:
            # Full responsive / desktop
            self.view_wrapper.setFixedWidth(QWIDGETSIZE_MAX := 16777215)
            self.view_wrapper.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.view_wrapper.setStyleSheet("border: none; border-radius: 0px;")
        else:
            # Fixed container width (centered in scroll area)
            self.view_wrapper.setFixedWidth(target_width)
            self.view_wrapper.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            self.view_wrapper.setStyleSheet(f"""
                #ViewWrapper {{
                    border: 2px solid {Colors.BORDER_ACTIVE};
                    border-radius: 12px;
                    margin: 8px 0px;
                }}
            """)

        self.viewport_changed.emit(mode)
        logger.debug(f"[WebViewPanel] Switched viewport mode to {mode} (width: {target_width})")

    def set_zoom_factor(self, factor: float) -> None:
        """Sets zoom factor between 0.5 and 3.0."""
        self._current_zoom = max(0.5, min(3.0, round(factor, 2)))
        self.web_view.setZoomFactor(self._current_zoom)
        self.lbl_zoom.setText(f"{int(self._current_zoom * 100)}%")

    def zoom_in(self) -> None:
        self.set_zoom_factor(self._current_zoom + 0.1)

    def zoom_out(self) -> None:
        self.set_zoom_factor(self._current_zoom - 0.1)

    def get_zoom_factor(self) -> float:
        return self._current_zoom

    def get_viewport_mode(self) -> str:
        return self._current_viewport_mode
