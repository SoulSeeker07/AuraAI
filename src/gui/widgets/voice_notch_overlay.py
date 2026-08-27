"""
AuraAI — VoiceOS-Style Dynamic Island Notch Overlay (PySide6)
==============================================================
A pixel-perfect recreation of the VoiceOS minimalist top-docked notch
(Dynamic Island) as a floating, frameless, always-on-top liquid-glass pill.

Visual Design:
- Shape: Capsule pill with continuous smooth curvature
- Background: Translucent deep liquid glass with specular sheen gradient
- Border: Crisp cybernetic glass rim (specular white / glowing cyan)
- Dynamic Island floating behavior: Anchored to active screen top (y = available_top + 10)
- Morphing: Smooth geometry animations across 5 states via QPropertyAnimation

States:
  IDLE        — Compact floating pill (240×40)   "● Aura AI  Ready"
  LISTENING   — Dynamic wider pill (340×44)     "🔴 Listening...  ∿∿∿∿" with live waveform
  PROCESSING  — Tactical wide pill (370×44)     "⚡ Aura Core  Planning DAG..." + spinner
  SUCCESS     — Wide feedback pill (350×44)     "✓ Done  [brief result]"
  EXPANDED    — Tall command panel (420×200)    Dropdown with transcript, mode pills, quick actions
"""

import math
import random
import sys
from enum import Enum, auto

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSettings,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


# ─────────────────────────────────────────────────────────────────────────────
# Constants & Design Tokens
# ─────────────────────────────────────────────────────────────────────────────

ORG_NAME = "AuraAI"
APP_NAME = "VoiceNotchOverlay"

# ── Notch dimensions per state ──
IDLE_W, IDLE_H = 240, 40
LISTENING_W, LISTENING_H = 340, 44
PROCESSING_W, PROCESSING_H = 370, 44
SUCCESS_W, SUCCESS_H = 350, 44
EXPANDED_W, EXPANDED_H = 420, 200

# ── Animation timing ──
MORPH_DURATION_MS = 220
SUCCESS_HOLD_MS = 2500

# ── Liquid Glass Colors ──
BG_GLASS_TOP = QColor(22, 27, 40, 248)
BG_GLASS_BOTTOM = QColor(10, 13, 20, 252)
BG_GLASS_HOVER_TOP = QColor(28, 35, 52, 252)
BG_GLASS_HOVER_BOTTOM = QColor(14, 18, 28, 254)

BORDER_IDLE = QColor(255, 255, 255, 60)
BORDER_HOVER = QColor(0, 229, 255, 150)
BORDER_ACTIVE = QColor(0, 229, 255, 190)

# ── Text Colors ──
TEXT_PRIMARY = QColor(245, 248, 255)
TEXT_SECONDARY = QColor(165, 185, 215)
TEXT_MUTED = QColor(110, 130, 155)
TEXT_SUCCESS = QColor(16, 185, 129)
TEXT_LISTENING = QColor(244, 63, 94)

# ── Accent Colors ──
CYAN = QColor(0, 229, 255)
CYAN_GLOW = QColor(51, 238, 255)
EMERALD = QColor(16, 185, 129)

# ── Waveform ──
WAVEFORM_BAR_COUNT = 5
WAVEFORM_BAR_W = 2.5
WAVEFORM_BAR_GAP = 3.0
WAVEFORM_BAR_COLOR_IDLE = QColor(120, 140, 165)
WAVEFORM_BAR_COLOR_ACTIVE = CYAN

# ── Notch Geometry ──
NOTCH_RADIUS = 20.0
TOP_MARGIN = 0

# ── Font ──
FONT_FAMILY = "Segoe UI, Inter, -apple-system, sans-serif"


class NotchState(Enum):
    IDLE = auto()
    LISTENING = auto()
    PROCESSING = auto()
    SUCCESS = auto()
    EXPANDED = auto()


def get_display_refresh_rate() -> float:
    """Detect native display refresh rate (e.g. 120Hz, 144Hz, 60Hz)."""
    try:
        from PySide6.QtGui import QCursor
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen:
            rate = screen.refreshRate()
            if rate and rate >= 45.0:
                return float(rate)
    except Exception:
        pass
    return 120.0  # Default to high refresh rate


# ─────────────────────────────────────────────────────────────────────────────
# Mini Waveform Widget
# ─────────────────────────────────────────────────────────────────────────────

