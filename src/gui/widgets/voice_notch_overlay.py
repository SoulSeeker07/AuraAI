"""
AuraAI — Ultra-Vibrant Colorful Holographic Dynamic Notch HUD (PySide6)
========================================================================
- Ultimate Futuristic Always-On-Top Cybernetic HUD Notch.
- Cyber Obsidian Glass with Neon Perimeter Glow & Tactical Corner Markers.
- Integrated Quantum Orb + AuraAI + Center Mini-Spectrum + Seamless Status Chip.
- 120Hz Fluid Mouse Hover Expansion to 3-Column Command Center.
- Full Live Backend Integration (Transcript, Dynamic Actions, Clickable Sources).
"""

import datetime
import logging
import math
import os
import random
import re
import sys
import time
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSettings,
    QTimer,
    QUrl,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QClipboard,
    QColor,
    QCursor,
    QDesktopServices,
    QFont,
    QGuiApplication,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


# ─────────────────────────────────────────────────────────────────────────────
# Futuristic Sci-Fi Design Tokens (Compact & Ultra-Sleek)
# ─────────────────────────────────────────────────────────────────────────────

ORG_NAME = "AuraAI"
APP_NAME = "VoiceNotchOverlay"

# Dimensions
IDLE_W, IDLE_H = 260, 36
LISTENING_W, LISTENING_H = 420, 42
PROCESSING_W, PROCESSING_H = 440, 76
SUCCESS_W, SUCCESS_H = 440, 76
EXPANDED_W, EXPANDED_H = 540, 320

# 120 FPS High-Refresh Animation Duration
MORPH_DURATION_MS = 220
SUCCESS_HOLD_MS = 6000

# Modern Corner Radius
NOTCH_RADIUS = 10.0

# Deep Cyber Obsidian Glass Palette
BG_DARK_TOP = QColor(6, 10, 22, 250)
BG_DARK_BOTTOM = QColor(2, 4, 12, 254)
BG_HOVER_TOP = QColor(10, 18, 36, 252)
BG_HOVER_BOTTOM = QColor(4, 8, 18, 254)

# Vibrant Neon Colors
NEON_CYAN = QColor(0, 240, 255)
NEON_BLUE = QColor(59, 130, 246)
NEON_VIOLET = QColor(168, 85, 247)
NEON_PINK = QColor(236, 72, 153)
NEON_AMBER = QColor(245, 158, 11)
NEON_YELLOW = QColor(234, 179, 8)
NEON_EMERALD = QColor(16, 185, 129)

FONT_SANS = "'Segoe UI', Inter, -apple-system, BlinkMacSystemFont, sans-serif"


class NotchState(Enum):
    IDLE = auto()
    LISTENING = auto()
    PROCESSING = auto()
    SUCCESS = auto()
    EXPANDED = auto()


def get_display_refresh_rate() -> float:
    try:
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen:
            rate = screen.refreshRate()
            if rate and rate >= 45.0:
                return float(rate)
    except Exception:
        pass
    return 120.0


def _extract_sources(text: str) -> List[Tuple[str, str, str, str]]:
    """Extract clickable source links from AI response text."""
    if not text:
        return []
    sources = []

    for url in re.findall(r"(https?://[^\s)\]\"'>]+)", text):
        try:
            domain = url.split("/")[2].replace("www.", "")
            badge = "in" if "linkedin" in domain else ("git" if "github" in domain else "G" if "google" in domain else "web")
            sources.append((badge, domain, "Web Page", url))
        except Exception:
            pass

    for p in re.findall(r"([A-Za-z]:\\[^\s\n\"'<>]+)", text):
        name = Path(p).name or p
        sources.append(("dir", name, "Local File", p))

    return sources


def _detect_action_type(query: str, response: str) -> str:
    """
    Detect what category of action the AI performed based on query + response.
    Returns: 'desktop' | 'web' | 'file' | 'chat'
    """
    combined = (query + " " + response).lower()

    # Desktop / App actions
    desktop_kw = ("open ", "launch", "start ", "run ", "execute", "chrome", "notepad",
                  "explorer", "browser", "app ", "application", "program", "cmd",
                  "terminal", "task manager", "calculator", "spotify", "vscode",
                  "opened", "launched", "started", "running")
    if any(k in combined for k in desktop_kw):
        return "desktop"

    # Web search / knowledge actions
    web_kw = ("search", "found online", "wikipedia", "wiki", "web ", "browse",
              "looked up", "according to", "result", "article", "source",
              "information about", "here's what", "definition", "meaning of")
    if any(k in combined for k in web_kw):
        return "web"

    # File / System actions
    file_kw = ("file", "folder", "directory", "saved", "created", "wrote",
               "deleted", "moved", "copied", "renamed", "path")
    if any(k in combined for k in file_kw):
        return "file"

    # Default: conversational chat
    return "chat"


# ─────────────────────────────────────────────────────────────────────────────
# Glowing Holographic Orb Widget
# ─────────────────────────────────────────────────────────────────────────────

class _GlowingOrb(QWidget):
    """Glowing circular Diamond Orb with pulsing aura (driven by master clock)."""

    def __init__(self, size: int = 18, parent=None):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
        self._theme_color = NEON_CYAN
        self._phase = 0.0

    def set_theme(self, color: QColor):
        self._theme_color = color
        self.update()

    def _tick_step(self, rate_factor: float = 1.0):
        if not self.isVisible():
            return
        self._phase = (self._phase + 0.05 * rate_factor) % (math.pi * 2)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2.0, h / 2.0
        r = min(w, h) / 2.0 - 1.0

        # Outer Pulsing Aura
        pulse = 0.85 + 0.15 * math.sin(self._phase)
        rad_grad = QRadialGradient(QPointF(cx, cy), r)
        c_glow = QColor(self._theme_color)
        c_glow.setAlphaF(0.45 * pulse)
        rad_grad.setColorAt(0.0, c_glow)
        rad_grad.setColorAt(0.7, QColor(self._theme_color.red(), self._theme_color.green(), self._theme_color.blue(), 25))
        rad_grad.setColorAt(1.0, QColor(0, 0, 0, 0))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(rad_grad))
        painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # Core Circle
        core_r = r * 0.72
        core_grad = QLinearGradient(cx, cy - core_r, cx, cy + core_r)
        core_grad.setColorAt(0.0, QColor(255, 255, 255, 220))
        core_grad.setColorAt(1.0, self._theme_color)
        painter.setBrush(QBrush(core_grad))
        painter.setPen(QPen(QColor(255, 255, 255, 180), 0.8))
        painter.drawEllipse(QRectF(cx - core_r, cy - core_r, core_r * 2, core_r * 2))

        # Inner Diamond ◈
        d_size = core_r * 0.52
        d_path = QPainterPath()
        d_path.moveTo(cx, cy - d_size)
        d_path.lineTo(cx + d_size, cy)
        d_path.lineTo(cx, cy + d_size)
        d_path.lineTo(cx - d_size, cy)
        d_path.closeSubpath()

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 240)))
        painter.fillPath(d_path, QBrush(QColor(255, 255, 255, 240)))


