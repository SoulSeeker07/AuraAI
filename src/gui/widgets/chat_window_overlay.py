"""
ChatWindowOverlay Widget
========================
Ultra-Modern Next-Gen Floating Holographic Chat Window HUD Overlay.
Connected to Genuine Real Backends & Signal Bus:
- Live Multi-Agent Cognitive Orchestrator & Groq LLM Engine
- Real-time conversation stream & recent history from Data/ChatLog.json
- Interactive quick prompt chips (Weather, Diagnostics, Memory Vault, Active Tasks)
- Live Microphone toggle with voice status sync
- Frameless, translucent, draggable, resizable with persistent geometry
"""

import sys
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from PySide6.QtCore import (
    Qt,
    QPoint,
    QRect,
    QRectF,
    QSize,
    QSettings,
    QTimer,
    QDateTime,
    QThread,
    Signal,
)
from PySide6.QtGui import (
    QPainter,
    QColor,
    QFont,
    QPen,
    QBrush,
    QPainterPath,
    QLinearGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
)

from gui.signals import app_signals, ExecutionStep
from gui.real_backend_bridge import RealBackendBridge

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHAT_LOG_PATH = PROJECT_ROOT / "Data" / "ChatLog.json"

REF_W = 1920
REF_H = 1080
MIN_W = 540
MIN_H = 480
GRIP_SIZE = 18

ORG_NAME = "AuraAI"
APP_NAME = "ChatWindowOverlay"


# ─────────────────────────────────────────────────────────────────────────────
# 1. HOLOGRAPHIC CHAT MESSAGE CARD
# ─────────────────────────────────────────────────────────────────────────────


class VoiceTranscribeWorker(QThread):
    """Background worker to transcribe recorded microphone audio."""
    transcription_ready = Signal(str)

    def __init__(self, audio_bytes: bytes, parent=None):
        super().__init__(parent)
        self.audio_bytes = audio_bytes

    def run(self):
        try:
            from tools.voice_recorder import LiveVoiceRecorder
            text = LiveVoiceRecorder.transcribe(self.audio_bytes)
            self.transcription_ready.emit(text)
        except Exception:
            self.transcription_ready.emit("")


class ChatOverlayMessageCard(QFrame):
    """Futuristic message card with chamfered styling, metadata badges, timestamps, and interactive diagram rendering."""

    def __init__(self, sender: str, text: str, intent_tag: str = "EXECUTION", timestamp: str = None, parent=None):
        super().__init__(parent)
        self.sender = sender
        self.is_user = sender.lower() == "user"
        self.intent_tag = intent_tag
        self.timestamp = timestamp or QDateTime.currentDateTime().toString("HH:mm:ss")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._setup_ui(text)

    def _setup_ui(self, text: str):
        self.setStyleSheet("background: transparent; border: none;")
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(0, 2, 0, 2)
        outer_layout.setSpacing(0)

        bubble = QFrame(self)
        if self.is_user:
            bubble.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #142848, stop:1 #1d3964);
                    border: 1px solid rgba(56, 189, 248, 0.45);
                    border-radius: 14px;
                    border-bottom-right-radius: 3px;
                }
            """)
            outer_layout.addStretch(1)
            outer_layout.addWidget(bubble, 0)
        else:
            bubble.setStyleSheet("""
                QFrame {
                    background: #0d1628;
                    border: 1px solid rgba(0, 229, 255, 0.25);
                    border-radius: 14px;
                    border-top-left-radius: 3px;
                }
            """)
            outer_layout.addWidget(bubble, 0)
            outer_layout.addStretch(1)

        layout = QVBoxLayout(bubble)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(8)

        # Header metadata
        head = QHBoxLayout()
        head.setSpacing(8)

        badge_txt = "OPERATOR" if self.is_user else "✦ AURA"
        badge_col = "#7dd3fc" if self.is_user else "#00e5ff"

        tag = QLabel(badge_txt)
        tag.setFont(QFont("Consolas", 8, QFont.Bold))
        tag.setStyleSheet(f"color: {badge_col}; background: transparent; letter-spacing: 0.8px;")
        head.addWidget(tag)

        if not self.is_user and self.intent_tag:
            intent_lbl = QLabel(f"[{self.intent_tag.upper()}]")
            intent_lbl.setFont(QFont("Consolas", 7, QFont.Bold))
            intent_lbl.setStyleSheet("""
                color: #fbbf24;
                background: rgba(251, 191, 36, 0.12);
                border: 1px solid rgba(251, 191, 36, 0.35);
                border-radius: 3px;
                padding: 2px 6px;
            """)
            head.addWidget(intent_lbl)

        head.addStretch()

        # Copy message button
        copy_btn = QPushButton("📋 Copy")
        copy_btn.setFont(QFont("Segoe UI", 7, QFont.Bold))
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 4px;
                color: #94a3b8;
                padding: 1px 6px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.18);
                border-color: #00e5ff;
                color: #ffffff;
            }
        """)
        def _do_copy():
            from PySide6.QtGui import QGuiApplication
            QGuiApplication.clipboard().setText(text)
            copy_btn.setText("✓ Copied!")
            QTimer.singleShot(1800, lambda: copy_btn.setText("📋 Copy"))

        copy_btn.clicked.connect(_do_copy)
        head.addWidget(copy_btn)

        clock_lbl = QLabel(self.timestamp)
        clock_lbl.setFont(QFont("Consolas", 8))
        clock_lbl.setStyleSheet("color: #627289; background: transparent;")
        head.addWidget(clock_lbl)
        layout.addLayout(head)

        # Parse content segments: text, code blocks, and diagrams
        from gui.widgets.message_parser import parse_message_segments, SegmentType
        from gui.widgets.diagram_viewer import DiagramArtifactWidget
        from gui.widgets.code_block_widget import CodeBlockWidget

        segments = parse_message_segments(text)
        for seg in segments:
            if seg.type == SegmentType.DIAGRAM:
                diag = DiagramArtifactWidget(seg.content, title=seg.title or "Aura Architecture Flow", parent=self)
                layout.addWidget(diag)
            elif seg.type == SegmentType.CODE:
                code_widget = CodeBlockWidget(seg.content, language=seg.language, parent=self)
                layout.addWidget(code_widget)
            else:
                body = QLabel()
                body.setWordWrap(True)
                body.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
                body.setFont(QFont("Segoe UI", 9))
                # Basic markdown formatting
                formatted = seg.content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                import re
                formatted = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", formatted)
                formatted = re.sub(r"\*(.+?)\*", r"<i>\1</i>", formatted)
                formatted = re.sub(r"`([^`]+)`", r'<code style="color:#00e5ff; background:rgba(0,229,255,0.1); padding:1px 4px; border-radius:3px; font-family:Consolas;">\1</code>', formatted)
                formatted = re.sub(r"(?m)^###\s+(.+)$", r'<div style="color:#38bdf8; font-weight:bold; font-size:12px; margin-top:6px; margin-bottom:2px;">\1</div>', formatted)
                formatted = re.sub(r"(?m)^##\s+(.+)$", r'<div style="color:#00e5ff; font-weight:bold; font-size:13px; margin-top:8px; margin-bottom:4px;">\1</div>', formatted)
                formatted = re.sub(r"(?m)^[\*\-]\s+(.+)$", r'&nbsp;&nbsp;• \1', formatted)
                formatted = formatted.replace("\n", "<br>")
                body.setText(f'<div style="color: #f1f5f9; line-height: 1.45;">{formatted}</div>')
                body.setStyleSheet("background: transparent;")
                layout.addWidget(body)


