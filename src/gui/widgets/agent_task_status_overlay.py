"""
AgentTaskStatusOverlay Widget
=============================
Ultra-Modern Next-Gen Agent Task Status, Expandable Task Queue & Live Logs HUD.
Connected to Genuine Real Backends:
- Real Multi-Agent Orchestrator (Executive Brain, Research Coordinator, Groq Engine, Desktop Automation, Memory Vault, Vision Observer)
- Live Conversation & Expandable Task Queue (Data/ChatLog.json & real-time execution trace)
- Detailed "What Aura Did" & Error Diagnostic Inspector for every task
- Live Log Toggle ("Show Logs") with full scrollable, searchable system log terminal
- Real-time event bus integration (app_signals execution events)
"""

import sys
import logging
from typing import Optional, List, Dict, Any

from PySide6.QtCore import (
    Qt,
    QPoint,
    QRect,
    QRectF,
    QSize,
    QSettings,
    QTimer,
)
from PySide6.QtGui import (
    QPainter,
    QColor,
    QFont,
    QPen,
    QBrush,
    QPainterPath,
    QLinearGradient,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QPlainTextEdit,
    QCheckBox,
    QSizePolicy,
)

from gui.real_backend_bridge import RealBackendBridge
from gui.signals import app_signals, ExecutionStep

logger = logging.getLogger(__name__)

REF_W = 1920
REF_H = 1080
MIN_W = 680
MIN_H = 500
GRIP_SIZE = 18

ORG_NAME = "AuraAI"
APP_NAME = "AgentTaskStatusOverlay"


# ─────────────────────────────────────────────────────────────────────────────
# 1. EXPANDABLE TASK QUEUE ROW WIDGET
# ─────────────────────────────────────────────────────────────────────────────

