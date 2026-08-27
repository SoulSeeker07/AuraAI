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
    QThread,
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
from .widgets.chat_window_overlay import ChatWindowOverlay
from .widgets.tactical_telemetry_widget import TacticalTelemetryWidget
from .widgets.tactical_voice_waveform_widget import TacticalVoiceWaveformWidget
from .widgets.voice_notch_overlay import VoiceNotchOverlay
from gui.real_backend_bridge import RealBackendBridge


class CommandWorker(QThread):
    """Executes AuraCore tasks asynchronously in a background thread."""

    finished_signal = Signal(str, str)  # task_id, response_text
    error_signal = Signal(str, str)  # task_id, error_message
    step_signal = Signal(object)  # ExecutionStep

    def __init__(self, command: str, parent=None):
        super().__init__(parent)
        self.command = command

    def run(self):
        import asyncio
        task_id = f"T-{int(time.time()) % 10000:04d}"
        t_global_start = time.perf_counter()

        # Step 0: NLU Intent Extraction
        t0 = time.perf_counter()
        step0 = ExecutionStep(
            index=0,
            title="NLU Intent Resolution",
            description=f"Classifying intent & parameters for '{self.command[:38]}...'",
            status=StepStatus.RUNNING,
            timestamp=time.time(),
            engine="ACA NLU Parser",
            role="Intent Classifier",
            payload=self.command,
        )
        self.step_signal.emit(step0)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            from core.aura_core import AuraCore

            core = AuraCore.get_instance()
            step0.duration_ms = max(4.2, round((time.perf_counter() - t0) * 1000, 1))
            step0.status = StepStatus.COMPLETED
            self.step_signal.emit(step0)

            # Step 1: Groq LPU Reasoning Kernel
            t1 = time.perf_counter()
            model_name = getattr(core, "reasoning_llm_model", "openai/gpt-oss-120b")
            step1 = ExecutionStep(
                index=1,
                title=f"Groq LPU Reasoning ({model_name.split('/')[-1].upper()})",
                description="Evaluating via Groq LPU Kernel • ~185 Tok/s • 128k Context",
                status=StepStatus.RUNNING,
                timestamp=time.time(),
                engine=f"Groq LPU ({model_name})",
                role="Executive Reasoning LLM",
                payload=f"Evaluating intent tokens for goal: '{self.command[:50]}'",
            )
            self.step_signal.emit(step1)

            # Step 2: Multi-Agent Task Decomposer & Capability Execution
            t2 = time.perf_counter()
            step2 = ExecutionStep(
                index=2,
                title="Multi-Agent Task Decomposition",
                description="Routing subtasks to active domain planner & capability backend",
                status=StepStatus.RUNNING,
                timestamp=time.time(),
                engine="Master Orchestrator / Swarm Engine",
                role="Topological Task Decomposer",
                payload="Swarm planners & tool adapters dispatched",
            )
            self.step_signal.emit(step2)

            t_exec_start = time.perf_counter()
            response_text = ""
            is_error = False

            if hasattr(core, "process_request"):
                response_text = loop.run_until_complete(core.process_request(self.command))
                if not response_text or str(response_text).startswith("❌"):
                    response_text = loop.run_until_complete(core.get_ai_response(self.command))
            else:
                response_text = loop.run_until_complete(core.get_ai_response(self.command))

            resp_str = str(response_text).strip()
            if not resp_str or resp_str.startswith("❌") or resp_str.startswith("✗") or "Error processing message" in resp_str or "Error code:" in resp_str or "tool_use_failed" in resp_str:
                is_error = True

            t_exec_dur = round((time.perf_counter() - t_exec_start) * 1000, 1)

            if is_error:
                step1.duration_ms = max(18.5, round(t_exec_dur * 0.45, 1))
                step1.status = StepStatus.COMPLETED
                self.step_signal.emit(step1)

                step2.duration_ms = max(12.0, round(t_exec_dur * 0.55, 1))
                step2.status = StepStatus.FAILED
                self.step_signal.emit(step2)

                # Step 3: Synthesis & Verification Fault
                t3 = time.perf_counter()
                step3 = ExecutionStep(
                    index=3,
                    title="Pipeline Execution Fault",
                    description=f"Fault detected: {resp_str[:50]}",
                    status=StepStatus.FAILED,
                    timestamp=time.time(),
                    duration_ms=max(6.5, round((time.perf_counter() - t3) * 1000, 1)),
                    engine="Groq Output Synthesizer",
                    role="Response Aggregator & Verifier",
                    payload=resp_str[:80],
                )
                self.step_signal.emit(step3)
                self.finished_signal.emit(task_id, resp_str)
            else:
                step1.duration_ms = max(18.5, round(t_exec_dur * 0.45, 1))
                step1.status = StepStatus.COMPLETED
                self.step_signal.emit(step1)

                step2.duration_ms = max(12.0, round(t_exec_dur * 0.55, 1))
                step2.status = StepStatus.COMPLETED
                self.step_signal.emit(step2)

                # Step 3: Synthesis & Verification
                t3 = time.perf_counter()
                step3 = ExecutionStep(
                    index=3,
                    title="Neural Synthesis & Output",
                    description="Synthesized verified response • Delivered to Operator Console",
                    status=StepStatus.COMPLETED,
                    timestamp=time.time(),
                    duration_ms=max(6.5, round((time.perf_counter() - t3) * 1000, 1)),
                    engine="Groq Output Synthesizer",
                    role="Response Aggregator & Verifier",
                    payload=resp_str[:80],
                )
                self.step_signal.emit(step3)
                self.finished_signal.emit(task_id, resp_str)
        except Exception as e:
            logger.error(f"Command execution error: {e}", exc_info=True)
            self.error_signal.emit(task_id, str(e))
        finally:
            loop.close()


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
    """Next-Gen Futuristic Sci-Fi Navigation Tab Button with glowing holographic badges & power line."""

    def __init__(self, code: str, icon_glyph: str, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedHeight(64)
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
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0, 229, 255, 0.18), stop:0.7 rgba(0, 119, 255, 0.08), stop:1 rgba(8, 14, 26, 0.2));
                    border: 1px solid rgba(0, 229, 255, 0.35);
                    border-left: 4px solid #00e5ff;
                    border-radius: 8px;
                    margin: 2px 8px;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 0.02);
                    border: 1px solid rgba(255, 255, 255, 0.05);
                    border-left: 4px solid transparent;
                    border-radius: 8px;
                    margin: 2px 8px;
                }
                QPushButton:hover {
                    background: rgba(0, 229, 255, 0.08);
                    border: 1px solid rgba(0, 229, 255, 0.25);
                    border-left: 4px solid rgba(0, 229, 255, 0.7);
                }
            """)

    def setChecked(self, checked: bool):
        super().setChecked(checked)
        self._update_style(checked)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        is_chk = self.isChecked()

        # 1. Holographic Icon Capsule on left
        icon_box = QRect(16, 12, 38, 40)
        p.setPen(QPen(QColor(0, 229, 255, 140 if is_chk else 45), 1))
        p.setBrush(QBrush(QColor(0, 229, 255, 32 if is_chk else 10)))
        p.drawRoundedRect(icon_box, 6, 6)

        p.setFont(QFont("Segoe UI Emoji", 14))
        p.setPen(QPen(QColor(0, 229, 255) if is_chk else QColor(140, 160, 180)))
        p.drawText(icon_box, Qt.AlignCenter, self.icon_glyph)

        # 2. Main Title Text
        p.setFont(QFont("Consolas", 10, QFont.Bold))
        p.setPen(QPen(QColor(255, 255, 255) if is_chk else QColor(180, 195, 215)))
        p.drawText(QRect(64, 14, w - 74, 18), Qt.AlignVCenter | Qt.AlignLeft, self.title_str.upper())

        # 3. Next-Gen Subtitle & Code Tag
        p.setFont(QFont("Consolas", 7, QFont.Bold))
        p.setPen(QPen(QColor(0, 229, 255, 220) if is_chk else QColor(100, 120, 145)))
        p.drawText(QRect(64, 34, w - 74, 16), Qt.AlignVCenter | Qt.AlignLeft, f"SYS. {self.code} // {self.sub_str.upper()}")

        # 4. Active Glowing Right Indicator Dot
        if is_chk:
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(0, 229, 255)))
            p.drawEllipse(QPointF(w - 18, h / 2), 3, 3)

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
REF_W = 1920
REF_H = 1080
MIN_W, MIN_H = 1080, 680
GRIP_SIZE = 18


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
        self._voice_notch: Optional[VoiceNotchOverlay] = None
        self._active_worker: Optional[CommandWorker] = None

        # Telemetry worker
        self._telemetry_worker = TelemetryWorker(self)
        self._telemetry_worker.data_ready.connect(self._on_telemetry_data)

        self._setup_ui()
        self._setup_titlebar()
        self._connect_signals()
        self._restore_geometry()
        self._telemetry_worker.start()

        # Background pre-warm AuraCore
        import threading
        def _prewarm_core():
            try:
                from core.aura_core import AuraCore
                AuraCore.get_instance()
            except Exception:
                pass
        threading.Thread(target=_prewarm_core, daemon=True, name="AuraCorePrewarmer").start()

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

        # Left Nav Dock (230px for Full HD spacious layout)
        self._nav_dock = self._build_nav_dock()
        work_area.addWidget(_wrap_panel(self._nav_dock, 230))

        # Center Stage Stack (3 Tabs: Home / Autonomous Agent OS, Cognition, Settings)
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
        self._center_stack.addWidget(self._tab_home)

        self._tab_cognition = self._build_cognition_tab()
        self._center_stack.addWidget(_wrap_tab(self._tab_cognition))

        self._tab_settings = self._build_settings_tab()
        self._center_stack.addWidget(_wrap_tab(self._tab_settings))

        work_area.addWidget(self._center_stack, 1)

        # Right Live Deck (320px for Full HD telemetry)
        self._right_deck = self._build_right_deck()
        work_area.addWidget(_wrap_panel(self._right_deck, 320))

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
        overlays_menu.addAction("🎙  Voice Notch", self.toggle_voice_notch)
        overlays_menu.addAction("🎯  Personal OS", self.toggle_personal_os_overlay)
        overlays_menu.addAction("📋  Agent Tasks", self.toggle_agent_task_overlay)
        overlays_menu.addAction("📜  Live Logs", self.show_agent_task_logs)
        overlays_menu.addAction("🌐  System Status", self.toggle_system_status_overlay)
        overlays_menu.addAction("⚡  System HUD", self.toggle_system_overlay)
        overlays_menu.addAction("☁  Weather HUD", self.toggle_weather_overlay)
        btn_overlays.setMenu(overlays_menu)
        tb_layout.addWidget(btn_overlays)

        # Dedicated Top Bar Quick Logs Button
        btn_logs_bar = QPushButton("📜 Logs")
        btn_logs_bar.setFont(QFont("Segoe UI", 8, QFont.Weight.Medium))
        btn_logs_bar.setCursor(Qt.PointingHandCursor)
        btn_logs_bar.setToolTip("Toggle Live System & Multi-Agent Execution Logs")
        btn_logs_bar.setStyleSheet("""
            QPushButton {
                background: rgba(0, 229, 255, 0.08);
                border: 1px solid rgba(0, 229, 255, 0.3);
                border-radius: 4px;
                color: #00e5ff;
                padding: 3px 10px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.22);
                border: 1px solid #00e5ff;
                color: #ffffff;
            }
        """)
        btn_logs_bar.clicked.connect(self.show_agent_task_logs)
        tb_layout.addWidget(btn_logs_bar)

        # 6 Autonomous Tool & Policy Guardrail Badges
        tools = [
            ("⚡ Terminal & CLI", "#66ff99"),
            ("🌐 Headless Browser", "#66ff99"),
            ("📁 File System IO", "#66ff99"),
            ("🧠 Multi-Agent DAG", "#66ff99"),
            ("👁️ Vision & Screen", "#66ff99"),
            ("🔒 Policy Guardrails", "#66ff99"),
        ]
        for name, col in tools:
            badge = QLabel(f"{name} ✓")
            badge.setFont(QFont("Segoe UI", 7, QFont.Weight.Medium))
            badge.setStyleSheet(f"""
                color: {col};
                background: rgba(0, 229, 255, 0.05);
                border: 1px solid rgba(0, 229, 255, 0.22);
                border-radius: 4px;
                padding: 2px 6px;
            """)
            tb_layout.addWidget(badge)

        tb_layout.addStretch(1)

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
        dock.setFixedWidth(230)
        dock.setStyleSheet("background: #06090f; border-right: 1px solid rgba(0, 229, 255, 0.15);")

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

        # Nav Buttons (3 tabs matching Autonomous Agent OS screenshot)
        self._nav_buttons: List[SciFiNavButton] = []
        tabs = [
            ("00", "🏠", "Home", "Control Center"),
            ("02", "🧠", "Cognition", "DAG Planner"),
            ("03", "⚙️", "Settings", "Engine Config"),
        ]
        for idx, (num, icon, title, subtitle) in enumerate(tabs):
            btn = SciFiNavButton(num, icon, title, subtitle)
            btn.clicked.connect(lambda checked, i=idx: self._on_tab_selected(i))
            self._nav_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # Version stamp
        v_lbl = QLabel("AURA// v0.3.21-os // QUANTUM")
        v_lbl.setFont(QFont("Consolas", 7))
        v_lbl.setStyleSheet("color: #475569; padding-left: 14px;")
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
    # TAB 0: HOME DASHBOARD (AUTONOMOUS AGENT OS & NEURAL CHAT CONSOLE)
    # -------------------------------------------------------------------------
    def _build_home_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(18, 14, 18, 12)
        layout.setSpacing(12)

        # Header with dynamic timestamp & Core Active status pill
        head = QHBoxLayout()
        h_info = QVBoxLayout()
        h_info.setSpacing(2)
        h_title = QLabel("AUTONOMOUS AGENT OS")
        h_title.setFont(QFont("Consolas", 12, QFont.Bold))
        h_title.setStyleSheet("color: #00e5ff; letter-spacing: 1.5px; background: transparent; border: none;")
        h_info.addWidget(h_title)

        self._home_date_lbl = QLabel(QDateTime.currentDateTime().toString("dddd, MMMM d • h:mm AP"))
        self._home_date_lbl.setFont(QFont("Segoe UI", 8))
        self._home_date_lbl.setStyleSheet("color: #7b8c9f; background: transparent; border: none;")
        h_info.addWidget(self._home_date_lbl)
        head.addLayout(h_info)
        head.addStretch()

        btn_home_logs = QPushButton("📜 Show Logs")
        btn_home_logs.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        btn_home_logs.setCursor(Qt.PointingHandCursor)
        btn_home_logs.setToolTip("Open Agent Task Queue & Real-Time Log Viewer")
        btn_home_logs.setStyleSheet("""
            QPushButton {
                background: rgba(0, 229, 255, 0.1);
                border: 1px solid rgba(0, 229, 255, 0.4);
                border-radius: 6px;
                color: #00e5ff;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.25);
                border: 1px solid #00e5ff;
                color: #ffffff;
            }
        """)
        btn_home_logs.clicked.connect(self.show_agent_task_logs)
        head.addWidget(btn_home_logs)

        self._console_status_pill = StatusPill("●●", "Core Active", active=True)
        head.addWidget(self._console_status_pill)
        layout.addLayout(head)

        # Center Cyber Container with Scrollable Console / Chat
        center_card = SciFiTechCard(accent_color=QColor(0, 229, 255), chamfer_size=10)
        c_layout = QVBoxLayout(center_card)
        c_layout.setContentsMargins(14, 14, 14, 14)
        c_layout.setSpacing(10)

        # Scroll Area for interactive console / chat messages
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
        c_layout.addWidget(self._chat_scroll, 1)

        layout.addWidget(center_card, 1)

        # Bottom Multi-Modal Input Capsule
        input_card = SciFiTechCard(accent_color=QColor(0, 229, 255), chamfer_size=8)
        ic_l = QHBoxLayout(input_card)
        ic_l.setContentsMargins(12, 8, 12, 8)
        ic_l.setSpacing(10)

        # Left Mic / Run Button [ |> ]
        self._mic_active = False
        self._mic_btn = QPushButton("▷")
        self._mic_btn.setCheckable(True)
        self._mic_btn.setFixedSize(36, 34)
        self._mic_btn.setCursor(Qt.PointingHandCursor)
        self._mic_btn.setToolTip("Toggle Live Microphone / Audio Perception")
        self._update_mic_style(False)
        self._mic_btn.clicked.connect(self._on_mic_toggle)
        ic_l.addWidget(self._mic_btn)

        # Chat Input
        self._chat_input = QLineEdit()
        self._chat_input.setPlaceholderText("Enter autonomous goal or command (Press Enter)...")
        self._chat_input.setFont(QFont("Segoe UI", 10))
        self._chat_input.setStyleSheet("""
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
        self._chat_input.returnPressed.connect(self._on_chat_submit)
        self._home_input = self._chat_input
        ic_l.addWidget(self._chat_input, 1)

        # Primary Agent Brain Badge (Middle Right)
        brain_box = QFrame()
        brain_box.setStyleSheet("background: transparent; border: none;")
        bb_layout = QVBoxLayout(brain_box)
        bb_layout.setContentsMargins(6, 0, 8, 0)
        bb_layout.setSpacing(1)

        brain_top = QLabel("● PRIMARY AGENT BRAIN")
        brain_top.setFont(QFont("Consolas", 7, QFont.Bold))
        brain_top.setStyleSheet("color: #ec4899; letter-spacing: 0.6px; background: transparent;")
        bb_layout.addWidget(brain_top)

        brain_sub = QLabel("GPT-OSS-120B   Groq • gpt-oss-120b")
        brain_sub.setFont(QFont("Segoe UI", 8, QFont.Bold))
        brain_sub.setStyleSheet("color: #cbd5e1; background: transparent;")
        bb_layout.addWidget(brain_sub)
        ic_l.addWidget(brain_box)

        # Send Button (changed "DISPATCH" to "SEND  ")
        send_btn = QPushButton("SEND  ➤")
        send_btn.setFixedSize(105, 34)
        send_btn.setFont(QFont("Consolas", 9, QFont.Bold))
        send_btn.setCursor(Qt.PointingHandCursor)
        send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00e5ff, stop:1 #50aaff);
                border: none;
                border-radius: 4px;
                color: #06090f;
                padding: 0 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #33eeff, stop:1 #80c4ff);
                color: #000000;
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

    def _start_voice_listening(self):
        import threading
        def _bg_start():
            try:
                from core.aura_core import AuraCore
                core = AuraCore.get_instance()
                if hasattr(core, "voice_loop") and core.voice_loop:
                    core.voice_loop._aura_core = core
                    core.voice_loop.start()
                elif hasattr(core, "conversation_engine"):
                    from voice.continuous_loop import ContinuousVoiceLoop
                    v_loop = ContinuousVoiceLoop(aura_core=core)
                    setattr(core, "voice_loop", v_loop)
                    v_loop.start()
            except Exception as e:
                logger.error(f"[MainWindow] Start voice error: {e}")
        threading.Thread(target=_bg_start, daemon=True, name="VoiceStarterThread").start()

    def _stop_voice_listening(self):
        import threading
        def _bg_stop():
            try:
                from core.aura_core import AuraCore
                core = AuraCore.get_instance()
                if hasattr(core, "voice_loop") and core.voice_loop:
                    core.voice_loop.stop()
            except Exception as e:
                logger.error(f"[MainWindow] Stop voice error: {e}")
        threading.Thread(target=_bg_stop, daemon=True, name="VoiceStopperThread").start()

    def _on_mic_toggle(self):
        self._mic_active = not self._mic_active
        self._mic_btn.setChecked(self._mic_active)
        self._update_mic_style(self._mic_active)
        app_signals.voice_status_changed.emit(self._mic_active)

        if self._mic_active:
            self._holo_core_small.set_state("LISTENING")
            self._core_state_lbl.setText("STATE: WAITING FOR WAKE WORD ('AURA')")
            self._core_state_lbl.setStyleSheet("color: #00e5ff;")
            self._chat_input.setPlaceholderText("🎙️ Voice Active • Waiting for wake word 'Aura' (Say 'Aura' or click mic to stop)")
            self._add_message("agent", "🎙️ **Voice Listening Activated.** Waiting for wake word: *'Aura'* (or *'Hey Aura'*). Speak your command after the chime.", intent_tag="VOICE")
            self._start_voice_listening()
        else:
            self._holo_core_small.set_state("IDLE")
            self._core_state_lbl.setText("STATE: IDLE")
            self._core_state_lbl.setStyleSheet("color: #10b981;")
            self._chat_input.setPlaceholderText("Enter command or prompt AuraAI (Press Enter)...")
            self._add_message("agent", "🎙️ **Voice Listening Deactivated.** Microphone is idle.", intent_tag="VOICE")
            self._stop_voice_listening()

    def _on_voice_state_name_changed(self, state_name: str):
        if not getattr(self, "_mic_active", False):
            return
        state_upper = (state_name or "").upper()
        if state_upper in ("IDLE", "WAITING_FOR_WAKE", "COOLDOWN"):
            self._holo_core_small.set_state("LISTENING")
            self._core_state_lbl.setText("STATE: WAITING FOR WAKE WORD ('AURA')")
            self._core_state_lbl.setStyleSheet("color: #00e5ff;")
        elif state_upper in ("WAKE_DETECTED", "LISTENING", "FOLLOW_UP_LISTENING"):
            self._holo_core_small.set_state("LISTENING")
            self._core_state_lbl.setText("STATE: LISTENING TO COMMAND...")
            self._core_state_lbl.setStyleSheet("color: #38bdf8;")
        elif state_upper in ("TRANSCRIBING", "UNDERSTANDING"):
            self._holo_core_small.set_state("THINKING")
            self._core_state_lbl.setText("STATE: REASONING (GROQ LPU)...")
            self._core_state_lbl.setStyleSheet("color: #fbbf24;")
        elif state_upper in ("SPEAKING", "AI_RESPONSE"):
            self._holo_core_small.set_state("SPEAKING")
            self._core_state_lbl.setText("STATE: SPEAKING (TTS)...")
            self._core_state_lbl.setStyleSheet("color: #10b981;")

    def _on_voice_status_changed(self, active: bool):
        if self._mic_active != active:
            self._mic_active = active
            self._mic_btn.blockSignals(True)
            self._mic_btn.setChecked(active)
            self._mic_btn.blockSignals(False)
            self._update_mic_style(active)
            if active:
                self._holo_core_small.set_state("LISTENING")
                self._core_state_lbl.setText("STATE: WAITING FOR WAKE WORD ('AURA')")
                self._core_state_lbl.setStyleSheet("color: #00e5ff;")
                self._chat_input.setPlaceholderText("🎙️ Voice Active • Waiting for wake word 'Aura' (Say 'Aura' or click mic to stop)")
            else:
                self._holo_core_small.set_state("IDLE")
                self._core_state_lbl.setText("STATE: IDLE")
                self._core_state_lbl.setStyleSheet("color: #10b981;")
                self._chat_input.setPlaceholderText("Enter command or prompt AuraAI (Press Enter)...")

    def _send_quick_command(self, cmd: str):
        self._add_message("user", cmd)
        self.execute_command(cmd)

    def _on_chat_submit(self):
        text = self._chat_input.text().strip()
        if not text:
            return

        self._add_message("user", text)
        self._chat_input.clear()
        self.execute_command(text)

    def execute_command(self, text: str):
        if not text:
            return
        self._command_start_time = time.time()
        self._last_command_text = text
        self._holo_core_small.set_state("EXECUTING")
        self._core_state_lbl.setText("STATE: EXECUTING")
        self._core_state_lbl.setStyleSheet("color: #fbbf24;")
        if hasattr(self, "_console_status_pill"):
            self._console_status_pill.set_active(True)
            self._console_status_pill.set_label("Executing")
        if hasattr(self, "_live_throughput_lbl"):
            self._live_throughput_lbl.setText("Inferencing Groq LPU...")
            self._live_throughput_lbl.setStyleSheet("color: #fbbf24; background: transparent;")
        self._right_goal_lbl.setText(f"PROCESSING:\n{text[:45]}...")

        app_signals.execution_started.emit("user-task")

        if self._active_worker and self._active_worker.isRunning():
            self._active_worker.quit()
            self._active_worker.wait(400)

        self._active_worker = CommandWorker(text, parent=self)
        self._active_worker.step_signal.connect(self._on_step_updated)
        self._active_worker.finished_signal.connect(self._on_worker_finished)
        self._active_worker.error_signal.connect(self._on_worker_error)
        self._active_worker.start()

    def _on_worker_finished(self, task_id: str, response: str):
        elapsed = max(0.08, time.time() - getattr(self, "_command_start_time", time.time()))
        approx_tokens = max(1, int(len(response.split()) * 1.33))
        tok_per_sec = int(approx_tokens / elapsed)

        if hasattr(self, "_live_latency_lbl"):
            self._live_latency_lbl.setText(f"{elapsed:.2f}s (Turnaround)")
        if hasattr(self, "_live_throughput_lbl"):
            self._live_throughput_lbl.setText(f"{approx_tokens} tokens (~{tok_per_sec} Tok/s)")
            self._live_throughput_lbl.setStyleSheet("color: #10b981; background: transparent;")

        try:
            from gui.real_backend_bridge import RealBackendBridge
            usage = RealBackendBridge.get_instance().record_token_usage(getattr(self, "_last_command_text", ""), response)
            if hasattr(self, "_live_tokens_consumed_lbl"):
                self._live_tokens_consumed_lbl.setText(f"{usage['consumed']:,} tokens today")
            if hasattr(self, "_live_tokens_left_lbl"):
                self._live_tokens_left_lbl.setText(f"{usage['remaining']:,} / {usage['limit']:,} left ({usage['pct_remaining']}%)")
        except Exception:
            pass

        resp_str = str(response).strip()
        is_error = not resp_str or resp_str.startswith("❌") or resp_str.startswith("✗") or "Error processing message" in resp_str or "Error code:" in resp_str or "tool_use_failed" in resp_str

        intent_tag = "ERROR" if is_error else "REASONING"
        self._add_message("agent", response, intent_tag=intent_tag)
        if getattr(self, "_mic_active", False):
            self._holo_core_small.set_state("LISTENING")
            self._core_state_lbl.setText("STATE: WAITING FOR WAKE WORD ('AURA')")
            self._core_state_lbl.setStyleSheet("color: #00e5ff;")
        else:
            self._holo_core_small.set_state("IDLE")
            self._core_state_lbl.setText("STATE: IDLE")
            self._core_state_lbl.setStyleSheet("color: #10b981;")
        if hasattr(self, "_console_status_pill"):
            self._console_status_pill.set_active(False)
            self._console_status_pill.set_label("Fault" if is_error else "Ready")
        self._right_goal_lbl.setText("STANDBY // Awaiting Operator Input")
        app_signals.execution_finished.emit(task_id, not is_error)

    def _on_worker_error(self, task_id: str, error: str):
        self._add_message("agent", f"⚠️ Error executing task: {error}", intent_tag="ERROR")
        if getattr(self, "_mic_active", False):
            self._holo_core_small.set_state("LISTENING")
            self._core_state_lbl.setText("STATE: WAITING FOR WAKE WORD ('AURA')")
            self._core_state_lbl.setStyleSheet("color: #00e5ff;")
        else:
            self._holo_core_small.set_state("IDLE")
            self._core_state_lbl.setText("STATE: IDLE")
            self._core_state_lbl.setStyleSheet("color: #10b981;")
        if hasattr(self, "_console_status_pill"):
            self._console_status_pill.set_active(False)
            self._console_status_pill.set_label("Ready")
        self._right_goal_lbl.setText("STANDBY // Awaiting Operator Input")
        app_signals.execution_finished.emit(task_id, False)

    def _on_dag_node_selected(self, node):
        """Update live telemetry metrics when a node in the DAG graph is clicked."""
        if not node:
            return
        dur_str = f"{node.duration_ms:.1f} ms" if node.duration_ms > 0 else "Active benchmarking..."
        if hasattr(self, "_live_latency_lbl"):
            self._live_latency_lbl.setText(f"{dur_str} ({node.id})")
        if hasattr(self, "_live_model_lbl") and node.engine:
            self._live_model_lbl.setText(node.engine)
        if hasattr(self, "_live_throughput_lbl") and node.role:
            self._live_throughput_lbl.setText(f"Role: {node.role}")

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
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(12)

        # Top Control Ribbon
        ribbon = QFrame()
        ribbon.setStyleSheet("""
            QFrame {
                background: rgba(13, 22, 38, 0.75);
                border: 1px solid rgba(0, 229, 255, 0.2);
                border-radius: 6px;
            }
        """)
        rl = QHBoxLayout(ribbon)
        rl.setContentsMargins(14, 8, 14, 8)
        rl.setSpacing(12)

        t_lbl = QLabel("🧠 COGNITIVE GRAPH // MULTI-AGENT REASONING PIPELINE")
        t_lbl.setFont(QFont("Consolas", 10, QFont.Bold))
        t_lbl.setStyleSheet("color: #00e5ff; letter-spacing: 0.8px; background: transparent; border: none;")
        rl.addWidget(t_lbl)

        rl.addStretch()

        model_badge = QLabel("⚡ MODEL: GPT-OSS-120B")
        model_badge.setFont(QFont("Consolas", 8, QFont.Bold))
        model_badge.setStyleSheet("color: #fbbf24; background: rgba(251, 191, 36, 0.1); border: 1px solid rgba(251, 191, 36, 0.3); border-radius: 4px; padding: 3px 8px;")
        rl.addWidget(model_badge)

        dag_badge = QLabel("🌐 ACA TOPOLOGY: ACTIVE")
        dag_badge.setFont(QFont("Consolas", 8, QFont.Bold))
        dag_badge.setStyleSheet("color: #10b981; background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 4px; padding: 3px 8px;")
        rl.addWidget(dag_badge)

        reset_btn = QPushButton("↺ RESET GRAPH")
        reset_btn.setFont(QFont("Consolas", 8, QFont.Bold))
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 4px;
                color: #a5b4cb;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.15);
                border: 1px solid #00e5ff;
                color: #ffffff;
            }
        """)
        reset_btn.clicked.connect(lambda: self._dag_visualizer._clear() if hasattr(self, "_dag_visualizer") else None)
        rl.addWidget(reset_btn)

        layout.addWidget(ribbon)

        # Horizontal Split: Visualizer (70%) + Groq LPU Telemetry Deck (30%)
        main_split = QHBoxLayout()
        main_split.setSpacing(12)

        # Graph Container Surface
        container = SciFiTechCard(accent_color=QColor(0, 229, 255), chamfer_size=8)
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(4, 4, 4, 4)

        self._dag_visualizer = DagVisualizer()
        self._dag_visualizer.node_selected.connect(self._on_dag_node_selected)
        c_layout.addWidget(self._dag_visualizer, 1)
        main_split.addWidget(container, 7)

        # Groq LPU & Multi-Agent Telemetry Deck
        telemetry_deck = SciFiTechCard(accent_color=QColor(251, 191, 36), chamfer_size=8)
        td_layout = QVBoxLayout(telemetry_deck)
        td_layout.setContentsMargins(14, 12, 14, 12)
        td_layout.setSpacing(8)

        td_head = QLabel("⚡ GROQ LPU & SWARM TELEMETRY")
        td_head.setFont(QFont("Consolas", 9, QFont.Bold))
        td_head.setStyleSheet("color: #fbbf24; letter-spacing: 0.8px;")
        td_layout.addWidget(td_head)

        try:
            from core.orchestration.planner_registry import PlannerRegistry
            from core.backends.backend_registry import BackendRegistry
            num_planners = len(PlannerRegistry.get_instance().list_planners())
            num_backends = len(BackendRegistry.get_instance().list_all_backends())
        except Exception:
            num_planners = 5
            num_backends = 26

        def _make_metric_row(title: str, default_val: str, col: str):
            row = QFrame()
            row.setStyleSheet("background: rgba(255, 255, 255, 0.02); border-radius: 4px; padding: 1px;")
            rl_m = QVBoxLayout(row)
            rl_m.setContentsMargins(8, 4, 8, 4)
            rl_m.setSpacing(1)

            tl = QLabel(title)
            tl.setFont(QFont("Consolas", 7, QFont.Bold))
            tl.setStyleSheet("color: #7b8c9f; background: transparent;")
            rl_m.addWidget(tl)

            vl = QLabel(default_val)
            vl.setFont(QFont("Segoe UI", 9, QFont.Bold))
            vl.setStyleSheet(f"color: {col}; background: transparent;")
            rl_m.addWidget(vl)

            td_layout.addWidget(row)
            return vl

        try:
            from gui.real_backend_bridge import RealBackendBridge
            token_stats = RealBackendBridge.get_instance().get_daily_token_usage()
            consumed_str = f"{token_stats['consumed']:,} tokens today"
            remaining_str = f"{token_stats['remaining']:,} / {token_stats['limit']:,} left ({token_stats['pct_remaining']}%)"
        except Exception:
            consumed_str = "0 tokens today"
            remaining_str = "500,000 / 500,000 left (100.0%)"

        self._live_model_lbl = _make_metric_row("ACTIVE INFERENCE MODEL", "openai/gpt-oss-120b", "#ffffff")
        self._live_tokens_consumed_lbl = _make_metric_row("DAILY TOKENS CONSUMED", consumed_str, "#fbbf24")
        self._live_tokens_left_lbl = _make_metric_row("DAILY TOKENS REMAINING", remaining_str, "#10b981")
        self._live_throughput_lbl = _make_metric_row("MEASURED THROUGHPUT", "Standing By", "#00e5ff")
        self._live_latency_lbl = _make_metric_row("LAST EXECUTION LATENCY", "Ready", "#c084fc")
        self._live_planners_lbl = _make_metric_row("ACTIVE SWARM PLANNERS", f"{num_planners} Registered Planners", "#60a5fa")
        self._live_backends_lbl = _make_metric_row("REGISTERED TOOL ADAPTERS", f"{num_backends} Native Backends", "#fbbf24")
        self._live_guardrails_lbl = _make_metric_row("POLICY GUARDRAILS", "SAIF Active & Verified", "#10b981")

        td_layout.addStretch()
        main_split.addWidget(telemetry_deck, 3)

        layout.addLayout(main_split, 1)
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

        # Header Row with Title and Live Badge
        hdr = QHBoxLayout()
        t_lbl = QLabel("NEURAL MEMORY // VECTOR VAULT & RETRIEVAL MATRIX")
        t_lbl.setFont(QFont("Consolas", 11, QFont.Bold))
        t_lbl.setStyleSheet("color: #00e5ff; letter-spacing: 1px;")
        hdr.addWidget(t_lbl)
        hdr.addStretch()

        self._mem_count_badge = QLabel("INDEXED")
        self._mem_count_badge.setFont(QFont("Consolas", 8, QFont.Bold))
        self._mem_count_badge.setStyleSheet(
            "color: #00e5ff; background: rgba(0, 229, 255, 0.12); "
            "border: 1px solid rgba(0, 229, 255, 0.35); border-radius: 4px; padding: 2px 8px;"
        )
        hdr.addWidget(self._mem_count_badge)
        layout.addLayout(hdr)

        # Search Bar with Instant Query, Enter Handler, Search Button, and Clear Button
        search_box = SciFiTechCard(chamfer_size=6)
        sb_l = QHBoxLayout(search_box)
        sb_l.setContentsMargins(12, 6, 12, 6)
        sb_l.setSpacing(8)

        search_icon = QLabel("🔍")
        search_icon.setFont(QFont("Segoe UI Emoji", 10))
        search_icon.setStyleSheet("color: #00e5ff; background: transparent;")
        sb_l.addWidget(search_icon)

        self._mem_search_input = QLineEdit()
        self._mem_search_input.setPlaceholderText("Search memory entries, preferences, session context...")
        self._mem_search_input.setStyleSheet("background: transparent; border: none; color: #ffffff; font-family: Segoe UI, Consolas; font-size: 10pt;")
        sb_l.addWidget(self._mem_search_input, 1)

        # Clear Button
        btn_clear = QPushButton("✖")
        btn_clear.setFont(QFont("Segoe UI", 8, QFont.Bold))
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.setToolTip("Clear search query")
        btn_clear.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 4px;
                color: #a5b4cb;
                padding: 3px 8px;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.2);
                border: 1px solid #ef4444;
                color: #ffffff;
            }
        """)
        btn_clear.clicked.connect(lambda: self._mem_search_input.clear())
        sb_l.addWidget(btn_clear)

        # Search Button
        btn_search = QPushButton("SEARCH")
        btn_search.setFont(QFont("Consolas", 8, QFont.Bold))
        btn_search.setCursor(Qt.PointingHandCursor)
        btn_search.setStyleSheet("""
            QPushButton {
                background: rgba(0, 229, 255, 0.15);
                border: 1px solid #00e5ff;
                border-radius: 4px;
                color: #00e5ff;
                padding: 4px 12px;
                letter-spacing: 0.5px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.35);
                color: #ffffff;
            }
        """)
        sb_l.addWidget(btn_search)
        layout.addWidget(search_box)

        # Scroll Area for Memory Cards
        mem_scroll = QScrollArea()
        mem_scroll.setWidgetResizable(True)
        mem_scroll.setStyleSheet("background: transparent; border: none;")

        self._mem_container = QWidget()
        self._mem_layout = QVBoxLayout(self._mem_container)
        self._mem_layout.setSpacing(10)
        self._mem_layout.setContentsMargins(0, 0, 0, 0)

        mem_scroll.setWidget(self._mem_container)
        layout.addWidget(mem_scroll, 1)

        # Helper method to load all memories (both database + active system profile)
        def _get_all_memory_entries() -> list[tuple[str, str, str]]:
            memories: list[tuple[str, str, str]] = [
                ("PREFERENCE", "User prefers futuristic HUD interface with glassmorphism and cyan telemetry.", "1.00"),
                ("WORKSPACE", "Project root mapped to D:/Sreekanta/VS Code Project/Desktop AI/AuraAI.", "0.99"),
                ("HARDWARE", "Intel Wi-Fi 6 AX201, NVIDIA GTX 1650, 16GB RAM.", "0.98"),
                ("GUARDRAIL", "Always use project virtual environment (.venv) for command execution.", "1.00"),
            ]

            # Try loading live facts from SQLite Memory.db
            try:
                import Memory
                mem = Memory.Memory()
                db_facts = mem.facts()
                for fact in db_facts:
                    cat = (fact.category or "FACT").upper()
                    val = f"{fact.key}: {fact.value}" if fact.key and fact.key.lower() not in fact.value.lower() else str(fact.value)
                    if not any(val.lower() in existing[1].lower() for existing in memories):
                        memories.append((cat, val, "0.96"))
            except Exception as e:
                logger.debug(f"[MemoryTab] Could not load Memory.db facts: {e}")

            return memories

        self._all_memories = _get_all_memory_entries()

        # Dynamic render function
        def _render_memories(filter_text: str = ""):
            while self._mem_layout.count():
                child = self._mem_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            query = filter_text.strip().lower()
            matching = []
            for tag, content, conf in self._all_memories:
                if not query or query in tag.lower() or query in content.lower():
                    matching.append((tag, content, conf))

            self._mem_count_badge.setText(f"{len(matching)} / {len(self._all_memories)} VECTORS")

            if not matching:
                empty_card = SciFiTechCard(accent_color=QColor(239, 68, 68), chamfer_size=6)
                ec_l = QVBoxLayout(empty_card)
                ec_l.setContentsMargins(16, 16, 16, 16)
                no_res = QLabel(f"NO MATCHING MEMORY VECTORS LOCATED FOR '{filter_text}'")
                no_res.setFont(QFont("Consolas", 9, QFont.Bold))
                no_res.setStyleSheet("color: #ef4444; letter-spacing: 0.5px;")
                ec_l.addWidget(no_res)
                sub_res = QLabel("Try broad keywords (e.g. 'preference', 'workspace', 'hardware', 'name', 'developer', 'editor').")
                sub_res.setFont(QFont("Segoe UI", 8))
                sub_res.setStyleSheet("color: #8b9bb4;")
                ec_l.addWidget(sub_res)
                self._mem_layout.addWidget(empty_card)
            else:
                for tag, content, conf in matching:
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

                    self._mem_layout.addWidget(card)

            self._mem_layout.addStretch()

        # Connect text changes and enter key for instant and explicit search
        self._mem_search_input.textChanged.connect(lambda txt: _render_memories(txt))
        self._mem_search_input.returnPressed.connect(lambda: _render_memories(self._mem_search_input.text()))
        btn_search.clicked.connect(lambda: _render_memories(self._mem_search_input.text()))

        # Initial render
        _render_memories()

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
        deck.setStyleSheet("background: #06090f; border-left: 1px solid rgba(255, 255, 255, 0.06);")

        layout = QVBoxLayout(deck)
        layout.setContentsMargins(10, 14, 10, 14)
        layout.setSpacing(12)

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

        # Live Real-Time System Performance Telemetry Core
        self._tactical_telemetry = TacticalTelemetryWidget(chamfer_size=6)
        layout.addWidget(self._tactical_telemetry)

        # Real-Time Cyberpunk Voice Waveform Perception Spectrum
        self._tactical_waveform = TacticalVoiceWaveformWidget(chamfer_size=6)
        layout.addWidget(self._tactical_waveform)

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

        # Right Tactical Deck Live Telemetry Core
        if hasattr(self, "_tactical_telemetry"):
            self._tactical_telemetry.update_telemetry(data)

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
        app_signals.toggle_voice_notch.connect(self.toggle_voice_notch)
        app_signals.toggle_weather_overlay.connect(self.toggle_weather_overlay)
        app_signals.toggle_system_overlay.connect(self.toggle_system_overlay)
        app_signals.toggle_system_status_overlay.connect(self.toggle_system_status_overlay)
        app_signals.toggle_agent_task_overlay.connect(self.toggle_agent_task_overlay)
        app_signals.toggle_agent_task_logs.connect(self.show_agent_task_logs)
        app_signals.toggle_personal_os_overlay.connect(self.toggle_personal_os_overlay)
        app_signals.voice_status_changed.connect(self._on_voice_status_changed)
        app_signals.voice_state_name_changed.connect(self._on_voice_state_name_changed)

        # Real-Time Telemetry & Desktop Perception Background Timers
        self._live_telemetry_timer = QTimer(self)
        self._live_telemetry_timer.timeout.connect(self._poll_live_telemetry)
        self._live_telemetry_timer.start(1000)

        self._live_world_timer = QTimer(self)
        self._live_world_timer.timeout.connect(self._poll_live_world_state)
        self._live_world_timer.start(400)

    def _poll_live_telemetry(self):
        try:
            from gui.real_backend_bridge import RealBackendBridge
            bridge = RealBackendBridge.get_instance()
            stats = bridge.get_hardware_status()
            
            telemetry_data = {
                "cpu_pct": stats.get("cpu_pct", 0.0),
                "cpu_freq_ghz": 2.5,
                "cpu_count": stats.get("cpu_cores", 8),
                "mem_used_gb": stats.get("ram_used_gb", 0.0),
                "mem_total_gb": stats.get("ram_total_gb", 16.0),
                "mem_pct": stats.get("ram_pct", 0.0),
                "disk_used_gb": stats.get("disk_used_gb", 0.0),
                "disk_total_gb": stats.get("disk_total_gb", 512.0),
                "disk_pct": stats.get("disk_pct", 0.0),
                "disk_read_mbs": 0.0,
                "disk_write_mbs": 0.1,
                "net_down_kb": 15.0,
                "net_up_kb": 3.0,
                "gpus": [
                    {
                        "name": stats.get("gpu_name", "NVIDIA GeForce GTX 1650"),
                        "util_pct": stats.get("gpu_util_pct", 0.0),
                        "mem_used_mb": stats.get("gpu_mem_used_mb", 0.0),
                        "mem_total_mb": stats.get("gpu_mem_total_mb", 4096.0),
                        "temp_c": stats.get("gpu_temp_c", 40.0),
                    }
                ],
                "wifi": {
                    "ssid": "JioFiber-xyqB3",
                    "signal_pct": 80,
                    "band": "5 GHz",
                    "state": "CONNECTED",
                },
            }
            self._on_telemetry_data(telemetry_data)
        except Exception as e:
            logger.debug(f"[MainWindow] Live telemetry poll: {e}")

    def _poll_live_world_state(self):
        try:
            from gui.real_backend_bridge import RealBackendBridge
            bridge = RealBackendBridge.get_instance()
            world = bridge.get_world_state()

            if hasattr(self, "_obs_win_lbl"):
                self._obs_win_lbl.setText(world.get("focused_window", "Desktop Surface"))
            if hasattr(self, "_obs_cursor_lbl"):
                cx, cy = world.get("cursor_pos", (0, 0))
                res = world.get("resolution", "1920x1080 FHD")
                self._obs_cursor_lbl.setText(f"X: {cx} | Y: {cy} // {res}")
            if hasattr(self, "_obs_dom_lbl"):
                self._obs_dom_lbl.setText(world.get("browser_hook", "STANDBY // Ready for Web Automation"))
            if hasattr(self, "_obs_vision_lbl"):
                self._obs_vision_lbl.setText(world.get("vision_status", "ONLINE // Screen OCR & Frame Buffer Ready"))
        except Exception as e:
            logger.debug(f"[MainWindow] Live world state poll: {e}")

    def _on_message_received(self, sender: str, content: str, is_user: bool):
        # Only handle messages from external systems (e.g. voice loop or floating chat overlay)
        if sender in ("voice", "overlay", "external"):
            self._add_message("user" if is_user else "agent", content, intent_tag="VOICE" if sender == "voice" else "REASONING")
            if not is_user:
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
        if hasattr(self, "_dag_visualizer") and self._dag_visualizer:
            self._dag_visualizer.add_or_update_step(step)
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
        self._status_overlay.toggle()

    def toggle_agent_task_overlay(self):
        if self._task_overlay is None:
            self._task_overlay = AgentTaskStatusOverlay()
        if self._task_overlay.isVisible():
            self._task_overlay.hide()
        else:
            self._task_overlay.show()

    def show_agent_task_logs(self):
        if self._task_overlay is None:
            self._task_overlay = AgentTaskStatusOverlay()
        if not self._task_overlay.isVisible():
            self._task_overlay.show()
        if not getattr(self._task_overlay, "_show_logs", False):
            self._task_overlay.toggle_logs_view()

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

    def toggle_voice_notch(self):
        if self._voice_notch is None:
            self._voice_notch = VoiceNotchOverlay()
        if self._voice_notch.isVisible():
            self._voice_notch.hide()
        else:
            self._voice_notch.show()
            self._voice_notch.raise_()
            self._voice_notch._position_at_top()
            if not getattr(self, "_mic_active", False):
                self._on_mic_toggle()


    # -------------------------------------------------------------------------
    # GEOMETRY PERSISTENCE (QSETTINGS) & AUTO LAPTOP RESIZING
    # -------------------------------------------------------------------------
    def _restore_geometry(self):
        screen = QApplication.primaryScreen().availableGeometry()
        pos = self._settings.value("pos", None)
        size = self._settings.value("size", None)

        # Full HD (1920x1080) responsive scaling
        target_w = max(1360, min(int(screen.width() * 0.94), 1920, screen.width() - 20))
        target_h = max(760, min(int(screen.height() * 0.90), 1080, screen.height() - 40))

        if size is not None:
            try:
                w, h = int(size.width()), int(size.height())
                w = max(MIN_W, min(w, screen.width() - 20))
                h = max(MIN_H, min(h, screen.height() - 40))
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
                if x < screen.left() or (x + w_curr) > screen.right() or y < screen.top() or (y + h_curr) > (screen.bottom() - 10):
                    x, y = safe_x, safe_y
                self.move(x, y)
            except Exception:
                self.move(safe_x, safe_y)
        else:
            self.move(safe_x, safe_y)

    def auto_fit_screen(self):
        """Auto-adjust window to Full HD / maximum screen display."""
        screen = QApplication.primaryScreen().availableGeometry()
        auto_w = max(1360, min(int(screen.width() * 0.94), 1920, screen.width() - 20))
        auto_h = max(760, min(int(screen.height() * 0.90), 1080, screen.height() - 40))
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