# ─────────────────────────────────────────────────────────────────────────────
# Rainbow Multi-Color Audio Spectrum Waveform
# ─────────────────────────────────────────────────────────────────────────────

class _RainbowWaveform(QWidget):
    """Full-Spectrum Rainbow Waveform matching the Holographic UI (driven by master clock)."""

    def __init__(self, bar_count: int = 22, bar_w: float = 2.2, gap: float = 1.8, h: int = 20, parent=None):
        super().__init__(parent)
        self._count = bar_count
        self._bar_w = bar_w
        self._gap = gap
        self._active = False
        self._levels = [0.2] * self._count
        self._target_levels = [0.2] * self._count
        self._phase = 0.0

        total_w = int(self._count * self._bar_w + (self._count - 1) * self._gap + 4)
        self.setFixedSize(total_w, h)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_active(self, active: bool):
        self._active = active
        if not active:
            self._target_levels = [0.2] * self._count
        else:
            self._last_voice_tick = time.time()

    def set_level(self, level: float):
        self._last_voice_tick = time.time()
        # Responsive square-root perceptual scaling
        perceived = min(1.0, max(0.20, math.sqrt(max(0.0, min(1.0, level)))))
        if self._active:
            self._phase += 0.45
            for i in range(self._count):
                center_dist = 1.0 - abs((i - self._count / 2.0) / (self._count / 2.0))
                base = perceived * (0.35 + 0.65 * center_dist * abs(math.sin(i * 0.50 + self._phase)))
                noise = random.uniform(-0.03, 0.03)
                self._target_levels[i] = max(0.15, min(1.0, base + noise))

    def _tick_step(self, rate_factor: float = 1.0):
        if not self.isVisible():
            return

        changed = False
        rate = 0.45 * rate_factor
        now = time.time()

        # If active and microphone level is quiescent, generate an organic dynamic wave
        if self._active and (now - getattr(self, "_last_voice_tick", 0) > 0.12):
            self._phase += 0.22 * rate_factor
            for i in range(self._count):
                center_dist = 1.0 - abs((i - self._count / 2.0) / (self._count / 2.0))
                synth = 0.25 + 0.50 * center_dist * abs(math.sin(i * 0.42 + self._phase))
                self._target_levels[i] = max(0.15, min(1.0, synth))

        for i in range(self._count):
            diff = self._target_levels[i] - self._levels[i]
            if abs(diff) > 0.002:
                self._levels[i] += diff * rate
                changed = True

        if not self._active:
            self._phase += 0.05 * rate_factor
            for i in range(self._count):
                self._levels[i] = 0.15 + 0.10 * math.sin(i * 0.35 + self._phase)
            changed = True

        if changed:
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        h = self.height()
        cy = h / 2.0

        colors = [
            QColor(168, 85, 247),  # Violet
            QColor(236, 72, 153),  # Pink
            QColor(249, 115, 22),  # Orange
            QColor(234, 179, 8),   # Yellow
            QColor(16, 185, 129),  # Green
            QColor(0, 240, 255),   # Cyan
        ]

        for i in range(self._count):
            x = 2 + i * (self._bar_w + self._gap)
            t = i / max(1, self._count - 1)

            idx = t * (len(colors) - 1)
            i0 = int(idx)
            i1 = min(len(colors) - 1, i0 + 1)
            frac = idx - i0
            c0, c1 = colors[i0], colors[i1]
            r = int(c0.red() + frac * (c1.red() - c0.red()))
            g = int(c0.green() + frac * (c1.green() - c0.green()))
            b = int(c0.blue() + frac * (c1.blue() - c0.blue()))
            bar_color = QColor(r, g, b, 240)

            lvl = self._levels[i]
            bar_h = max(3.0, lvl * (h - 2))
            bar_rect = QRectF(x, cy - bar_h / 2, self._bar_w, bar_h)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(bar_color))
            painter.drawRoundedRect(bar_rect, 1.0, 1.0)


# ─────────────────────────────────────────────────────────────────────────────
# Expanded Panel (Seamless Live Backend Linked)
# ─────────────────────────────────────────────────────────────────────────────