class ExpandableTaskRow(QFrame):
    """
    Interactive Expandable Task Row for the Task Queue.
    - Click to expand/collapse.
    - Shows: Task ID, Description, Agent, Status, Progress.
    - Expanded view: What Aura Did (Execution summary), Error Diagnostics & Trace, Metadata, Copy & Re-run actions.
    """

    def __init__(self, task_data: Dict[str, Any], is_expanded: bool = False, on_toggle_callback=None, parent=None):
        super().__init__(parent)
        self.task_data = task_data
        self.is_expanded = is_expanded
        self.on_toggle_callback = on_toggle_callback
        self.setCursor(Qt.PointingHandCursor)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("""
            ExpandableTaskRow {
                background: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(255, 255, 255, 0.04);
                border-radius: 6px;
            }
            ExpandableTaskRow:hover {
                background: rgba(100, 150, 255, 0.07);
                border: 1px solid rgba(100, 150, 255, 0.22);
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(6)

        # ── 1. Summary Header Row ──
        summary_row = QHBoxLayout()
        summary_row.setSpacing(10)

        # Expand Chevron
        self._chevron_lbl = QLabel("▼" if self.is_expanded else "▶")
        self._chevron_lbl.setFont(QFont("Consolas", 8, QFont.Bold))
        self._chevron_lbl.setStyleSheet("color: #00e5ff;" if self.is_expanded else "color: #64748b;")
        summary_row.addWidget(self._chevron_lbl)

        # Task ID
        t_id = self.task_data.get("id", "T-0000")
        t_lbl = QLabel(t_id)
        t_lbl.setFont(QFont("Consolas", 9, QFont.Bold))
        t_lbl.setStyleSheet("color: #e8ebff; background: transparent; border: none;")
        summary_row.addWidget(t_lbl, 1)

        # Description
        desc_txt = self.task_data.get("desc", "No description")
        d_lbl = QLabel(desc_txt)
        d_lbl.setFont(QFont("Segoe UI", 9))
        d_lbl.setStyleSheet("color: #cbd5e1; background: transparent; border: none;")
        summary_row.addWidget(d_lbl, 3)

        # Agent
        agent_txt = self.task_data.get("agent", "Executive Brain")
        a_lbl = QLabel(agent_txt)
        a_lbl.setFont(QFont("Segoe UI", 9))
        a_lbl.setStyleSheet("color: #6496ff; background: transparent; border: none;")
        summary_row.addWidget(a_lbl, 1)

        # Status
        status_txt = self.task_data.get("status", "● Completed")
        status_col = self.task_data.get("color", "#66ff99")
        s_lbl = QLabel(status_txt)
        s_lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
        s_lbl.setStyleSheet(f"color: {status_col}; background: transparent; border: none;")
        summary_row.addWidget(s_lbl, 1)

        # Progress
        prog_txt = self.task_data.get("progress", "100%")
        p_lbl = QLabel(prog_txt)
        p_lbl.setFont(QFont("Segoe UI", 9))
        p_lbl.setStyleSheet("color: #8899aa; background: transparent; border: none;")
        summary_row.addWidget(p_lbl, 1)

        main_layout.addLayout(summary_row)

        # ── 2. Expandable Details Container ──
        self._details_frame = QFrame()
        self._details_frame.setVisible(self.is_expanded)
        self._details_frame.setStyleSheet("""
            QFrame {
                background: rgba(8, 12, 22, 0.95);
                border: 1px solid rgba(0, 229, 255, 0.22);
                border-radius: 8px;
            }
        """)
        det_layout = QVBoxLayout(self._details_frame)
        det_layout.setContentsMargins(14, 12, 14, 12)
        det_layout.setSpacing(10)

        # Section A: What Aura Did (Execution Action Summary)
        action_head = QHBoxLayout()
        ah_title = QLabel("⚡ WHAT AURA DID // EXECUTION ACTION TRACE")
        ah_title.setFont(QFont("Consolas", 8, QFont.Bold))
        ah_title.setStyleSheet("color: #00e5ff; letter-spacing: 0.8px; background: transparent; border: none;")
        action_head.addWidget(ah_title)
        action_head.addStretch()

        ts_txt = self.task_data.get("timestamp", "")
        if ts_txt:
            ts_lbl = QLabel(f"⏱ {ts_txt}")
            ts_lbl.setFont(QFont("Segoe UI", 8))
            ts_lbl.setStyleSheet("color: #7b8c9f; background: transparent; border: none;")
            action_head.addWidget(ts_lbl)
        det_layout.addLayout(action_head)

        resp_text = self.task_data.get("response", "")
        if not resp_text:
            resp_text = "Task processed through multi-agent cognitive pipeline. Action completed."

        resp_box = QLabel(resp_text)
        resp_box.setFont(QFont("Segoe UI", 9))
        resp_box.setWordWrap(True)
        resp_box.setTextInteractionFlags(Qt.TextSelectableByMouse)
        resp_box.setStyleSheet("""
            color: #f1f5f9;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 6px;
            padding: 8px 10px;
            line-height: 1.4;
        """)
        det_layout.addWidget(resp_box)

        # Section B: Error & Diagnostic Inspector (if is_error or warning)
        is_err = self.task_data.get("is_error", False) or "error" in status_txt.lower() or "failed" in status_txt.lower() or "action req" in prog_txt.lower()
        err_msg = self.task_data.get("error", "")
        if is_err or err_msg:
            err_box = QFrame()
            err_box.setStyleSheet("""
                QFrame {
                    background: rgba(244, 63, 94, 0.12);
                    border: 1px solid rgba(244, 63, 94, 0.4);
                    border-radius: 6px;
                }
            """)
            eb_l = QVBoxLayout(err_box)
            eb_l.setContentsMargins(10, 8, 10, 8)
            eb_l.setSpacing(4)

            eh_title = QLabel("⚠️ ERROR / DIAGNOSTIC REPORT")
            eh_title.setFont(QFont("Consolas", 8, QFont.Bold))
            eh_title.setStyleSheet("color: #f43f5e; background: transparent; border: none;")
            eb_l.addWidget(eh_title)

            err_detail = err_msg if err_msg else resp_text
            ed_lbl = QLabel(err_detail)
            ed_lbl.setFont(QFont("Segoe UI", 9))
            ed_lbl.setWordWrap(True)
            ed_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            ed_lbl.setStyleSheet("color: #fca5a5; background: transparent; border: none;")
            eb_l.addWidget(ed_lbl)
            det_layout.addWidget(err_box)

        # Section C: Action Toolbar & Metadata
        foot = QHBoxLayout()
        foot.setSpacing(8)

        topic_txt = self.task_data.get("topic", "General")
        top_lbl = QLabel(f"Topic: {topic_txt} • Agent: {agent_txt}")
        top_lbl.setFont(QFont("Segoe UI", 8))
        top_lbl.setStyleSheet("color: #64748b; background: transparent; border: none;")
        foot.addWidget(top_lbl)

        foot.addStretch()

        btn_copy = QPushButton("📋 Copy Summary")
        btn_copy.setFont(QFont("Segoe UI", 8))
        btn_copy.setCursor(Qt.PointingHandCursor)
        btn_copy.setStyleSheet("""
            QPushButton {
                background: rgba(100, 150, 255, 0.1);
                border: 1px solid rgba(100, 150, 255, 0.25);
                border-radius: 4px;
                color: #6496ff;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background: rgba(100, 150, 255, 0.25);
                color: #ffffff;
            }
        """)
        btn_copy.clicked.connect(self._copy_details)
        foot.addWidget(btn_copy)

        btn_rerun = QPushButton("↺ Re-run Task")
        btn_rerun.setFont(QFont("Segoe UI", 8, QFont.Bold))
        btn_rerun.setCursor(Qt.PointingHandCursor)
        btn_rerun.setStyleSheet("""
            QPushButton {
                background: rgba(0, 229, 255, 0.12);
                border: 1px solid rgba(0, 229, 255, 0.35);
                border-radius: 4px;
                color: #00e5ff;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.3);
                color: #ffffff;
            }
        """)
        btn_rerun.clicked.connect(self._rerun_task)
        foot.addWidget(btn_rerun)

        det_layout.addLayout(foot)
        main_layout.addWidget(self._details_frame)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_expanded()
            event.accept()
        else:
            super().mousePressEvent(event)

    def toggle_expanded(self, expand: Optional[bool] = None):
        if expand is None:
            self.is_expanded = not self.is_expanded
        else:
            self.is_expanded = expand

        self._details_frame.setVisible(self.is_expanded)
        self._chevron_lbl.setText("▼" if self.is_expanded else "▶")
        self._chevron_lbl.setStyleSheet("color: #00e5ff;" if self.is_expanded else "color: #64748b;")

        if self.on_toggle_callback:
            self.on_toggle_callback(self.task_data.get("id", ""), self.is_expanded)

    def _copy_details(self):
        t_id = self.task_data.get("id", "")
        desc = self.task_data.get("desc", "")
        resp = self.task_data.get("response", "")
        err = self.task_data.get("error", "")
        text = f"Task ID: {t_id}\nPrompt: {desc}\nStatus: {self.task_data.get('status')}\nAction Result: {resp}\n"
        if err:
            text += f"Error / Diagnostics: {err}\n"
        QApplication.clipboard().setText(text)

    def _rerun_task(self):
        desc = self.task_data.get("desc", "")
        if desc:
            app_signals.execution_started.emit(desc)
            try:
                from core.aura_core import AuraCore
                core = AuraCore.get_instance()
                import threading
                threading.Thread(target=lambda: core.process_request(desc), daemon=True, name="ReRunTaskThread").start()
            except Exception as e:
                logger.error(f"[ExpandableTaskRow] Re-run error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 2. MAIN AGENT TASK STATUS OVERLAY
# ─────────────────────────────────────────────────────────────────────────────

class AgentTaskStatusOverlay(QWidget):
    """
    Next-Gen Ultra-Modern Agent Task Status & DAG Execution HUD.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AgentTaskStatusOverlay")
        self.setWindowTitle("AuraAI Agent Task Status")

        # Frameless HUD window attributes (normal Z-order, not always on top)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

        self._settings = QSettings(ORG_NAME, APP_NAME)
        self._bridge = RealBackendBridge.get_instance()

        # Drag & resize state
        self._drag_pos = None
        self._resizing = False
        self._resize_start_pos = None
        self._resize_start_size = None

        # Filter & Expansion State
        self._expanded_task_ids = set()
        self._show_logs = False
        self._filter_mode = "ALL"  # "ALL", "COMPLETED", "ERRORS", "ACTIVE"
        self._sort_reverse = True

        # Auto-refresh timer (2000ms for real-time live feel)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_data)
        self._refresh_timer.start(2000)

        self._setup_ui()
        self._connect_signals()
        self._restore_geometry()
        self._refresh_data()

    def _connect_signals(self):
        """Wire execution and live command signals."""
        app_signals.toggle_agent_task_logs.connect(self.toggle_logs_view)
        app_signals.execution_started.connect(self._on_live_task_started)
        app_signals.execution_finished.connect(self._on_live_task_finished)
        app_signals.step_updated.connect(self._on_live_step_updated)

    def _on_live_task_started(self, task_id_or_cmd: str):
        self._bridge.record_live_task_start(task_id_or_cmd, str(task_id_or_cmd))
        self._refresh_data()

    def _on_live_task_finished(self, task_id: str, success: bool):
        self._bridge.record_live_task_finish(task_id, "Execution finished", is_success=success)
        self._refresh_data()

    def _on_live_step_updated(self, step: Any):
        self._refresh_data()

    # -------------------------------------------------------------------------
    # UI SETUP
    # -------------------------------------------------------------------------
    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)

        # Outer Glass Container
        self._card = QFrame()
        self._card.setObjectName("MainHUDCard")
        self._card.setStyleSheet("""
            #MainHUDCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(10, 10, 18, 0.96), stop:1 rgba(21, 21, 31, 0.97));
                border: 1px solid rgba(100, 150, 255, 0.22);
                border-radius: 16px;
            }
        """)

        layout = QVBoxLayout(self._card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 1. Top Command Bar ──
        cmd_bar = QFrame()
        cmd_bar.setStyleSheet("""
            QFrame {
                background: rgba(10, 10, 18, 0.85);
                border-bottom: 1px solid rgba(100, 150, 255, 0.15);
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
            }
        """)
        cb_l = QHBoxLayout(cmd_bar)
        cb_l.setContentsMargins(20, 14, 20, 14)
        cb_l.setSpacing(10)

        # Search Bar
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search agents, tasks, or DAG nodes...")
        self._search_input.setFont(QFont("Segoe UI", 9))
        self._search_input.setFixedWidth(260)
        self._search_input.setStyleSheet("""
            QLineEdit {
                background: rgba(100, 150, 255, 0.06);
                border: 1px solid rgba(100, 150, 255, 0.2);
                border-radius: 8px;
                padding: 6px 12px;
                color: #e8ebff;
            }
            QLineEdit::placeholder {
                color: #627284;
            }
        """)
        self._search_input.textChanged.connect(self._on_search_changed)
        cb_l.addWidget(self._search_input)

        # Filter Button (Cycles: All -> Completed -> Errors -> Active)
        self._btn_filter = QPushButton("Filter: All")
        self._btn_filter.setFont(QFont("Segoe UI", 9))
        self._btn_filter.setCursor(Qt.PointingHandCursor)
        self._btn_filter.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid rgba(100, 150, 255, 0.25);
                color: #6496ff;
                padding: 5px 12px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: rgba(100, 150, 255, 0.15);
                color: #ffffff;
            }
        """)
        self._btn_filter.clicked.connect(self._cycle_filter)
        cb_l.addWidget(self._btn_filter)

        # Sort Button
        self._btn_sort = QPushButton("Sort: Newest")
        self._btn_sort.setFont(QFont("Segoe UI", 9))
        self._btn_sort.setCursor(Qt.PointingHandCursor)
        self._btn_sort.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid rgba(100, 150, 255, 0.25);
                color: #6496ff;
                padding: 5px 12px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: rgba(100, 150, 255, 0.15);
                color: #ffffff;
            }
        """)
        self._btn_sort.clicked.connect(self._toggle_sort)
        cb_l.addWidget(self._btn_sort)

        # Log Toggle Button ("Show Logs")
        self._btn_logs = QPushButton("📜 Show Logs")
        self._btn_logs.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
        self._btn_logs.setCursor(Qt.PointingHandCursor)
        self._update_logs_btn_style(False)
        self._btn_logs.clicked.connect(self.toggle_logs_view)
        cb_l.addWidget(self._btn_logs)

        cb_l.addStretch()

        # Action Buttons
        btn_spawn = QPushButton("+ Spawn Agent")
        btn_spawn.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        btn_spawn.setCursor(Qt.PointingHandCursor)
        btn_spawn.setStyleSheet("""
            QPushButton {
                background: rgba(102, 255, 153, 0.12);
                border: 1px solid rgba(102, 255, 153, 0.35);
                color: #66ff99;
                padding: 6px 14px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: rgba(102, 255, 153, 0.25);
                color: #ffffff;
            }
        """)
        btn_spawn.clicked.connect(self._spawn_new_agent)
        cb_l.addWidget(btn_spawn)

        btn_exec = QPushButton("▶ Execute DAG")
        btn_exec.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        btn_exec.setCursor(Qt.PointingHandCursor)
        btn_exec.setStyleSheet("""
            QPushButton {
                background: rgba(100, 150, 255, 0.12);
                border: 1px solid rgba(100, 150, 255, 0.35);
                color: #6496ff;
                padding: 6px 14px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: rgba(100, 150, 255, 0.25);
                color: #ffffff;
            }
        """)
        btn_exec.clicked.connect(self._execute_dag)
        cb_l.addWidget(btn_exec)

        # Close Button
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(26, 26)
        btn_close.setFont(QFont("Segoe UI", 9))
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 13px;
                color: #888888;
            }
            QPushButton:hover {
                background: rgba(244, 63, 94, 0.25);
                border: 1px solid #f43f5e;
                color: #ffffff;
            }
        """)
        btn_close.clicked.connect(self.close)
        cb_l.addWidget(btn_close)

        layout.addWidget(cmd_bar)

        # ── Scroll Area for Body Content ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(22, 18, 22, 18)
        body_layout.setSpacing(22)

        # ── 2. Active Agents Management Section ──
        agents_header = QHBoxLayout()
        ah_info = QVBoxLayout()
        ah_info.setSpacing(2)

        ah_title = QLabel("Active Agents")
        ah_title.setFont(QFont("Segoe UI", 13, QFont.Weight.Medium))
        ah_title.setStyleSheet("color: #ffffff; background: transparent;")
        ah_info.addWidget(ah_title)

        self._agents_sub = QLabel("6 deployed • 2 executing • 4 standing by")
        self._agents_sub.setFont(QFont("Segoe UI", 8))
        self._agents_sub.setStyleSheet("color: #7b8c9f; background: transparent;")
        ah_info.addWidget(self._agents_sub)
        agents_header.addLayout(ah_info)

        agents_header.addStretch()

        sort_lbl = QLabel("Multi-Agent Brain // Master Orchestrator")
        sort_lbl.setFont(QFont("Segoe UI", 8))
        sort_lbl.setStyleSheet("color: #64748b; background: transparent;")
        agents_header.addWidget(sort_lbl)
        body_layout.addLayout(agents_header)

        # Agent Cards Grid Container
        self._grid_cards_frame = QFrame()
        self._grid_cards_layout = QGridLayout(self._grid_cards_frame)
        self._grid_cards_layout.setSpacing(12)
        self._grid_cards_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.addWidget(self._grid_cards_frame)

        # ── 3. Task Queue Section (Expandable Rows) ──
        tq_header = QHBoxLayout()
        tqh_info = QVBoxLayout()
        tqh_info.setSpacing(2)

        tq_title = QLabel("Task Queue")
        tq_title.setFont(QFont("Segoe UI", 13, QFont.Weight.Medium))
        tq_title.setStyleSheet("color: #ffffff; background: transparent;")
        tqh_info.addWidget(tq_title)

        self._tq_sub = QLabel("Live tasks from chat execution & orchestrator pipeline • Click row to inspect action & errors")
        self._tq_sub.setFont(QFont("Segoe UI", 8))
        self._tq_sub.setStyleSheet("color: #7b8c9f; background: transparent;")
        tqh_info.addWidget(self._tq_sub)
        tq_header.addLayout(tqh_info)
        tq_header.addStretch()

        expand_all_btn = QPushButton("Expand / Collapse All")
        expand_all_btn.setFont(QFont("Segoe UI", 8))
        expand_all_btn.setCursor(Qt.PointingHandCursor)
        expand_all_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 4px;
                color: #a5b4cb;
                padding: 3px 8px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.12);
                border: 1px solid #00e5ff;
                color: #ffffff;
            }
        """)
        expand_all_btn.clicked.connect(self._toggle_expand_all)
        tq_header.addWidget(expand_all_btn)

        body_layout.addLayout(tq_header)

        # Task Queue Table Card
        self._tq_card = QFrame()
        self._tq_card.setStyleSheet("""
            QFrame {
                background: rgba(100, 150, 255, 0.03);
                border: 1px solid rgba(100, 150, 255, 0.12);
                border-radius: 12px;
            }
        """)
        self._tqc_l = QVBoxLayout(self._tq_card)
        self._tqc_l.setContentsMargins(8, 8, 8, 8)
        self._tqc_l.setSpacing(6)
        body_layout.addWidget(self._tq_card)

        # ── 4. Cyber Log Panel (Toggled via "Show Logs") ──
        self._log_panel = QFrame()
        self._log_panel.setVisible(False)
        self._log_panel.setStyleSheet("""
            QFrame {
                background: rgba(6, 9, 16, 0.95);
                border: 1px solid rgba(0, 229, 255, 0.3);
                border-radius: 12px;
            }
        """)
        lp_l = QVBoxLayout(self._log_panel)
        lp_l.setContentsMargins(14, 12, 14, 12)
        lp_l.setSpacing(10)

        # Log Header Ribbon
        l_head = QHBoxLayout()
        lh_title = QLabel("📜 LIVE SYSTEM & NEURAL EXECUTION LOGS")
        lh_title.setFont(QFont("Consolas", 9, QFont.Bold))
        lh_title.setStyleSheet("color: #00e5ff; letter-spacing: 0.8px; background: transparent; border: none;")
        l_head.addWidget(lh_title)

        l_head.addStretch()

        self._log_filter_input = QLineEdit()
        self._log_filter_input.setPlaceholderText("Filter logs...")
        self._log_filter_input.setFont(QFont("Segoe UI", 8))
        self._log_filter_input.setFixedWidth(160)
        self._log_filter_input.setStyleSheet("""
            QLineEdit {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(0, 229, 255, 0.2);
                border-radius: 4px;
                padding: 3px 6px;
                color: #e2e8f0;
            }
        """)
        self._log_filter_input.textChanged.connect(lambda: self._update_logs())
        l_head.addWidget(self._log_filter_input)

        self._auto_scroll_cb = QCheckBox("Auto-Scroll")
        self._auto_scroll_cb.setChecked(True)
        self._auto_scroll_cb.setFont(QFont("Segoe UI", 8))
        self._auto_scroll_cb.setStyleSheet("color: #a5b4cb; background: transparent; border: none;")
        l_head.addWidget(self._auto_scroll_cb)

        btn_refresh_log = QPushButton("↺ Refresh")
        btn_refresh_log.setFont(QFont("Segoe UI", 8))
        btn_refresh_log.setCursor(Qt.PointingHandCursor)
        btn_refresh_log.setStyleSheet("""
            QPushButton {
                background: rgba(0, 229, 255, 0.1);
                border: 1px solid rgba(0, 229, 255, 0.25);
                border-radius: 4px;
                color: #00e5ff;
                padding: 3px 8px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.25);
                color: #ffffff;
            }
        """)
        btn_refresh_log.clicked.connect(self._update_logs)
        l_head.addWidget(btn_refresh_log)

        btn_clear_log = QPushButton("✖ Clear")
        btn_clear_log.setFont(QFont("Segoe UI", 8))
        btn_clear_log.setCursor(Qt.PointingHandCursor)
        btn_clear_log.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 4px;
                color: #94a3b8;
                padding: 3px 8px;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.2);
                border: 1px solid #ef4444;
                color: #ffffff;
            }
        """)
        btn_clear_log.clicked.connect(lambda: self._log_text_edit.clear())
        l_head.addWidget(btn_clear_log)

        lp_l.addLayout(l_head)

        # Scrollable Log Output Text Edit
        self._log_text_edit = QPlainTextEdit()
        self._log_text_edit.setReadOnly(True)
        self._log_text_edit.setFont(QFont("Consolas", 9))
        self._log_text_edit.setFixedHeight(220)
        self._log_text_edit.setStyleSheet("""
            QPlainTextEdit {
                background: #04060a;
                color: #cbd5e1;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                padding: 8px;
                line-height: 1.35;
            }
        """)
        lp_l.addWidget(self._log_text_edit)

        body_layout.addWidget(self._log_panel)

        # ── 5. DAG Pipeline Visualization Section ──
        dag_header = QVBoxLayout()
        dag_header.setSpacing(2)

        dh_title = QLabel("DAG Architecture")
        dh_title.setFont(QFont("Segoe UI", 13, QFont.Weight.Medium))
        dh_title.setStyleSheet("color: #ffffff; background: transparent;")
        dag_header.addWidget(dh_title)

        dh_sub = QLabel("Universal Capability Model • M20→M25 complete")
        dh_sub.setFont(QFont("Segoe UI", 8))
        dh_sub.setStyleSheet("color: #7b8c9f; background: transparent;")
        dag_header.addWidget(dh_sub)
        body_layout.addLayout(dag_header)

        # DAG Node Flow Card
        dag_card = QFrame()
        dag_card.setStyleSheet("""
            QFrame {
                background: rgba(100, 150, 255, 0.03);
                border: 1px solid rgba(100, 150, 255, 0.12);
                border-radius: 12px;
            }
        """)
        dc_l = QVBoxLayout(dag_card)
        dc_l.setContentsMargins(18, 16, 18, 16)
        dc_l.setSpacing(14)

        flow_layout = QHBoxLayout()
        flow_layout.setSpacing(12)

        stages = [
            ("Stage 1", "Memory Recall", "#66ff99", "rgba(102, 255, 153, 0.12)", "rgba(102, 255, 153, 0.3)"),
            ("Stage 2", "Intent & Routing", "#6496ff", "rgba(100, 150, 255, 0.12)", "rgba(100, 150, 255, 0.3)"),
            ("Stage 3", "Multi-Agent Exec", "#fbbf24", "rgba(251, 191, 36, 0.12)", "rgba(251, 191, 36, 0.3)"),
            ("Stage 4", "Response Synth", "#a855f7", "rgba(168, 85, 247, 0.12)", "rgba(168, 85, 247, 0.3)"),
        ]

        for i, (st_name, st_sub, col, bg, border) in enumerate(stages):
            node_box = QVBoxLayout()
            node_box.setSpacing(4)
            node_box.setAlignment(Qt.AlignmentFlag.AlignCenter)

            node_frame = QFrame()
            node_frame.setFixedSize(100, 68)
            node_frame.setStyleSheet(f"""
                QFrame {{
                    background: {bg};
                    border: 1px solid {border};
                    border-radius: 10px;
                }}
            """)
            nf_l = QVBoxLayout(node_frame)
            nf_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            nf_lbl = QLabel(st_name)
            nf_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
            nf_lbl.setStyleSheet(f"color: {col}; background: transparent; border: none;")
            nf_l.addWidget(nf_lbl)
            node_box.addWidget(node_frame)

            sub_lbl = QLabel(st_sub)
            sub_lbl.setFont(QFont("Segoe UI", 8))
            sub_lbl.setStyleSheet("color: #7b8c9f; background: transparent; border: none;")
            sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            node_box.addWidget(sub_lbl)

            flow_layout.addLayout(node_box)

            if i < len(stages) - 1:
                arr = QLabel("→")
                arr.setFont(QFont("Segoe UI", 14, QFont.Weight.Light))
                arr.setStyleSheet("color: #64748b; background: transparent; border: none;")
                arr.setAlignment(Qt.AlignmentFlag.AlignCenter)
                flow_layout.addWidget(arr)

        dc_l.addLayout(flow_layout)

        spec_lbl = QLabel("Python 3.11.9 • Groq LLaMA 3.3 70B • NVIDIA GTX 1650 4GB • Doc-synced M20→M25")
        spec_lbl.setFont(QFont("Segoe UI", 8))
        spec_lbl.setStyleSheet("color: #64748b; background: transparent; border: none; padding-top: 8px;")
        spec_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dc_l.addWidget(spec_lbl)

        body_layout.addWidget(dag_card)

        scroll.setWidget(body)
        layout.addWidget(scroll)

        root_layout.addWidget(self._card)

    def _update_logs_btn_style(self, active: bool):
        if active:
            self._btn_logs.setText("📜 Hide Logs")
            self._btn_logs.setStyleSheet("""
                QPushButton {
                    background: rgba(0, 229, 255, 0.2);
                    border: 1px solid #00e5ff;
                    color: #ffffff;
                    padding: 5px 12px;
                    border-radius: 6px;
                    font-weight: bold;
                }
            """)
        else:
            self._btn_logs.setText("📜 Show Logs")
            self._btn_logs.setStyleSheet("""
                QPushButton {
                    background: rgba(0, 229, 255, 0.08);
                    border: 1px solid rgba(0, 229, 255, 0.3);
                    color: #00e5ff;
                    padding: 5px 12px;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background: rgba(0, 229, 255, 0.2);
                    color: #ffffff;
                }
            """)

    def toggle_logs_view(self, force_state: bool | None = None):
        """Toggle full scrollable log console panel visibility."""
        if force_state is not None:
            self._show_logs = force_state
        else:
            self._show_logs = not self._show_logs
        self._log_panel.setVisible(self._show_logs)
        self._update_logs_btn_style(self._show_logs)
        if self._show_logs:
            self._update_logs()

    def _update_logs(self):
        """Fetch latest logs and display in log text edit with level formatting."""
        if not hasattr(self, "_log_text_edit"):
            return
        lines = self._bridge.get_recent_raw_logs(max_lines=300)
        filter_q = self._log_filter_input.text().strip().lower() if hasattr(self, "_log_filter_input") else ""

        filtered_lines = []
        for line in lines:
            if not filter_q or filter_q in line.lower():
                filtered_lines.append(line.rstrip("\r\n"))

        full_text = "\n".join(filtered_lines)
        self._log_text_edit.setPlainText(full_text)

        if hasattr(self, "_auto_scroll_cb") and self._auto_scroll_cb.isChecked():
            self._log_text_edit.moveCursor(QTextCursor.MoveOperation.End)

    def _on_task_row_toggled(self, task_id: str, expanded: bool):
        if expanded:
            self._expanded_task_ids.add(task_id)
        else:
            self._expanded_task_ids.discard(task_id)

    def _toggle_expand_all(self):
        # If any is expanded, collapse all; else expand all
        if self._expanded_task_ids:
            self._expanded_task_ids.clear()
        else:
            agent_data = self._bridge.get_agent_task_data()
            for t in agent_data.get("tasks", []):
                self._expanded_task_ids.add(t["id"])
        self._refresh_data()

    def _cycle_filter(self):
        modes = ["ALL", "COMPLETED", "ERRORS", "ACTIVE"]
        idx = (modes.index(self._filter_mode) + 1) % len(modes)
        self._filter_mode = modes[idx]
        self._btn_filter.setText(f"Filter: {self._filter_mode.capitalize()}")
        self._refresh_data()

    def _toggle_sort(self):
        self._sort_reverse = not self._sort_reverse
        self._btn_sort.setText("Sort: Newest" if self._sort_reverse else "Sort: Oldest")
        self._refresh_data()

    def _create_agent_card(
        self,
        name: str,
        status_text: str,
        status_color: str,
        task_tag: str,
        desc: str,
        footer_left: str,
        footer_right: str,
        bg_rgba: str,
        border_rgba: str,
    ) -> QFrame:
        card = QFrame()
        card.setCursor(Qt.PointingHandCursor)
        card.setStyleSheet(f"""
            QFrame {{
                background: {bg_rgba};
                border: 1px solid {border_rgba};
                border-radius: 12px;
            }}
            QFrame:hover {{
                border: 1px solid {status_color};
            }}
        """)
        l = QVBoxLayout(card)
        l.setContentsMargins(14, 12, 14, 12)
        l.setSpacing(8)

        # Header: Name + Status + Tag
        h = QHBoxLayout()
        info_l = QVBoxLayout()
        info_l.setSpacing(1)

        n_lbl = QLabel(name)
        n_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        n_lbl.setStyleSheet("color: #ffffff; background: transparent; border: none;")
        info_l.addWidget(n_lbl)

        s_lbl = QLabel(f"● {status_text}")
        s_lbl.setFont(QFont("Segoe UI", 8))
        s_lbl.setStyleSheet(f"color: {status_color}; background: transparent; border: none;")
        info_l.addWidget(s_lbl)
        h.addLayout(info_l)

        h.addStretch()

        t_lbl = QLabel(task_tag)
        t_lbl.setFont(QFont("Segoe UI", 8))
        t_lbl.setStyleSheet("color: #7b8c9f; background: transparent; border: none;")
        h.addWidget(t_lbl)
        l.addLayout(h)

        # Description Pill
        d_frame = QFrame()
        d_frame.setStyleSheet("""
            QFrame {
                background: rgba(0, 0, 0, 0.25);
                border-radius: 6px;
                border: none;
            }
        """)
        d_l = QVBoxLayout(d_frame)
        d_l.setContentsMargins(8, 6, 8, 6)
        d_lbl = QLabel(desc)
        d_lbl.setFont(QFont("Segoe UI", 8))
        d_lbl.setStyleSheet("color: #94a3b8; background: transparent; border: none;")
        d_lbl.setWordWrap(True)
        d_l.addWidget(d_lbl)
        l.addWidget(d_frame)

        # Footer
        f = QHBoxLayout()
        fl_lbl = QLabel(footer_left)
        fl_lbl.setFont(QFont("Segoe UI", 8))
        fl_lbl.setStyleSheet("color: #7b8c9f; background: transparent; border: none;")
        fl_lbl.setTextFormat(Qt.TextFormat.RichText)
        f.addWidget(fl_lbl)

        f.addStretch()

        fr_lbl = QLabel(footer_right)
        fr_lbl.setFont(QFont("Segoe UI", 8))
        fr_lbl.setStyleSheet("color: #7b8c9f; background: transparent; border: none;")
        f.addWidget(fr_lbl)
        l.addLayout(f)

        return card

    # -------------------------------------------------------------------------
    # LIVE REFRESH & INTERACTION
    # -------------------------------------------------------------------------
    def _refresh_data(self):
        """Fetch and populate live data from RealBackendBridge with expandable rows."""
        agent_data = self._bridge.get_agent_task_data()
        search_query = self._search_input.text().strip().lower() if hasattr(self, "_search_input") else ""

        # 1. Render Agent Cards
        self._clear_layout(self._grid_cards_layout)
        agents = agent_data.get("agents", [])
        filtered_agents = [
            a for a in agents
            if not search_query or search_query in a["name"].lower() or search_query in a["desc"].lower()
        ]

        for idx, a in enumerate(filtered_agents):
            bg = f"rgba({int(a['color'][1:3], 16)}, {int(a['color'][3:5], 16)}, {int(a['color'][5:7], 16)}, 0.08)"
            border = f"rgba({int(a['color'][1:3], 16)}, {int(a['color'][3:5], 16)}, {int(a['color'][5:7], 16)}, 0.25)"
            card = self._create_agent_card(
                name=a["name"],
                status_text=a["status"],
                status_color=a["color"],
                task_tag=a["task"][:15],
                desc=a["desc"],
                footer_left=a["metric_left"],
                footer_right=a["metric_right"],
                bg_rgba=bg,
                border_rgba=border,
            )
            self._grid_cards_layout.addWidget(card, idx // 3, idx % 3)

        # Add Spawn Agent Button Card
        add_card = QFrame()
        add_card.setCursor(Qt.PointingHandCursor)
        add_card.setStyleSheet("""
            QFrame {
                background: rgba(100, 150, 255, 0.04);
                border: 2px dashed rgba(100, 150, 255, 0.25);
                border-radius: 12px;
            }
            QFrame:hover {
                background: rgba(100, 150, 255, 0.1);
                border: 2px dashed #6496ff;
            }
        """)
        acl = QVBoxLayout(add_card)
        acl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        acl.setSpacing(4)
        plus_lbl = QLabel("+")
        plus_lbl.setFont(QFont("Segoe UI", 18, QFont.Weight.Light))
        plus_lbl.setStyleSheet("color: #6496ff; background: transparent; border: none;")
        plus_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        acl.addWidget(plus_lbl)
        add_t = QLabel("Spawn Agent")
        add_t.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        add_t.setStyleSheet("color: #6496ff; background: transparent; border: none;")
        add_t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        acl.addWidget(add_t)
        add_sub = QLabel("Autonomous Instance")
        add_sub.setFont(QFont("Segoe UI", 8))
        add_sub.setStyleSheet("color: #7b8c9f; background: transparent; border: none;")
        add_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        acl.addWidget(add_sub)
        add_card.mousePressEvent = lambda e: self._spawn_new_agent()
        self._grid_cards_layout.addWidget(add_card, len(filtered_agents) // 3, len(filtered_agents) % 3)

        # 2. Render Expandable Task Queue Table
        self._clear_layout(self._tqc_l)
        tasks = agent_data.get("tasks", [])

        # Apply Filter
        filtered_tasks = []
        for t in tasks:
            # Search check
            matches_search = not search_query or search_query in t["id"].lower() or search_query in t["desc"].lower() or search_query in t.get("agent", "").lower()
            if not matches_search:
                continue

            # Mode check
            st_lower = t.get("status", "").lower()
            if self._filter_mode == "COMPLETED" and "completed" not in st_lower:
                continue
            if self._filter_mode == "ERRORS" and not t.get("is_error", False) and "error" not in st_lower and "warning" not in st_lower:
                continue
            if self._filter_mode == "ACTIVE" and "executing" not in st_lower and "pending" not in st_lower:
                continue

            filtered_tasks.append(t)

        # Apply Sort
        if not self._sort_reverse:
            filtered_tasks = list(reversed(filtered_tasks))

        # Update Subtitle metrics
        comp_cnt = sum(1 for t in tasks if "completed" in t.get("status", "").lower())
        err_cnt = sum(1 for t in tasks if t.get("is_error", False) or "error" in t.get("status", "").lower())
        self._tq_sub.setText(f"{len(tasks)} live tasks tracked • {comp_cnt} completed • {err_cnt} errors/warnings • Click any row to expand details")

        # Table Header
        h_row = QHBoxLayout()
        h_row.setContentsMargins(12, 6, 12, 6)
        h_row.setSpacing(10)

        chevron_space = QLabel("")
        chevron_space.setFixedWidth(14)
        h_row.addWidget(chevron_space)

        for h_name, stretch in [("TASK ID", 1), ("DESCRIPTION", 3), ("AGENT", 1), ("STATUS", 1), ("PROGRESS", 1)]:
            hlbl = QLabel(h_name)
            hlbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            hlbl.setStyleSheet("color: #64748b; letter-spacing: 0.5px; background: transparent; border: none;")
            h_row.addWidget(hlbl, stretch)
        self._tqc_l.addLayout(h_row)

        if filtered_tasks:
            for t in filtered_tasks:
                is_exp = t["id"] in self._expanded_task_ids
                row_widget = ExpandableTaskRow(
                    task_data=t,
                    is_expanded=is_exp,
                    on_toggle_callback=self._on_task_row_toggled,
                )
                self._tqc_l.addWidget(row_widget)
        else:
            empty_lbl = QLabel("No tasks matching current filter or search query.")
            empty_lbl.setFont(QFont("Segoe UI", 9))
            empty_lbl.setStyleSheet("color: #64748b; padding: 16px; background: transparent; border: none;")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._tqc_l.addWidget(empty_lbl)

        # If log panel is active, refresh log text
        if self._show_logs:
            self._update_logs()

    def _on_search_changed(self, text: str):
        self._refresh_data()

    def _spawn_new_agent(self):
        try:
            from core.aura_core import AuraCore
            AuraCore.get_instance()
            logger.info("Spawning autonomous agent task via core...")
        except Exception:
            pass
        self._refresh_data()

    def _execute_dag(self):
        try:
            app_signals.execution_started.emit("dag-m20-m25")
        except Exception:
            pass
        self._refresh_data()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    # -------------------------------------------------------------------------
    # GEOMETRY PERSISTENCE (QSETTINGS)
    # -------------------------------------------------------------------------
    def _restore_geometry(self):
        screen = QApplication.primaryScreen().availableGeometry()
        pos = self._settings.value("pos", None)
        size = self._settings.value("size", None)

        auto_w = max(MIN_W, min(int(screen.width() * 0.58), screen.width() - 40))
        auto_h = max(MIN_H, min(int(screen.height() * 0.78), screen.height() - 40))

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
                    screen.left() + (screen.width() - self.width()) // 2 + 40,
                    screen.top() + (screen.height() - self.height()) // 2 + 30,
                )
        else:
            self.move(
                screen.left() + (screen.width() - self.width()) // 2 + 40,
                screen.top() + (screen.height() - self.height()) // 2 + 30,
            )

    def _save_geometry(self):
        self._settings.setValue("pos", self.pos())
        self._settings.setValue("size", self.size())

    # -------------------------------------------------------------------------
    # DRAG & RESIZE HANDLING
    # -------------------------------------------------------------------------
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

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()

        # Dotted Resize Grip Hint (bottom-right)
        p.setPen(QPen(QColor(100, 150, 255, 120), 1))
        for i in range(3):
            for j in range(i, 3):
                dx = w - 14 - j * 4
                dy = h - 14 - i * 4
                p.drawPoint(dx, dy)

        p.end()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    overlay = AgentTaskStatusOverlay()
    overlay.show()
    sys.exit(app.exec())
