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
MIN_W = 520
MIN_H = 460
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
    """Futuristic message card with chamfered styling, metadata badges and timestamps."""

    def __init__(self, sender: str, text: str, intent_tag: str = "EXECUTION", timestamp: str = None, parent=None):
        super().__init__(parent)
        self.sender = sender
        self.is_user = sender.lower() == "user"
        self.intent_tag = intent_tag
        self.timestamp = timestamp or QDateTime.currentDateTime().toString("HH:mm:ss")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._setup_ui(text)

    def _setup_ui(self, text: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(6)

        if self.is_user:
            self.setStyleSheet("""
                ChatOverlayMessageCard {
                    background: rgba(30, 58, 110, 0.45);
                    border: 1px solid rgba(80, 170, 255, 0.35);
                    border-radius: 10px;
                }
            """)
        else:
            self.setStyleSheet("""
                ChatOverlayMessageCard {
                    background: rgba(12, 22, 36, 0.75);
                    border: 1px solid rgba(0, 229, 255, 0.25);
                    border-radius: 10px;
                }
            """)

        # Header metadata
        head = QHBoxLayout()
        head.setSpacing(8)

        badge_txt = "OPERATOR // USER" if self.is_user else "AURA // NEURAL COGNITION"
        badge_col = "#60a5fa" if self.is_user else "#00e5ff"

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
                padding: 1px 5px;
            """)
            head.addWidget(intent_lbl)

        head.addStretch()

        clock_lbl = QLabel(self.timestamp)
        clock_lbl.setFont(QFont("Consolas", 8))
        clock_lbl.setStyleSheet("color: #627289; background: transparent;")
        head.addWidget(clock_lbl)
        layout.addLayout(head)

        # Message Text
        body = QLabel(text)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        body.setFont(QFont("Segoe UI", 9))
        body.setStyleSheet("color: #f1f5f9; background: transparent; line-height: 1.4;")
        layout.addWidget(body)


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

        # Outer Glass Container
        self._card = QFrame()
        self._card.setObjectName("MainChatCard")
        self._card.setStyleSheet("""
            #MainChatCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(10, 14, 24, 0.96), stop:1 rgba(18, 24, 38, 0.97));
                border: 1px solid rgba(56, 189, 248, 0.35);
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
                background: rgba(10, 14, 24, 0.85);
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
            padding: 3px 8px;
        """)
        hb_l.addWidget(engine_badge)

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

        # ── 2. Quick Prompt Chips ──
        chips_bar = QFrame()
        chips_bar.setStyleSheet("background: rgba(10, 14, 24, 0.5); border-bottom: 1px solid rgba(255, 255, 255, 0.04);")
        chips_layout = QHBoxLayout(chips_bar)
        chips_layout.setContentsMargins(16, 8, 16, 8)
        chips_layout.setSpacing(8)

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
                    border-radius: 10px;
                    color: #cbd5e1;
                    padding: 4px 10px;
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
        layout.addWidget(chips_bar)

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
        layout.addWidget(self._scroll_area, 1)

        # ── 4. Bottom Input Bar ──
        input_bar = QFrame()
        input_bar.setStyleSheet("""
            QFrame {
                background: rgba(10, 14, 24, 0.85);
                border-top: 1px solid rgba(56, 189, 248, 0.2);
                border-bottom-left-radius: 16px;
                border-bottom-right-radius: 16px;
            }
        """)
        ib_l = QHBoxLayout(input_bar)
        ib_l.setContentsMargins(16, 12, 16, 12)
        ib_l.setSpacing(10)

        # Live Mic Toggle
        self._mic_btn = QPushButton("🎙️")
        self._mic_btn.setCheckable(True)
        self._mic_btn.setFixedSize(36, 34)
        self._mic_btn.setCursor(Qt.PointingHandCursor)
        self._mic_btn.setToolTip("Toggle Live Voice Input")
        self._update_mic_style(False)
        self._mic_btn.clicked.connect(self._on_mic_toggle)
        ib_l.addWidget(self._mic_btn)

        # Text input
        self._input_field = QLineEdit()
        self._input_field.setPlaceholderText("Ask AuraAI anything or enter a system goal...")
        self._input_field.setFont(QFont("Segoe UI", 9))
        self._input_field.setStyleSheet("""
            QLineEdit {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(56, 189, 248, 0.25);
                border-radius: 6px;
                color: #ffffff;
                padding: 6px 10px;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
                background: rgba(56, 189, 248, 0.08);
            }
            QLineEdit::placeholder {
                color: #64748b;
            }
        """)
        self._input_field.returnPressed.connect(self._on_submit)
        ib_l.addWidget(self._input_field, 1)

        # Send Button
        send_btn = QPushButton("SEND ➤")
        send_btn.setFont(QFont("Consolas", 8, QFont.Bold))
        send_btn.setFixedSize(80, 34)
        send_btn.setCursor(Qt.PointingHandCursor)
        send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #06b6d4);
                border: none;
                border-radius: 6px;
                color: #ffffff;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369a1, stop:1 #0891b2);
            }
        """)
        send_btn.clicked.connect(self._on_submit)
        ib_l.addWidget(send_btn)

        layout.addWidget(input_bar)
        root_layout.addWidget(self._card)

        # ── 5. Integrated Hardware Size Grip ──
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
        app_signals.toggle_chat_overlay.connect(self.toggle)

    def _load_initial_history(self):
        # Auto-load recent history from ChatLog.json if available
        loaded = False
        if CHAT_LOG_PATH.exists():
            try:
                with open(CHAT_LOG_PATH, "r", encoding="utf-8") as f:
                    chat_data = json.load(f)
                if isinstance(chat_data, list) and chat_data:
                    for entry in chat_data[-8:]:
                        role = entry.get("role", "user")
                        content = entry.get("content", "")
                        if content.strip():
                            sender = "user" if role == "user" else "agent"
                            intent = "HISTORY"
                            self._append_card(sender, content, intent_tag=intent)
                    loaded = True
            except Exception as e:
                logger.debug(f"[ChatWindowOverlay] Error loading ChatLog: {e}")

        if not loaded:
            self._append_card(
                "agent",
                "✦ AuraAI Holographic Chat HUD online. Ready for multi-agent reasoning, desktop automation, and queries.",
                intent_tag="INITIALIZE",
            )

    def _append_card(self, sender: str, text: str, intent_tag: str = "REASONING"):
        card = ChatOverlayMessageCard(sender, text, intent_tag=intent_tag)
        count = self._messages_layout.count()
        self._messages_layout.insertWidget(max(0, count - 1), card)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        QTimer.singleShot(
            40,
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
        self._append_card(
            "agent",
            "Chat feed cleared. Standing by for instructions.",
            intent_tag="STANDBY",
        )

    def _send_quick_command(self, cmd: str):
        self._input_field.setText(cmd)
        self._on_submit()

    def _on_submit(self):
        text = self._input_field.text().strip()
        if not text:
            return

        self._append_card("user", text)
        self._input_field.clear()
        self.command_submitted.emit(text)
        app_signals.message_received.emit("user", text, True)

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
        if step.description and step.status.name == "RUNNING":
            pass

    def _update_mic_style(self, active: bool):
        if active:
            self._mic_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(244, 63, 94, 0.25);
                    border: 1.5px solid #f43f5e;
                    border-radius: 6px;
                    color: #ff4d6d;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background: rgba(244, 63, 94, 0.4);
                }
            """)
        else:
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
            self._input_field.setPlaceholderText("🎙️ Listening... (Speak now, click mic to stop & send)")
        else:
            # 2. Stopped Listening -> Transcribe & Submit
            self._input_field.setPlaceholderText("⏳ Transcribing speech...")
            audio_bytes = self._recorder.stop_recording()
            if audio_bytes and len(audio_bytes) > 4000:
                self._transcribe_worker = VoiceTranscribeWorker(audio_bytes, self)
                self._transcribe_worker.transcription_ready.connect(self._on_transcription_ready)
                self._transcribe_worker.start()
            else:
                self._input_field.setPlaceholderText("Enter command or query (e.g. 'what is the weather?', 'inspect memory')...")

    def _on_transcription_ready(self, text: str):
        self._input_field.setPlaceholderText("Enter command or query (e.g. 'what is the weather?', 'inspect memory')...")
        if text.strip():
            self._input_field.setText(text.strip())
            self._on_submit()

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
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
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

        target_w = max(MIN_W, min(int(screen.width() * 0.38), 640))
        target_h = max(MIN_H, min(int(screen.height() * 0.65), 720))

        if size is not None:
            try:
                w, h = int(size.width()), int(size.height())
                self.resize(max(MIN_W, w), max(MIN_H, h))
            except Exception:
                self.resize(target_w, target_h)
        else:
            self.resize(target_w, target_h)

        if pos is not None:
            try:
                self.move(pos)
            except Exception:
                self.move(
                    screen.left() + (screen.width() - self.width()) // 2,
                    screen.top() + (screen.height() - self.height()) // 2,
                )
        else:
            self.move(
                screen.left() + int(screen.width() * 0.58),
                screen.top() + int(screen.height() * 0.18),
            )

    def _save_geometry(self):
        self._settings.setValue("pos", self.pos())
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