class _ExpandedPanel(QWidget):
    """Compact Holographic Command Center (500×240px) linked to Backend."""

    mode_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent_overlay = parent
        self._has_real_messages = False
        self._has_actions = False
        self._has_sources = False
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 10)
        root.setSpacing(8)

        # ── Header ──
        header = QHBoxLayout()
        header.setSpacing(6)

        self._orb = _GlowingOrb(18)
        header.addWidget(self._orb)

        t_label = QLabel("AuraAI")
        t_label.setStyleSheet(f"color:#ffffff; font-family:{FONT_SANS}; font-size:12px; font-weight:800; letter-spacing:1px;")
        header.addWidget(t_label)

        header.addStretch()

        self._online_badge = QLabel("● Online")
        self._online_badge.setStyleSheet(f"color:#10b981; font-family:{FONT_SANS}; font-size:9px; font-weight:700; background:rgba(16,185,129,0.12); border:1px solid rgba(16,185,129,0.3); border-radius:6px; padding:2px 8px;")
        header.addWidget(self._online_badge)

        self._settings_btn = QPushButton("⚙")
        self._settings_btn.setFixedSize(22, 22)
        self._settings_btn.setStyleSheet("QPushButton{color:#94a3b8; background:rgba(15,23,42,0.6); border:1px solid rgba(255,255,255,0.1); border-radius:5px; font-size:10px;} QPushButton:hover{color:#fff; border-color:#00f0ff;}")
        self._settings_btn.clicked.connect(self._open_main_gui)
        header.addWidget(self._settings_btn)

        self._close_btn = QPushButton("×")
        self._close_btn.setFixedSize(22, 22)
        self._close_btn.setStyleSheet("QPushButton{color:#94a3b8; background:transparent; border:none; font-size:15px;} QPushButton:hover{color:#fff;}")
        self._close_btn.clicked.connect(self._close_panel)
        header.addWidget(self._close_btn)
        root.addLayout(header)

        # ── 1. Live Transcript Card (Full Width & Maximum Vertical Height) ──
        col1 = QFrame()
        col1.setStyleSheet("QFrame{background:rgba(8,12,24,0.75); border:1px solid rgba(59,130,246,0.25); border-radius:8px;}")
        c1_lay = QVBoxLayout(col1)
        c1_lay.setContentsMargins(6, 4, 6, 4)
        c1_lay.setSpacing(2)

        c1_head = QLabel("∿  Transcript")
        c1_head.setStyleSheet(f"color:#60a5fa; font-family:{FONT_SANS}; font-size:9px; font-weight:800; text-transform:uppercase;")
        c1_lay.addWidget(c1_head)

        self._transcript_scroll = QScrollArea()
        self._transcript_scroll.setWidgetResizable(True)
        self._transcript_scroll.setStyleSheet("background:transparent; border:none;")
        self._transcript_content = QWidget()
        self._transcript_layout = QVBoxLayout(self._transcript_content)
        self._transcript_layout.setContentsMargins(0, 0, 0, 0)
        self._transcript_layout.setSpacing(2)

        self._placeholder_lbl = QLabel("Say a command or hold Space...")
        self._placeholder_lbl.setStyleSheet("color:#64748b; font-size:9px; font-family:'Segoe UI';")
        self._transcript_layout.addWidget(self._placeholder_lbl)

        self._transcript_scroll.setWidget(self._transcript_content)
        c1_lay.addWidget(self._transcript_scroll, 1)
        root.addWidget(col1, 1)

        # ── 2. Compact Sources Bar (Placed Directly Below Transcript, Hidden by Default) ──
        self._sources_bar = QFrame()
        self._sources_bar.setStyleSheet("QFrame{background:rgba(8,12,24,0.75); border:1px solid rgba(0,240,255,0.25); border-radius:6px;}")
        s_bar_lay = QHBoxLayout(self._sources_bar)
        s_bar_lay.setContentsMargins(6, 2, 6, 2)
        s_bar_lay.setSpacing(6)

        c3_head = QLabel("⬡ Sources:")
        c3_head.setStyleSheet(f"color:#00f0ff; font-family:{FONT_SANS}; font-size:9px; font-weight:800; text-transform:uppercase;")
        s_bar_lay.addWidget(c3_head)

        self._sources_box = QHBoxLayout()
        self._sources_box.setSpacing(4)
        s_bar_lay.addLayout(self._sources_box, 1)
        s_bar_lay.addStretch()

        self._sources_bar.setVisible(False)
        root.addWidget(self._sources_bar)

        # ── 3. Bottom Command Bar with Focus Badge & Rainbow Waveform Audio Visualizer ──
        bottom_bar = QFrame()
        bottom_bar.setStyleSheet("QFrame{background:rgba(6,10,20,0.9); border:1px solid rgba(0,240,255,0.3); border-radius:8px;}")
        b_lay = QHBoxLayout(bottom_bar)
        b_lay.setContentsMargins(8, 2, 8, 2)
        b_lay.setSpacing(6)

        mic_lbl = QLabel("🎙")
        mic_lbl.setStyleSheet("font-size:12px; color:#00f0ff;")
        b_lay.addWidget(mic_lbl)

        self._input_field = QLineEdit()
        self._input_field.setPlaceholderText("Ask anything… · Hold Space")
        self._input_field.setFixedHeight(24)
        self._input_field.setStyleSheet(f"QLineEdit{{color:#ffffff; background:transparent; border:none; font-family:{FONT_SANS}; font-size:10px;}}")
        self._input_field.returnPressed.connect(self._on_bottom_submit)
        b_lay.addWidget(self._input_field, 1)

        self._focus_badge = QLabel("Focus: Active")
        self._focus_badge.setStyleSheet(f"QLabel{{color:#00f0ff; background:rgba(0,240,255,0.12); border:1px solid rgba(0,240,255,0.35); border-radius:4px; font-family:{FONT_SANS}; font-size:9px; font-weight:700; padding:2px 6px;}}")
        b_lay.addWidget(self._focus_badge)

        self._bottom_wave = _RainbowWaveform(bar_count=18, bar_w=1.8, gap=1.8, h=16)
        b_lay.addWidget(self._bottom_wave)

        root.addWidget(bottom_bar)

    def _clear_box(self, box):
        while box.count():
            item = box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def clear_panel(self):
        """Reset the panel to a clean slate for a new query."""
        self._clear_box(self._sources_box)
        self._sources_bar.setVisible(False)
        self._has_sources = False

    def populate_result(self, query: str, response: str):
        """Populate the expanded panel with clickable source links if real sources exist."""
        sources = _extract_sources(response)
        if sources:
            self._clear_box(self._sources_box)
            for badge, title, _, url in sources[:4]:
                btn = self._make_source_card(badge, title, url)
                self._sources_box.addWidget(btn)
            self._sources_bar.setVisible(True)
            self._has_sources = True
        else:
            self._sources_bar.setVisible(False)
            self._has_sources = False

    def _tick_step(self, rate_factor: float = 1.0):
        if not self.isVisible():
            return
        if hasattr(self, "_orb") and self._orb:
            self._orb._tick_step(rate_factor)
        if hasattr(self, "_bottom_wave") and self._bottom_wave:
            self._bottom_wave._tick_step(rate_factor)

    def _make_action_card(self, icon: str, label: str, accent: str, handler) -> QPushButton:
        btn = QPushButton(f"{icon}  {label}")
        btn.setFixedHeight(24)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                padding-left: 6px;
                color: #e2e8f0;
                background: rgba(15, 23, 42, 0.8);
                border: 1px solid {accent}44;
                border-radius: 5px;
                font-family: {FONT_SANS};
                font-size: 9px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {accent}22;
                border-color: {accent};
                color: #ffffff;
            }}
        """)
        if handler:
            btn.clicked.connect(handler)
        return btn

    def _make_source_card(self, badge: str, title: str, url: str) -> QPushButton:
        btn = QPushButton(f"[{badge}]  {title[:14]} ↗")
        btn.setFixedHeight(24)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                padding: 0 5px;
                color: #cbd5e1;
                background: rgba(15, 23, 42, 0.6);
                border: 1px solid rgba(0, 240, 255, 0.15);
                border-radius: 5px;
                font-family: {FONT_SANS};
                font-size: 9px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: rgba(0, 240, 255, 0.15);
                border-color: #00f0ff;
                color: #ffffff;
            }}
        """)
        if url:
            if url.startswith("http://") or url.startswith("https://"):
                btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
            else:
                # Non-blocking file launch on click (no synchronous disk check in UI build path)
                def _open_file_target():
                    try:
                        if os.path.exists(url):
                            os.startfile(url)
                    except Exception as e:
                        logger.debug(f"Source file open failed: {e}")
                btn.clicked.connect(_open_file_target)
        return btn

    def add_transcript_msg(self, sender: str, msg: str, is_user: bool):
        # Prevent back-to-back duplicate rendering of the exact same message
        if getattr(self, "_last_added_msg", None) == (sender, msg):
            return
        self._last_added_msg = (sender, msg)

        if not self._has_real_messages:
            self._placeholder_lbl.setVisible(False)
            self._has_real_messages = True

        row = QHBoxLayout()
        row.setSpacing(4)
        s_lbl = QLabel(sender)
        s_lbl.setStyleSheet(f"color:{'#00f0ff' if is_user else '#a855f7'}; font-family:{FONT_SANS}; font-size:9px; font-weight:700;")
        m_lbl = QLabel(msg)
        m_lbl.setWordWrap(True)
        m_lbl.setStyleSheet(f"color:#f1f5f9; font-family:{FONT_SANS}; font-size:9px;")

        row.addWidget(s_lbl)
        row.addWidget(m_lbl, 1)
        self._transcript_layout.addLayout(row)

    def _open_main_gui(self):
        import subprocess
        root = Path(__file__).resolve().parents[3]
        py = root / ".venv" / "Scripts" / "python.exe"
        subprocess.Popen([str(py), str(root / "main.py"), "--gui"], cwd=str(root))

    def _open_spotlight_chat(self):
        import subprocess
        root = Path(__file__).resolve().parents[3]
        py = root / ".venv" / "Scripts" / "python.exe"
        subprocess.Popen([str(py), str(root / "run_chat_window.py")], cwd=str(root))

    def _close_panel(self):
        if self._parent_overlay:
            self._parent_overlay.set_state(NotchState.IDLE)
        elif self.parent():
            self.parent().set_state(NotchState.IDLE)

    def _on_bottom_submit(self):
        text = self._input_field.text().strip()
        if not text:
            return
        self._input_field.clear()
        if self._parent_overlay and hasattr(self._parent_overlay, "_execute_command"):
            self._parent_overlay._execute_command(text)