class _MiniWaveform(QWidget):
    """
    Embedded voice visualizer inside the notch pill.
    Auto-FPS adapts to 120Hz / 144Hz / 60Hz native display rate.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active = False
        self._levels = [0.15] * WAVEFORM_BAR_COUNT
        self._target_levels = [0.15] * WAVEFORM_BAR_COUNT
        self._current_level = 0.0
        self._phase = 0.0

        total_w = int(
            WAVEFORM_BAR_COUNT * WAVEFORM_BAR_W
            + (WAVEFORM_BAR_COUNT - 1) * WAVEFORM_BAR_GAP
            + 6
        )
        self.setFixedSize(total_w, 20)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # Auto-detect monitor refresh rate (120Hz -> 8ms, 144Hz -> 7ms, 60Hz -> 16ms)
        self._hz = get_display_refresh_rate()
        self._interval_ms = max(4, int(1000.0 / self._hz))

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(self._interval_ms)

    def update_fps_for_screen(self):
        hz = get_display_refresh_rate()
        if abs(hz - self._hz) > 5.0:
            self._hz = hz
            self._interval_ms = max(4, int(1000.0 / self._hz))
            self._timer.setInterval(self._interval_ms)

    def set_active(self, active: bool):
        self._active = active
        if not active:
            self._target_levels = [0.15] * WAVEFORM_BAR_COUNT

    def set_level(self, level: float):
        # Non-linear logarithmic perception curve for punchy responsive audio visualization
        perceived = math.sqrt(max(0.0, min(1.0, level)))
        self._current_level = perceived
        if self._active:
            self._phase += 0.25 * (60.0 / self._hz)
            for i in range(WAVEFORM_BAR_COUNT):
                base = self._current_level * (
                    0.40 + 0.60 * abs(math.sin(i * 1.15 + self._phase))
                )
                noise = random.uniform(-0.04, 0.04)
                self._target_levels[i] = max(0.12, min(1.0, base + noise))

    def _animate(self):
        changed = False
        # Delta-time normalized physics for identical physical speed at 120Hz/60Hz
        rate = 0.40 * (60.0 / self._hz)
        for i in range(WAVEFORM_BAR_COUNT):
            diff = self._target_levels[i] - self._levels[i]
            if abs(diff) > 0.002:
                self._levels[i] += diff * rate
                changed = True
        if changed or self._active:
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w = self.width()
        h = self.height()
        cy = h / 2.0

        for i in range(WAVEFORM_BAR_COUNT):
            x = 3 + i * (WAVEFORM_BAR_W + WAVEFORM_BAR_GAP)
            level = self._levels[i]

            if self._active:
                bar_h = max(3.5, level * (h - 2))
                bar_rect = QRectF(x, cy - bar_h / 2, WAVEFORM_BAR_W, bar_h)

                # Vibrant cyan-to-sky gradient
                bar_grad = QLinearGradient(x, cy - bar_h / 2, x, cy + bar_h / 2)
                bar_grad.setColorAt(0.0, QColor(0, 240, 255, int(180 + level * 75)))
                bar_grad.setColorAt(1.0, QColor(56, 189, 248, int(160 + level * 95)))

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(bar_grad))
                painter.drawRoundedRect(bar_rect, 1.25, 1.25)
            else:
                dot_r = 1.4
                color = QColor(WAVEFORM_BAR_COLOR_IDLE)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(color))
                painter.drawEllipse(
                    QRectF(x - dot_r + WAVEFORM_BAR_W / 2,
                           cy - dot_r,
                           dot_r * 2, dot_r * 2)
                )


# ─────────────────────────────────────────────────────────────────────────────
# Expanded Dropdown Panel
# ─────────────────────────────────────────────────────────────────────────────

class _ExpandedPanel(QWidget):
    """Content shown in the expanded dropdown state."""

    mode_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_mode = "agent"
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 14)
        layout.setSpacing(10)

        # Separator line with cyan gradient glow
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0,229,255,0), stop:0.5 rgba(0,229,255,0.4), stop:1 rgba(0,229,255,0));")
        layout.addWidget(sep)

        # Latest transcript preview
        self._transcript_label = QLabel("Say a command or hold hotkey to dictate...")
        self._transcript_label.setWordWrap(True)
        self._transcript_label.setStyleSheet(
            f"color: rgba(240, 245, 255, 0.98);"
            f"font-family: {FONT_FAMILY};"
            f"font-size: 13px;"
            f"line-height: 1.45;"
            f"background: rgba(0, 229, 255, 0.06);"
            f"border: 1px solid rgba(0, 229, 255, 0.2);"
            f"border-radius: 8px;"
            f"padding: 8px 12px;"
        )
        self._transcript_label.setMinimumHeight(54)
        layout.addWidget(self._transcript_label)

        # Mode toggle pills
        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)

        self._dictation_btn = self._make_mode_pill("🎤", "Dictation")
        self._agent_btn = self._make_mode_pill("⚡", "Agent")

        self._dictation_btn.clicked.connect(lambda: self._set_mode("dictation"))
        self._agent_btn.clicked.connect(lambda: self._set_mode("agent"))

        mode_row.addWidget(self._dictation_btn)
        mode_row.addWidget(self._agent_btn)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        # Quick-action badges row
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self._voice_badge = self._make_badge("🎙️", "Voice Active")
        self._screen_badge = self._make_badge("👁️", "Vision Ready")
        self._engine_badge = self._make_badge("⚡", "Groq LPU")

        action_row.addWidget(self._voice_badge)
        action_row.addWidget(self._screen_badge)
        action_row.addStretch()
        action_row.addWidget(self._engine_badge)
        layout.addLayout(action_row)

        self._update_mode_pills()

    def _make_mode_pill(self, icon: str, label: str) -> QPushButton:
        btn = QPushButton(f"{icon}  {label}")
        btn.setFixedHeight(30)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: rgba(30, 41, 59, 0.7);"
            f"  border: 1px solid rgba(255, 255, 255, 0.12);"
            f"  border-radius: 15px;"
            f"  padding: 4px 14px;"
            f"  font-family: {FONT_FAMILY};"
            f"  font-size: 12px;"
            f"  font-weight: 500;"
            f"  color: rgba(200, 215, 235, 0.95);"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: rgba(40, 55, 75, 0.85);"
            f"  border: 1px solid rgba(0, 229, 255, 0.4);"
            f"}}"
        )
        return btn

    def _make_badge(self, icon: str, label: str) -> QLabel:
        badge = QLabel(f"{icon} {label}")
        badge.setStyleSheet(
            f"color: rgba(140, 165, 195, 0.9);"
            f"font-family: {FONT_FAMILY};"
            f"font-size: 11px;"
            f"background: transparent;"
            f"border: none;"
        )
        return badge

    def _set_mode(self, mode: str):
        self._current_mode = mode
        self._update_mode_pills()
        self.mode_changed.emit(mode)

    def _update_mode_pills(self):
        active_style = (
            f"QPushButton {{"
            f"  background: rgba(0, 229, 255, 0.18);"
            f"  border: 1px solid rgba(0, 229, 255, 0.7);"
            f"  border-radius: 15px;"
            f"  padding: 4px 14px;"
            f"  font-family: {FONT_FAMILY};"
            f"  font-size: 12px;"
            f"  font-weight: 600;"
            f"  color: #00f0ff;"
            f"}}"
        )
        inactive_style = (
            f"QPushButton {{"
            f"  background: rgba(30, 41, 59, 0.7);"
            f"  border: 1px solid rgba(255, 255, 255, 0.12);"
            f"  border-radius: 15px;"
            f"  padding: 4px 14px;"
            f"  font-family: {FONT_FAMILY};"
            f"  font-size: 12px;"
            f"  font-weight: 500;"
            f"  color: rgba(200, 215, 235, 0.95);"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: rgba(40, 55, 75, 0.85);"
            f"  border: 1px solid rgba(0, 229, 255, 0.4);"
            f"}}"
        )
        if self._current_mode == "dictation":
            self._dictation_btn.setStyleSheet(active_style)
            self._agent_btn.setStyleSheet(inactive_style)
        else:
            self._agent_btn.setStyleSheet(active_style)
            self._dictation_btn.setStyleSheet(inactive_style)

    def set_transcript(self, text: str):
        truncated = text[:350] + "..." if len(text) > 350 else text
        self._transcript_label.setText(truncated)

    def set_engine(self, name: str):
        self._engine_badge.setText(f"⚡ {name}")


# ─────────────────────────────────────────────────────────────────────────────
# Main VoiceNotchOverlay Widget
# ─────────────────────────────────────────────────────────────────────────────

class VoiceNotchOverlay(QWidget):
    """
    VoiceOS-style Dynamic Island Notch — a floating, frameless, always-on-top
    liquid-glass pill anchored to the top-center of the active monitor.
    """

    command_submitted = Signal(str)
    mode_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VoiceNotchOverlay")
        self.setWindowTitle("AuraAI Voice Notch")

        # Top-level frameless always-on-top HUD window
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

        # State
        self._state = NotchState.IDLE
        self._is_hovered = False
        self._is_dragging = False
        self._drag_start_pos = QPoint()
        self._drag_start_geom = QPoint()
        self._latest_transcript = ""
        self._processing_label = ""
        self._success_text = ""
        self._engine_name = "Groq"

        # Settings persistence
        self._settings = QSettings(ORG_NAME, APP_NAME)

        # Build UI
        self._setup_ui()

        # Position at top center
        self._position_at_top()

        # Success auto-return timer
        self._success_timer = QTimer(self)
        self._success_timer.setSingleShot(True)
        self._success_timer.timeout.connect(lambda: self.set_state(NotchState.IDLE))

        # Hover expansion timer
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(400)
        self._hover_timer.timeout.connect(self._expand_from_hover)

        # Hover collapse timer
        self._collapse_timer = QTimer(self)
        self._collapse_timer.setSingleShot(True)
        self._collapse_timer.setInterval(300)
        self._collapse_timer.timeout.connect(self._collapse_from_hover)

        # Spinner rotation for processing state (Auto-FPS)
        self._hz = get_display_refresh_rate()
        spinner_ms = max(4, int(1000.0 / self._hz))
        self._spinner_step = 6.0 * (60.0 / self._hz)
        self._spinner_angle = 0.0
        self._spinner_timer = QTimer(self)
        self._spinner_timer.setInterval(spinner_ms)
        self._spinner_timer.timeout.connect(self._update_spinner)

        # Connect to Aura signal bus
        self._connect_signals()

    # ─────────────────────────────────────────────────────────────────────────
    # UI Setup
    # ─────────────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        # Band (always visible top row)
        self._band = QWidget()
        self._band.setFixedHeight(IDLE_H)
        self._band.setStyleSheet("background: transparent;")
        band_layout = QHBoxLayout(self._band)
        band_layout.setContentsMargins(14, 0, 16, 0)
        band_layout.setSpacing(10)

        # Waveform indicator
        self._waveform = _MiniWaveform()
        band_layout.addWidget(self._waveform)

        # Status icon + label area
        self._status_stack = QStackedWidget()
        self._status_stack.setStyleSheet("background: transparent; border: none;")

        # Page 0: IDLE content
        idle_page = QWidget()
        idle_layout = QHBoxLayout(idle_page)
        idle_layout.setContentsMargins(0, 0, 0, 0)
        idle_layout.setSpacing(8)
        self._idle_dot = QLabel("●")
        self._idle_dot.setStyleSheet("color: #10b981; font-size: 9px; background: transparent; border: none;")
        self._idle_dot.setFixedWidth(12)
        self._idle_label = QLabel("Aura AI")
        self._idle_label.setStyleSheet(f"color: #ffffff; font-family: {FONT_FAMILY}; font-size: 13px; font-weight: 700; letter-spacing: -0.2px; background: transparent; border: none;")
        idle_layout.addWidget(self._idle_dot)
        idle_layout.addWidget(self._idle_label)
        idle_layout.addStretch()
        self._idle_status = QLabel("Ready")
        self._idle_status.setStyleSheet(f"color: #7dd3fc; font-family: {FONT_FAMILY}; font-size: 11px; font-weight: 500; background: transparent; border: none;")
        idle_layout.addWidget(self._idle_status)
        self._status_stack.addWidget(idle_page)

        # Page 1: LISTENING content
        listen_page = QWidget()
        listen_layout = QHBoxLayout(listen_page)
        listen_layout.setContentsMargins(0, 0, 0, 0)
        listen_layout.setSpacing(8)
        self._listen_dot = QLabel("●")
        self._listen_dot.setStyleSheet("color: #f43f5e; font-size: 10px; background: transparent; border: none;")
        self._listen_dot.setFixedWidth(12)
        self._listen_label = QLabel("Listening...")
        self._listen_label.setStyleSheet(f"color: #ffffff; font-family: {FONT_FAMILY}; font-size: 13px; font-weight: 700; background: transparent; border: none;")
        listen_layout.addWidget(self._listen_dot)
        listen_layout.addWidget(self._listen_label)
        listen_layout.addStretch()
        self._listen_activity = QLabel("")
        self._listen_activity.setStyleSheet(f"color: #38bdf8; font-family: {FONT_FAMILY}; font-size: 11px; font-weight: 500; background: transparent; border: none;")
        listen_layout.addWidget(self._listen_activity)
        self._status_stack.addWidget(listen_page)

        # Page 2: PROCESSING content
        proc_page = QWidget()
        proc_layout = QHBoxLayout(proc_page)
        proc_layout.setContentsMargins(0, 0, 0, 0)
        proc_layout.setSpacing(8)
        self._proc_icon = QLabel("⚡")
        self._proc_icon.setStyleSheet("color: #00f0ff; font-size: 12px; background: transparent; border: none;")
        self._proc_icon.setFixedWidth(16)
        self._proc_label = QLabel("Aura Core")
        self._proc_label.setStyleSheet(f"color: #ffffff; font-family: {FONT_FAMILY}; font-size: 13px; font-weight: 700; background: transparent; border: none;")
        proc_layout.addWidget(self._proc_icon)
        proc_layout.addWidget(self._proc_label)
        proc_layout.addStretch()
        self._proc_activity = QLabel("Processing...")
        self._proc_activity.setStyleSheet(f"color: #fbbf24; font-family: {FONT_FAMILY}; font-size: 11px; font-weight: 500; background: transparent; border: none;")
        proc_layout.addWidget(self._proc_activity)
        self._status_stack.addWidget(proc_page)

        # Page 3: SUCCESS content
        success_page = QWidget()
        success_layout = QHBoxLayout(success_page)
        success_layout.setContentsMargins(0, 0, 0, 0)
        success_layout.setSpacing(8)
        self._success_icon = QLabel("✓")
        self._success_icon.setStyleSheet("color: #10b981; font-size: 14px; font-weight: bold; background: transparent; border: none;")
        self._success_icon.setFixedWidth(16)
        self._success_label = QLabel("Done")
        self._success_label.setStyleSheet(f"color: #10b981; font-family: {FONT_FAMILY}; font-size: 13px; font-weight: 700; background: transparent; border: none;")
        success_layout.addWidget(self._success_icon)
        success_layout.addWidget(self._success_label)
        success_layout.addStretch()
        self._success_detail = QLabel("")
        self._success_detail.setStyleSheet(f"color: #94a3b8; font-family: {FONT_FAMILY}; font-size: 11px; background: transparent; border: none;")
        success_layout.addWidget(self._success_detail)
        self._status_stack.addWidget(success_page)

        band_layout.addWidget(self._status_stack, stretch=1)
        self._root_layout.addWidget(self._band)

        # Expanded panel (hidden by default)
        self._expanded_panel = _ExpandedPanel()
        self._expanded_panel.setVisible(False)
        self._expanded_panel.mode_changed.connect(self.mode_changed.emit)
        self._root_layout.addWidget(self._expanded_panel)

    # ─────────────────────────────────────────────────────────────────────────
    # Positioning
    # ─────────────────────────────────────────────────────────────────────────

    def _position_at_top(self):
        cursor_pos = QCursor.pos()
        screen = QApplication.screenAt(cursor_pos) or QApplication.primaryScreen()
        if not screen:
            return
        sg = screen.availableGeometry()

        saved_x = self._settings.value("notch_x", None)
        saved_y = self._settings.value("notch_y", None)
        w, h = IDLE_W, IDLE_H

        if saved_x is not None and saved_y is not None:
            try:
                x = int(saved_x)
                y = int(saved_y)
                found_screen = None
                for s in QApplication.screens():
                    if s.geometry().contains(x + w // 2, y + h // 2):
                        found_screen = s
                        break
                if found_screen:
                    f_sg = found_screen.availableGeometry()
                    x = max(f_sg.left() + 10, min(x, f_sg.right() - w - 10))
                    y = max(f_sg.top() + 4, min(y, f_sg.bottom() - h - 10))
                    self.setGeometry(x, y, w, h)
                    return
            except Exception:
                pass

        if saved_x is not None:
            try:
                x = int(saved_x)
                x = max(sg.left() + 20, min(x, sg.right() - w - 20))
            except Exception:
                x = sg.left() + (sg.width() - w) // 2
        else:
            x = sg.left() + (sg.width() - w) // 2

        y = sg.top() + TOP_MARGIN
        self.setGeometry(x, y, w, h)

    # ─────────────────────────────────────────────────────────────────────────
    # Painting
    # ─────────────────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        rect = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()

        rad = float(NOTCH_RADIUS)
        path.addRoundedRect(QRectF(rect), rad, rad)

        # Liquid Glass Gradient Fill
        bg_grad = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
        if self._is_hovered:
            bg_grad.setColorAt(0.0, BG_GLASS_HOVER_TOP)
            bg_grad.setColorAt(1.0, BG_GLASS_HOVER_BOTTOM)
        else:
            bg_grad.setColorAt(0.0, BG_GLASS_TOP)
            bg_grad.setColorAt(1.0, BG_GLASS_BOTTOM)

        painter.fillPath(path, QBrush(bg_grad))

        # Top-edge Specular Sheen
        sheen_h = min(14.0, rect.height() * 0.4)
        sheen_grad = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.top() + sheen_h)
        sheen_grad.setColorAt(0.0, QColor(255, 255, 255, 45))
        sheen_grad.setColorAt(0.6, QColor(255, 255, 255, 12))
        sheen_grad.setColorAt(1.0, QColor(255, 255, 255, 0))

        sheen_path = QPainterPath()
        sheen_path.addRoundedRect(
            QRectF(rect.left() + 2, rect.top() + 1, rect.width() - 4, sheen_h),
            rad - 1, rad - 1
        )
        painter.fillPath(sheen_path, QBrush(sheen_grad))

        # Perimeter Rim (Border)
        if self._state == NotchState.LISTENING:
            border_color = QColor(244, 63, 94, 160)
            pen = QPen(border_color, 1.4)
        elif self._state == NotchState.PROCESSING:
            border_color = BORDER_ACTIVE
            pen = QPen(border_color, 1.4)
        elif self._is_hovered:
            border_color = BORDER_HOVER
            pen = QPen(border_color, 1.3)
        else:
            border_color = BORDER_IDLE
            pen = QPen(border_color, 1.1)

        painter.strokePath(path, pen)

        # Spinner for PROCESSING state
        if self._state == NotchState.PROCESSING:
            self._draw_spinner(painter)

        painter.end()

    def _draw_spinner(self, painter: QPainter):
        cx = self.width() - 28
        cy = self._band.height() / 2
        r = 5.0

        angle_rad = math.radians(self._spinner_angle)
        dot_x = cx + r * math.cos(angle_rad)
        dot_y = cy + r * math.sin(angle_rad)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(CYAN))
        painter.drawEllipse(QRectF(dot_x - 1.8, dot_y - 1.8, 3.6, 3.6))

        for i in range(3):
            trail_angle = angle_rad - (i + 1) * 0.5
            tx = cx + r * math.cos(trail_angle)
            ty = cy + r * math.sin(trail_angle)
            trail_color = QColor(CYAN)
            trail_color.setAlphaF(0.35 - i * 0.09)
            painter.setBrush(QBrush(trail_color))
            painter.drawEllipse(QRectF(tx - 1.2, ty - 1.2, 2.4, 2.4))

    def _update_spinner(self):
        self._spinner_angle = (self._spinner_angle + self._spinner_step) % 360
        self.update()

    # ─────────────────────────────────────────────────────────────────────────
    # State Machine & Morphing
    # ─────────────────────────────────────────────────────────────────────────

    def set_state(self, state: NotchState, text: str = ""):
        if state == self._state and state != NotchState.PROCESSING:
            return

        old_state = self._state
        self._state = state

        self._success_timer.stop()
        if state != NotchState.PROCESSING:
            self._spinner_timer.stop()

        if old_state == NotchState.EXPANDED and state != NotchState.EXPANDED:
            self._expanded_panel.setVisible(False)

        cursor_pos = QCursor.pos()
        screen = QApplication.screenAt(cursor_pos) or QApplication.primaryScreen()
        if not screen:
            return
        sg = screen.availableGeometry()

        if state == NotchState.IDLE:
            target_w, target_h = IDLE_W, IDLE_H
            self._status_stack.setCurrentIndex(0)
            self._waveform.set_active(False)
            self._expanded_panel.setVisible(False)

        elif state == NotchState.LISTENING:
            target_w, target_h = LISTENING_W, LISTENING_H
            self._status_stack.setCurrentIndex(1)
            self._waveform.set_active(True)
            self._listen_activity.setText(text or "")
            self._expanded_panel.setVisible(False)

        elif state == NotchState.PROCESSING:
            target_w, target_h = PROCESSING_W, PROCESSING_H
            self._processing_label = text or "Processing..."
            self._proc_activity.setText(self._processing_label)
            self._status_stack.setCurrentIndex(2)
            self._waveform.set_active(False)
            self._spinner_timer.start()
            self._expanded_panel.setVisible(False)

        elif state == NotchState.SUCCESS:
            target_w, target_h = SUCCESS_W, SUCCESS_H
            self._success_text = text
            self._success_detail.setText(
                text[:55] + "..." if len(text) > 55 else text
            )
            self._success_label.setText("Done")
            self._success_label.setStyleSheet(
                f"color: #10b981;"
                f"font-family: {FONT_FAMILY};"
                f"font-size: 13px;"
                f"font-weight: 700;"
                f"background: transparent; border: none;"
            )
            self._success_icon.setStyleSheet(
                f"color: #10b981;"
                f"font-size: 14px;"
                f"font-weight: bold;"
                f"background: transparent; border: none;"
            )
            self._status_stack.setCurrentIndex(3)
            self._waveform.set_active(False)
            self._expanded_panel.setVisible(False)
            self._success_timer.start(SUCCESS_HOLD_MS)

        elif state == NotchState.EXPANDED:
            target_w, target_h = EXPANDED_W, EXPANDED_H
            self._expanded_panel.setVisible(True)
            self._waveform.set_active(False)
            self._success_timer.start(8000)

        else:
            return

        # Geometry morph animation
        current_geom = self.geometry()
        current_cx = current_geom.x() + current_geom.width() // 2
        target_x = current_cx - target_w // 2

        target_x = max(sg.left() + 10, min(target_x, sg.right() - target_w - 10))
        target_y = current_geom.y()

        target_geom = QRect(target_x, target_y, target_w, target_h)

        self._morph_anim = QPropertyAnimation(self, b"geometry")
        self._morph_anim.setDuration(MORPH_DURATION_MS)
        self._morph_anim.setStartValue(current_geom)
        self._morph_anim.setEndValue(target_geom)
        self._morph_anim.setEasingCurve(QEasingCurve.Type.OutQuart)
        self._morph_anim.start()

        self.update()

    def set_processing_label(self, label: str):
        if self._state == NotchState.PROCESSING:
            self._processing_label = label
            self._proc_activity.setText(label)

    def set_transcript(self, text: str):
        self._latest_transcript = text
        self._expanded_panel.set_transcript(text)

    def set_engine(self, name: str):
        self._engine_name = name
        self._expanded_panel.set_engine(name)

    # ─────────────────────────────────────────────────────────────────────────
    # Mouse Events
    # ─────────────────────────────────────────────────────────────────────────

    def enterEvent(self, event):
        self._is_hovered = True
        self._collapse_timer.stop()
        if self._state not in (NotchState.EXPANDED, NotchState.LISTENING, NotchState.PROCESSING):
            self._hover_timer.start()
        self.update()

    def leaveEvent(self, event):
        self._is_hovered = False
        self._hover_timer.stop()
        if self._state == NotchState.EXPANDED:
            self._collapse_timer.start()
        self.update()

    def _expand_from_hover(self):
        if self._is_hovered and self._state == NotchState.IDLE:
            self.set_state(NotchState.EXPANDED)

    def _collapse_from_hover(self):
        if not self._is_hovered and self._state == NotchState.EXPANDED:
            self.set_state(NotchState.IDLE)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_start_pos = event.globalPosition().toPoint()
            self._drag_start_geom = self.pos()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
            event.accept()

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            delta = event.globalPosition().toPoint() - self._drag_start_pos
            new_x = self._drag_start_geom.x() + delta.x()
            new_y = self._drag_start_geom.y() + delta.y()

            screen = QApplication.screenAt(event.globalPosition().toPoint()) or QApplication.primaryScreen()
            if screen:
                sg = screen.availableGeometry()
                new_x = max(sg.left() + 10, min(new_x, sg.right() - self.width() - 10))
                new_y = max(sg.top() + 4, min(new_y, sg.bottom() - self.height() - 10))

            self.move(new_x, new_y)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            was_dragging = self._is_dragging
            drag_distance = 0
            if was_dragging:
                drag_distance = (
                    event.globalPosition().toPoint() - self._drag_start_pos
                ).manhattanLength()

            self._is_dragging = False

            if drag_distance < 6:
                if self._state == NotchState.EXPANDED:
                    self.set_state(NotchState.IDLE)
                elif self._state == NotchState.IDLE:
                    self.set_state(NotchState.EXPANDED)

            self._settings.setValue("notch_x", self.x())
            self._settings.setValue("notch_y", self.y())
            self._settings.sync()
            event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self._state == NotchState.EXPANDED:
                self.set_state(NotchState.IDLE)
            else:
                self.hide()
            event.accept()
        elif event.key() == Qt.Key.Key_Space:
            if self._state == NotchState.IDLE:
                self.set_state(NotchState.LISTENING)
            elif self._state == NotchState.LISTENING:
                self.set_state(NotchState.IDLE)
            event.accept()
        else:
            super().keyPressEvent(event)

    def _show_context_menu(self, pos: QPoint):
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{"
            f"  background: rgba(18, 23, 36, 0.96);"
            f"  border: 1px solid rgba(0, 229, 255, 0.3);"
            f"  border-radius: 10px;"
            f"  padding: 6px;"
            f"  font-family: {FONT_FAMILY};"
            f"  font-size: 12px;"
            f"  color: #f1f5f9;"
            f"}}"
            f"QMenu::item {{"
            f"  padding: 6px 18px;"
            f"  border-radius: 6px;"
            f"}}"
            f"QMenu::item:selected {{"
            f"  background: rgba(0, 229, 255, 0.18);"
            f"  color: #00f0ff;"
            f"}}"
        )

        gui_action = menu.addAction("🖥️  Open Full GUI Dashboard")
        chat_action = menu.addAction("💬  Open Spotlight Chat (Alt+Space)")
        menu.addSeparator()
        dictation_action = menu.addAction("🎤  Dictation Mode")
        agent_action = menu.addAction("⚡  Agent Mode")
        menu.addSeparator()
        try:
            from system.autostart import is_autostart_enabled, enable_autostart, disable_autostart
            autostart_active = is_autostart_enabled()
        except Exception:
            autostart_active = False

        autostart_label = "✅  Start with Windows" if autostart_active else "⬜  Start with Windows"
        autostart_action = menu.addAction(autostart_label)
        menu.addSeparator()

        snap_action = menu.addAction("📌  Snap to Top Center (Touch Taskbar)")
        reset_pos_action = menu.addAction("📍  Reset Position to Center")
        menu.addSeparator()
        hide_action = menu.addAction("✕  Hide Notch")

        action = menu.exec(pos)

        if action == gui_action:
            import subprocess
            from pathlib import Path
            root = Path(__file__).resolve().parents[3]
            py = root / ".venv" / "Scripts" / "python.exe"
            subprocess.Popen([str(py), str(root / "main.py"), "--gui"], cwd=str(root))
        elif action == chat_action:
            import subprocess
            from pathlib import Path
            root = Path(__file__).resolve().parents[3]
            py = root / ".venv" / "Scripts" / "python.exe"
            subprocess.Popen([str(py), str(root / "run_chat_window.py")], cwd=str(root))
        elif action == autostart_action:
            try:
                from system.autostart import enable_autostart, disable_autostart
                if autostart_active:
                    disable_autostart()
                else:
                    enable_autostart()
            except Exception:
                pass
        elif action == dictation_action:
            self.mode_changed.emit("dictation")
        elif action == agent_action:
            self.mode_changed.emit("agent")
        elif action in (snap_action, reset_pos_action):
            self._settings.remove("notch_x")
            self._settings.remove("notch_y")
            self._settings.sync()
            self._position_at_top()
        elif action == hide_action:
            self.hide()

    # ─────────────────────────────────────────────────────────────────────────
    # Signal Bus Connection
    # ─────────────────────────────────────────────────────────────────────────

    def _connect_signals(self):
        try:
            from gui.signals import app_signals

            app_signals.voice_status_changed.connect(self._on_voice_status)
            app_signals.voice_level.connect(self._on_voice_level)
            app_signals.voice_state_name_changed.connect(self._on_voice_state_name)
            app_signals.execution_started.connect(self._on_execution_started)
            app_signals.execution_finished.connect(self._on_execution_finished)
            app_signals.message_received.connect(self._on_message_received)
            app_signals.provider_changed.connect(self._on_provider_changed)
            app_signals.step_updated.connect(self._on_step_updated)

            if hasattr(app_signals, "live_speech_transcribed"):
                app_signals.live_speech_transcribed.connect(self._on_live_speech_transcribed)

            if hasattr(app_signals, "toggle_voice_notch"):
                app_signals.toggle_voice_notch.connect(self.toggle)
        except ImportError:
            pass

    def _on_voice_status(self, active: bool):
        # Do not force LISTENING state on background mic start; standby stays as 'Aura AI' (IDLE)
        if not active and self._state == NotchState.LISTENING:
            self.set_state(NotchState.IDLE)

    def _on_voice_level(self, level: float):
        self._waveform.set_level(level)

    def _on_voice_state_name(self, name: str):
        name_upper = (name or "").upper()
        if name_upper in ("WAKE_DETECTED", "COMMAND_LISTENING", "ACTIVE_LISTENING", "FOLLOW_UP_LISTENING"):
            self.set_state(NotchState.LISTENING, "Listening...")
        elif name_upper == "TRANSCRIBING":
            self.set_state(NotchState.PROCESSING, "Transcribing...")
        elif name_upper in ("UNDERSTANDING", "EXECUTING", "AI_RESPONSE", "PLANNING", "THINKING"):
            self.set_state(NotchState.PROCESSING, "Aura Core...")
        elif name_upper == "SPEAKING":
            self.set_state(NotchState.SUCCESS, "Speaking...")
        elif name_upper in ("IDLE", "LISTENING", "COOLDOWN", "WAITING_FOR_WAKE_WORD", "STANDBY"):
            # When in standby waiting for wake word, state remains IDLE ("Aura AI")
            self.set_state(NotchState.IDLE)
        else:
            if self._state == NotchState.LISTENING:
                self._listen_activity.setText(name)

    def _on_execution_started(self, task_id: str):
        self.set_state(NotchState.PROCESSING, "Planning...")

    def _on_execution_finished(self, task_id: str, success: bool):
        if success:
            self.set_state(NotchState.SUCCESS, "Task completed")
        else:
            self.set_state(NotchState.SUCCESS, "Task failed")
            self._success_label.setText("Failed")
            self._success_label.setStyleSheet(
                f"color: #f43f5e;"
                f"font-family: {FONT_FAMILY};"
                f"font-size: 13px;"
                f"font-weight: 700;"
                f"background: transparent; border: none;"
            )
            self._success_icon.setStyleSheet(
                f"color: #f43f5e;"
                f"font-size: 14px;"
                f"font-weight: bold;"
                f"background: transparent; border: none;"
            )

    def _on_live_speech_transcribed(self, text: str, is_final: bool):
        if not text:
            return
        if self._state in (NotchState.LISTENING, NotchState.IDLE):
            if self._state != NotchState.LISTENING:
                self.set_state(NotchState.LISTENING)
            display_text = f"\"{text[:30]}...\"" if len(text) > 30 else f"\"{text}\""
            self._listen_activity.setText(display_text)
            self.set_transcript(text)

    def _on_message_received(self, sender: str, content: str, is_user: bool):
        if not is_user and content:
            self.set_transcript(content)
            # Auto-expand if the response is longer than 45 chars so it is fully readable
            if len(content) > 45:
                self.set_state(NotchState.EXPANDED)
            else:
                self.set_state(NotchState.SUCCESS, content)

    def _on_provider_changed(self, name: str):
        self.set_engine(name)

    def _on_step_updated(self, step):
        if self._state == NotchState.PROCESSING:
            label = getattr(step, "title", "") or getattr(step, "description", "")
            if label:
                self.set_processing_label(label[:50])

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def toggle(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self._position_at_top()

    @property
    def current_state(self) -> NotchState:
        return self._state
