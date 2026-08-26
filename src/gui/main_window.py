"""
AuraAI — Next-Gen Holographic Cyber Command OS (Main Window)
============================================================
Ultra-Advanced Sci-Fi HUD Control Interface featuring:
- Animated Holographic AI Core (Arc Reactor with rotating concentric energy rings)
- 60 FPS Tactical Scan-Line Sweeper and Ambient HUD Vector Grid
- Chamfered Sci-Fi Corner Brackets and High-Tech Matrix Badges
- Real-Time Hardware Telemetry Gauges (CPU, GPU0 GTX 1650, RAM, Network, Wi-Fi 6)
- Interactive Multi-Agent Neural Console with Cognitive Intent Badges
- Live Vector Memory Vault, World Observatory, Cognitive DAG Visualizer
- Seamless One-Touch HUD Overlay Spawner (Weather HUD & System Telemetry HUD)
"""

import sys
import os
import math
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SRC_DIR = _PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(1, str(_PROJECT_ROOT))

from PySide6.QtCore import (
    Qt,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    QSettings,
    QTimer,
    QDateTime,
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
    QRadialGradient,
    QPolygonF,
    QCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QMainWindow,
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QStackedWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QGridLayout,
    QProgressBar,
    QComboBox,
    QMenu,
)

from gui.signals import (
    app_signals,
    ExecutionStep,
    StepStatus,
    TaskNode,
    TaskNodeStatus,
    WorldStateSnapshot,
)
from gui.theme import (
    Colors,
    Radius,
    Spacing,
    Typography,
    build_global_stylesheet,
    main_window_stylesheet,
)
from gui.widgets.status_pill import StatusPill
from gui.widgets.dag_visualizer import DagVisualizer
from gui.widgets.weather_overlay import WeatherOverlay
from gui.widgets.system_monitor_overlay import SystemMonitorOverlay, TelemetryWorker
from gui.widgets.system_status_overlay import SystemStatusOverlay
from gui.widgets.agent_task_status_overlay import AgentTaskStatusOverlay
from gui.widgets.personal_os_dashboard_overlay import PersonalOSDashboardOverlay
from gui.widgets.chat_window_overlay import ChatWindowOverlay
from gui.real_backend_bridge import RealBackendBridge


# ─────────────────────────────────────────────────────────────────────────────
# 1. ANIMATED HOLOGRAPHIC AI CORE (ARC REACTOR)
# ─────────────────────────────────────────────────────────────────────────────

class HoloCoreWidget(QWidget):
    """
    Animated Holographic AI Core Orb (Arc Reactor).
    Concentric rings rotate smoothly, pulsing with energy that reacts to agent state.
    """

    def __init__(self, size: int = 130, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle_outer = 0.0
        self._angle_mid = 0.0
        self._angle_inner = 0.0
        self._pulse = 0.0
        self._pulse_dir = 1
        self._state = "IDLE"  # "IDLE", "LISTENING", "THINKING", "EXECUTING"

        # 60 FPS animation timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate_step)
        self._timer.start(16)

    def set_state(self, state: str):
        self._state = state
        self.update()

    def _animate_step(self):
        speed = 2.5 if self._state == "EXECUTING" else (1.8 if self._state == "THINKING" else 0.8)
        self._angle_outer = (self._angle_outer + speed * 1.0) % 360
        self._angle_mid = (self._angle_mid - speed * 1.5) % 360
        self._angle_inner = (self._angle_inner + speed * 2.2) % 360

        self._pulse += self._pulse_dir * 0.02 * (2.0 if self._state != "IDLE" else 1.0)
        if self._pulse >= 1.0:
            self._pulse = 1.0
            self._pulse_dir = -1
        elif self._pulse <= 0.0:
            self._pulse = 0.0
            self._pulse_dir = 1

        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r_max = min(w, h) / 2 - 6

        # Theme color determination based on state
        if self._state == "EXECUTING":
            base_col = QColor(255, 180, 50)  # Neon Amber
            core_col = QColor(255, 220, 100)
        elif self._state == "THINKING":
            base_col = QColor(130, 90, 255)  # Neural Purple
            core_col = QColor(190, 160, 255)
        elif self._state == "LISTENING":
            base_col = QColor(50, 230, 140)  # Emerald
            core_col = QColor(120, 255, 180)
        else:
            base_col = QColor(0, 229, 255)   # Cyber Cyan
            core_col = QColor(120, 245, 255)

        # 1. Radial Energy Glow Backdrop
        radial = QRadialGradient(cx, cy, r_max)
        c_glow = QColor(base_col)
        c_glow.setAlpha(int(35 + 25 * self._pulse))
        radial.setColorAt(0.0, c_glow)
        radial.setColorAt(0.8, QColor(base_col.red(), base_col.green(), base_col.blue(), 6))
        radial.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(radial))
        p.drawEllipse(QPointF(cx, cy), r_max, r_max)

        # 2. Outer Segmented Ring
        p.save()
        p.translate(cx, cy)
        p.rotate(self._angle_outer)
        p.setPen(QPen(QColor(base_col.red(), base_col.green(), base_col.blue(), 180), 1.5))
        p.setBrush(Qt.NoBrush)
        num_outer_segs = 6
        seg_len = 360 / num_outer_segs
        for i in range(num_outer_segs):
            span_angle = int((seg_len - 14) * 16)
            start_angle = int((i * seg_len) * 16)
            p.drawArc(QRectF(-r_max, -r_max, r_max * 2, r_max * 2), start_angle, span_angle)
        p.restore()

        # 3. Middle Tactical Tech Ring with Notches
        r_mid = r_max * 0.76
        p.save()
        p.translate(cx, cy)
        p.rotate(self._angle_mid)
        pen_mid = QPen(QColor(255, 255, 255, 120), 1.0, Qt.DashLine)
        p.setPen(pen_mid)
        p.drawEllipse(QPointF(0, 0), r_mid, r_mid)

        # Small tick markers
        p.setPen(QPen(base_col, 2.0))
        for deg in range(0, 360, 45):
            rad = math.radians(deg)
            x1 = (r_mid - 4) * math.cos(rad)
            y1 = (r_mid - 4) * math.sin(rad)
            x2 = (r_mid + 4) * math.cos(rad)
            y2 = (r_mid + 4) * math.sin(rad)
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        p.restore()

        # 4. Inner Ring with Counter-Rotation
        r_in = r_max * 0.50
        p.save()
        p.translate(cx, cy)
        p.rotate(self._angle_inner)
        p.setPen(QPen(core_col, 2.0))
        p.drawArc(QRectF(-r_in, -r_in, r_in * 2, r_in * 2), 0, int(100 * 16))
        p.drawArc(QRectF(-r_in, -r_in, r_in * 2, r_in * 2), int(180 * 16), int(100 * 16))
        p.restore()

        # 5. Core Pulsing Reactor Nucleus
        r_core = r_max * (0.24 + 0.06 * self._pulse)
        core_radial = QRadialGradient(cx, cy, r_core)
        core_radial.setColorAt(0.0, QColor(255, 255, 255, 240))
        core_radial.setColorAt(0.5, core_col)
        core_radial.setColorAt(1.0, QColor(base_col.red(), base_col.green(), base_col.blue(), 40))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(core_radial))
        p.drawEllipse(QPointF(cx, cy), r_core, r_core)

        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# 2. FUTURISTIC SCI-FI TECH CARD (CHAMFERED HUD GLASS)
# ─────────────────────────────────────────────────────────────────────────────

class SciFiTechCard(QFrame):
    """Futuristic HUD container with chamfered corners, scan-line clip, and tech brackets."""

    def __init__(self, parent=None, accent_color: QColor = None, chamfer_size: int = 10):
        super().__init__(parent)
        self.accent_color = accent_color or QColor(0, 229, 255)
        self.chamfer = chamfer_size
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent; border: none;")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        c = self.chamfer

        # Chamfered Polygon Path (Top-Right and Bottom-Left cut)
        path = QPainterPath()
        path.moveTo(c, 0)
        path.lineTo(w - c, 0)
        path.lineTo(w, c)
        path.lineTo(w, h - c)
        path.lineTo(w - c, h)
        path.lineTo(c, h)
        path.lineTo(0, h - c)
        path.lineTo(0, c)
        path.closeSubpath()

        # Glass Fill
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(13, 18, 28, 220)))
        p.drawPath(path)

        # Subtle Cyber Grid / Border
        p.setPen(QPen(QColor(255, 255, 255, 20), 1.0))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)

        # Tactical Glow Accent Edge (Top chamfer + bottom chamfer)
        p.setPen(QPen(self.accent_color, 1.8))
        # Top-left notch
        p.drawLine(0, c + 14, 0, c)
        p.drawLine(0, c, c, 0)
        p.drawLine(c, 0, c + 18, 0)

        # Bottom-right notch
        p.drawLine(w, h - c - 14, w, h - c)
        p.drawLine(w, h - c, w - c, h)
        p.drawLine(w - c, h, w - c - 18, h)

        # Subtle Header Accent Dot
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(self.accent_color))
        p.drawRect(c + 24, 2, 8, 2)

        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# 3. SCI-FI CYBER NAVIGATION BUTTON
# ─────────────────────────────────────────────────────────────────────────────