class MultilinePromptTextEdit(QPlainTextEdit):
    """
    Auto-expanding multiline prompt text editor for chat input.
    - Shift+Enter inserts newline
    - Enter submits prompt
    - Up/Down cycles prompt history
    """
    submitted = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.returnPressed = self.submitted  # Backward-compatible alias
        self._history: List[str] = []
        self._history_idx = -1
        self._saved_draft = ""
        self.setFixedHeight(36)
        self.setFont(QFont("Segoe UI", 9))
        self.setPlaceholderText("Ask AuraAI anything or enter a system goal...")
        self.setStyleSheet("""
            QPlainTextEdit {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(56, 189, 248, 0.25);
                border-radius: 6px;
                color: #ffffff;
                padding: 6px 10px;
            }
            QPlainTextEdit:focus {
                border: 1px solid #38bdf8;
                background: rgba(56, 189, 248, 0.08);
            }
        """)
        self.textChanged.connect(self._adjust_height)

    def _adjust_height(self):
        doc_height = int(self.document().size().height())
        target_h = max(36, min(doc_height + 12, 110))
        if target_h != self.height():
            self.setFixedHeight(target_h)

    def text(self) -> str:
        return self.toPlainText()

    def setText(self, val: str):
        self.setPlainText(val)

    def append_history(self, text: str):
        if text and (not self._history or self._history[-1] != text):
            self._history.append(text)
        self._history_idx = -1
        self._saved_draft = ""

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.submitted.emit()
                event.accept()
            return

        if event.key() == Qt.Key.Key_Up:
            cursor = self.textCursor()
            if cursor.blockNumber() == 0 and self._history:
                if self._history_idx == -1:
                    self._saved_draft = self.toPlainText()
                    self._history_idx = len(self._history) - 1
                elif self._history_idx > 0:
                    self._history_idx -= 1
                self.setPlainText(self._history[self._history_idx])
                self.moveCursor(self.textCursor().MoveOperation.End)
                event.accept()
                return

        if event.key() == Qt.Key.Key_Down:
            if self._history_idx != -1:
                if self._history_idx < len(self._history) - 1:
                    self._history_idx += 1
                    self.setPlainText(self._history[self._history_idx])
                else:
                    self._history_idx = -1
                    self.setPlainText(self._saved_draft)
                self.moveCursor(self.textCursor().MoveOperation.End)
                event.accept()
                return

        super().keyPressEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
