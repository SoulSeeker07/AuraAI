"""
Overlay Window (Spotlight HUD)
==============================
Frameless glassmorphism command bar triggered by Alt+Space.
"""

from PySide6.QtCore import QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.signals import app_signals
from gui.theme import Animations, Colors, Radius, overlay_stylesheet
from gui.widgets import StatusPill, StepListWidget, VoiceWaveform


class OverlayWindow(QWidget):
    """
    Floating Spotlight HUD for ultra-fast desktop automation.
    Shortcut: Alt+Space toggle.
    """

    command_submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("OverlayWindow")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._setup_ui()
        self._setup_shortcuts()
        self._setup_shadow()
        self._connect_signals()

        self.setStyleSheet(overlay_stylesheet())
        self.resize(640, 400)
        self.hide()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # ── Top Status Bar ──
        status_layout = QHBoxLayout()
        status_layout.setSpacing(8)

        self._voice_pill = StatusPill("🎙️", "Voice", active=False, animate=True)
        self._screen_pill = StatusPill("👁️", "Screen", active=False, animate=False)
        self._engine_pill = StatusPill("⚡", "Groq", active=True, animate=False)

        status_layout.addWidget(self._voice_pill)
        status_layout.addWidget(self._screen_pill)
        status_layout.addWidget(self._engine_pill)
        status_layout.addStretch()

        # Close button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: {Radius.SM};
                color: {Colors.TEXT_MUTED};
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: {Colors.BG_CARD};
                color: {Colors.TEXT_PRIMARY};
            }}
        """)
        close_btn.clicked.connect(self.hide)
        status_layout.addWidget(close_btn)

        layout.addLayout(status_layout)

        # ── Omni Input ──
        self._input = QLineEdit()
        self._input.setObjectName("OmniInput")
        self._input.setPlaceholderText("Ask Aura anything or type a command...")
        self._input.returnPressed.connect(self._on_submit)
        layout.addWidget(self._input)

        # ── Action Tools Bar ──
        tools_layout = QHBoxLayout()
        tools_layout.setSpacing(8)

        self._voice_toggle = QPushButton("🎙️ Voice")
        self._voice_toggle.setCheckable(True)
        self._voice_toggle.setStyleSheet(f"""
            QPushButton {{
                background: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: {Radius.PILL};
                padding: 6px 14px;
                color: {Colors.TEXT_SECONDARY};
                font-size: 12px;
            }}
            QPushButton:checked {{
                background: rgba(6, 182, 212, 0.15);
                border: 1px solid {Colors.CYAN};
                color: {Colors.CYAN_GLOW};
            }}
        """)
        self._voice_toggle.toggled.connect(self._on_voice_toggle)
        tools_layout.addWidget(self._voice_toggle)

        self._screen_toggle = QPushButton("👁️ Share Screen")
        self._screen_toggle.setCheckable(True)
        self._screen_toggle.setStyleSheet(self._voice_toggle.styleSheet())
        self._screen_toggle.toggled.connect(self._on_screen_toggle)
        tools_layout.addWidget(self._screen_toggle)

        # Provider selector
        self._provider = QPushButton("⚡ Groq ▾")
        self._provider.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: {Radius.PILL};
                padding: 6px 14px;
                color: {Colors.TEXT_SECONDARY};
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: {Colors.BG_CARD};
            }}
        """)
        tools_layout.addWidget(self._provider)
        tools_layout.addStretch()

        layout.addLayout(tools_layout)

        # ── Voice Waveform (hidden by default) ──
        self._waveform = VoiceWaveform(bar_count=32)
        self._waveform.setVisible(False)
        layout.addWidget(self._waveform, alignment=Qt.AlignmentFlag.AlignCenter)

        # ── Step Execution Feed ──
        self._step_list = StepListWidget()
        self._step_list.setMaximumHeight(200)
        layout.addWidget(self._step_list)

        # ── Response Preview ──
        self._response = QLabel()
        self._response.setWordWrap(True)
        self._response.setStyleSheet(f"""
            color: {Colors.TEXT_SECONDARY};
            font-size: 13px;
            padding: 8px;
            background: transparent;
        """)
        self._response.setText("Aura is ready. Type a command to begin.")
        layout.addWidget(self._response)

        layout.addStretch()

    def _setup_shortcuts(self):
        self._shortcut = QShortcut(QKeySequence("Alt+Space"), self)
        self._shortcut.activated.connect(self.toggle)

        # Secondary fallback hotkey in case Alt+Space collides with Windows OS menu / PowerToys
        self._fallback_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Space"), self)
        self._fallback_shortcut.activated.connect(self.toggle)

        # Escape key quick dismiss
        self._esc_shortcut = QShortcut(QKeySequence("Escape"), self)
        self._esc_shortcut.activated.connect(self.hide)

    def _setup_shadow(self):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 0, 0, 120))
        shadow.setOffset(0, 12)
        self.setGraphicsEffect(shadow)

    def _connect_signals(self):
        app_signals.voice_status_changed.connect(self._on_voice_status)
        app_signals.screen_status_changed.connect(self._on_screen_status)
        app_signals.provider_changed.connect(self._on_provider_changed)
        app_signals.message_received.connect(self._on_message_received)
        app_signals.toggle_overlay.connect(self.toggle)

    def _on_submit(self):
        text = self._input.text().strip()
        if text:
            self.command_submitted.emit(text)
            self._input.clear()
            self._response.setText("Processing...")

    def _on_voice_toggle(self, checked: bool):
        app_signals.voice_status_changed.emit(checked)

    def _on_screen_toggle(self, checked: bool):
        app_signals.screen_status_changed.emit(checked, "Desktop")

    def _on_voice_status(self, active: bool):
        self._voice_pill.set_active(active)
        self._waveform.setVisible(active)
        self._voice_toggle.setChecked(active)

    def _on_screen_status(self, active: bool, window: str):
        self._screen_pill.set_active(active)
        self._screen_pill.set_label(window if active else "Screen")

    def _on_provider_changed(self, name: str):
        self._engine_pill.set_label(name)
        self._provider.setText(f"⚡ {name} ▾")

    def _on_message_received(self, sender: str, content: str, is_user: bool):
        if not is_user:
            self._response.setText(
                content[:200] + "..." if len(content) > 200 else content
            )

    def toggle(self):
        if self.isVisible():
            self._fade_out()
        else:
            self._fade_in()

    def _fade_in(self):
        self.show()
        self._center_on_screen()
        self.setWindowOpacity(0.0)
        self._anim = Animations.fade_in(self, 200)
        self._anim.start()
        self._input.setFocus()

    def _fade_out(self):
        self._anim = QPropertyAnimation(self, b"windowOpacity")
        self._anim.setDuration(150)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self.hide)
        self._anim.start()

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = int(screen.height() * 0.15)
        self.move(x, y)

    def paintEvent(self, event):
        from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(1, 1, -1, -1), 16, 16)

        painter.fillPath(path, QBrush(QColor(Colors.BG_DEEP)))

        # Subtle border gradient
        pen = QPainterPath()
        pen.setWidth(1.5)
        painter.strokePath(path, QBrush(QColor(34, 211, 238, 60)))

        super().paintEvent(event)