class SciFiNavButton(QPushButton):
    """Tactical Cyber Navigation Tab Button with glowing status bar."""

    def __init__(self, code: str, icon_glyph: str, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedHeight(58)
        self.setCursor(Qt.PointingHandCursor)
        self.code = code
        self.icon_glyph = icon_glyph
        self.title_str = title
        self.sub_str = subtitle
        self._update_style(False)

    def _update_style(self, checked: bool):
        if checked:
            self.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0, 229, 255, 0.22), stop:1 rgba(15, 22, 35, 0.7));
                    border-left: 4px solid #00e5ff;
                    border-top: 1px solid rgba(0, 229, 255, 0.35);
                    border-bottom: 1px solid rgba(0, 229, 255, 0.35);
                    border-right: none;
                    color: #00e5ff;
                    text-align: left;
                    padding-left: 16px;
                    font-family: Consolas;
                    font-weight: bold;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    border-left: 4px solid transparent;
                    color: #7b8c9f;
                    text-align: left;
                    padding-left: 16px;
                    font-family: Consolas;
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 0.04);
                    color: #e2eaf4;
                    border-left: 4px solid rgba(0, 229, 255, 0.5);
                }
            """)

    def setChecked(self, checked: bool):
        super().setChecked(checked)
        self._update_style(checked)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Render custom HUD typography inside the button
        w, h = self.width(), self.height()
        is_chk = self.isChecked()

        p.setFont(QFont("Segoe UI Emoji", 12))
        p.setPen(QPen(QColor(0, 229, 255) if is_chk else QColor(140, 160, 180)))
        p.drawText(QRect(18, 12, 28, 32), Qt.AlignVCenter | Qt.AlignLeft, self.icon_glyph)

        p.setFont(QFont("Consolas", 10, QFont.Bold if is_chk else QFont.Normal))
        p.setPen(QPen(QColor(245, 248, 255) if is_chk else QColor(165, 178, 195)))
        p.drawText(QRect(52, 12, w - 80, 18), Qt.AlignVCenter | Qt.AlignLeft, self.title_str.upper())

        p.setFont(QFont("Consolas", 7))
        p.setPen(QPen(QColor(0, 229, 255, 180) if is_chk else QColor(95, 110, 128)))
        p.drawText(QRect(52, 32, w - 80, 14), Qt.AlignVCenter | Qt.AlignLeft, f"SYS.{self.code} // {self.sub_str.upper()}")

        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# 4. NEURAL CHAT BUBBLE (SCI-FI INTENT CARD)
# ─────────────────────────────────────────────────────────────────────────────

class HoloMessageCard(SciFiTechCard):
    """Next-gen Sci-Fi chat message card with metadata tags and execution intent."""

    def __init__(self, sender: str, text: str, intent_tag: str = "EXECUTION", parent=None):
        is_usr = sender.lower() == "user"
        accent = QColor(80, 170, 255) if is_usr else QColor(0, 229, 255)
        super().__init__(parent, accent_color=accent, chamfer_size=8)
        self.sender = sender
        self.is_user = is_usr
        self._setup_ui(text, intent_tag)

    def _setup_ui(self, text: str, intent_tag: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(8)

        # Header metadata
        head = QHBoxLayout()
        head.setSpacing(10)

        badge_txt = "OPERATOR // HUMAN NODE" if self.is_user else "AURA // NEURAL COGNITION"
        badge_col = "#50aaff" if self.is_user else "#00e5ff"

        tag = QLabel(badge_txt)
        tag.setFont(QFont("Consolas", 9, QFont.Bold))
        tag.setStyleSheet(f"color: {badge_col}; background: transparent; letter-spacing: 1px;")
        head.addWidget(tag)

        if not self.is_user and intent_tag:
            intent_lbl = QLabel(f"[{intent_tag.upper()}]")
            intent_lbl.setFont(QFont("Consolas", 8, QFont.Bold))
            intent_lbl.setStyleSheet("""
                color: #fbbf24;
                background: rgba(251, 191, 36, 0.12);
                border: 1px solid rgba(251, 191, 36, 0.35);
                border-radius: 3px;
                padding: 1px 6px;
            """)
            head.addWidget(intent_lbl)

        head.addStretch()

        clock_lbl = QLabel(QDateTime.currentDateTime().toString("HH:mm:ss"))
        clock_lbl.setFont(QFont("Consolas", 8))
        clock_lbl.setStyleSheet("color: #627289; background: transparent;")
        head.addWidget(clock_lbl)
        layout.addLayout(head)

        # Message Text
        body = QLabel(text)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        body.setFont(QFont("Segoe UI", 10))
        body.setStyleSheet("color: #f3f6fc; background: transparent; line-height: 1.45;")
        layout.addWidget(body)


ORG_NAME = "AuraAI"
APP_NAME = "MainWindowHUD"
REF_W, REF_H = 1920, 1080
MIN_W, MIN_H = 760, 520
GRIP_SIZE = 20


# ─────────────────────────────────────────────────────────────────────────────
# 5. MAIN CYBER COMMAND CENTER WINDOW
# ─────────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """
    Next-Gen Futuristic Sci-Fi Holographic Command Center for AuraAI.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MainWindow")
        self.setWindowTitle("AuraAI Next-Gen Cyber Command OS")

        # Frameless HUD window configuration with translucent background
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setStyleSheet(build_global_stylesheet() + main_window_stylesheet())

        self._settings = QSettings(ORG_NAME, APP_NAME)

        # Drag & resize state
        self._drag_pos = None
        self._resizing = False
        self._resize_start_pos = None
        self._resize_start_size = None

        # Scan-line animation
        self._scan_y = 0.0
        self._scan_dir = 1
        self._scan_timer = QTimer(self)
        self._scan_timer.timeout.connect(self._advance_scan)
        self._scan_timer.start(16)

        # Overlays references
        self._weather_overlay: Optional[WeatherOverlay] = None
        self._sys_overlay: Optional[SystemMonitorOverlay] = None
        self._status_overlay: Optional[SystemStatusOverlay] = None
        self._task_overlay: Optional[AgentTaskStatusOverlay] = None
        self._personal_os_overlay: Optional[PersonalOSDashboardOverlay] = None
        self._chat_overlay: Optional[ChatWindowOverlay] = None

        # Telemetry worker
        self._telemetry_worker = TelemetryWorker(self)
        self._telemetry_worker.data_ready.connect(self._on_telemetry_data)

        self._setup_ui()
        self._setup_titlebar()
        self._connect_signals()
        self._restore_geometry()

        self._telemetry_worker.start()

    # -------------------------------------------------------------------------
    # MAIN UI ASSEMBLE
    # -------------------------------------------------------------------------
    def _setup_ui(self):
        central = QWidget()
        central.setObjectName("CentralSurface")
        central.setStyleSheet("""
            #CentralSurface {
                background-color: rgba(7, 10, 16, 245);
                border: 1px solid rgba(0, 229, 255, 0.35);
                border-radius: 8px;
            }
        """)
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Custom Titlebar (46px)
        self._titlebar_widget = QWidget()
        self._titlebar_widget.setFixedHeight(46)
        main_layout.addWidget(self._titlebar_widget)

        # 2. Main Work Area
        work_area = QHBoxLayout()
        work_area.setContentsMargins(0, 0, 0, 0)
        def _wrap_panel(widget: QWidget, fixed_width: int) -> QScrollArea:
            scroll = QScrollArea()
            scroll.setWidget(widget)
            scroll.setWidgetResizable(True)
            scroll.setFixedWidth(fixed_width)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll.setStyleSheet("background: transparent; border: none;")
            return scroll

        # Left Nav Dock (190px)
        self._nav_dock = self._build_nav_dock()
        work_area.addWidget(_wrap_panel(self._nav_dock, 190))

        # Center Stage Stack (7 Tabs)
        self._center_stack = QStackedWidget()
        self._center_stack.setObjectName("CenterStage")
        self._center_stack.setStyleSheet("background: #090d15;")

        def _wrap_tab(widget: QWidget) -> QWidget:
            scroll = QScrollArea()
            scroll.setWidget(widget)
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll.setStyleSheet("background: transparent; border: none;")
            return scroll

        self._tab_home = self._build_home_tab()
        self._center_stack.addWidget(_wrap_tab(self._tab_home))

        self._tab_console = self._build_console_tab()
        self._center_stack.addWidget(_wrap_tab(self._tab_console))

        self._tab_cognition = self._build_cognition_tab()
        self._center_stack.addWidget(_wrap_tab(self._tab_cognition))

        self._tab_observatory = self._build_observatory_tab()
        self._center_stack.addWidget(_wrap_tab(self._tab_observatory))

        self._tab_memory = self._build_memory_tab()
        self._center_stack.addWidget(_wrap_tab(self._tab_memory))

        self._tab_telemetry = self._build_telemetry_tab()
        self._center_stack.addWidget(_wrap_tab(self._tab_telemetry))

        self._tab_settings = self._build_settings_tab()
        self._center_stack.addWidget(_wrap_tab(self._tab_settings))

        work_area.addWidget(self._center_stack, 1)

        # Right Live Deck (210px)
        self._right_deck = self._build_right_deck()
        work_area.addWidget(_wrap_panel(self._right_deck, 210))

        main_layout.addLayout(work_area, 1)

        # Wire global signals and check recovery state
        self._connect_signals()
        self._check_restart_recovery()

    def _check_restart_recovery(self):
        try:
            from tools.restart_manager import RestartManager
            recovery = RestartManager.load_and_restore_state()
            if recovery:
                routines_cnt = len(recovery.get("active_routines", []))
                self._add_message(
                    "agent",
                    f"🔄 **AuraAI Restarts Complete**: Session state recovered successfully ({routines_cnt} active routine(s), memory and background tasks preserved).",
                    intent_tag="RECOVERY"
                )
        except Exception as e:
            logger.debug(f"[MainWindow] Restart recovery check: {e}")

    # -------------------------------------------------------------------------
    # SCI-FI HUD TITLEBAR
    # -------------------------------------------------------------------------
    def _setup_titlebar(self):
        tb_layout = QHBoxLayout(self._titlebar_widget)
        tb_layout.setContentsMargins(8, 0, 8, 0)
        tb_layout.setSpacing(6)

        self._titlebar_widget.setStyleSheet("""
            QWidget {
                background: #06080d;
                border-bottom: 1px solid rgba(0, 229, 255, 0.25);
            }
        """)

        # Sci-Fi Title
        title_box = QHBoxLayout()
        title_box.setSpacing(4)
        star = QLabel("✦")
        star.setFont(QFont("Consolas", 10, QFont.Bold))
        star.setStyleSheet("color: #00e5ff;")
        title_box.addWidget(star)

        title_lbl = QLabel("AURA OS")
        title_lbl.setFont(QFont("Consolas", 9, QFont.Bold))
        title_lbl.setStyleSheet("color: #ffffff; letter-spacing: 1px;")
        title_box.addWidget(title_lbl)
        tb_layout.addLayout(title_box)

        # Pulsing Live LED
        core_badge = QLabel("● ON")
        core_badge.setFont(QFont("Consolas", 7, QFont.Bold))
        core_badge.setStyleSheet("""
            color: #10b981;
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.4);
            border-radius: 6px;
            padding: 1px 5px;
        """)
        tb_layout.addWidget(core_badge)

        # Compact HUD Overlays Dropdown Menu Button
        btn_overlays = QPushButton("⚡ Overlays ▾")
        btn_overlays.setFont(QFont("Segoe UI", 8, QFont.Weight.Medium))
        btn_overlays.setCursor(Qt.PointingHandCursor)
        btn_overlays.setStyleSheet("""
            QPushButton {
                background: rgba(0, 229, 255, 0.08);
                border: 1px solid rgba(0, 229, 255, 0.25);
                border-radius: 4px;
                color: #00e5ff;
                padding: 3px 8px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.2);
                border: 1px solid #00e5ff;
                color: #ffffff;
            }
            QPushButton::menu-indicator {
                image: none;
            }
        """)

        overlays_menu = QMenu(btn_overlays)
        overlays_menu.setStyleSheet("""
            QMenu {
                background-color: #090d15;
                border: 1px solid rgba(0, 229, 255, 0.3);
                border-radius: 6px;
                padding: 4px;
                color: #e2e8f0;
            }
            QMenu::item {
                padding: 6px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: rgba(0, 229, 255, 0.15);
                color: #00e5ff;
            }
        """)

        overlays_menu.addAction("💬  Chat HUD", self.toggle_chat_overlay)
        overlays_menu.addAction("🎯  Personal OS", self.toggle_personal_os_overlay)
        overlays_menu.addAction("📋  Agent Tasks", self.toggle_agent_task_overlay)
        overlays_menu.addAction("🌐  System Status", self.toggle_system_status_overlay)
        overlays_menu.addAction("⚡  System HUD", self.toggle_system_overlay)
        overlays_menu.addAction("☁  Weather HUD", self.toggle_weather_overlay)
        btn_overlays.setMenu(overlays_menu)
        tb_layout.addWidget(btn_overlays)

        tb_layout.addStretch(1)

        # Live Top Ticker
        self._title_ticker = QLabel("CPU: --% | RAM: --GB")
        self._title_ticker.setFont(QFont("Consolas", 8))
        self._title_ticker.setStyleSheet("color: #50aaff;")
        self._title_ticker.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._title_ticker.setMinimumWidth(0)
        tb_layout.addWidget(self._title_ticker)

        # Clock
        self._title_clock = QLabel()
        self._title_clock.setFont(QFont("Consolas", 8, QFont.Bold))
        self._title_clock.setStyleSheet("color: #a5b4cb;")
        self._update_clock()
        tb_layout.addWidget(self._title_clock)

        c_timer = QTimer(self)
        c_timer.timeout.connect(self._update_clock)
        c_timer.start(1000)

        # Auto-Fit Laptop Screen Button
        btn_fit = QPushButton("⛶")
        btn_fit.setFixedSize(26, 24)
        btn_fit.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        btn_fit.setToolTip("Auto-adjust window size to fit your laptop screen perfectly")
        btn_fit.setCursor(Qt.PointingHandCursor)
        btn_fit.setStyleSheet("""
            QPushButton {
                background: rgba(0, 229, 255, 0.08);
                border: 1px solid rgba(0, 229, 255, 0.3);
                border-radius: 4px;
                color: #00e5ff;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.2);
                color: #ffffff;
            }
        """)
        btn_fit.clicked.connect(self.auto_fit_screen)
        tb_layout.addWidget(btn_fit)

        # Window Controls
        for sym, color, hover_bg, action in [
            ("−", "#e2e8f0", "rgba(255, 255, 255, 0.15)", self.showMinimized),
            ("□", "#e2e8f0", "rgba(255, 255, 255, 0.15)", self._toggle_maximize),
            ("✕", "#f43f5e", "rgba(244, 63, 94, 0.35)", self.close),
        ]:
            btn = QPushButton(sym)
            btn.setFixedSize(28, 24)
            btn.setFont(QFont("Consolas", 10, QFont.Bold))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(255, 255, 255, 0.12);
                    border-radius: 4px;
                    color: {color};
                }}
                QPushButton:hover {{
                    background: {hover_bg};
                    border: 1px solid {color};
                    color: #ffffff;
                }}
            """)
            btn.clicked.connect(action)
            tb_layout.addWidget(btn)

    def _update_clock(self):
        now = QDateTime.currentDateTime()
        if hasattr(self, "_title_clock"):
            self._title_clock.setText(now.toString("HH:mm:ss"))
        if hasattr(self, "_home_date_lbl"):
            self._home_date_lbl.setText(now.toString("dddd, MMMM d • h:mm AP"))

    # -------------------------------------------------------------------------
    # LEFT NAVIGATION DOCK
    # -------------------------------------------------------------------------
    def _build_nav_dock(self) -> QWidget:
        dock = QWidget()
        dock.setFixedWidth(190)
        dock.setStyleSheet("background: #06090f; border-right: 1px solid rgba(255, 255, 255, 0.06);")

        layout = QVBoxLayout(dock)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(4)

        # Holographic Arc Reactor mini avatar
        core_box = QHBoxLayout()
        core_box.setContentsMargins(14, 0, 14, 10)
        self._holo_core_small = HoloCoreWidget(size=64)
        core_box.addWidget(self._holo_core_small)

        core_info = QVBoxLayout()
        core_info.setSpacing(2)
        c_title = QLabel("AURA CORE")
        c_title.setFont(QFont("Consolas", 9, QFont.Bold))
        c_title.setStyleSheet("color: #00e5ff; letter-spacing: 1px;")
        core_info.addWidget(c_title)

        self._core_state_lbl = QLabel("STATE: IDLE")
        self._core_state_lbl.setFont(QFont("Consolas", 7))
        self._core_state_lbl.setStyleSheet("color: #10b981;")
        core_info.addWidget(self._core_state_lbl)
        core_box.addLayout(core_info)
        layout.addLayout(core_box)

        # Nav Buttons
        self._nav_buttons: List[SciFiNavButton] = []
        tabs = [
            ("00", "🏠", "Home", "Control Center"),
            ("01", "💬", "Console", "Neural Chat"),
            ("02", "🧠", "Cognition", "DAG Planner"),
            ("03", "👁️", "Observer", "World Vision"),
            ("04", "💾", "Memory", "Vector Vault"),
            ("05", "⚡", "Telemetry", "Hardware Hub"),
            ("06", "⚙️", "Settings", "Engine Config"),
        ]
        for idx, (num, icon, title, subtitle) in enumerate(tabs):
            btn = SciFiNavButton(num, icon, title, subtitle)
            btn.clicked.connect(lambda checked, i=idx: self._on_tab_selected(i))
            self._nav_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # Standalone HUD Overlay Launcher Box
        hud_box = QVBoxLayout()
        hud_box.setContentsMargins(12, 0, 12, 0)
        hud_box.setSpacing(6)

        h_title = QLabel("STANDALONE HUDS")
        h_title.setFont(QFont("Consolas", 7, QFont.Bold))
        h_title.setStyleSheet("color: #50aaff; letter-spacing: 1px;")
        hud_box.addWidget(h_title)

        # Weather HUD Launch Button
        btn_weather_hud = QPushButton("☁ Launch Weather HUD")
        btn_weather_hud.setFont(QFont("Consolas", 8))
        btn_weather_hud.setCursor(Qt.PointingHandCursor)
        btn_weather_hud.setStyleSheet("""
            QPushButton {
                background: rgba(0, 229, 255, 0.08);
                border: 1px solid rgba(0, 229, 255, 0.3);
                border-radius: 4px;
                color: #00e5ff;
                padding: 6px;
                text-align: left;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.2);
                border: 1px solid #00e5ff;
                color: #ffffff;
            }
        """)
        btn_weather_hud.clicked.connect(self.toggle_weather_overlay)
        hud_box.addWidget(btn_weather_hud)

        # System Monitor HUD Launch Button
        btn_sys_hud = QPushButton("⚡ Launch System HUD")
        btn_sys_hud.setFont(QFont("Consolas", 8))
        btn_sys_hud.setCursor(Qt.PointingHandCursor)
        btn_sys_hud.setStyleSheet("""
            QPushButton {
                background: rgba(16, 185, 129, 0.08);
                border: 1px solid rgba(16, 185, 129, 0.3);
                border-radius: 4px;
                color: #10b981;
                padding: 6px;
                text-align: left;
            }
            QPushButton:hover {
                background: rgba(16, 185, 129, 0.2);
                border: 1px solid #10b981;
                color: #ffffff;
            }
        """)
        btn_sys_hud.clicked.connect(self.toggle_system_overlay)
        hud_box.addWidget(btn_sys_hud)

        # System Status HUD Launch Button
        btn_status_hud = QPushButton("🌐 System Status HUD")
        btn_status_hud.setFont(QFont("Consolas", 8))
        btn_status_hud.setCursor(Qt.PointingHandCursor)
        btn_status_hud.setStyleSheet("""
            QPushButton {
                background: rgba(102, 255, 153, 0.08);
                border: 1px solid rgba(102, 255, 153, 0.3);
                border-radius: 4px;
                color: #66ff99;
                padding: 6px;
                text-align: left;
            }
            QPushButton:hover {
                background: rgba(102, 255, 153, 0.2);
                border: 1px solid #66ff99;
                color: #ffffff;
            }
        """)
        btn_status_hud.clicked.connect(self.toggle_system_status_overlay)
        hud_box.addWidget(btn_status_hud)

        # Agent Task Status HUD Launch Button
        btn_task_hud = QPushButton("📋 Agent Tasks HUD")
        btn_task_hud.setFont(QFont("Consolas", 8))
        btn_task_hud.setCursor(Qt.PointingHandCursor)
        btn_task_hud.setStyleSheet("""
            QPushButton {
                background: rgba(192, 132, 252, 0.08);
                border: 1px solid rgba(192, 132, 252, 0.3);
                border-radius: 4px;
                color: #c084fc;
                padding: 6px;
                text-align: left;
            }
            QPushButton:hover {
                background: rgba(192, 132, 252, 0.2);
                border: 1px solid #c084fc;
                color: #ffffff;
            }
        """)
        btn_task_hud.clicked.connect(self.toggle_agent_task_overlay)
        hud_box.addWidget(btn_task_hud)

        # Personal OS Dashboard HUD Launch Button
        btn_pos = QPushButton("🎯 Personal OS HUD")
        btn_pos.setFont(QFont("Consolas", 8))
        btn_pos.setCursor(Qt.PointingHandCursor)
        btn_pos.setStyleSheet("""
            QPushButton {
                background: rgba(251, 191, 36, 0.08);
                border: 1px solid rgba(251, 191, 36, 0.3);
                border-radius: 4px;
                color: #fbbf24;
                padding: 6px;
                text-align: left;
            }
            QPushButton:hover {
                background: rgba(251, 191, 36, 0.2);
                border: 1px solid #fbbf24;
                color: #ffffff;
            }
        """)
        btn_pos.clicked.connect(self.toggle_personal_os_overlay)
        hud_box.addWidget(btn_pos)

        # Chat Window HUD Launch Button
        btn_chat = QPushButton("💬 Chat Window HUD")
        btn_chat.setFont(QFont("Consolas", 8))
        btn_chat.setCursor(Qt.PointingHandCursor)
        btn_chat.setStyleSheet("""
            QPushButton {
                background: rgba(56, 189, 248, 0.08);
                border: 1px solid rgba(56, 189, 248, 0.3);
                border-radius: 4px;
                color: #38bdf8;
                padding: 6px;
                text-align: left;
            }
            QPushButton:hover {
                background: rgba(56, 189, 248, 0.2);
                border: 1px solid #38bdf8;
                color: #ffffff;
            }
        """)
        btn_chat.clicked.connect(self.toggle_chat_overlay)
        hud_box.addWidget(btn_chat)

        layout.addLayout(hud_box)
        layout.addSpacing(10)

        # Version stamp
        v_lbl = QLabel("AURAAI // v0.32.0-os")
        v_lbl.setFont(QFont("Consolas", 6))
        v_lbl.setStyleSheet("color: #334155; padding-left: 14px;")
        layout.addWidget(v_lbl)

        # Set default active
        if self._nav_buttons:
            self._nav_buttons[0].setChecked(True)

        return dock

    def _on_tab_selected(self, index: int):
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)
        self._center_stack.setCurrentIndex(index)

    # -------------------------------------------------------------------------
    # TAB 0: HOME DASHBOARD (UNIFIED CONTROL CENTER)
    # -------------------------------------------------------------------------
    def _build_home_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(18, 14, 18, 12)
        layout.setSpacing(12)

        # Header with dynamic timestamp
        head = QHBoxLayout()
        h_info = QVBoxLayout()
        h_info.setSpacing(2)
        h_title = QLabel("MISSION CONTROL // AUTONOMOUS AGENT OS")
        h_title.setFont(QFont("Consolas", 12, QFont.Bold))
        h_title.setStyleSheet("color: #00e5ff; letter-spacing: 1.5px; background: transparent; border: none;")
        h_info.addWidget(h_title)

        self._home_date_lbl = QLabel(QDateTime.currentDateTime().toString("dddd, MMMM d • h:mm AP"))
        self._home_date_lbl.setFont(QFont("Segoe UI", 8))
        self._home_date_lbl.setStyleSheet("color: #7b8c9f; background: transparent; border: none;")
        h_info.addWidget(self._home_date_lbl)
        head.addLayout(h_info)
        head.addStretch()

        live_pill = StatusPill("●", "Core Active", active=True)
        head.addWidget(live_pill)
        layout.addLayout(head)

        # Scroll area for Home Content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        b_layout = QVBoxLayout(body)
        b_layout.setContentsMargins(0, 0, 0, 0)
        b_layout.setSpacing(12)

        # Fetch real backend data
        bridge = RealBackendBridge.get_instance()
        pos_data = bridge.get_personal_os_data()
        ag_data = bridge.get_agent_orchestration_stats()
        tp_data = bridge.get_throughput_stats()
        dg_data = bridge.get_dag_health_stats()

        t_comp = pos_data["stats"]["tasks_completed"]
        t_tot = pos_data["stats"]["tasks_total"]
        t_pend = pos_data["stats"]["pending"]
        t_over = pos_data["stats"]["overdue"]

        # 1. Top HUD Metric Ribbon (Sleek Compact Stat Strip)
        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(10)

        card_ag = self._create_home_kpi("🧠 PRIMARY AGENT BRAIN", tp_data["model"].upper(), tp_data["subtitle"], "#6496ff", "rgba(100, 150, 255, 0.06)", "rgba(100, 150, 255, 0.2)")
        kpi_grid.addWidget(card_ag, 0, 0)

        card_tp = self._create_home_kpi("⚡ AGENT SWARM POOL", f"{ag_data['active_count']} Active", ag_data["subtitle"], "#66ff99", "rgba(102, 255, 153, 0.06)", "rgba(102, 255, 153, 0.2)")
        kpi_grid.addWidget(card_tp, 0, 1)

        tk_sub = f"{t_pend} pending • {t_over} overdue" if t_tot > 0 else "0 queued tasks"
        card_tk = self._create_home_kpi("📋 ROUTINES & TASKS", f"{t_comp}/{t_tot}", tk_sub, "#fbbf24", "rgba(251, 191, 36, 0.06)", "rgba(251, 191, 36, 0.2)")
        kpi_grid.addWidget(card_tk, 0, 2)

        card_dg = self._create_home_kpi("🛡️ SAFETY & DAG HEALTH", dg_data["score"], dg_data["subtitle"], "#a855f7", "rgba(168, 85, 247, 0.06)", "rgba(168, 85, 247, 0.2)")
        kpi_grid.addWidget(card_dg, 0, 3)

        b_layout.addLayout(kpi_grid)

        # 2. Main 2-Column Command Grid: Left 60% (Mission Hub) | Right 40% (Capabilities & Triggers)
        split_layout = QHBoxLayout()
        split_layout.setSpacing(12)

        # LEFT COLUMN: Mission Dispatch & Live Tasks
        left_col = QVBoxLayout()
        left_col.setSpacing(12)

        # Mission Quick-Dispatch Deck
        mission_card = SciFiTechCard(accent_color=QColor(0, 229, 255), chamfer_size=6)
        m_layout = QVBoxLayout(mission_card)
        m_layout.setContentsMargins(14, 12, 14, 12)
        m_layout.setSpacing(10)

        m_head = QHBoxLayout()
        mh_title = QLabel("⚡ QUICK MISSION DISPATCH")
        mh_title.setFont(QFont("Consolas", 9, QFont.Bold))
        mh_title.setStyleSheet("color: #00e5ff; letter-spacing: 0.8px;")
        m_head.addWidget(mh_title)
        m_head.addStretch()

        m_tag = QLabel("ONE-TOUCH DISPATCH")
        m_tag.setFont(QFont("Consolas", 7))
        m_tag.setStyleSheet("color: #a5b4cb; background: rgba(255, 255, 255, 0.04); border-radius: 4px; padding: 2px 6px;")
        m_head.addWidget(m_tag)
        m_layout.addLayout(m_head)

        chips_grid = QGridLayout()
        chips_grid.setSpacing(8)
        quick_missions = [
            ("⚡ Run System Diagnostics", "run full system diagnostics and check hardware health", "#66ff99"),
            ("🔍 Scan Workspace & Symbols", "scan workspace and inspect files", "#00e5ff"),
            ("🌤️ Weather & Briefing", "what is the current weather and news briefing?", "#80c4ff"),
            ("🧠 Inspect DAG Reasoner", "inspect active DAG reasoning graph and subagent pool", "#c084fc"),
            ("📊 Hardware & GPU Health", "check cpu, nvidia gtx 1650 gpu and ram status", "#fbbf24"),
            ("📁 Clean Downloads Folder", "scan and categorize downloads folder", "#38bdf8"),
        ]
        for idx, (label, cmd, col) in enumerate(quick_missions):
            btn = QPushButton(label)
            btn.setFont(QFont("Consolas", 8))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(22, 30, 44, 0.7);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 6px;
                    color: {col};
                    padding: 8px 10px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background: rgba(0, 229, 255, 0.12);
                    border: 1px solid {col};
                    color: #ffffff;
                }}
            """)
            btn.clicked.connect(lambda checked, c=cmd: self._send_quick_command(c))
            chips_grid.addWidget(btn, idx // 2, idx % 2)

        m_layout.addLayout(chips_grid)
        left_col.addWidget(mission_card)

        # Active Tasks Queue Card
        t_card = SciFiTechCard(accent_color=QColor(100, 150, 255), chamfer_size=6)
        t_layout = QVBoxLayout(t_card)
        t_layout.setContentsMargins(14, 12, 14, 12)
        t_layout.setSpacing(10)

        t_head = QHBoxLayout()
        th_l = QLabel("📋 ACTIVE TASK QUEUE")
        th_l.setFont(QFont("Consolas", 9, QFont.Bold))
        th_l.setStyleSheet("color: #6496ff; letter-spacing: 0.8px;")
        t_head.addWidget(th_l)
        t_head.addStretch()
        th_sub = QLabel(f"{t_pend} pending • {t_over} overdue" if t_tot > 0 else "0 tasks in queue")
        th_sub.setFont(QFont("Segoe UI", 8))
        th_sub.setStyleSheet("color: #7b8c9f;")
        t_head.addWidget(th_sub)
        t_layout.addLayout(t_head)

        tasks_data = pos_data.get("tasks", [])[:4]
        if tasks_data:
            for t in tasks_data:
                item = QFrame()
                item.setStyleSheet("background: rgba(255, 255, 255, 0.02); border-radius: 6px; padding: 2px;")
                il = QHBoxLayout(item)
                il.setContentsMargins(8, 6, 8, 6)
                il.setSpacing(8)

                t_lbl = QLabel(t.get("title", ""))
                t_lbl.setFont(QFont("Segoe UI", 9))
                t_lbl.setStyleSheet("color: #ffffff; background: transparent;")
                il.addWidget(t_lbl, 2)

                st = t.get("status", "pending")
                col = "#ef4444" if st == "overdue" else ("#66ff99" if st in ("completed", "executing") else "#fbbf24")
                s_lbl = QLabel(f"● {st.replace('_', ' ').title()}")
                s_lbl.setFont(QFont("Segoe UI", 8))
                s_lbl.setStyleSheet(f"color: {col}; background: transparent;")
                il.addWidget(s_lbl, 1)

                c_lbl = QLabel(t.get("category", "General"))
                c_lbl.setFont(QFont("Segoe UI", 8))
                c_lbl.setStyleSheet("color: #7b8c9f; background: transparent;")
                il.addWidget(c_lbl)

                t_layout.addWidget(item)
        else:
            empty_task = QLabel("No active tasks in queue. Type a goal or click a mission chip above.")
            empty_task.setFont(QFont("Segoe UI", 8))
            empty_task.setStyleSheet("color: #7b8c9f; padding: 10px; background: rgba(255, 255, 255, 0.02); border-radius: 6px;")
            t_layout.addWidget(empty_task)

        left_col.addWidget(t_card)
        split_layout.addLayout(left_col, 6)

        # RIGHT COLUMN: Tools Matrix & Automated Triggers
        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        # System Capabilities & Tool Matrix
        cap_card = SciFiTechCard(accent_color=QColor(0, 229, 255), chamfer_size=6)
        cap_layout = QVBoxLayout(cap_card)
        cap_layout.setContentsMargins(14, 12, 14, 12)
        cap_layout.setSpacing(10)

        cap_head = QLabel("🛠️ AUTONOMOUS CAPABILITIES & TOOLS")
        cap_head.setFont(QFont("Consolas", 9, QFont.Bold))
        cap_head.setStyleSheet("color: #00e5ff; letter-spacing: 0.8px;")
        cap_layout.addWidget(cap_head)

        cap_grid = QGridLayout()
        cap_grid.setSpacing(6)
        tools = [
            ("⚡ Terminal & CLI", "#66ff99"),
            ("🌐 Headless Browser", "#66ff99"),
            ("📁 File System IO", "#66ff99"),
            ("🧠 Multi-Agent DAG", "#66ff99"),
            ("👁️ Vision & Screen", "#66ff99"),
            ("🔒 Policy Guardrails", "#66ff99"),
        ]
        for i, (name, col) in enumerate(tools):
            badge = QLabel(f"{name} ✓")
            badge.setFont(QFont("Segoe UI", 8))
            badge.setStyleSheet(f"""
                color: {col};
                background: rgba(0, 229, 255, 0.06);
                border: 1px solid rgba(0, 229, 255, 0.2);
                border-radius: 4px;
                padding: 6px 8px;
            """)
            cap_grid.addWidget(badge, i // 2, i % 2)

        cap_layout.addLayout(cap_grid)
        right_col.addWidget(cap_card)

        # Active Triggers & Routines Card
        tr_card = SciFiTechCard(accent_color=QColor(102, 255, 153), chamfer_size=6)
        tr_layout = QVBoxLayout(tr_card)
        tr_layout.setContentsMargins(14, 12, 14, 12)
        tr_layout.setSpacing(8)

        tr_head = QHBoxLayout()
        trh_l = QLabel("⏰ AUTOMATION TRIGGERS")
        trh_l.setFont(QFont("Consolas", 9, QFont.Bold))
        trh_l.setStyleSheet("color: #66ff99; letter-spacing: 0.8px;")
        tr_head.addWidget(trh_l)
        tr_head.addStretch()

        tr_cnt = pos_data["stats"]["active_triggers_count"]
        tr_badge = QLabel(f"● {tr_cnt} live" if tr_cnt > 0 else "0 live")
        tr_badge.setFont(QFont("Segoe UI", 8))
        tr_badge.setStyleSheet("color: #66ff99;" if tr_cnt > 0 else "color: #7b8c9f;")
        tr_head.addWidget(tr_badge)
        tr_layout.addLayout(tr_head)

        tr_list = pos_data.get("triggers", [])[:4]
        if tr_list:
            for tr in tr_list:
                tr_row = QHBoxLayout()
                tn_lbl = QLabel(tr.get("name", "Trigger"))
                tn_lbl.setFont(QFont("Segoe UI", 8))
                tn_lbl.setStyleSheet("color: #ffffff;")
                tr_row.addWidget(tn_lbl)
                tr_row.addStretch()
                tm_lbl = QLabel(tr.get("schedule", "on_demand"))
                tm_lbl.setFont(QFont("Segoe UI", 7))
                tm_lbl.setStyleSheet("color: #7b8c9f;")
                tr_row.addWidget(tm_lbl)
                tr_layout.addLayout(tr_row)
        else:
            empty_tr = QLabel("No automated triggers configured. Use /schedule to set routines.")
            empty_tr.setFont(QFont("Segoe UI", 8))
            empty_tr.setStyleSheet("color: #7b8c9f; padding: 10px; background: rgba(255, 255, 255, 0.02); border-radius: 4px;")
            tr_layout.addWidget(empty_tr)

        right_col.addWidget(tr_card)
        split_layout.addLayout(right_col, 4)

        b_layout.addLayout(split_layout)
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)

        # 3. Bottom Multi-Modal Input Capsule
        input_card = SciFiTechCard(accent_color=QColor(0, 229, 255), chamfer_size=8)
        ic_l = QHBoxLayout(input_card)
        ic_l.setContentsMargins(14, 8, 14, 8)
        ic_l.setSpacing(12)

        # Live Mic Button
        home_mic_btn = QPushButton("🎙️")
        home_mic_btn.setFixedSize(36, 34)
        home_mic_btn.setCursor(Qt.PointingHandCursor)
        home_mic_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(0, 229, 255, 0.25);
                border-radius: 4px;
                color: #a5b4cb;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.15);
                border: 1px solid #00e5ff;
                color: #00e5ff;
            }
        """)
        home_mic_btn.clicked.connect(self._on_mic_toggle)
        ic_l.addWidget(home_mic_btn)

        # Chat Input
        self._home_input = QLineEdit()
        self._home_input.setPlaceholderText("Enter autonomous goal or command (Press Enter)...")
        self._home_input.setFont(QFont("Segoe UI", 10))
        self._home_input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #ffffff;
                padding: 4px;
            }
            QLineEdit::placeholder {
                color: #50657a;
            }
        """)
        # Send Button
        send_btn = QPushButton("DISPATCH ➤")
        send_btn.setFixedHeight(34)
        send_btn.setFont(QFont("Consolas", 9, QFont.Bold))
        send_btn.setCursor(Qt.PointingHandCursor)
        send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00e5ff, stop:1 #50aaff);
                border: none;
                border-radius: 4px;
                color: #06090f;
                padding: 0 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #33eeff, stop:1 #80c4ff);
                color: #000000;
            }
        """)
        send_btn.clicked.connect(self._on_home_submit)
        ic_l.addWidget(send_btn)

        layout.addWidget(input_card)
        return tab

    def _create_home_kpi(self, title: str, main_val: str, sub_val: str, text_color: str, bg_rgba: str, border_rgba: str) -> QFrame:
        card = QFrame()
        card.setFixedHeight(68)
        card.setStyleSheet(f"""
            QFrame {{
                background: {bg_rgba};
                border: 1px solid {border_rgba};
                border-radius: 8px;
            }}
        """)
        l = QVBoxLayout(card)
        l.setContentsMargins(12, 8, 12, 8)
        l.setSpacing(2)

        t_lbl = QLabel(title)
        t_lbl.setFont(QFont("Consolas", 7, QFont.Bold))
        t_lbl.setStyleSheet(f"color: {text_color}; letter-spacing: 0.8px; background: transparent; border: none;")
        l.addWidget(t_lbl)

        val_row = QHBoxLayout()
        val_row.setSpacing(8)

        v_lbl = QLabel(main_val)
        v_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        v_lbl.setStyleSheet("color: #ffffff; background: transparent; border: none;")
        val_row.addWidget(v_lbl)

        s_lbl = QLabel(f"• {sub_val}")
        s_lbl.setFont(QFont("Segoe UI", 8))
        s_lbl.setStyleSheet("color: #7b8c9f; background: transparent; border: none;")
        val_row.addWidget(s_lbl)
        val_row.addStretch()

        l.addLayout(val_row)
        return card

    def _on_home_submit(self):
        text = self._home_input.text().strip()
        if not text:
            return
        self._home_input.clear()
        self._add_message("user", text)
        self._holo_core_small.set_state("THINKING")
        self._core_state_lbl.setText("STATE: THINKING")
        self._core_state_lbl.setStyleSheet("color: #50aaff;")
        self._right_goal_lbl.setText(f"PROCESSING:\n{text[:45]}...")
        self._on_tab_selected(1)
        app_signals.message_received.emit("user", text, True)

    # -------------------------------------------------------------------------
    # TAB 1: CONSOLE (INTERACTIVE NEURAL CHAT)
    # -------------------------------------------------------------------------
    def _build_console_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(12)

        # Header with Holographic Status
        head = QHBoxLayout()
        t_lbl = QLabel("NEURAL CONSOLE // MULTIMODAL EXECUTIVE")
        t_lbl.setFont(QFont("Consolas", 11, QFont.Bold))
        t_lbl.setStyleSheet("color: #00e5ff; letter-spacing: 1px;")
        head.addWidget(t_lbl)

        head.addStretch()

        self._console_status_pill = StatusPill("●", "Ready", active=True)
        head.addWidget(self._console_status_pill)
        layout.addLayout(head)

        # Quick Action Chips inside a horizontal scroll area so they don't bloat min width
        chips_container = QWidget()
        chips_container.setStyleSheet("background: transparent;")
        chips_layout = QHBoxLayout(chips_container)
        chips_layout.setContentsMargins(0, 0, 0, 0)
        chips_layout.setSpacing(8)
        prompts = [
            ("🌤️ Weather Check", "what is the current weather?"),
            ("⚡ System Diagnostics", "run full system diagnostics"),
            ("🧠 Inspect Memory", "inspect active working memory"),
            ("🔍 Scan Workspace", "scan workspace and inspect files"),
            ("📊 Hardware Health", "check cpu and gpu status"),
        ]
        for label, cmd in prompts:
            btn = QPushButton(label)
            btn.setFont(QFont("Consolas", 8))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(22, 30, 44, 0.8);
                    border: 1px solid rgba(0, 229, 255, 0.25);
                    border-radius: 12px;
                    color: #a5b4cb;
                    padding: 5px 12px;
                }
                QPushButton:hover {
                    background: rgba(0, 229, 255, 0.15);
                    border: 1px solid #00e5ff;
                    color: #ffffff;
                }
            """)
            btn.clicked.connect(lambda checked, c=cmd: self._send_quick_command(c))
            chips_layout.addWidget(btn)
        chips_layout.addStretch()

        chips_scroll = QScrollArea()
        chips_scroll.setWidget(chips_container)
        chips_scroll.setWidgetResizable(True)
        chips_scroll.setFixedHeight(36)
        chips_scroll.setFrameShape(QFrame.Shape.NoFrame)
        chips_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        chips_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        chips_scroll.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(chips_scroll)

        # Scroll Area for Messages
        self._chat_scroll = QScrollArea()
        self._chat_scroll.setWidgetResizable(True)
        self._chat_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._chat_scroll.setStyleSheet("background: transparent; border: none;")

        self._chat_container = QWidget()
        self._chat_container.setStyleSheet("background: transparent;")
        self._chat_layout = QVBoxLayout(self._chat_container)
        self._chat_layout.setContentsMargins(4, 4, 4, 4)
        self._chat_layout.setSpacing(12)
        self._chat_layout.addStretch()

        self._chat_scroll.setWidget(self._chat_container)
        layout.addWidget(self._chat_scroll, 1)

        # Initial Welcome Card
        self._add_message(
            "agent",
            "AuraAI Holographic Cognitive Core active. Multi-agent routing, hardware telemetry, vector memory vaults, and tool execution pipelines standing by.",
            intent_tag="INITIALIZE",
        )

        # Input Capsule
        input_card = SciFiTechCard(accent_color=QColor(0, 229, 255), chamfer_size=8)
        ic_l = QHBoxLayout(input_card)
        ic_l.setContentsMargins(14, 8, 14, 8)
        ic_l.setSpacing(12)

        # Live Mic Toggle Button
        self._mic_active = False
        self._mic_btn = QPushButton("🎙️")
        self._mic_btn.setCheckable(True)
        self._mic_btn.setFixedSize(36, 34)
        self._mic_btn.setCursor(Qt.PointingHandCursor)
        self._mic_btn.setToolTip("Toggle Live Microphone")
        self._update_mic_style(False)
        self._mic_btn.clicked.connect(self._on_mic_toggle)
        ic_l.addWidget(self._mic_btn)

        # Text input
        self._chat_input = QLineEdit()
        self._chat_input.setPlaceholderText("Enter command or prompt AuraAI (Press Enter)...")
        self._chat_input.setFont(QFont("Segoe UI", 10))
        self._chat_input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #ffffff;
                padding: 6px;
            }
            QLineEdit::placeholder {
                color: #55657a;
            }
        """)
        self._chat_input.returnPressed.connect(self._on_chat_submit)
        ic_l.addWidget(self._chat_input, 1)

        send_btn = QPushButton("SEND ➤")
        send_btn.setFont(QFont("Consolas", 9, QFont.Bold))
        send_btn.setFixedSize(85, 34)
        send_btn.setCursor(Qt.PointingHandCursor)
        send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00e5ff, stop:1 #50aaff);
                border: none;
                border-radius: 4px;
                color: #06090f;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #33eeff, stop:1 #80c4ff);
            }
        """)
        send_btn.clicked.connect(self._on_chat_submit)
        ic_l.addWidget(send_btn)

        layout.addWidget(input_card)
        return tab

    def _update_mic_style(self, active: bool):
        if active:
            self._mic_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(244, 63, 94, 0.25);
                    border: 1.5px solid #f43f5e;
                    border-radius: 4px;
                    color: #ff4d6d;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background: rgba(244, 63, 94, 0.4);
                }
            """)
        else:
            self._mic_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(0, 229, 255, 0.25);
                    border-radius: 4px;
                    color: #a5b4cb;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background: rgba(0, 229, 255, 0.15);
                    border: 1px solid #00e5ff;
                    color: #00e5ff;
                }
            """)

    def _on_mic_toggle(self):
        self._mic_active = not self._mic_active
        self._mic_btn.setChecked(self._mic_active)
        self._update_mic_style(self._mic_active)
        if self._mic_active:
            self._holo_core_small.set_state("LISTENING")
            self._core_state_lbl.setText("STATE: LISTENING")
            self._core_state_lbl.setStyleSheet("color: #10b981;")
            self._chat_input.setPlaceholderText("🎙️ Live Mic Active... (Speak or click mic to stop)")
        else:
            self._holo_core_small.set_state("IDLE")
            self._core_state_lbl.setText("STATE: IDLE")
            self._core_state_lbl.setStyleSheet("color: #10b981;")
            self._chat_input.setPlaceholderText("Enter command or prompt AuraAI (Press Enter)...")

    def _send_quick_command(self, cmd: str):
        self._chat_input.setText(cmd)
        self._on_chat_submit()

    def _on_chat_submit(self):
        text = self._chat_input.text().strip()
        if not text:
            return

        self._add_message("user", text)
        self._chat_input.clear()
        self._holo_core_small.set_state("THINKING")
        self._core_state_lbl.setText("STATE: THINKING")
        self._core_state_lbl.setStyleSheet("color: #818cf8;")
        app_signals.message_received.emit("user", text, True)

    def _add_message(self, sender: str, text: str, intent_tag: str = "EXECUTION"):
        card = HoloMessageCard(sender, text, intent_tag=intent_tag)
        count = self._chat_layout.count()
        self._chat_layout.insertWidget(max(0, count - 1), card)
        QTimer.singleShot(50, lambda: self._chat_scroll.verticalScrollBar().setValue(
            self._chat_scroll.verticalScrollBar().maximum()
        ))

    # -------------------------------------------------------------------------
    # TAB 1: COGNITION & DAG VISUALIZER
    # -------------------------------------------------------------------------
    def _build_cognition_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(12)

        t_lbl = QLabel("COGNITIVE GRAPH // MULTI-AGENT REASONING PIPELINE")
        t_lbl.setFont(QFont("Consolas", 11, QFont.Bold))
        t_lbl.setStyleSheet("color: #00e5ff; letter-spacing: 1px;")
        layout.addWidget(t_lbl)

        self._dag_visualizer = DagVisualizer()
        layout.addWidget(self._dag_visualizer, 1)
        return tab

    # -------------------------------------------------------------------------
    # TAB 2: OBSERVATORY MATRIX
    # -------------------------------------------------------------------------
    def _build_observatory_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(14)

        t_lbl = QLabel("OBSERVATORY // WORLD STATE & DESKTOP PERCEPTION")
        t_lbl.setFont(QFont("Consolas", 11, QFont.Bold))
        t_lbl.setStyleSheet("color: #00e5ff; letter-spacing: 1px;")
        layout.addWidget(t_lbl)

        grid = QGridLayout()
        grid.setSpacing(14)

        card1 = SciFiTechCard()
        l1 = QVBoxLayout(card1)
        l1.addWidget(QLabel("ACTIVE FOCUSED WINDOW"))
        self._obs_win_lbl = QLabel("AuraAI Cyber Command OS")
        self._obs_win_lbl.setFont(QFont("Consolas", 11))
        self._obs_win_lbl.setStyleSheet("color: #50aaff;")
        l1.addWidget(self._obs_win_lbl)
        grid.addWidget(card1, 0, 0)

        card2 = SciFiTechCard()
        l2 = QVBoxLayout(card2)
        l2.addWidget(QLabel("CURSOR & RESOLUTION TRACKER"))
        self._obs_cursor_lbl = QLabel("X: 960 | Y: 540 // 1920x1080 FHD")
        self._obs_cursor_lbl.setFont(QFont("Consolas", 11))
        self._obs_cursor_lbl.setStyleSheet("color: #10b981;")
        l2.addWidget(self._obs_cursor_lbl)
        grid.addWidget(card2, 0, 1)

        card3 = SciFiTechCard()
        l3 = QVBoxLayout(card3)
        l3.addWidget(QLabel("BROWSER DOM HOOK / ACTIVE URL"))
        self._obs_dom_lbl = QLabel("NO ACTIVE WEB HOOK DETECTED")
        self._obs_dom_lbl.setFont(QFont("Consolas", 10))
        self._obs_dom_lbl.setStyleSheet("color: #a5b4cb;")
        l3.addWidget(self._obs_dom_lbl)
        grid.addWidget(card3, 1, 0)

        card4 = SciFiTechCard()
        l4 = QVBoxLayout(card4)
        l4.addWidget(QLabel("SCREEN CAPTURE & VISION ENGINE"))
        self._obs_vision_lbl = QLabel("ONLINE // Screen OCR & Frame Buffer Ready")
        self._obs_vision_lbl.setFont(QFont("Consolas", 10))
        self._obs_vision_lbl.setStyleSheet("color: #00e5ff;")
        l4.addWidget(self._obs_vision_lbl)
        grid.addWidget(card4, 1, 1)

        layout.addLayout(grid)
        layout.addStretch()
        return tab

    # -------------------------------------------------------------------------
    # TAB 3: NEURAL MEMORY VAULT
    # -------------------------------------------------------------------------
    def _build_memory_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(14)

        t_lbl = QLabel("NEURAL MEMORY // VECTOR VAULT & RETRIEVAL MATRIX")
        t_lbl.setFont(QFont("Consolas", 11, QFont.Bold))
        t_lbl.setStyleSheet("color: #00e5ff; letter-spacing: 1px;")
        layout.addWidget(t_lbl)

        search_box = SciFiTechCard(chamfer_size=6)
        sb_l = QHBoxLayout(search_box)
        sb_l.setContentsMargins(12, 6, 12, 6)
        s_input = QLineEdit()
        s_input.setPlaceholderText("Search memory entries, preferences, session context...")
        s_input.setStyleSheet("background: transparent; border: none; color: #ffffff;")
        sb_l.addWidget(s_input)
        layout.addWidget(search_box)

        mem_scroll = QScrollArea()
        mem_scroll.setWidgetResizable(True)
        mem_scroll.setStyleSheet("background: transparent; border: none;")

        mem_cont = QWidget()
        mem_l = QVBoxLayout(mem_cont)
        mem_l.setSpacing(10)

        entries = [
            ("PREFERENCE", "User prefers futuristic HUD interface with glassmorphism and cyan telemetry.", "1.00"),
            ("WORKSPACE", "Project root mapped to D:/Sreekanta/VS Code Project/Desktop AI/AuraAI.", "0.99"),
            ("HARDWARE", "Intel Wi-Fi 6 AX201, NVIDIA GTX 1650, 16GB RAM.", "0.98"),
            ("GUARDRAIL", "Always use project virtual environment (.venv) for command execution.", "1.00"),
        ]

        for tag, content, conf in entries:
            card = SciFiTechCard(accent_color=QColor(80, 170, 255), chamfer_size=6)
            c_l = QVBoxLayout(card)
            c_l.setContentsMargins(14, 10, 14, 10)

            ch = QHBoxLayout()
            b = QLabel(f"[{tag}]")
            b.setFont(QFont("Consolas", 8, QFont.Bold))
            b.setStyleSheet("color: #fbbf24; background: rgba(251, 191, 36, 0.12); padding: 2px 6px; border-radius: 3px;")
            ch.addWidget(b)
            ch.addStretch()

            cf = QLabel(f"CONFIDENCE: {conf}")
            cf.setFont(QFont("Consolas", 8))
            cf.setStyleSheet("color: #627289;")
            ch.addWidget(cf)
            c_l.addLayout(ch)

            ct = QLabel(content)
            ct.setFont(QFont("Segoe UI", 9))
            ct.setStyleSheet("color: #f3f6fc;")
            ct.setWordWrap(True)
            c_l.addWidget(ct)

            mem_l.addWidget(card)

        mem_l.addStretch()
        mem_scroll.setWidget(mem_cont)
        layout.addWidget(mem_scroll, 1)
        return tab

    # -------------------------------------------------------------------------
    # TAB 4: DEEP HARDWARE TELEMETRY
    # -------------------------------------------------------------------------
    def _build_telemetry_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(14)

        t_lbl = QLabel("HARDWARE TELEMETRY // LIVE HARDWARE GAUGES")
        t_lbl.setFont(QFont("Consolas", 11, QFont.Bold))
        t_lbl.setStyleSheet("color: #00e5ff; letter-spacing: 1px;")
        layout.addWidget(t_lbl)

        grid = QGridLayout()
        grid.setSpacing(14)

        # CPU Card
        card_cpu = SciFiTechCard()
        cl = QVBoxLayout(card_cpu)
        cl.addWidget(QLabel("CPU LOAD & FREQUENCY"))
        self._tab_cpu_val = QLabel("--%")
        self._tab_cpu_val.setFont(QFont("Consolas", 22, QFont.Bold))
        self._tab_cpu_val.setStyleSheet("color: #00e5ff;")
        cl.addWidget(self._tab_cpu_val)
        self._tab_cpu_sub = QLabel("8 Cores / 16 Threads")
        self._tab_cpu_sub.setStyleSheet("color: #a5b4cb;")
        cl.addWidget(self._tab_cpu_sub)
        grid.addWidget(card_cpu, 0, 0)

        # GPU Card
        card_gpu = SciFiTechCard()
        gl = QVBoxLayout(card_gpu)
        gl.addWidget(QLabel("GPU 0 (NVIDIA GTX 1650)"))
        self._tab_gpu_val = QLabel("--%")
        self._tab_gpu_val.setFont(QFont("Consolas", 22, QFont.Bold))
        self._tab_gpu_val.setStyleSheet("color: #50aaff;")
        gl.addWidget(self._tab_gpu_val)
        self._tab_gpu_sub = QLabel("VRAM: -- / 4096MB | Temp: --°C")
        self._tab_gpu_sub.setStyleSheet("color: #a5b4cb;")
        gl.addWidget(self._tab_gpu_sub)
        grid.addWidget(card_gpu, 0, 1)

        # RAM Card
        card_ram = SciFiTechCard()
        rl = QVBoxLayout(card_ram)
        rl.addWidget(QLabel("SYSTEM MEMORY (RAM)"))
        self._tab_ram_val = QLabel("-- GB")
        self._tab_ram_val.setFont(QFont("Consolas", 22, QFont.Bold))
        self._tab_ram_val.setStyleSheet("color: #10b981;")
        rl.addWidget(self._tab_ram_val)
        self._tab_ram_sub = QLabel("Usage: --%")
        self._tab_ram_sub.setStyleSheet("color: #a5b4cb;")
        rl.addWidget(self._tab_ram_sub)
        grid.addWidget(card_ram, 1, 0)

        # Network Card
        card_net = SciFiTechCard()
        nl = QVBoxLayout(card_net)
        nl.addWidget(QLabel("NETWORK & WI-FI 6 LINK"))
        self._tab_net_val = QLabel("↓ -- KB/s")
        self._tab_net_val.setFont(QFont("Consolas", 22, QFont.Bold))
        self._tab_net_val.setStyleSheet("color: #fbbf24;")
        nl.addWidget(self._tab_net_val)
        self._tab_net_sub = QLabel("SSID: -- | Signal: --%")
        self._tab_net_sub.setStyleSheet("color: #a5b4cb;")
        nl.addWidget(self._tab_net_sub)
        grid.addWidget(card_net, 1, 1)

        layout.addLayout(grid)
        layout.addStretch()
        return tab

    # -------------------------------------------------------------------------
    # TAB 5: SYSTEM SETTINGS
    # -------------------------------------------------------------------------
    def _build_settings_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(14)

        t_lbl = QLabel("SYSTEM CONFIGURATION // AI & COGNITIVE ENGINES")
        t_lbl.setFont(QFont("Consolas", 11, QFont.Bold))
        t_lbl.setStyleSheet("color: #00e5ff; letter-spacing: 1px;")
        layout.addWidget(t_lbl)

        card = SciFiTechCard()
        cl = QVBoxLayout(card)
        cl.setSpacing(14)

        cl.addWidget(QLabel("PRIMARY COGNITIVE AI MODEL"))
        cb_ai = QComboBox()
        cb_ai.addItems([
            "Groq Cloud (LLaMA 3.3 70B Versatile) [Active]",
            "Claude 3.5 Sonnet (Anthropic Direct)",
            "Google Gemini 2.0 Flash",
            "Ollama (Local Offline Reasoning)",
        ])
        cb_ai.setStyleSheet("""
            QComboBox {
                background: #101622;
                border: 1px solid rgba(0, 229, 255, 0.35);
                border-radius: 4px;
                padding: 8px 12px;
                color: #ffffff;
                font-family: Consolas;
            }
        """)
        cl.addWidget(cb_ai)

        cl.addWidget(QLabel("HARDWARE ACCELERATION ENGINE"))
        cb_accel = QComboBox()
        cb_accel.addItems([
            "NVIDIA CUDA (GeForce GTX 1650) [Active]",
            "DirectML GPU Acceleration",
            "CPU Multi-Threading (16 Cores)",
        ])
        cb_accel.setStyleSheet("""
            QComboBox {
                background: #101622;
                border: 1px solid rgba(0, 229, 255, 0.35);
                border-radius: 4px;
                padding: 8px 12px;
                color: #ffffff;
                font-family: Consolas;
            }
        """)
        cl.addWidget(cb_accel)

        layout.addWidget(card)
        layout.addStretch()
        return tab

    # -------------------------------------------------------------------------
    # RIGHT LIVE DECK
    # -------------------------------------------------------------------------
    def _build_right_deck(self) -> QWidget:
        deck = QWidget()
        deck.setFixedWidth(210)
        deck.setStyleSheet("background: #06090f; border-left: 1px solid rgba(255, 255, 255, 0.06);")

        layout = QVBoxLayout(deck)
        layout.setContentsMargins(14, 16, 14, 16)
        layout.setSpacing(14)

        d_title = QLabel("TACTICAL DECK")
        d_title.setFont(QFont("Consolas", 8, QFont.Bold))
        d_title.setStyleSheet("color: #00e5ff; letter-spacing: 1px;")
        layout.addWidget(d_title)

        # Active Goal Card
        g_card = SciFiTechCard(accent_color=QColor(251, 191, 36), chamfer_size=6)
        gc_l = QVBoxLayout(g_card)
        gc_l.setContentsMargins(12, 10, 12, 10)
        gc_l.addWidget(QLabel("ACTIVE COGNITIVE GOAL"))
        self._right_goal_lbl = QLabel("STANDBY // Awaiting Operator Input")
        self._right_goal_lbl.setFont(QFont("Consolas", 8))
        self._right_goal_lbl.setStyleSheet("color: #fbbf24;")
        self._right_goal_lbl.setWordWrap(True)
        gc_l.addWidget(self._right_goal_lbl)
        layout.addWidget(g_card)

        # Hardware Progress Bars
        hw_card = SciFiTechCard(chamfer_size=6)
        hc_l = QVBoxLayout(hw_card)
        hc_l.setContentsMargins(12, 10, 12, 10)
        hc_l.setSpacing(8)

        hc_l.addWidget(QLabel("CPU ACTIVITY"))
        self._deck_bar_cpu = QProgressBar()
        self._deck_bar_cpu.setRange(0, 100)
        self._deck_bar_cpu.setValue(20)
        self._deck_bar_cpu.setFixedHeight(4)
        self._deck_bar_cpu.setTextVisible(False)
        self._deck_bar_cpu.setStyleSheet("QProgressBar { background: #141c2b; border-radius: 2px; } QProgressBar::chunk { background: #00e5ff; }")
        hc_l.addWidget(self._deck_bar_cpu)

        hc_l.addWidget(QLabel("RAM ACTIVITY"))
        self._deck_bar_ram = QProgressBar()
        self._deck_bar_ram.setRange(0, 100)
        self._deck_bar_ram.setValue(60)
        self._deck_bar_ram.setFixedHeight(4)
        self._deck_bar_ram.setTextVisible(False)
        self._deck_bar_ram.setStyleSheet("QProgressBar { background: #141c2b; border-radius: 2px; } QProgressBar::chunk { background: #10b981; }")
        hc_l.addWidget(self._deck_bar_ram)

        layout.addWidget(hw_card)
        layout.addStretch()
        return deck

    # -------------------------------------------------------------------------
    # LIVE TELEMETRY UPDATE HANDLER
    # -------------------------------------------------------------------------
    def _on_telemetry_data(self, data: dict):
        cpu = data.get("cpu_pct", 0.0)
        mem_u = data.get("mem_used_gb", 0.0)
        mem_t = data.get("mem_total_gb", 16.0)
        mem_pct = data.get("mem_pct", 0.0)
        net_d = data.get("net_down_kb", 0.0)
        gpus = data.get("gpus", [])
        wifi = data.get("wifi", {})

        down_str = f"{net_d/1024:.1f}MB/s" if net_d > 1024 else f"{net_d:.0f}KB/s"

        # Top Titlebar
        if hasattr(self, "_title_ticker"):
            gpu_u = gpus[0].get("util_pct", 0.0) if gpus else 0.0
            self._title_ticker.setText(f"CPU: {cpu:.0f}% | GPU: {gpu_u:.0f}% | RAM: {mem_u:.1f}/{mem_t:.1f}G | NET: ↓{down_str}")

        # Right Deck Bars
        if hasattr(self, "_deck_bar_cpu"):
            self._deck_bar_cpu.setValue(int(cpu))
        if hasattr(self, "_deck_bar_ram"):
            self._deck_bar_ram.setValue(int(mem_pct))

        # Telemetry Tab
        if hasattr(self, "_tab_cpu_val"):
            self._tab_cpu_val.setText(f"{cpu:.1f}%")
            self._tab_ram_val.setText(f"{mem_u:.1f} / {mem_t:.1f} GB")
            self._tab_ram_sub.setText(f"Usage: {mem_pct:.1f}%")
            self._tab_net_val.setText(f"↓ {down_str}")
            self._tab_net_sub.setText(f"SSID: {wifi.get('ssid', 'N/A')} | Signal: {wifi.get('signal_pct', 0)}%")

            if gpus:
                g0 = gpus[0]
                self._tab_gpu_val.setText(f"{g0.get('util_pct', 0):.0f}%")
                self._tab_gpu_sub.setText(f"VRAM: {g0.get('mem_used_mb', 0):.0f}/{g0.get('mem_total_mb', 4096):.0f}MB | Temp: {g0.get('temp_c', 0):.0f}°C")

    # -------------------------------------------------------------------------
    # SIGNALS & OVERLAYS INTERACTION
    # -------------------------------------------------------------------------
    def _connect_signals(self):
        app_signals.message_received.connect(self._on_message_received)
        app_signals.execution_started.connect(self._on_execution_started)
        app_signals.execution_finished.connect(self._on_execution_finished)
        app_signals.step_updated.connect(self._on_step_updated)
        app_signals.world_state_changed.connect(self._on_world_state)
        app_signals.toggle_chat_overlay.connect(self.toggle_chat_overlay)
        app_signals.toggle_weather_overlay.connect(self.toggle_weather_overlay)
        app_signals.toggle_system_overlay.connect(self.toggle_system_overlay)
        app_signals.toggle_system_status_overlay.connect(self.toggle_system_status_overlay)
        app_signals.toggle_agent_task_overlay.connect(self.toggle_agent_task_overlay)
        app_signals.toggle_personal_os_overlay.connect(self.toggle_personal_os_overlay)

    def _on_message_received(self, sender: str, content: str, is_user: bool):
        if not is_user:
            self._add_message("agent", content, intent_tag="REASONING")
            self._holo_core_small.set_state("IDLE")
            self._core_state_lbl.setText("STATE: IDLE")
            self._core_state_lbl.setStyleSheet("color: #10b981;")

    def _on_execution_started(self, task_id: str):
        self._console_status_pill.set_active(True)
        self._console_status_pill.set_label("Executing")
        self._holo_core_small.set_state("EXECUTING")
        self._core_state_lbl.setText("STATE: EXECUTING")
        self._core_state_lbl.setStyleSheet("color: #fbbf24;")
        self._right_goal_lbl.setText(f"TASK: {task_id}")

    def _on_execution_finished(self, task_id: str, success: bool):
        self._console_status_pill.set_active(False)
        self._console_status_pill.set_label("Ready")
        self._holo_core_small.set_state("IDLE")
        self._core_state_lbl.setText("STATE: IDLE")
        self._core_state_lbl.setStyleSheet("color: #10b981;")
        self._right_goal_lbl.setText("STANDBY // Awaiting Operator Input")

    def _on_step_updated(self, step: ExecutionStep):
        if step.description:
            self._right_goal_lbl.setText(f"STEP: {step.title}\n{step.description[:50]}...")

    def _on_world_state(self, snapshot: WorldStateSnapshot):
        if hasattr(self, "_obs_win_lbl"):
            self._obs_win_lbl.setText(snapshot.focused_window or "Desktop Surface")
            self._obs_cursor_lbl.setText(f"X: {snapshot.mouse_position[0]} | Y: {snapshot.mouse_position[1]} // 1920x1080 FHD")
            if snapshot.active_url:
                self._obs_dom_lbl.setText(snapshot.active_url)

    # -------------------------------------------------------------------------
    # OVERLAYS LAUNCHERS
    # -------------------------------------------------------------------------
    def toggle_weather_overlay(self):
        if self._weather_overlay is None:
            self._weather_overlay = WeatherOverlay()
        if self._weather_overlay.isVisible():
            self._weather_overlay.hide()
        else:
            self._weather_overlay.show()

    def toggle_system_overlay(self):
        if self._sys_overlay is None:
            self._sys_overlay = SystemMonitorOverlay(auto_poll=True)
        if self._sys_overlay.isVisible():
            self._sys_overlay.hide()
        else:
            self._sys_overlay.show()

    def toggle_system_status_overlay(self):
        if self._status_overlay is None:
            self._status_overlay = SystemStatusOverlay()
        if self._status_overlay.isVisible():
            self._status_overlay.hide()
        else:
            self._status_overlay.show()

    def toggle_agent_task_overlay(self):
        if self._task_overlay is None:
            self._task_overlay = AgentTaskStatusOverlay()
        if self._task_overlay.isVisible():
            self._task_overlay.hide()
        else:
            self._task_overlay.show()

    def toggle_personal_os_overlay(self):
        if self._personal_os_overlay is None:
            self._personal_os_overlay = PersonalOSDashboardOverlay()
        if self._personal_os_overlay.isVisible():
            self._personal_os_overlay.hide()
        else:
            self._personal_os_overlay.show()

    def toggle_chat_overlay(self):
        if self._chat_overlay is None:
            self._chat_overlay = ChatWindowOverlay()
        if self._chat_overlay.isVisible():
            self._chat_overlay.hide()
        else:
            self._chat_overlay.show()
            self._chat_overlay.raise_()
            self._chat_overlay.activateWindow()

    # -------------------------------------------------------------------------
    # GEOMETRY PERSISTENCE (QSETTINGS) & AUTO LAPTOP RESIZING
    # -------------------------------------------------------------------------
    def _restore_geometry(self):
        screen = QApplication.primaryScreen().availableGeometry()
        pos = self._settings.value("pos", None)
        size = self._settings.value("size", None)

        # Comfortable laptop scaling (~76% width, ~68% height, max 580px height to stay well clear of taskbars)
        target_w = max(MIN_W, min(int(screen.width() * 0.76), 1140, screen.width() - 40))
        target_h = max(MIN_H, min(int(screen.height() * 0.68), 580, screen.height() - 100))

        if size is not None:
            try:
                w, h = int(size.width()), int(size.height())
                if w > int(screen.width() * 0.80) or h > 600 or h > int(screen.height() * 0.72):
                    w, h = target_w, target_h
                w = max(MIN_W, min(w, screen.width() - 40))
                h = max(MIN_H, min(h, 580, screen.height() - 100))
            except Exception:
                w, h = target_w, target_h
            self.resize(w, h)
        else:
            self.resize(target_w, target_h)

        # Center safely on screen
        w_curr = self.width()
        h_curr = self.height()
        safe_x = screen.left() + max(10, (screen.width() - w_curr) // 2)
        safe_y = screen.top() + max(10, (screen.height() - h_curr) // 2)

        if pos is not None:
            try:
                x = int(pos.x()) if hasattr(pos, "x") else int(pos[0])
                y = int(pos.y()) if hasattr(pos, "y") else int(pos[1])
                # If cached position would push bottom or right off screen, re-center
                if x < screen.left() or (x + w_curr) > screen.right() or y < screen.top() or (y + h_curr) > (screen.bottom() - 10):
                    x, y = safe_x, safe_y
                self.move(x, y)
            except Exception:
                self.move(safe_x, safe_y)
        else:
            self.move(safe_x, safe_y)

    def auto_fit_screen(self):
        """Auto-adjust window to perfectly fit current laptop display."""
        screen = QApplication.primaryScreen().availableGeometry()
        auto_w = max(MIN_W, min(int(screen.width() * 0.76), 1140, screen.width() - 40))
        auto_h = max(MIN_H, min(int(screen.height() * 0.68), 580, screen.height() - 100))
        self.resize(auto_w, auto_h)
        self.move(
            screen.left() + (screen.width() - auto_w) // 2,
            screen.top() + (screen.height() - auto_h) // 2,
        )
        self._save_geometry()

    def set_1080p(self):
        """Snap window to 1080p resolution (if supported by screen) or auto-fit."""
        self.auto_fit_screen()

    def _save_geometry(self):
        self._settings.setValue("pos", self.pos())
        self._settings.setValue("size", self.size())

    # -------------------------------------------------------------------------
    # SCAN-LINE SWEEP ANIMATION
    # -------------------------------------------------------------------------
    def _advance_scan(self):
        h = self.height()
        self._scan_y += self._scan_dir * 2.5
        if self._scan_y >= h or self._scan_y <= 0:
            self._scan_dir *= -1
        self.update()

    # -------------------------------------------------------------------------
    # DRAG & RESIZE HANDLING
    # -------------------------------------------------------------------------
    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

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
            self.width() - GRIP_SIZE - 6,
            self.height() - GRIP_SIZE - 6,
            GRIP_SIZE,
            GRIP_SIZE,
        )
        return grip_rect.contains(pos)

    def closeEvent(self, event):
        self._save_geometry()
        if hasattr(self, "_scan_timer") and self._scan_timer.isActive():
            self._scan_timer.stop()
        if hasattr(self, "_telemetry_worker") and self._telemetry_worker.isRunning():
            self._telemetry_worker.stop()
            self._telemetry_worker.wait(1000)
        if self._weather_overlay and self._weather_overlay.isVisible():
            self._weather_overlay.close()
        if self._sys_overlay and self._sys_overlay.isVisible():
            self._sys_overlay.close()
        if self._status_overlay and self._status_overlay.isVisible():
            self._status_overlay.close()
        if self._task_overlay and self._task_overlay.isVisible():
            self._task_overlay.close()
        if self._personal_os_overlay and self._personal_os_overlay.isVisible():
            self._personal_os_overlay.close()
        super().closeEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        r = QRect(0, 0, w, h)

        # Glowing corner brackets
        bl = 16
        p.setPen(QPen(QColor(0, 229, 255), 2))
        # Top-left
        p.drawLine(2, 2, 2 + bl, 2)
        p.drawLine(2, 2, 2, 2 + bl)
        # Top-right
        p.drawLine(w - 2, 2, w - 2 - bl, 2)
        p.drawLine(w - 2, 2, w - 2, 2 + bl)
        # Bottom-left
        p.drawLine(2, h - 2, 2 + bl, h - 2)
        p.drawLine(2, h - 2, 2, h - 2 - bl)
        # Bottom-right
        p.drawLine(w - 2, h - 2, w - 2 - bl, h - 2)
        p.drawLine(w - 2, h - 2, w - 2, h - 2 - bl)

        # Scan line (clipped to card interior)
        p.save()
        p.setClipRect(r.adjusted(2, 2, -2, -2))
        scan_col = QColor(0, 229, 255, 35)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(scan_col))
        p.drawRect(2, int(self._scan_y), w - 4, 2)
        p.restore()

        # Dotted Resize Grip Hint (bottom-right)
        p.setPen(QPen(QColor(90, 110, 135), 1))
        for i in range(3):
            for j in range(i, 3):
                dx = w - 8 - j * 4
                dy = h - 8 - i * 4
                p.drawPoint(dx, dy)

        p.end()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