# ─────────────────────────────────────────────────────────────────────────────
# Main Holographic Voice Notch Overlay Widget (Always-on-Top Cyber HUD)
# ─────────────────────────────────────────────────────────────────────────────

class VoiceNotchOverlay(QWidget):
    """
    Ultra-Sleek Always-on-Top Cybernetic Dynamic Island Notch HUD.
    """

    mode_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VoiceNotchOverlay")
        self.setWindowTitle("AuraAI Voice Notch")

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

        self._state = NotchState.IDLE
        self._is_hovered = False
        self._current_query = ""
        self._current_response = ""
        self._progress_val = 0.0
        self._has_interacted_voice = False
        self._has_last_result = False  # True = hover can re-show last result

        # Debounced Hover Timers (180ms hover debounce, 250ms collapse)
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(180)
        self._hover_timer.timeout.connect(self._expand_from_hover)

        self._collapse_timer = QTimer(self)
        self._collapse_timer.setSingleShot(True)
        self._collapse_timer.setInterval(250)
        self._collapse_timer.timeout.connect(self._collapse_from_hover)

        # Result Auto-Collapse Timer (6s after showing result)
        self._result_collapse_timer = QTimer(self)
        self._result_collapse_timer.setSingleShot(True)
        self._result_collapse_timer.setInterval(6000)
        self._result_collapse_timer.timeout.connect(self._collapse_result)

        # Single Reusable 30s Watchdog Timer for PROCESSING state
        self._proc_timeout = QTimer(self)
        self._proc_timeout.setSingleShot(True)
        self._proc_timeout.setInterval(30000)
        self._proc_timeout.timeout.connect(self._on_proc_timeout)

        # Single Master 60 FPS Animation Clock (~16ms) driving all active widgets
        self._hz = get_display_refresh_rate()
        self._master_anim_timer = QTimer(self)
        self._master_anim_timer.setInterval(max(16, int(1000.0 / min(60.0, self._hz))))
        self._master_anim_timer.timeout.connect(self._on_master_anim_tick)
        self._master_anim_timer.start()

        self._setup_ui()
        self._position_at_top()
        self._connect_signals()

    # ─────────────────────────────────────────────────────────────────────────
    # UI Setup
    # ─────────────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)
        self._root_layout.setSizeConstraint(QLayout.SetNoConstraint)

        self._band = QWidget()
        self._band.setStyleSheet("background: transparent;")
        band_layout = QVBoxLayout(self._band)
        band_layout.setContentsMargins(8, 0, 8, 0)
        band_layout.setSpacing(0)

        # Status Stack
        self._status_stack = QStackedWidget()
        self._status_stack.setStyleSheet("background: transparent; border: none;")

        # ── State 1: IDLE (Futuristic Seamless Cyber Pill) ──
        idle_page = QWidget()
        idle_layout = QHBoxLayout(idle_page)
        idle_layout.setContentsMargins(0, 0, 0, 0)
        idle_layout.setSpacing(8)

        # Left: Pulsing Orb + Luminous Brand
        self._idle_orb = _GlowingOrb(18)
        self._idle_orb.set_theme(NEON_CYAN)
        idle_layout.addWidget(self._idle_orb)

        self._idle_title = QLabel("AuraAI")
        self._idle_title.setStyleSheet(f"""
            QLabel {{
                color: #ffffff;
                font-family: {FONT_SANS};
                font-size: 11px;
                font-weight: 800;
                letter-spacing: 1.2px;
                background: transparent;
            }}
        """)
        idle_layout.addWidget(self._idle_title)

        # Center: Breathing Mini Equalizer Bars
        self._idle_spectrum = _RainbowWaveform(bar_count=6, bar_w=1.8, gap=1.8, h=14)
        self._idle_spectrum.set_active(False)
        idle_layout.addWidget(self._idle_spectrum)

        idle_layout.addStretch(1)

        # Right: Seamless Status (Clean Emerald Green Text, No Background Box)
        idle_status_box = QHBoxLayout()
        idle_status_box.setSpacing(4)

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet("color: #10b981; font-size: 7px; background: transparent; border: none;")
        idle_status_box.addWidget(self._status_dot)

        self._idle_status = QLabel("STANDBY")
        self._idle_status.setStyleSheet(f"""
            QLabel {{
                color: #10b981;
                font-family: {FONT_SANS};
                font-size: 9px;
                font-weight: 800;
                letter-spacing: 1px;
                background: transparent;
                border: none;
            }}
        """)
        idle_status_box.addWidget(self._idle_status)

        idle_layout.addLayout(idle_status_box)
        self._status_stack.addWidget(idle_page)

        # ── State 2: LISTENING (Rainbow Waveform from Image 2) ──
        listen_page = QWidget()
        listen_layout = QHBoxLayout(listen_page)
        listen_layout.setContentsMargins(0, 0, 0, 0)
        listen_layout.setSpacing(6)

        self._listen_orb = _GlowingOrb(20)
        self._listen_orb.set_theme(NEON_VIOLET)
        listen_layout.addWidget(self._listen_orb)

        self._listen_text = QLabel("Listening...")
        self._listen_text.setStyleSheet(f"color: #ffffff; font-family: {FONT_SANS}; font-size: 11px; font-weight: 600;")
        listen_layout.addWidget(self._listen_text)

        # Centered Rainbow Waveform
        self._rainbow_wave = _RainbowWaveform(bar_count=22, bar_w=2.2, gap=1.8, h=20)
        self._rainbow_wave.set_active(True)
        listen_layout.addWidget(self._rainbow_wave, 1)

        self._status_stack.addWidget(listen_page)

        # ── State 3: PROCESSING (Thinking from Image 3) ──
        proc_page = QWidget()
        proc_layout = QHBoxLayout(proc_page)
        proc_layout.setContentsMargins(2, 4, 2, 4)
        proc_layout.setSpacing(10)

        self._proc_orb = _GlowingOrb(24)
        self._proc_orb.set_theme(NEON_BLUE)
        proc_layout.addWidget(self._proc_orb)

        proc_mid = QVBoxLayout()
        proc_mid.setSpacing(3)

        self._proc_title = QLabel("Processing your request...")
        self._proc_title.setStyleSheet(f"color: #ffffff; font-family: {FONT_SANS}; font-size: 11px; font-weight: 700;")
        proc_mid.addWidget(self._proc_title)

        self._proc_bullets = QLabel("Analyzing  •  Planning  •  Executing")
        self._proc_bullets.setStyleSheet(f"color: #94a3b8; font-family: {FONT_SANS}; font-size: 9px; font-weight: 500;")
        proc_mid.addWidget(self._proc_bullets)

        self._proc_rail = QFrame()
        self._proc_rail.setFixedHeight(3)
        self._proc_rail.setStyleSheet("background: rgba(255, 255, 255, 0.1); border-radius: 1.5px;")
        proc_mid.addWidget(self._proc_rail)

        proc_layout.addLayout(proc_mid, 1)

        self._proc_brain = QLabel("🧠")
        self._proc_brain.setAlignment(Qt.AlignCenter)
        self._proc_brain.setFixedSize(32, 32)
        self._proc_brain.setStyleSheet("QLabel{font-size:16px; background:radial-gradient(circle, rgba(168,85,247,0.3) 0%, rgba(0,240,255,0.1) 60%, transparent 100%); border:1px solid rgba(0,240,255,0.4); border-radius:16px;}")
        proc_layout.addWidget(self._proc_brain)

        self._status_stack.addWidget(proc_page)

        # ── State 4: SUCCESS (Completed from Image 4) ──
        succ_page = QWidget()
        succ_layout = QHBoxLayout(succ_page)
        succ_layout.setContentsMargins(2, 4, 2, 4)
        succ_layout.setSpacing(10)

        self._succ_orb = _GlowingOrb(24)
        self._succ_orb.set_theme(NEON_EMERALD)
        succ_layout.addWidget(self._succ_orb)

        succ_mid = QVBoxLayout()
        succ_mid.setSpacing(2)

        self._succ_title = QLabel("Task Completed Successfully")
        self._succ_title.setStyleSheet(f"color: #10b981; font-family: {FONT_SANS}; font-size: 11px; font-weight: 700;")
        succ_mid.addWidget(self._succ_title)

        self._succ_query = QLabel('"Task executed"')
        self._succ_query.setStyleSheet(f"color: #f1f5f9; font-family: {FONT_SANS}; font-size: 10px; font-weight: 600;")
        succ_mid.addWidget(self._succ_query)

        self._succ_meta = QLabel("✓ Action completed  ·  ⏱ 1.8s")
        self._succ_meta.setStyleSheet(f"color: #34d399; font-family: {FONT_SANS}; font-size: 9px; font-weight: 600;")
        succ_mid.addWidget(self._succ_meta)

        succ_layout.addLayout(succ_mid, 1)

        self._succ_hex = QLabel("✓")
        self._succ_hex.setAlignment(Qt.AlignCenter)
        self._succ_hex.setFixedSize(32, 32)
        self._succ_hex.setStyleSheet("QLabel{color:#10b981; font-size:16px; font-weight:900; background:rgba(16,185,129,0.15); border:1.5px solid #10b981; border-radius:8px;}")
        succ_layout.addWidget(self._succ_hex)

        self._status_stack.addWidget(succ_page)

        band_layout.addWidget(self._status_stack)
        self._root_layout.addWidget(self._band)

        # ── State 5: EXPANDED (Full Seamless Holographic Terminal) ──
        self._expanded_panel = _ExpandedPanel(self)
        self._expanded_panel.setVisible(False)
        self._root_layout.addWidget(self._expanded_panel)

    # ─────────────────────────────────────────────────────────────────────────
    # Positioning & Smooth Hover Expansion
    # ─────────────────────────────────────────────────────────────────────────

    def _position_at_top(self):
        screen = QApplication.primaryScreen()
        if not screen:
            return
        sg = screen.availableGeometry()
        w = IDLE_W if self._state == NotchState.IDLE else self.width()
        h = IDLE_H if self._state == NotchState.IDLE else self.height()
        x = sg.left() + (sg.width() - w) // 2
        y = max(6, sg.top() + 4)  # Ensure clearly visible below top taskbar
        self.setGeometry(x, y, w, h)

    def _on_master_anim_tick(self):
        if not self.isVisible():
            return
        try:
            # Tick ONLY active widgets based on current state (sleeps hidden state pages)
            if self._state == NotchState.IDLE:
                if hasattr(self, "_idle_orb") and self._idle_orb.isVisible():
                    try:
                        self._idle_orb._tick_step()
                    except Exception:
                        pass
                if hasattr(self, "_idle_spectrum") and self._idle_spectrum.isVisible():
                    try:
                        self._idle_spectrum._tick_step()
                    except Exception:
                        pass
            elif self._state == NotchState.LISTENING:
                if hasattr(self, "_listen_orb") and self._listen_orb.isVisible():
                    try:
                        self._listen_orb._tick_step()
                    except Exception:
                        pass
                if hasattr(self, "_rainbow_wave") and self._rainbow_wave.isVisible():
                    try:
                        self._rainbow_wave._tick_step()
                    except Exception:
                        pass
            elif self._state == NotchState.PROCESSING:
                if hasattr(self, "_proc_orb") and self._proc_orb.isVisible():
                    try:
                        self._proc_orb._tick_step()
                    except Exception:
                        pass
                try:
                    self._tick_proc_progress()
                except Exception:
                    pass
            elif self._state == NotchState.SUCCESS:
                if hasattr(self, "_succ_orb") and self._succ_orb.isVisible():
                    try:
                        self._succ_orb._tick_step()
                    except Exception:
                        pass
            elif self._state == NotchState.EXPANDED:
                if hasattr(self, "_expanded_panel") and self._expanded_panel.isVisible():
                    try:
                        self._expanded_panel._tick_step()
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"[VoiceNotchOverlay] Master animation clock tick error: {e}")

    def enterEvent(self, event):
        self._is_hovered = True
        self._collapse_timer.stop()
        if self._state == NotchState.IDLE:
            self._hover_timer.start(180)
        self.update()

    def leaveEvent(self, event):
        self._is_hovered = False
        self._hover_timer.stop()
        if self._state == NotchState.EXPANDED:
            self._collapse_timer.start(250)
        self.update()

    def _expand_from_hover(self):
        if self._is_hovered and self._state == NotchState.IDLE:
            self.set_state(NotchState.EXPANDED)

    def _collapse_from_hover(self):
        if not self._is_hovered and self._state == NotchState.EXPANDED:
            self.set_state(NotchState.IDLE)

    def _tick_proc_progress(self):
        self._progress_val = (self._progress_val + 0.04) % 1.0
        self.update()

    def _collapse_result(self):
        """Auto-collapse expanded result after 6s. Hover can re-open it."""
        if self._state == NotchState.EXPANDED and not self._is_hovered:
            self._has_last_result = True
            self._mark_ready()
            self.set_state(NotchState.IDLE)

    def _mark_ready(self):
        self._has_interacted_voice = True
        self._status_dot.setStyleSheet("color: #10b981; font-size: 7px; background: transparent; border: none;")
        self._idle_status.setText("READY")
        self._idle_status.setStyleSheet(f"""
            QLabel {{
                color: #10b981;
                font-family: {FONT_SANS};
                font-size: 9px;
                font-weight: 800;
                letter-spacing: 1px;
                background: transparent;
                border: none;
            }}
        """)

    # ─────────────────────────────────────────────────────────────────────────
    # Painting (Vibrant Holographic Rounded-Rectangle with Tactical Ticks)
    # ─────────────────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        rect = self.rect().adjusted(1, 1, -1, -1)
        rad = NOTCH_RADIUS
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), rad, rad)

        # 1. Base Gradient
        bg_grad = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
        if self._is_hovered:
            bg_grad.setColorAt(0.0, BG_HOVER_TOP)
            bg_grad.setColorAt(1.0, BG_HOVER_BOTTOM)
        else:
            bg_grad.setColorAt(0.0, BG_DARK_TOP)
            bg_grad.setColorAt(1.0, BG_DARK_BOTTOM)
        painter.fillPath(path, QBrush(bg_grad))

        # 2. Electric Blue Wave Sheen
        wave_grad = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
        wave_grad.setColorAt(0.0, QColor(0, 180, 255, 30))
        wave_grad.setColorAt(0.5, QColor(59, 130, 246, 12))
        wave_grad.setColorAt(1.0, QColor(168, 85, 247, 25))
        painter.fillPath(path, QBrush(wave_grad))

        # 3. Top Specular Sheen
        sheen_h = min(12.0, rect.height() * 0.35)
        sheen_grad = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.top() + sheen_h)
        sheen_grad.setColorAt(0.0, QColor(255, 255, 255, 50))
        sheen_grad.setColorAt(0.6, QColor(255, 255, 255, 10))
        sheen_grad.setColorAt(1.0, QColor(255, 255, 255, 0))

        sheen_path = QPainterPath()
        sheen_path.addRect(QRectF(rect.left(), rect.top(), rect.width(), sheen_h))
        painter.fillPath(sheen_path.intersected(path), QBrush(sheen_grad))

        # 4. Multi-Color Perimeter Border
        rim_grad = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
        if self._state == NotchState.LISTENING:
            rim_grad.setColorAt(0.0, NEON_VIOLET)
            rim_grad.setColorAt(0.5, NEON_PINK)
            rim_grad.setColorAt(1.0, NEON_CYAN)
            pen = QPen(QBrush(rim_grad), 1.4)
        elif self._state == NotchState.PROCESSING:
            rim_grad.setColorAt(0.0, NEON_CYAN)
            rim_grad.setColorAt(1.0, NEON_BLUE)
            pen = QPen(QBrush(rim_grad), 1.4)
        elif self._state == NotchState.SUCCESS:
            rim_grad.setColorAt(0.0, NEON_EMERALD)
            rim_grad.setColorAt(1.0, NEON_CYAN)
            pen = QPen(QBrush(rim_grad), 1.4)
        elif self._is_hovered:
            rim_grad.setColorAt(0.0, NEON_CYAN)
            rim_grad.setColorAt(1.0, NEON_VIOLET)
            pen = QPen(QBrush(rim_grad), 1.4)
        else:
            rim_grad.setColorAt(0.0, QColor(0, 240, 255, 140))
            rim_grad.setColorAt(0.5, QColor(59, 130, 246, 80))
            rim_grad.setColorAt(1.0, QColor(168, 85, 247, 100))
            pen = QPen(QBrush(rim_grad), 1.2)

        painter.strokePath(path, pen)

        # 5. Tactical Corner Accents
        corner_color = NEON_EMERALD if self._state == NotchState.SUCCESS else NEON_CYAN
        self._draw_tactical_corners(painter, rect, corner_color)

        # 6. Animated Progress Rail for Processing State
        if self._state == NotchState.PROCESSING:
            self._draw_progress_beam(painter)

        painter.end()

    def _draw_tactical_corners(self, painter: QPainter, rect: QRect, color: QColor):
        blen = 5.0
        cpen = QPen(color, 1.4)
        painter.setPen(cpen)
        painter.drawLine(rect.left() + 5, rect.top() + 2, int(rect.left() + 5 + blen), rect.top() + 2)
        painter.drawLine(int(rect.right() - 5 - blen), rect.top() + 2, rect.right() - 5, rect.top() + 2)

    def _draw_progress_beam(self, painter: QPainter):
        if hasattr(self, "_proc_rail") and self._proc_rail.isVisible():
            r = self._proc_rail.geometry()
            # Use mapToGlobal → mapFromGlobal to safely traverse any widget nesting depth
            global_top_left = self._proc_rail.mapToGlobal(r.topLeft() - r.topLeft())
            local_top_left = self.mapFromGlobal(global_top_left)
            rail_rect = QRectF(local_top_left.x(), local_top_left.y(), r.width(), r.height())

            beam_w = rail_rect.width() * 0.4
            beam_x = rail_rect.left() + (rail_rect.width() - beam_w) * self._progress_val
            beam_rect = QRectF(beam_x, rail_rect.top(), beam_w, rail_rect.height())

            b_grad = QLinearGradient(beam_rect.left(), beam_rect.top(), beam_rect.right(), beam_rect.top())
            b_grad.setColorAt(0.0, QColor(0, 240, 255, 0))
            b_grad.setColorAt(0.5, NEON_CYAN)
            b_grad.setColorAt(1.0, QColor(168, 85, 247, 0))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(b_grad))
            painter.drawRoundedRect(beam_rect, 1.5, 1.5)

    # ─────────────────────────────────────────────────────────────────────────
    # State Machine & Morphing
    # ─────────────────────────────────────────────────────────────────────────

    def set_state(self, state: NotchState, text: str = ""):
        if state == self._state and state != NotchState.PROCESSING and not text:
            return

        old_state = self._state
        self._state = state

        if state == NotchState.IDLE:
            self._proc_timeout.stop()
            target_w, target_h = IDLE_W, IDLE_H
            self._band.setVisible(True)
            self._status_stack.setCurrentIndex(0)
            self._rainbow_wave.set_active(False)
            self._expanded_panel.setVisible(False)
            self._result_collapse_timer.stop()

        elif state == NotchState.LISTENING:
            self._proc_timeout.stop()
            target_w, target_h = LISTENING_W, LISTENING_H
            self._band.setVisible(True)
            self._status_stack.setCurrentIndex(1)
            self._rainbow_wave.set_active(True)
            self._listen_text.setText(text if text else "Listening...")
            self._expanded_panel.setVisible(False)
            self._result_collapse_timer.stop()
            self._has_last_result = False

        elif state == NotchState.PROCESSING:
            target_w, target_h = PROCESSING_W, PROCESSING_H
            if text:
                self._proc_title.setText(text)
            self._band.setVisible(True)
            self._status_stack.setCurrentIndex(2)
            self._rainbow_wave.set_active(False)
            self._proc_timeout.start()
            self._expanded_panel.setVisible(False)
            self._result_collapse_timer.stop()

        elif state == NotchState.SUCCESS:
            self._proc_timeout.stop()
            target_w, target_h = SUCCESS_W, SUCCESS_H
            if text:
                self._succ_query.setText(f'"{text[:30]}"')
            self._band.setVisible(True)
            self._status_stack.setCurrentIndex(3)
            self._rainbow_wave.set_active(False)
            self._expanded_panel.setVisible(False)

        elif state == NotchState.EXPANDED:
            self._proc_timeout.stop()
            target_w, target_h = EXPANDED_W, EXPANDED_H
            self._band.setVisible(False)
            self._expanded_panel.setVisible(True)
            self._rainbow_wave.set_active(False)
            if not self._is_hovered:
                self._result_collapse_timer.start()

        else:
            return

        screen = QApplication.primaryScreen()
        if not screen:
            return
        sg = screen.availableGeometry()

        target_x = sg.left() + (sg.width() - target_w) // 2
        target_y = sg.top()  # Flush directly against the taskbar/top edge

        target_geom = QRect(target_x, target_y, target_w, target_h)

        if hasattr(self, "_morph_anim") and self._morph_anim is not None:
            self._morph_anim.stop()

        self._morph_anim = QPropertyAnimation(self, b"geometry")
        self._morph_anim.setDuration(MORPH_DURATION_MS)
        self._morph_anim.setStartValue(self.geometry())
        self._morph_anim.setEndValue(target_geom)
        self._morph_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._morph_anim.valueChanged.connect(lambda: self.update())
        self._morph_anim.start()

        self.update()

    def _execute_command(self, text: str):
        self._current_query = text
        self._has_last_result = False
        self._expanded_panel.clear_panel()
        self._expanded_panel.add_transcript_msg("You:", text, True)
        self._proc_title.setText("Processing your request...")
        self.set_state(NotchState.PROCESSING, "Processing your request...")
        logger.info(f"[CHAT] You: {text}")

        # Update live Focus Thread badge chip
        try:
            from core.aura_core import AuraCore
            core = AuraCore.get_instance()
            if core and hasattr(core, "focus_manager") and core.focus_manager:
                curr = core.focus_manager.get_current()
                task_name = curr.task_id if curr else "Active"
                self._expanded_panel._focus_badge.setText(f"Focus: {task_name}")
        except Exception:
            pass

        # Cancel any previous in-flight task output
        if hasattr(self, "_active_cmd_cancel_event") and self._active_cmd_cancel_event is not None:
            self._active_cmd_cancel_event.set()

        cancel_event = threading.Event()
        self._active_cmd_cancel_event = cancel_event

        # Reuse existing single watchdog timer instance (never re-instantiate QTimer)
        if hasattr(self, "_proc_timeout") and self._proc_timeout is not None:
            self._proc_timeout.stop()
            self._proc_timeout.setInterval(60000)  # Extended to 60s for autonomous goals
            self._proc_timeout.start()

        import threading
        def _run_cmd():
            try:
                import asyncio
                core = None
                try:
                    from core.aura_core import AuraCore
                    core = AuraCore.get_instance()
                except Exception:
                    pass

                reply_text = ""
                loop = asyncio.new_event_loop()
                try:
                    if core is not None and hasattr(core, "get_ai_response"):
                        reply_text = loop.run_until_complete(core.get_ai_response(text, enable_tools=True))
                    elif core is not None and hasattr(core, "process_request"):
                        reply_text = loop.run_until_complete(core.process_request(text))
                    else:
                        reply_text = "Backend is initializing. Please try again in a moment."
                finally:
                    loop.close()

                if cancel_event.is_set():
                    logger.info("[VoiceNotchOverlay] Suppressing late response for canceled in-flight command.")
                    return

                from gui.signals import app_signals
                final_content = reply_text if reply_text else "Done."
                app_signals.message_received.emit("AuraAI", final_content, False)
            except Exception as e:
                logger.error(f"[VoiceNotchOverlay] Error running command: {e}")
                if not cancel_event.is_set():
                    try:
                        from gui.signals import app_signals
                        app_signals.message_received.emit("AuraAI", f"Error: {e}", False)
                    except Exception:
                        pass
        threading.Thread(target=_run_cmd, daemon=True).start()

    def _on_proc_timeout(self):
        """Safety net: recover from stuck PROCESSING state."""
        if self._state == NotchState.PROCESSING:
            logger.warning("[VoiceNotchOverlay] Processing timed out, canceling in-flight UI output.")
            if hasattr(self, "_active_cmd_cancel_event") and self._active_cmd_cancel_event is not None:
                self._active_cmd_cancel_event.set()
            self._expanded_panel.add_transcript_msg("AuraAI:", "Request timed out.", False)
            self._has_last_result = True
            self._mark_ready()
            self.set_state(NotchState.EXPANDED)

    # ─────────────────────────────────────────────────────────────────────────
    # Mouse & Keyboard Events
    # ─────────────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
            event.accept()
        elif event.button() == Qt.MouseButton.LeftButton:
            # Clicking the notch triggers active voice listening immediately
            vl = getattr(self, "_voice_loop", None)
            if vl and hasattr(vl, "trigger_wake_detected"):
                vl.trigger_wake_detected()
            elif getattr(self, "_voice_manager", None):
                try:
                    self._voice_manager._start_active_listening()
                except Exception:
                    pass
            event.accept()
        else:
            super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            # Unconditional manual barge-in: stop TTS immediately if speaking
            try:
                vm = getattr(self, "_voice_manager", None)
                if vm and hasattr(vm, "tts_manager"):
                    vm.tts_manager.stop()
            except Exception:
                pass
            # Dismiss listening / processing / expanded -> go back to IDLE
            if self._state in (NotchState.EXPANDED, NotchState.LISTENING, NotchState.PROCESSING, NotchState.SUCCESS):
                self.set_state(NotchState.IDLE)
            # NEVER call self.close() on Escape!
            event.accept()
        elif event.key() == Qt.Key.Key_Space:
            if not event.isAutoRepeat():
                # Unconditional manual barge-in: stop TTS if speaking, and trigger active listening
                try:
                    vm = getattr(self, "_voice_manager", None)
                    if vm and hasattr(vm, "tts_manager"):
                        vm.tts_manager.stop()
                except Exception:
                    pass
                vl = getattr(self, "_voice_loop", None)
                if vl and hasattr(vl, "trigger_wake_detected"):
                    vl.trigger_wake_detected()
                elif getattr(self, "_voice_manager", None):
                    try:
                        self._voice_manager._start_active_listening()
                    except Exception:
                        pass
                else:
                    self.set_state(NotchState.LISTENING)
            event.accept()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """Cleanly stop all timers, release audio streams, and terminate application process."""
        logger.info("[VoiceNotchOverlay] closeEvent received — shutting down completely.")
        # 1. Stop all notch internal timers
        for timer_name in ("_master_anim_timer", "_hover_timer", "_collapse_timer", "_result_collapse_timer", "_proc_timeout"):
            t = getattr(self, timer_name, None)
            if t is not None and hasattr(t, "stop"):
                try:
                    t.stop()
                except Exception:
                    pass

        # 2. Emit voice status changed False
        try:
            from gui.signals import app_signals
            if hasattr(app_signals, "voice_status_changed"):
                app_signals.voice_status_changed.emit(False)
        except Exception:
            pass

        # 3. If running as standalone Notch or primary top-level, exit QApplication completely
        try:
            app = QApplication.instance()
            if app and not getattr(self, "_is_test_env", False):
                top_levels = [w for w in app.topLevelWidgets() if w.isVisible() and w is not self]
                if not top_levels or app.applicationName() == "Aura Voice Notch":
                    app.quit()
        except Exception:
            pass

        super().closeEvent(event)

    def _show_context_menu(self, pos: QPoint):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: rgba(10, 14, 26, 0.98);
                border: 1px solid #00f0ff;
                border-radius: 8px;
                padding: 6px;
                color: #f1f5f9;
                font-family: {FONT_SANS};
                font-size: 11px;
                font-weight: 700;
            }}
            QMenu::item {{
                padding: 6px 18px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background: rgba(0, 240, 255, 0.2);
                color: #00f0ff;
            }}
            QMenu::separator {{
                height: 1px;
                background: rgba(0, 240, 255, 0.2);
                margin: 4px 6px;
            }}
        """)

        gui_action = menu.addAction("🖥️  Open Main Window")
        chat_action = menu.addAction("💬  Open Spotlight Chat")
        menu.addSeparator()

        dictation_action = menu.addAction("🎤  Dictation Mode")
        agent_action = menu.addAction("⚡  Agent Mode")
        menu.addSeparator()

        restart_action = menu.addAction("🔄  Restart AuraAI")
        menu.addSeparator()
        close_action = menu.addAction("✕  Close Notch")

        action = menu.exec(pos)

        if action == gui_action:
            import subprocess
            root = Path(__file__).resolve().parents[3]
            py = root / ".venv" / "Scripts" / "python.exe"
            subprocess.Popen([str(py), str(root / "main.py"), "--gui"], cwd=str(root))
        elif action == chat_action:
            import subprocess
            root = Path(__file__).resolve().parents[3]
            py = root / ".venv" / "Scripts" / "python.exe"
            subprocess.Popen([str(py), str(root / "run_chat_window.py")], cwd=str(root))
        elif action == dictation_action:
            self.mode_changed.emit("dictation")
        elif action == agent_action:
            self.mode_changed.emit("agent")
        elif action == restart_action:
            try:
                self.set_state(NotchState.PROCESSING, "Restarting...")
                root = Path(__file__).resolve().parents[3]
                py = root / ".venv" / "Scripts" / "python.exe"
                launcher = root / "run_voice_notch.py"
                from tools.restart_manager import RestartManager
                RestartManager.restart_aura(
                    delay_seconds=0.6,
                    target_cmd=[str(py), str(launcher)]
                )
            except Exception as e:
                logger.error(f"[VoiceNotchOverlay] Restart error: {e}")
        elif action == close_action:
            self.close()

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
            app_signals.step_updated.connect(self._on_step_updated)

            if hasattr(app_signals, "live_speech_transcribed"):
                app_signals.live_speech_transcribed.connect(self._on_live_speech_transcribed)

            if hasattr(app_signals, "toggle_voice_notch"):
                app_signals.toggle_voice_notch.connect(self.toggle)
        except ImportError:
            pass

    def _on_voice_status(self, active: bool):
        if not active and self._state == NotchState.LISTENING:
            self.set_state(NotchState.IDLE)

    def _on_voice_level(self, level: float):
        self._rainbow_wave.set_level(level)
        if hasattr(self, "_idle_spectrum"):
            self._idle_spectrum.set_level(level)
        if hasattr(self, "_expanded_panel") and hasattr(self._expanded_panel, "_bottom_wave"):
            self._expanded_panel._bottom_wave.set_level(level)

    def _on_voice_state_name(self, name: str):
        name_upper = (name or "").upper()
        if name_upper in ("WAKE_DETECTED", "COMMAND_LISTENING", "ACTIVE_LISTENING", "FOLLOW_UP_LISTENING", "LISTENING"):
            self.set_state(NotchState.LISTENING)
        elif name_upper in ("TRANSCRIBING", "STT_ACTIVE"):
            self.set_state(NotchState.LISTENING)
        elif name_upper in ("UNDERSTANDING", "EXECUTING", "AI_RESPONSE", "PLANNING", "THINKING"):
            self.set_state(NotchState.PROCESSING, "Processing your request...")
        elif name_upper == "SPEAKING":
            # AI is speaking the reply — immediately auto-expand to show result card
            if hasattr(self, "_proc_timeout") and self._proc_timeout.isActive():
                self._proc_timeout.stop()
            self._has_last_result = True
            self._mark_ready()
            self.set_state(NotchState.EXPANDED)
        elif name_upper in ("IDLE", "COOLDOWN", "WAITING_FOR_WAKE_WORD", "STANDBY"):
            # Passive states → show AuraAI idle notch
            if self._state not in (NotchState.EXPANDED,):
                self.set_state(NotchState.IDLE)

    def _on_execution_started(self, task_id: str):
        self.set_state(NotchState.PROCESSING, "Executing actions...")

    def _on_execution_finished(self, task_id: str, success: bool):
        # After execution, auto-expand with result (don't just show success pill)
        if self._current_response:
            self._has_last_result = True
            self._mark_ready()
            self.set_state(NotchState.EXPANDED)
        elif success:
            self.set_state(NotchState.SUCCESS, "Task Completed")
        else:
            self.set_state(NotchState.SUCCESS, "Task Failed")

    def _on_live_speech_transcribed(self, text: str, is_final: bool):
        if not text:
            return
        clean_text = text.strip()
        self._current_query = clean_text
        if self._state in (NotchState.LISTENING, NotchState.IDLE):
            if self._state != NotchState.LISTENING:
                self.set_state(NotchState.LISTENING)
            # Display clean rolling speech transcript in notch
            display_text = clean_text if len(clean_text) <= 32 else f"...{clean_text[-28:]}"
            self._listen_text.setText(display_text)
            self._rainbow_wave.set_level(0.75)
            self.update()

    def _on_message_received(self, sender: str, content: str, is_user: bool):
        logger.info(f"[CHAT] {sender}: {content}")
        if is_user:
            self._current_query = content
            self._has_last_result = False
            self._expanded_panel.clear_panel()
            self._expanded_panel.add_transcript_msg("You:", content, True)
            self._proc_title.setText("Processing your request...")
        else:
            if content:
                self._current_response = content
                # Cancel processing timeout if still running
                if hasattr(self, '_proc_timeout') and self._proc_timeout.isActive():
                    self._proc_timeout.stop()
                # Populate transcript + context-aware actions/sources
                self._expanded_panel.add_transcript_msg("AuraAI:", content, False)
                self._expanded_panel.populate_result(self._current_query, content)
                self._has_last_result = True
                self._mark_ready()
                # Auto-expand to show the result (will auto-collapse after 5s)
                self.set_state(NotchState.EXPANDED)

    def _on_step_updated(self, step):
        if self._state == NotchState.PROCESSING:
            label = getattr(step, "title", "") or getattr(step, "description", "")
            if label:
                self._proc_bullets.setText(label[:35])

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def toggle(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self._position_at_top()
            self.raise_()
            self.activateWindow()

    @property
    def current_state(self) -> NotchState:
        return self._state