# 2. CHAT WINDOW HUD OVERLAY
# ─────────────────────────────────────────────────────────────────────────────

class ChatWindowOverlay(QWidget):
    """
    Next-Gen Ultra-Modern Futuristic Chat Window HUD Overlay.
    Provides instant holographic access to AuraAI neural dialog anywhere on desktop.
    """

    command_submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ChatWindowOverlay")
        self.setWindowTitle("AuraAI Neural Chat HUD")

        self._settings = QSettings(ORG_NAME, APP_NAME)
        self._always_on_top = self._settings.value("always_on_top", False, type=bool)

        # Frameless window attributes (normal window layering, not always on top)
        self._apply_window_flags()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

        self._bridge = RealBackendBridge.get_instance()

        # Drag & resize state
        self._drag_pos = None
        self._resizing = False
        self._resize_start_pos = None
        self._resize_start_size = None

        self._mic_active = False

        from tools.voice_recorder import LiveVoiceRecorder
        self._recorder = LiveVoiceRecorder()
        self._transcribe_worker = None

        self._setup_ui()
        self._restore_geometry()
        self._connect_signals()
        self._load_initial_history()

    # -------------------------------------------------------------------------
    # UI SETUP
    # -------------------------------------------------------------------------
    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)

        # Outer Solid Frame Container (Opaque: No Terminal Bleed-Through)
        self._card = QFrame()
        self._card.setObjectName("MainChatCard")
        self._card.setStyleSheet("""
            #MainChatCard {
                background: #070b16;
                border: 1.5px solid rgba(56, 189, 248, 0.35);
                border-radius: 16px;
            }
        """)

        layout = QVBoxLayout(self._card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 1. Top Header Bar ──
        header_bar = QFrame()
        header_bar.setStyleSheet("""
            QFrame {
                background: #0b1120;
                border-bottom: 1px solid rgba(56, 189, 248, 0.2);
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
            }
        """)
        header_bar.mousePressEvent = self._header_mouse_press
        header_bar.mouseMoveEvent = self._header_mouse_move
        header_bar.mouseReleaseEvent = self._header_mouse_release
        hb_l = QHBoxLayout(header_bar)
        hb_l.setContentsMargins(18, 12, 18, 12)
        hb_l.setSpacing(12)

        # Live Pulse Dot & Title
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        self._status_dot = QLabel("●")
        self._status_dot.setFont(QFont("Consolas", 10, QFont.Bold))
        self._status_dot.setStyleSheet("color: #10b981; background: transparent;")
        title_row.addWidget(self._status_dot)

        title = QLabel("AURAAI // NEURAL CHAT HUD")
        title.setFont(QFont("Consolas", 10, QFont.Bold))
        title.setStyleSheet("color: #ffffff; letter-spacing: 1px; background: transparent;")
        title_row.addWidget(title)
        title_row.addStretch()
        title_box.addLayout(title_row)

        sub = QLabel("COGNITIVE REASONING • GROQ GPT-OSS 120B • MULTI-AGENT")
        sub.setFont(QFont("Consolas", 7))
        sub.setStyleSheet("color: #7dd3fc; letter-spacing: 0.5px; background: transparent;")
        title_box.addWidget(sub)
        hb_l.addLayout(title_box)

        hb_l.addStretch()

        # Engine Badge
        engine_badge = QLabel("⚡ Groq / GPT-OSS 120B")
        engine_badge.setFont(QFont("Consolas", 8, QFont.Bold))
        engine_badge.setStyleSheet("""
            color: #38bdf8;
            background: rgba(56, 189, 248, 0.12);
            border: 1px solid rgba(56, 189, 248, 0.3);
            border-radius: 8px;
            padding: 4px 8px;
        """)
        hb_l.addWidget(engine_badge)

        # Left Rail (History) Toggle Action
        self._toggle_hist_btn = QPushButton("◨ History")
        self._toggle_hist_btn.setFont(QFont("Consolas", 8))
        self._toggle_hist_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_hist_btn.setToolTip("Toggle Conversation History Rail")
        self._toggle_hist_btn.clicked.connect(self._toggle_history_rail)
        hb_l.addWidget(self._toggle_hist_btn)

        # Right Rail (Telemetry) Toggle Action
        self._toggle_ops_btn = QPushButton("◧ Telemetry")
        self._toggle_ops_btn.setFont(QFont("Consolas", 8))
        self._toggle_ops_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_ops_btn.setToolTip("Toggle Operations & Telemetry Rail")
        self._toggle_ops_btn.clicked.connect(self._toggle_ops_rail)
        hb_l.addWidget(self._toggle_ops_btn)

        # Pin / Always on Top Action
        self._pin_btn = QPushButton("📌 Pin")
        self._pin_btn.setFont(QFont("Consolas", 8))
        self._pin_btn.setCursor(Qt.PointingHandCursor)
        self._pin_btn.setToolTip("Toggle Always on Top (Default: Off)")
        self._update_pin_style()
        self._pin_btn.clicked.connect(self._toggle_pin)
        hb_l.addWidget(self._pin_btn)

        # Clear Action
        clear_btn = QPushButton("🗑 Clear")
        clear_btn.setFont(QFont("Consolas", 8))
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 6px;
                color: #94a3b8;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background: rgba(244, 63, 94, 0.15);
                border: 1px solid #f43f5e;
                color: #ff4d6d;
            }
        """)
        clear_btn.clicked.connect(self._clear_messages)
        hb_l.addWidget(clear_btn)

        # Close Action
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 13px;
                color: #94a3b8;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #f43f5e;
                border-color: #f43f5e;
                color: #ffffff;
            }
        """)
        close_btn.clicked.connect(self.hide)
        hb_l.addWidget(close_btn)

        layout.addWidget(header_bar)

        # ── 2. Quick Prompt Chips (Contained Scroll Area, No Overflow) ──
        chips_scroll = QScrollArea()
        chips_scroll.setFixedHeight(44)
        chips_scroll.setWidgetResizable(True)
        chips_scroll.setFrameShape(QFrame.Shape.NoFrame)
        chips_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        chips_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        chips_scroll.setStyleSheet("background: #0b1222; border-bottom: 1px solid rgba(56, 189, 248, 0.12); border-top-left-radius: 12px; border-top-right-radius: 12px;")

        chips_bar = QWidget()
        chips_bar.setStyleSheet("background: transparent;")
        chips_layout = QHBoxLayout(chips_bar)
        chips_layout.setContentsMargins(12, 6, 12, 6)
        chips_layout.setSpacing(6)

        prompts = [
            ("🌤️ Weather", "what is the current weather?"),
            ("⚡ Diagnostics", "run full system diagnostics"),
            ("🧠 Memory", "inspect active working memory"),
            ("📋 Tasks", "list active agent tasks"),
            ("🔍 Workspace", "scan workspace and inspect files"),
        ]
        for label, cmd in prompts:
            btn = QPushButton(label)
            btn.setFont(QFont("Consolas", 8))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(30, 41, 59, 0.7);
                    border: 1px solid rgba(56, 189, 248, 0.25);
                    border-radius: 8px;
                    color: #cbd5e1;
                    padding: 3px 8px;
                }
                QPushButton:hover {
                    background: rgba(56, 189, 248, 0.2);
                    border: 1px solid #38bdf8;
                    color: #ffffff;
                }
            """)
            btn.clicked.connect(lambda checked, c=cmd: self._send_quick_command(c))
            chips_layout.addWidget(btn)
        chips_layout.addStretch()
        chips_scroll.setWidget(chips_bar)

        # ── 3. Scrollable Message Feed ──
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setStyleSheet("background: transparent; border: none;")

        self._messages_container = QWidget()
        self._messages_container.setStyleSheet("background: transparent;")
        self._messages_layout = QVBoxLayout(self._messages_container)
        self._messages_layout.setContentsMargins(16, 12, 16, 12)
        self._messages_layout.setSpacing(10)
        self._messages_layout.addStretch()

        self._scroll_area.setWidget(self._messages_container)

        # ── 4. Bottom Input Bar ──
        input_bar = QFrame()
        input_bar.setStyleSheet("""
            QFrame {
                background: #0b1222;
                border-top: 1px solid rgba(56, 189, 248, 0.16);
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
            }
        """)
        ib_l = QHBoxLayout(input_bar)
        ib_l.setContentsMargins(16, 10, 16, 10)
        ib_l.setSpacing(10)

        # Live Mic Toggle
        self._mic_btn = QPushButton("🎙️")
        self._mic_btn.setCheckable(True)
        self._mic_btn.setFixedSize(36, 36)
        self._mic_btn.setCursor(Qt.PointingHandCursor)
        self._mic_btn.setToolTip("Toggle Live Voice Input")
        self._update_mic_style(False)
        self._mic_btn.clicked.connect(self._on_mic_toggle)
        ib_l.addWidget(self._mic_btn, 0, Qt.AlignmentFlag.AlignBottom)

        # Multiline Text input (Shift+Enter for newline, Enter to submit, Up/Down for history)
        self._input_field = MultilinePromptTextEdit()
        self._input_field.submitted.connect(self._on_submit)
        ib_l.addWidget(self._input_field, 1)

        # Send Button
        send_btn = QPushButton("SEND ➤")
        send_btn.setFont(QFont("Consolas", 8, QFont.Bold))
        send_btn.setFixedSize(80, 36)
        send_btn.setCursor(Qt.PointingHandCursor)
        send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00b4d8, stop:1 #00e5ff);
                border: none;
                border-radius: 8px;
                color: #04101e;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0096c7, stop:1 #00c8e6);
            }
        """)
        send_btn.clicked.connect(self._on_submit)
        ib_l.addWidget(send_btn, 0, Qt.AlignmentFlag.AlignBottom)

        # ── 5. Three-Pane Body Container (Distinct Card Modular Layout) ──
        body_container = QWidget()
        body_container.setStyleSheet("background: transparent;")
        body_l = QHBoxLayout(body_container)
        body_l.setContentsMargins(10, 8, 10, 10)
        body_l.setSpacing(10)

        # 5a. Left Rail: History Sidebar (Modular Card)
        from gui.widgets.chat_history_sidebar import ChatHistorySidebar
        self._history_sidebar = ChatHistorySidebar(self)
        self._history_sidebar.new_chat_requested.connect(self._start_new_chat)
        self._history_sidebar.history_item_selected.connect(self._on_history_item_selected)
        body_l.addWidget(self._history_sidebar)

        # 5b. Center Chat Pane (Modular Rounded Card Container)
        center_pane = QFrame()
        center_pane.setObjectName("CenterChatPane")
        center_pane.setStyleSheet("""
            #CenterChatPane {
                background: #080d19;
                border: 1px solid rgba(56, 189, 248, 0.16);
                border-radius: 12px;
            }
        """)
        cp_l = QVBoxLayout(center_pane)
        cp_l.setContentsMargins(0, 0, 0, 0)
        cp_l.setSpacing(0)
        cp_l.addWidget(chips_scroll)
        cp_l.addWidget(self._scroll_area, 1)
        cp_l.addWidget(input_bar)
        body_l.addWidget(center_pane, 1)

        # 5c. Right Rail: Operations & Telemetry (Modular Card)
        from gui.widgets.chat_right_rail import ChatRightRail
        self._right_rail = ChatRightRail(self)
        body_l.addWidget(self._right_rail)

        layout.addWidget(body_container, 1)
        root_layout.addWidget(self._card)

        # ── 6. Integrated Hardware Size Grip ──
        from PySide6.QtWidgets import QSizeGrip
        self._size_grip = QSizeGrip(self)
        self._size_grip.setFixedSize(22, 22)
        self._size_grip.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self._size_grip.setStyleSheet("""
            QSizeGrip {
                background: transparent;
                width: 22px;
                height: 22px;
            }
        """)

    # -------------------------------------------------------------------------
    # SIGNALS & BACKEND INTEGRATION
    # -------------------------------------------------------------------------
    def _connect_signals(self):
        app_signals.message_received.connect(self._on_message_received)
        app_signals.voice_status_changed.connect(self._on_voice_status_changed)
        app_signals.execution_started.connect(self._on_execution_started)
        app_signals.execution_finished.connect(self._on_execution_finished)
        app_signals.step_updated.connect(self._on_step_updated)

    def _load_initial_history(self):
        # Defer loading recent history slightly so the window paints instantly (<400ms)
        def _do_load():
            loaded = False
            if CHAT_LOG_PATH.exists():
                try:
                    with open(CHAT_LOG_PATH, "r", encoding="utf-8") as f:
                        chat_data = json.load(f)
                    if isinstance(chat_data, list) and chat_data:
                        for entry in chat_data[-6:]:
                            role = entry.get("role", "user")
                            content = entry.get("content", "")
                            if content.strip():
                                sender = "user" if role == "user" else "agent"
                                intent = "HISTORY"
                                self._append_card(sender, content, intent_tag=intent)
                        loaded = True
                except Exception as e:
                    logger.debug(f"[ChatWindowOverlay] Error loading ChatLog: {e}")

            if not loaded and self._messages_layout.count() <= 1:
                self._append_card(
                    "agent",
                    "✦ AuraAI Holographic Chat HUD online. Ready for multi-agent reasoning, desktop automation, and queries.",
                    intent_tag="INITIALIZE",
                )

        QTimer.singleShot(50, _do_load)

    MAX_CARDS: int = 100

    def _append_card(self, sender: str, text: str, intent_tag: str = "REASONING"):
        card = ChatOverlayMessageCard(sender, text, intent_tag=intent_tag)
        count = self._messages_layout.count()
        self._messages_layout.insertWidget(max(0, count - 1), card)

        # FIFO Prune to enforce bounded memory / prevent unconstrained widget growth
        while self._messages_layout.count() > (self.MAX_CARDS + 1):
            item = self._messages_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # Persist conversation turn if it is a live user/agent turn
        if intent_tag not in ("HISTORY", "INITIALIZE", "STANDBY"):
            try:
                from datetime import datetime
                role = "user" if sender == "user" else "assistant"
                entry = {
                    "role": role,
                    "content": text,
                    "topic": intent_tag.lower(),
                    "timestamp": datetime.now().isoformat(),
                }
                chat_data = []
                if CHAT_LOG_PATH.exists():
                    try:
                        with open(CHAT_LOG_PATH, "r", encoding="utf-8") as f:
                            chat_data = json.load(f)
                    except Exception:
                        chat_data = []
                chat_data.append(entry)
                # Keep last 50 entries
                chat_data = chat_data[-50:]
                with open(CHAT_LOG_PATH, "w", encoding="utf-8") as f:
                    json.dump(chat_data, f, indent=2)
            except Exception as pe:
                logger.debug(f"[ChatWindowOverlay] Error saving turn to ChatLog: {pe}")

        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        for delay in (40, 150, 450, 1200):
            QTimer.singleShot(
                delay,
                lambda: self._scroll_area.verticalScrollBar().setValue(
                    self._scroll_area.verticalScrollBar().maximum()
                ),
            )

    def _clear_messages(self):
        while self._messages_layout.count() > 1:
            item = self._messages_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # Persistently wipe the stored chat history file
        try:
            if CHAT_LOG_PATH.exists():
                with open(CHAT_LOG_PATH, "w", encoding="utf-8") as f:
                    json.dump([], f, indent=2)
                logger.info("[ChatWindowOverlay] Persistent ChatLog.json reset successfully.")
        except Exception as e:
            logger.warning(f"[ChatWindowOverlay] Failed to clear ChatLog.json: {e}")

        # Also reset AuraCore conversation history if initialized
        try:
            from core.aura_core import AuraCore
            if AuraCore._instance and hasattr(AuraCore._instance, "conversation_history"):
                AuraCore._instance.conversation_history.clear()
        except Exception:
            pass

        self._append_card(
            "agent",
            "Chat feed cleared. Standing by for instructions.",
            intent_tag="STANDBY",
        )

    def _start_new_chat(self):
        """Clear the visual chat buffer to begin a fresh neural turn without deleting ChatLog.json."""
        while self._messages_layout.count() > 1:
            item = self._messages_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._append_card(
            "agent",
            "✦ New neural session initiated. Ready for instructions, system diagnostics, and multi-agent workflows.",
            intent_tag="INITIALIZE",
        )

    def _on_history_item_selected(self, prompt: str, response: str):
        """Populate the message feed with a past conversation session."""
        while self._messages_layout.count() > 1:
            item = self._messages_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._append_card("user", prompt, intent_tag="HISTORY")
        if response:
            self._append_card("agent", response, intent_tag="HISTORY")

    def _send_quick_command(self, cmd: str):
        self._input_field.setText(cmd)
        self._on_submit()

    def _on_submit(self):
        # If user pressed enter or submitted while mic was active, stop & transcribe first
        if self._mic_active:
            self._on_mic_toggle()
            return

        text = self._input_field.text().strip()
        if not text:
            return

        self._input_field.append_history(text)
        self._append_card("user", text)
        self._input_field.clear()
        self.command_submitted.emit(text)
        app_signals.message_received.emit("user", text, True)

        if hasattr(self, "_history_sidebar"):
            QTimer.singleShot(400, self._history_sidebar.reload_history)

    def _on_message_received(self, sender: str, content: str, is_user: bool):
        if not is_user:
            self._append_card("agent", content, intent_tag="REASONING")
            self._status_dot.setText("●")
            self._status_dot.setStyleSheet("color: #10b981; background: transparent;")

    def _on_execution_started(self, task_id: str):
        self._status_dot.setText("◐")
        self._status_dot.setStyleSheet("color: #fbbf24; background: transparent;")

    def _on_execution_finished(self, task_id: str, success: bool):
        self._status_dot.setText("●")
        col = "#10b981" if success else "#ef4444"
        self._status_dot.setStyleSheet(f"color: {col}; background: transparent;")

    def _on_step_updated(self, step: ExecutionStep):
        if step and step.description:
            status_str = step.status.name if hasattr(step.status, "name") else str(step.status)
            if status_str == "RUNNING":
                self._status_dot.setText("◐")
                self._status_dot.setStyleSheet("color: #fbbf24; background: transparent;")
            elif status_str in ("COMPLETED", "FINISHED"):
                self._status_dot.setText("●")
                self._status_dot.setStyleSheet("color: #10b981; background: transparent;")
            elif status_str in ("FAILED", "ERROR"):
                self._status_dot.setText("●")
                self._status_dot.setStyleSheet("color: #f43f5e; background: transparent;")

    def _update_mic_style(self, active: bool):
        if active:
            self._mic_btn.setText("🔴")
            self._mic_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(244, 63, 94, 0.35);
                    border: 1.5px solid #f43f5e;
                    border-radius: 6px;
                    color: #ff4d6d;
                    font-size: 14px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: rgba(244, 63, 94, 0.55);
                }
            """)
        else:
            self._mic_btn.setText("🎙️")
            self._mic_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(56, 189, 248, 0.25);
                    border-radius: 6px;
                    color: #94a3b8;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background: rgba(56, 189, 248, 0.15);
                    border: 1px solid #38bdf8;
                    color: #38bdf8;
                }
            """)

    def _on_mic_toggle(self):
        self._mic_active = not self._mic_active
        self._mic_btn.setChecked(self._mic_active)
        self._update_mic_style(self._mic_active)
        app_signals.voice_status_changed.emit(self._mic_active)

        if self._mic_active:
            # 1. Started Listening
            self._recorder.start_recording()
            self._input_field.setPlaceholderText("🔴 RECORDING... Speak now (Click mic or press Enter to submit)")
        else:
            # 2. Stopped Listening -> Transcribe & Submit
            self._input_field.setPlaceholderText("⏳ Transcribing speech via Groq Whisper...")
            audio_bytes = self._recorder.stop_recording()
            if audio_bytes and len(audio_bytes) > 3000:
                self._transcribe_worker = VoiceTranscribeWorker(audio_bytes, self)
                self._transcribe_worker.transcription_ready.connect(self._on_transcription_ready)
                self._transcribe_worker.start()
            else:
                self._input_field.setPlaceholderText("⚠️ No audio detected. Click mic to try again...")
                QTimer.singleShot(2200, lambda: self._input_field.setPlaceholderText(
                    "Enter command or query (e.g. 'what is the weather?', 'inspect memory')..."
                ))

    def _on_transcription_ready(self, text: str):
        self._input_field.setPlaceholderText("Enter command or query (e.g. 'what is the weather?', 'inspect memory')...")
        if text.strip():
            # Append user card and emit as voice event to trigger spoken TTS reply
            self._append_card("user", text.strip())
            self.command_submitted.emit(text.strip())
            app_signals.message_received.emit("voice", text.strip(), True)
        else:
            self._input_field.setPlaceholderText("⚠️ No speech recognized. Speak closer to the microphone.")
            QTimer.singleShot(2500, lambda: self._input_field.setPlaceholderText(
                "Enter command or query (e.g. 'what is the weather?', 'inspect memory')..."
            ))

    def _on_voice_status_changed(self, active: bool):
        self._mic_active = active
        self._mic_btn.blockSignals(True)
        self._mic_btn.setChecked(active)
        self._mic_btn.blockSignals(False)
        self._update_mic_style(active)

    def _apply_window_flags(self):
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        if self._always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    def toggle(self):
        """Toggle visibility, focus, and state of the Chat Window HUD."""
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.showNormal()
            self.setWindowState(
                (self.windowState() & ~Qt.WindowState.WindowMinimized)
                | Qt.WindowState.WindowActive
            )
            self.raise_()
            self.activateWindow()
            if hasattr(self, "_input_field"):
                self._input_field.setFocus()

    def _toggle_pin(self):
        self._always_on_top = not self._always_on_top
        self._settings.setValue("always_on_top", self._always_on_top)
        self._update_pin_style()
        self._apply_window_flags()
        self.show()

    def _toggle_history_rail(self):
        if not hasattr(self, "_history_sidebar"):
            return
        visible = not self._history_sidebar.isVisible()
        self._history_sidebar.setVisible(visible)
        self._settings.setValue("left_rail_visible", visible)
        self._update_rail_button_styles()

    def _toggle_ops_rail(self):
        if not hasattr(self, "_right_rail"):
            return
        visible = not self._right_rail.isVisible()
        self._right_rail.setVisible(visible)
        self._settings.setValue("right_rail_visible", visible)
        self._update_rail_button_styles()

    def _update_rail_button_styles(self):
        hist_active = hasattr(self, "_history_sidebar") and self._history_sidebar.isVisible()
        ops_active = hasattr(self, "_right_rail") and self._right_rail.isVisible()

        if hasattr(self, "_toggle_hist_btn"):
            if hist_active:
                self._toggle_hist_btn.setStyleSheet("""
                    QPushButton {
                        background: rgba(56, 189, 248, 0.22);
                        border: 1px solid #38bdf8;
                        border-radius: 6px;
                        color: #38bdf8;
                        font-weight: bold;
                        padding: 4px 8px;
                    }
                    QPushButton:hover {
                        background: rgba(56, 189, 248, 0.35);
                    }
                """)
            else:
                self._toggle_hist_btn.setStyleSheet("""
                    QPushButton {
                        background: rgba(255, 255, 255, 0.05);
                        border: 1px solid rgba(255, 255, 255, 0.12);
                        border-radius: 6px;
                        color: #94a3b8;
                        padding: 4px 8px;
                    }
                    QPushButton:hover {
                        background: rgba(56, 189, 248, 0.15);
                        border: 1px solid #38bdf8;
                        color: #38bdf8;
                    }
                """)

        if hasattr(self, "_toggle_ops_btn"):
            if ops_active:
                self._toggle_ops_btn.setStyleSheet("""
                    QPushButton {
                        background: rgba(56, 189, 248, 0.22);
                        border: 1px solid #38bdf8;
                        border-radius: 6px;
                        color: #38bdf8;
                        font-weight: bold;
                        padding: 4px 8px;
                    }
                    QPushButton:hover {
                        background: rgba(56, 189, 248, 0.35);
                    }
                """)
            else:
                self._toggle_ops_btn.setStyleSheet("""
                    QPushButton {
                        background: rgba(255, 255, 255, 0.05);
                        border: 1px solid rgba(255, 255, 255, 0.12);
                        border-radius: 6px;
                        color: #94a3b8;
                        padding: 4px 8px;
                    }
                    QPushButton:hover {
                        background: rgba(56, 189, 248, 0.15);
                        border: 1px solid #38bdf8;
                        color: #38bdf8;
                    }
                """)

    def _update_pin_style(self):
        if not hasattr(self, "_pin_btn"):
            return
        if self._always_on_top:
            self._pin_btn.setText("📌 Pinned")
            self._pin_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(56, 189, 248, 0.2);
                    border: 1px solid #38bdf8;
                    border-radius: 6px;
                    color: #38bdf8;
                    font-weight: bold;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background: rgba(56, 189, 248, 0.35);
                }
            """)
        else:
            self._pin_btn.setText("📌 Pin")
            self._pin_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(255, 255, 255, 0.12);
                    border-radius: 6px;
                    color: #94a3b8;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background: rgba(56, 189, 248, 0.15);
                    border: 1px solid #38bdf8;
                    color: #38bdf8;
                }
            """)

    # -------------------------------------------------------------------------
    # GEOMETRY RESTORATION
    # -------------------------------------------------------------------------
    def _restore_geometry(self):
        screen = QApplication.primaryScreen().availableGeometry()
        pos = self._settings.value("pos", None)
        size = self._settings.value("size", None)

        # Restore Rail States
        left_visible = self._settings.value("left_rail_visible", True, type=bool)
        right_visible = self._settings.value("right_rail_visible", True, type=bool)
        if hasattr(self, "_history_sidebar"):
            self._history_sidebar.setVisible(left_visible)
        if hasattr(self, "_right_rail"):
            self._right_rail.setVisible(right_visible)
        self._update_rail_button_styles()

        target_w = max(MIN_W, min(int(screen.width() * 0.65), 1180))
        target_h = max(MIN_H, min(int(screen.height() * 0.72), 780))

        if size is not None:
            try:
                w, h = int(size.width()), int(size.height())
            except (AttributeError, TypeError, ValueError):
                try:
                    w, h = int(size[0]), int(size[1])
                except Exception:
                    w, h = target_w, target_h
            w = max(MIN_W, min(w, screen.width() - 40))
            h = max(MIN_H, min(h, screen.height() - 40))
            self.resize(w, h)
        else:
            self.resize(target_w, target_h)

        if pos is not None:
            try:
                x = int(pos.x()) if hasattr(pos, "x") else int(pos[0])
                y = int(pos.y()) if hasattr(pos, "y") else int(pos[1])
                # Ensure clamped to visible screen boundaries so it can never be offscreen or -32000
                x = max(screen.left() + 10, min(x, screen.right() - self.width() - 10))
                y = max(screen.top() + 10, min(y, screen.bottom() - self.height() - 10))
                self.move(x, y)
            except Exception:
                self.move(
                    screen.left() + int(screen.width() * 0.58),
                    screen.top() + int(screen.height() * 0.18),
                )
        else:
            self.move(
                screen.left() + int(screen.width() * 0.58),
                screen.top() + int(screen.height() * 0.18),
            )

    def _save_geometry(self):
        if not self.isMinimized() and self.isVisible():
            screen = QApplication.primaryScreen().availableGeometry()
            p = self.pos()
            if (
                p.x() >= screen.left() - 50
                and p.x() <= screen.right()
                and p.y() >= screen.top() - 50
                and p.y() <= screen.bottom()
            ):
                self._settings.setValue("pos", p)
                self._settings.setValue("size", self.size())

    # -------------------------------------------------------------------------
    # DRAG & RESIZE HANDLING
    # -------------------------------------------------------------------------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_size_grip") and self._size_grip is not None:
            self._size_grip.move(self.width() - 24, self.height() - 24)
            self._size_grip.raise_()

    def _header_mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()

    def _header_mouse_move(self, event):
        if self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _header_mouse_release(self, event):
        self._drag_pos = None
        self._save_geometry()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._in_resize_grip(event.position().toPoint()):
                self._resizing = True
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_size = self.size()
            else:
                self._drag_pos = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
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
            self.width() - GRIP_SIZE - 12,
            self.height() - GRIP_SIZE - 12,
            GRIP_SIZE + 12,
            GRIP_SIZE + 12,
        )
        return grip_rect.contains(pos)

    def closeEvent(self, event):
        self._save_geometry()
        super().closeEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()

        # Dotted Resize Grip Hint (bottom-right)
        p.setPen(QPen(QColor(56, 189, 248, 160), 1))
        for i in range(3):
            for j in range(i, 3):
                dx = w - 12 - j * 4
                dy = h - 12 - i * 4
                p.drawPoint(dx, dy)

        p.end()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    overlay = ChatWindowOverlay()
    overlay.show()
    sys.exit(app.exec())
