"""
AuraAI — Dedicated Live System & Engine Log Viewer Overlay
==========================================================
Futuristic, high-contrast Cyber Log HUD console for streaming,
filtering, searching, and inspecting live AuraAI system logs.
"""

import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

from PySide6.QtCore import QPoint, QRect, QSettings, QTimer, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.signals import app_signals

FONT_FAMILY = "Segoe UI"
FONT_MONO = "Consolas, 'Cascadia Code', 'Fira Code', monospace"
MIN_W = 600
MIN_H = 420
GRIP_SIZE = 16

ORG_NAME = "SoulSeeker"
APP_NAME = "AuraAI_LogViewer"


class LiveLogViewerOverlay(QWidget):
    """
    Dedicated Futuristic Cyber Log Viewer HUD Overlay.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LiveLogViewerOverlay")
        self.setWindowTitle("AuraAI Live System Logs")

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

        self._settings = QSettings(ORG_NAME, APP_NAME)

        # Drag & resize state
        self._drag_pos: Optional[QPoint] = None
        self._resizing = False
        self._resize_start_pos: Optional[QPoint] = None
        self._resize_start_size = None

        self._current_level = "ALL"  # "ALL", "INFO", "DEBUG", "WARNING", "ERROR"

        self._setup_ui()
        self._connect_signals()
        self._restore_geometry()

        # 1.5s Auto-refresh timer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_logs)
        self._refresh_timer.start(1500)

        self._refresh_logs()

    def _connect_signals(self):
        if hasattr(app_signals, "toggle_log_viewer_overlay"):
            app_signals.toggle_log_viewer_overlay.connect(self.toggle)

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)

        # Outer Glass Container
        self._card = QFrame()
        self._card.setStyleSheet("""
            QFrame {
                background: rgba(6, 10, 20, 0.94);
                border: 1px solid rgba(0, 240, 255, 0.4);
                border-radius: 12px;
            }
        """)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(10)

        # ── 1. Header Bar ──
        header = QHBoxLayout()
        header.setSpacing(10)

        orb_lbl = QLabel("●")
        orb_lbl.setStyleSheet("color: #00f0ff; font-size: 14px; background: transparent; border: none;")
        header.addWidget(orb_lbl)

        title_lbl = QLabel("AuraAI  //  Live System & Engine Logs")
        title_lbl.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #00f0ff; letter-spacing: 1px; background: transparent; border: none;")
        header.addWidget(title_lbl)

        header.addStretch()

        self._log_count_lbl = QLabel("0 entries")
        self._log_count_lbl.setFont(QFont(FONT_FAMILY, 9))
        self._log_count_lbl.setStyleSheet("color: #64748b; background: transparent; border: none;")
        header.addWidget(self._log_count_lbl)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 12px;
                color: #94a3b8;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.3);
                border-color: #ef4444;
                color: #ffffff;
            }
        """)
        btn_close.clicked.connect(self.hide)
        header.addWidget(btn_close)

        card_layout.addLayout(header)

        # ── 2. Filter & Command Ribbon ──
        ribbon = QHBoxLayout()
        ribbon.setSpacing(6)

        # Level Selector Buttons
        self._level_btns = {}
        for lvl, col in [("ALL", "#00f0ff"), ("CHAT", "#38bdf8"), ("INFO", "#10b981"), ("DEBUG", "#a855f7"), ("WARNING", "#f59e0b"), ("ERROR", "#ef4444")]:
            btn = QPushButton(lvl)
            btn.setFont(QFont(FONT_FAMILY, 8, QFont.Weight.Bold))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(24)
            btn.setStyleSheet(self._make_lvl_btn_style(lvl == "ALL", col))
            btn.clicked.connect(lambda _, l=lvl: self._set_level(l))
            self._level_btns[lvl] = (btn, col)
            ribbon.addWidget(btn)

        ribbon.addSpacing(10)

        # Search Input
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search logs / regex...")
        self._search_input.setFont(QFont(FONT_FAMILY, 8))
        self._search_input.setFixedHeight(24)
        self._search_input.setStyleSheet("""
            QLineEdit {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(0, 240, 255, 0.25);
                border-radius: 5px;
                padding: 0 8px;
                color: #f1f5f9;
                font-family: Consolas;
            }
            QLineEdit:focus {
                border-color: #00f0ff;
                background: rgba(0, 240, 255, 0.08);
            }
        """)
        self._search_input.textChanged.connect(self._refresh_logs)
        ribbon.addWidget(self._search_input, 1)

        # Auto Scroll Checkbox
        self._auto_scroll_cb = QCheckBox("Auto-Scroll")
        self._auto_scroll_cb.setChecked(True)
        self._auto_scroll_cb.setFont(QFont(FONT_FAMILY, 8))
        self._auto_scroll_cb.setStyleSheet("color: #94a3b8; background: transparent; border: none;")
        ribbon.addWidget(self._auto_scroll_cb)

        # Refresh Button
        btn_ref = QPushButton("↺")
        btn_ref.setFixedSize(24, 24)
        btn_ref.setToolTip("Refresh Logs")
        btn_ref.setCursor(Qt.PointingHandCursor)
        btn_ref.setStyleSheet("""
            QPushButton {
                background: rgba(0, 240, 255, 0.1);
                border: 1px solid rgba(0, 240, 255, 0.3);
                border-radius: 4px;
                color: #00f0ff;
                font-size: 12px;
            }
            QPushButton:hover {
                background: rgba(0, 240, 255, 0.25);
                color: #ffffff;
            }
        """)
        btn_ref.clicked.connect(self._refresh_logs)
        ribbon.addWidget(btn_ref)

        # Copy Button
        btn_copy = QPushButton("📋")
        btn_copy.setFixedSize(24, 24)
        btn_copy.setToolTip("Copy All Logs")
        btn_copy.setCursor(Qt.PointingHandCursor)
        btn_copy.setStyleSheet("""
            QPushButton {
                background: rgba(168, 85, 247, 0.1);
                border: 1px solid rgba(168, 85, 247, 0.3);
                border-radius: 4px;
                color: #a855f7;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(168, 85, 247, 0.25);
                color: #ffffff;
            }
        """)
        btn_copy.clicked.connect(self._copy_logs)
        ribbon.addWidget(btn_copy)

        # Clear Button
        btn_clear = QPushButton("✖")
        btn_clear.setFixedSize(24, 24)
        btn_clear.setToolTip("Clear Display")
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.setStyleSheet("""
            QPushButton {
                background: rgba(239, 68, 68, 0.1);
                border: 1px solid rgba(239, 68, 68, 0.3);
                border-radius: 4px;
                color: #ef4444;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.25);
                color: #ffffff;
            }
        """)
        btn_clear.clicked.connect(lambda: self._log_view.clear())
        ribbon.addWidget(btn_clear)

        card_layout.addLayout(ribbon)

        # ── 3. Monospace Log Viewer ──
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setFont(QFont("Consolas", 9))
        self._log_view.setStyleSheet("""
            QPlainTextEdit {
                background: rgba(2, 4, 10, 0.95);
                color: #cbd5e1;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                padding: 10px;
                line-height: 1.4;
            }
        """)
        card_layout.addWidget(self._log_view, 1)

        root_layout.addWidget(self._card)

    def _make_lvl_btn_style(self, active: bool, color: str) -> str:
        if active:
            return f"""
                QPushButton {{
                    background: {color}33;
                    border: 1px solid {color};
                    border-radius: 4px;
                    color: #ffffff;
                    padding: 0 8px;
                }}
            """
        else:
            return f"""
                QPushButton {{
                    background: rgba(255, 255, 255, 0.03);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 4px;
                    color: #94a3b8;
                    padding: 0 8px;
                }}
                QPushButton:hover {{
                    background: {color}18;
                    border-color: {color}66;
                    color: #ffffff;
                }}
            """

    def _set_level(self, level: str):
        self._current_level = level
        for lvl, (btn, col) in self._level_btns.items():
            btn.setStyleSheet(self._make_lvl_btn_style(lvl == level, col))
        self._refresh_logs()

    def _copy_logs(self):
        text = self._log_view.toPlainText()
        if text:
            from PySide6.QtGui import QGuiApplication
            QGuiApplication.clipboard().setText(text)

    def _tail_file(self, path: Path, max_bytes: int = 98304) -> list[str]:
        """High-speed binary seek to read only the last few KB of large log files instantly."""
        if not path.exists():
            return []
        try:
            with open(path, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                if size == 0:
                    return []
                f.seek(max(0, size - max_bytes), os.SEEK_SET)
                chunk = f.read().decode("utf-8", errors="replace")
                lines = chunk.splitlines()
                # Drop first line if partial chunk was read
                return lines[1:] if size > max_bytes and len(lines) > 1 else lines
        except Exception:
            return []

    def _refresh_logs(self):
        try:
            import json
            import datetime
            root = Path(__file__).resolve().parents[3]
            raw_lines = []

            # 1. High-speed tail of active session logs from today's directory
            today_str = datetime.date.today().isoformat()
            today_dir = root / "logs" / today_str
            if today_dir.exists():
                session_files = sorted(today_dir.glob("session_*.log"), key=lambda f: f.stat().st_mtime)
                if session_files:
                    raw_lines.extend(self._tail_file(session_files[-1], max_bytes=65536))

            # 2. High-speed tail of aura.log
            aura_log = root / "logs" / "aura.log"
            if aura_log.exists():
                raw_lines.extend(self._tail_file(aura_log, max_bytes=65536))

            # 3. Load Chat History from Data/ChatLog.json (last 30 entries)
            chat_log_file = root / "Data" / "ChatLog.json"
            if chat_log_file.exists():
                try:
                    with open(chat_log_file, "r", encoding="utf-8", errors="replace") as cf:
                        data = json.load(cf)
                    if isinstance(data, list):
                        for item in data[-30:]:
                            role = item.get("role", "user")
                            content = item.get("content", "").replace("\n", " ")
                            ts = item.get("timestamp", "")
                            t_part = ts.split("T")[-1][:8] if "T" in ts else ts
                            sender = "User" if role == "user" else "AuraAI"
                            raw_lines.append(f"{t_part} [CHAT    ] {sender}: {content}")
                except Exception:
                    pass

            # Deduplicate or cap to latest 400 lines
            if len(raw_lines) > 400:
                raw_lines = raw_lines[-400:]

            # Compute category counts for badge counters
            counts = {
                "ALL": len(raw_lines),
                "CHAT": sum(1 for l in raw_lines if "[CHAT" in l or "[User Query]" in l or "[AuraAI" in l),
                "INFO": sum(1 for l in raw_lines if "[INFO" in l),
                "DEBUG": sum(1 for l in raw_lines if "[DEBUG" in l),
                "WARNING": sum(1 for l in raw_lines if "[WARNING" in l or "[WARN" in l),
                "ERROR": sum(1 for l in raw_lines if "[ERROR" in l or "[CRITICAL" in l or "Traceback" in l),
            }

            # Update button labels with counts
            for lvl, (btn, col) in self._level_btns.items():
                cnt = counts.get(lvl, 0)
                btn.setText(f"{lvl} ({cnt})")

            # Filter by Level
            if self._current_level == "CHAT":
                filtered = [l for l in raw_lines if "[CHAT" in l or "[User Query]" in l or "[AuraAI" in l]
            elif self._current_level == "INFO":
                filtered = [l for l in raw_lines if "[INFO" in l]
            elif self._current_level == "DEBUG":
                filtered = [l for l in raw_lines if "[DEBUG" in l]
            elif self._current_level == "WARNING":
                filtered = [l for l in raw_lines if "[WARNING" in l or "[WARN" in l]
            elif self._current_level == "ERROR":
                filtered = [l for l in raw_lines if "[ERROR" in l or "[CRITICAL" in l or "Traceback" in l]
            else:
                filtered = raw_lines

            # Filter by Search Text
            query = self._search_input.text().strip().lower()
            if query:
                filtered = [l for l in filtered if query in l.lower()]

            self._log_count_lbl.setText(f"{len(filtered)} entries shown")

            content = "\n".join(filtered) if filtered else f"No log entries found for filter: {self._current_level}"

            # Only update GUI if content changed to prevent lag
            if getattr(self, "_last_rendered_text", None) != content:
                self._last_rendered_text = content
                self._log_view.setPlainText(content)

                if self._auto_scroll_cb.isChecked():
                    sb = self._log_view.verticalScrollBar()
                    if sb:
                        sb.setValue(sb.maximum())
        except Exception as e:
            logger.debug(f"[LiveLogViewerOverlay] Refresh error: {e}")

    # -------------------------------------------------------------------------
    # Drag & Resize & Persistence
    # -------------------------------------------------------------------------
    def _restore_geometry(self):
        screen = QApplication.primaryScreen().availableGeometry()
        pos = self._settings.value("pos", None)
        size = self._settings.value("size", None)

        auto_w = max(MIN_W, min(int(screen.width() * 0.52), screen.width() - 40))
        auto_h = max(MIN_H, min(int(screen.height() * 0.65), screen.height() - 40))

        if size is not None:
            try:
                w, h = int(size.width()), int(size.height())
            except AttributeError:
                w, h = int(size[0]), int(size[1])
            w = max(MIN_W, min(w, screen.width() - 20))
            h = max(MIN_H, min(h, screen.height() - 20))
            self.resize(w, h)
        else:
            self.resize(auto_w, auto_h)

        if pos is not None:
            try:
                x = int(pos.x()) if hasattr(pos, "x") else int(pos[0])
                y = int(pos.y()) if hasattr(pos, "y") else int(pos[1])
                x = max(screen.left() + 10, min(x, screen.right() - self.width() - 10))
                y = max(screen.top() + 10, min(y, screen.bottom() - self.height() - 10))
                self.move(x, y)
            except Exception:
                self.move(
                    screen.left() + (screen.width() - self.width()) // 2,
                    screen.top() + (screen.height() - self.height()) // 2,
                )
        else:
            self.move(
                screen.left() + (screen.width() - self.width()) // 2,
                screen.top() + (screen.height() - self.height()) // 2,
            )

    def _save_geometry(self):
        self._settings.setValue("pos", self.pos())
        self._settings.setValue("size", self.size())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._in_resize_grip(event.position().toPoint()):
                self._resizing = True
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_size = self.size()
            else:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._resizing and self._resize_start_pos is not None:
            delta = event.globalPosition().toPoint() - self._resize_start_pos
            new_w = max(MIN_W, self._resize_start_size.width() + delta.x())
            new_h = max(MIN_H, self._resize_start_size.height() + delta.y())
            self.resize(new_w, new_h)
            event.accept()
        elif self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        else:
            if self._in_resize_grip(event.position().toPoint()):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._resizing = False
        self._resize_start_pos = None
        self._save_geometry()
        event.accept()

    def _in_resize_grip(self, pos: QPoint) -> bool:
        grip_rect = QRect(
            self.width() - GRIP_SIZE - 8,
            self.height() - GRIP_SIZE - 8,
            GRIP_SIZE,
            GRIP_SIZE,
        )
        return grip_rect.contains(pos)

    def closeEvent(self, event):
        self._save_geometry()
        if hasattr(self, "_refresh_timer") and self._refresh_timer.isActive():
            self._refresh_timer.stop()
        super().closeEvent(event)

    def toggle(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = LiveLogViewerOverlay()
    viewer.show()
    sys.exit(app.exec())
