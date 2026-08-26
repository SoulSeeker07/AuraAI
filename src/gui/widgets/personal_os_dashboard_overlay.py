"""
PersonalOSDashboardOverlay Widget
=================================
Ultra-Modern Next-Gen Personal OS & Daily Control Center HUD Overlay.
Connected to Genuine Real Backends:
- Memory.db (facts, preferences, project memories, topic summaries)
- PersonalOSStateStore (persistent tasks, automations, schedules)
- DailyContextEngine (agenda synthesis, calendar events)
- Real-time task toggle & memory deep-dive actions
"""

import sys
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
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QComboBox,
    QCheckBox,
    QSizePolicy,
)

from gui.real_backend_bridge import RealBackendBridge

REF_W = 1920
REF_H = 1080
MIN_W = 660
MIN_H = 480
GRIP_SIZE = 18

ORG_NAME = "AuraAI"
APP_NAME = "PersonalOSDashboardOverlay"


class PersonalOSDashboardOverlay(QWidget):
    """
    Next-Gen Ultra-Modern Personal OS Daily Control Center HUD.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PersonalOSDashboardOverlay")
        self.setWindowTitle("AuraAI Personal OS Dashboard")

        # Frameless HUD window attributes
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
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

        # Clock & refresh timer
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._on_tick)
        self._clock_timer.start(1000)

        self._setup_ui()
        self._restore_geometry()
        self._refresh_data()

    # -------------------------------------------------------------------------
    # UI SETUP
    # -------------------------------------------------------------------------
    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)

        # Outer Glass Container
        self._card = QFrame()
        self._card.setObjectName("MainOSCard")
        self._card.setStyleSheet("""
            #MainOSCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(10, 10, 18, 0.96), stop:1 rgba(21, 21, 31, 0.97));
                border: 1px solid rgba(100, 150, 255, 0.22);
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
                background: rgba(10, 10, 18, 0.85);
                border-bottom: 1px solid rgba(100, 150, 255, 0.15);
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
            }
        """)
        hb_l = QHBoxLayout(header_bar)
        hb_l.setContentsMargins(24, 16, 24, 16)
        hb_l.setSpacing(14)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title = QLabel("Personal OS")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Light))
        title.setStyleSheet("color: #ffffff; letter-spacing: -0.5px; background: transparent; border: none;")
        title_box.addWidget(title)

        self._date_time_lbl = QLabel()
        self._date_time_lbl.setFont(QFont("Segoe UI", 8))
        self._date_time_lbl.setStyleSheet("color: #7b8c9f; background: transparent; border: none;")
        title_box.addWidget(self._date_time_lbl)
        hb_l.addLayout(title_box)

        hb_l.addStretch()

        # Action Buttons
        btn_trigger = QPushButton("+ New Trigger")
        btn_trigger.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        btn_trigger.setCursor(Qt.PointingHandCursor)
        btn_trigger.setStyleSheet("""
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
        btn_trigger.clicked.connect(self._add_quick_trigger)
        hb_l.addWidget(btn_trigger)

        btn_capture = QPushButton("📝 Capture")
        btn_capture.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        btn_capture.setCursor(Qt.PointingHandCursor)
        btn_capture.setStyleSheet("""
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
        btn_capture.clicked.connect(self._quick_capture)
        hb_l.addWidget(btn_capture)

        # Close button
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
        hb_l.addWidget(btn_close)

        layout.addWidget(header_bar)

        # ── Scroll Area for Dashboard Body ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(24, 20, 24, 20)
        body_layout.setSpacing(24)

        # ── 2. Top Overview Row (4 KPI Cards) ──
        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(12)

        # 1. Today's Tasks
        self._kpi_tasks = self._create_kpi_card(
            "TODAY'S TASKS", "7<span style='font-size:16px; color:#888;'>/12</span>", "5 pending • 2 overdue",
            "#66ff99", "rgba(102, 255, 153, 0.08)", "rgba(102, 255, 153, 0.22)"
        )
        kpi_grid.addWidget(self._kpi_tasks, 0, 0)

        # 2. Active Triggers
        self._kpi_triggers = self._create_kpi_card(
            "ACTIVE TRIGGERS", "4", "Last fired: 12 min ago",
            "#6496ff", "rgba(100, 150, 255, 0.08)", "rgba(100, 150, 255, 0.22)"
        )
        kpi_grid.addWidget(self._kpi_triggers, 0, 1)

        # 3. Calendar Events
        self._kpi_events = self._create_kpi_card(
            "CALENDAR EVENTS", "3", "Next: Design Review (4pm)",
            "#fbbf24", "rgba(251, 191, 36, 0.08)", "rgba(251, 191, 36, 0.22)"
        )
        kpi_grid.addWidget(self._kpi_events, 0, 2)

        # 4. Memory Context
        self._kpi_memory = self._create_kpi_card(
            "MEMORY CONTEXT", "8", "Stores active • 247 items",
            "#a855f7", "rgba(168, 85, 247, 0.08)", "rgba(168, 85, 247, 0.22)"
        )
        kpi_grid.addWidget(self._kpi_memory, 0, 3)

        body_layout.addLayout(kpi_grid)

        # ── 3. Dual Columns (2fr Tasks & Calendar / 1fr Triggers & Memory) ──
        dual_layout = QHBoxLayout()
        dual_layout.setSpacing(20)

        # ── LEFT COLUMN (Tasks & Calendar) ──
        left_col = QVBoxLayout()
        left_col.setSpacing(24)

        # Today's Tasks Section
        tasks_section = QVBoxLayout()
        tasks_section.setSpacing(10)

        th_layout = QHBoxLayout()
        th_title = QLabel("Today's Tasks")
        th_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
        th_title.setStyleSheet("color: #ffffff; background: transparent;")
        th_layout.addWidget(th_title)

        th_layout.addStretch()

        self._filter_cb = QComboBox()
        self._filter_cb.addItems(["All tasks", "Pending only", "Overdue only", "Completed"])
        self._filter_cb.setFont(QFont("Segoe UI", 8))
        self._filter_cb.setStyleSheet("""
            QComboBox {
                background: rgba(100, 150, 255, 0.1);
                border: 1px solid rgba(100, 150, 255, 0.25);
                color: #6496ff;
                padding: 4px 10px;
                border-radius: 6px;
            }
        """)
        self._filter_cb.currentIndexChanged.connect(self._refresh_data)
        th_layout.addWidget(self._filter_cb)
        tasks_section.addLayout(th_layout)

        self._tasks_card = QFrame()
        self._tasks_card.setStyleSheet("""
            QFrame {
                background: rgba(100, 150, 255, 0.03);
                border: 1px solid rgba(100, 150, 255, 0.12);
                border-radius: 12px;
            }
        """)
        self._tasks_list_layout = QVBoxLayout(self._tasks_card)
        self._tasks_list_layout.setContentsMargins(8, 8, 8, 8)
        self._tasks_list_layout.setSpacing(6)
        tasks_section.addWidget(self._tasks_card)
        left_col.addLayout(tasks_section)

        # Upcoming Events Section
        events_section = QVBoxLayout()
        events_section.setSpacing(10)

        eh_title = QLabel("Upcoming Events")
        eh_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
        eh_title.setStyleSheet("color: #ffffff; background: transparent;")
        events_section.addWidget(eh_title)

        self._events_card = QFrame()
        self._events_card.setStyleSheet("""
            QFrame {
                background: rgba(100, 150, 255, 0.03);
                border: 1px solid rgba(100, 150, 255, 0.12);
                border-radius: 12px;
            }
        """)
        self._events_list_layout = QVBoxLayout(self._events_card)
        self._events_list_layout.setContentsMargins(10, 10, 10, 10)
        self._events_list_layout.setSpacing(8)
        events_section.addWidget(self._events_card)
        left_col.addLayout(events_section)

        dual_layout.addLayout(left_col, 2)

        # ── RIGHT COLUMN (Triggers & Memory) ──
        right_col = QVBoxLayout()
        right_col.setSpacing(24)

        # Active Triggers Section
        trig_section = QVBoxLayout()
        trig_section.setSpacing(10)

        trig_header = QHBoxLayout()
        trig_title = QLabel("Active Triggers")
        trig_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
        trig_title.setStyleSheet("color: #ffffff; background: transparent;")
        trig_header.addWidget(trig_title)
        trig_header.addStretch()

        self._trig_badge = QLabel("● 4 live")
        self._trig_badge.setFont(QFont("Segoe UI", 8))
        self._trig_badge.setStyleSheet("color: #66ff99; background: transparent;")
        trig_header.addWidget(self._trig_badge)
        trig_section.addLayout(trig_header)

        self._trig_card = QFrame()
        self._trig_card.setStyleSheet("""
            QFrame {
                background: rgba(100, 150, 255, 0.03);
                border: 1px solid rgba(100, 150, 255, 0.12);
                border-radius: 12px;
            }
        """)
        self._trig_list_layout = QVBoxLayout(self._trig_card)
        self._trig_list_layout.setContentsMargins(10, 10, 10, 10)
        self._trig_list_layout.setSpacing(8)
        trig_section.addWidget(self._trig_card)
        right_col.addLayout(trig_section)

        # Memory Context Section
        mem_section = QVBoxLayout()
        mem_section.setSpacing(10)

        mem_title = QLabel("Memory Context")
        mem_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
        mem_title.setStyleSheet("color: #ffffff; background: transparent;")
        mem_section.addWidget(mem_title)

        self._mem_card = QFrame()
        self._mem_card.setStyleSheet("""
            QFrame {
                background: rgba(100, 150, 255, 0.03);
                border: 1px solid rgba(100, 150, 255, 0.12);
                border-radius: 12px;
            }
        """)
        self._mem_list_layout = QVBoxLayout(self._mem_card)
        self._mem_list_layout.setContentsMargins(12, 12, 12, 12)
        self._mem_list_layout.setSpacing(12)
        mem_section.addWidget(self._mem_card)
        right_col.addLayout(mem_section)

        dual_layout.addLayout(right_col, 1)
        body_layout.addLayout(dual_layout)

        scroll.setWidget(body)
        layout.addWidget(scroll)

        root_layout.addWidget(self._card)

    def _create_kpi_card(
        self, title: str, main_val: str, sub_val: str, text_color: str, bg_rgba: str, border_rgba: str
    ) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {bg_rgba};
                border: 1px solid {border_rgba};
                border-radius: 12px;
            }}
        """)
        l = QVBoxLayout(card)
        l.setContentsMargins(14, 12, 14, 12)
        l.setSpacing(4)

        t_lbl = QLabel(title)
        t_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        t_lbl.setStyleSheet(f"color: {text_color}; letter-spacing: 0.8px; background: transparent; border: none;")
        l.addWidget(t_lbl)

        v_lbl = QLabel(main_val)
        v_lbl.setObjectName("MainVal")
        v_lbl.setFont(QFont("Segoe UI", 22, QFont.Weight.Light))
        v_lbl.setStyleSheet("color: #ffffff; letter-spacing: -0.5px; background: transparent; border: none;")
        v_lbl.setTextFormat(Qt.TextFormat.RichText)
        l.addWidget(v_lbl)

        s_lbl = QLabel(sub_val)
        s_lbl.setObjectName("SubVal")
        s_lbl.setFont(QFont("Segoe UI", 8))
        s_lbl.setStyleSheet("color: #7b8c9f; background: transparent; border: none;")
        l.addWidget(s_lbl)
        return card

    def _create_memory_chip(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFont(QFont("Segoe UI", 8))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background: rgba(100, 150, 255, 0.1);
                border: 1px solid rgba(100, 150, 255, 0.25);
                border-radius: 6px;
                padding: 4px 8px;
                color: #6496ff;
            }
            QPushButton:hover {
                background: rgba(100, 150, 255, 0.22);
                color: #ffffff;
            }
        """)
        return btn

    # -------------------------------------------------------------------------
    # LIVE REFRESH & ACTIONS
    # -------------------------------------------------------------------------
    def _on_tick(self):
        now = QDateTime.currentDateTime()
        self._date_time_lbl.setText(now.toString("dddd, MMMM d • h:mm AP"))

    def _refresh_data(self):
        """Fetch and populate live data from Memory.db and PersonalOSStateStore."""
        mem_data = self._bridge.get_memory_stats()
        pos_data = self._bridge.get_personal_os_data()

        # 1. Update KPI Cards
        # Tasks KPI
        t_comp = pos_data["stats"]["tasks_completed"]
        t_tot = pos_data["stats"]["tasks_total"]
        t_pend = pos_data["stats"]["pending"]
        t_over = pos_data["stats"]["overdue"]
        self._set_kpi_text(self._kpi_tasks, f"{t_comp}<span style='font-size:16px; color:#888;'>/{t_tot}</span>", f"{t_pend} pending • {t_over} overdue")

        # Triggers KPI
        tr_cnt = pos_data["stats"]["active_triggers_count"]
        self._set_kpi_text(self._kpi_triggers, str(tr_cnt), "Live automated routines")
        self._trig_badge.setText(f"● {tr_cnt} live")

        # Calendar KPI
        ev_cnt = len(pos_data["events"])
        next_ev = pos_data["events"][0]["title"] if ev_cnt > 0 else "None scheduled"
        self._set_kpi_text(self._kpi_events, str(ev_cnt), f"Next: {next_ev[:20]}")

        # Memory KPI
        m_facts = mem_data["total_facts"]
        m_top = mem_data["total_topics"]
        self._set_kpi_text(self._kpi_memory, str(m_facts), f"{m_top} topic vaults • Memory.db")

        # 2. Render Tasks
        self._render_tasks(pos_data["tasks"])

        # 3. Render Events
        self._render_events(pos_data["events"])

        # 4. Render Triggers
        self._render_triggers(pos_data["triggers"])

        # 5. Render Memory Context
        self._render_memory_context(mem_data)

    def _set_kpi_text(self, card: QFrame, main_val: str, sub_val: str):
        v = card.findChild(QLabel, "MainVal")
        s = card.findChild(QLabel, "SubVal")
        if v:
            v.setText(main_val)
        if s:
            s.setText(sub_val)

    def _render_tasks(self, tasks: List[Dict[str, Any]]):
        self._clear_layout(self._tasks_list_layout)
        filter_mode = self._filter_cb.currentText() if hasattr(self, "_filter_cb") else "All tasks"

        for task in tasks:
            t_id = task.get("id", "")
            t_title = task.get("title", "")
            t_cat = task.get("category", "General")
            t_status = task.get("status", "pending")
            t_due = task.get("due", "")
            t_checked = bool(task.get("completed", False))

            if filter_mode == "Pending only" and t_checked:
                continue
            if filter_mode == "Completed" and not t_checked:
                continue
            if filter_mode == "Overdue only" and t_status != "overdue":
                continue

            bg = "rgba(239, 68, 68, 0.08)" if t_status == "overdue" else ("rgba(102, 255, 153, 0.04)" if t_checked else "transparent")
            col = "#ef4444" if t_status == "overdue" else ("#66ff99" if t_checked else "#fbbf24")

            item_frame = QFrame()
            item_frame.setStyleSheet(f"""
                QFrame {{
                    background: {bg};
                    border-bottom: 1px solid rgba(100, 150, 255, 0.06);
                    border-radius: 6px;
                }}
                QFrame:hover {{
                    background: rgba(100, 150, 255, 0.08);
                }}
            """)
            if_l = QHBoxLayout(item_frame)
            if_l.setContentsMargins(10, 8, 10, 8)
            if_l.setSpacing(10)

            chk = QCheckBox()
            chk.setChecked(t_checked)
            chk.toggled.connect(lambda checked, tid=t_id: self._on_task_toggled(tid, checked))
            if_l.addWidget(chk)

            info_l = QVBoxLayout()
            info_l.setSpacing(2)

            tl = QLabel(t_title)
            tl.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
            if t_checked:
                tl.setStyleSheet("color: #8899aa; text-decoration: line-through; background: transparent; border: none;")
            else:
                tl.setStyleSheet("color: #ffffff; background: transparent; border: none;")
            info_l.addWidget(tl)

            sl = QLabel(f"Due: {t_due} • {t_status.replace('_', ' ').title()}")
            sl.setFont(QFont("Segoe UI", 8))
            sl.setStyleSheet(f"color: {col}; background: transparent; border: none;")
            info_l.addWidget(sl)
            if_l.addLayout(info_l, 1)

            cat_lbl = QLabel(t_cat)
            cat_lbl.setFont(QFont("Segoe UI", 8))
            cat_lbl.setStyleSheet("color: #7b8c9f; background: transparent; border: none;")
            if_l.addWidget(cat_lbl)

            self._tasks_list_layout.addWidget(item_frame)

    def _on_task_toggled(self, task_id: str, checked: bool):
        self._bridge.toggle_task_completion(task_id, checked)
        self._refresh_data()

    def _render_events(self, events: List[Dict[str, Any]]):
        self._clear_layout(self._events_list_layout)
        for ev in events:
            ev_frame = QFrame()
            ev_frame.setStyleSheet("""
                QFrame {
                    background: rgba(255, 255, 255, 0.02);
                    border-bottom: 1px solid rgba(100, 150, 255, 0.05);
                    border-radius: 6px;
                }
                QFrame:hover {
                    background: rgba(100, 150, 255, 0.08);
                }
            """)
            ef_l = QHBoxLayout(ev_frame)
            ef_l.setContentsMargins(10, 8, 10, 8)
            ef_l.setSpacing(10)

            bar = QFrame()
            bar.setFixedSize(4, 28)
            bar.setStyleSheet(f"background: {ev.get('color', '#6496ff')}; border-radius: 2px;")
            ef_l.addWidget(bar)

            e_info = QVBoxLayout()
            e_info.setSpacing(2)

            et = QLabel(ev.get("title", "Event"))
            et.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
            et.setStyleSheet("color: #ffffff; background: transparent; border: none;")
            e_info.addWidget(et)

            es = QLabel(f"{ev.get('time', '')} • {ev.get('meta', '')}")
            es.setFont(QFont("Segoe UI", 8))
            es.setStyleSheet("color: #7b8c9f; background: transparent; border: none;")
            e_info.addWidget(es)
            ef_l.addLayout(e_info, 1)

            self._events_list_layout.addWidget(ev_frame)

    def _render_triggers(self, triggers: List[Dict[str, Any]]):
        self._clear_layout(self._trig_list_layout)
        for tr in triggers:
            tr_item = QFrame()
            tr_item.setStyleSheet("""
                QFrame {
                    background: rgba(255, 255, 255, 0.02);
                    border-bottom: 1px solid rgba(100, 150, 255, 0.05);
                    border-radius: 6px;
                }
                QFrame:hover {
                    background: rgba(102, 255, 153, 0.06);
                }
            """)
            tri_l = QHBoxLayout(tr_item)
            tri_l.setContentsMargins(10, 8, 10, 8)

            t_box = QVBoxLayout()
            t_box.setSpacing(2)
            tn = QLabel(tr.get("name", "Trigger"))
            tn.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
            tn.setStyleSheet("color: #ffffff; background: transparent; border: none;")
            t_box.addWidget(tn)

            schedule = tr.get("schedule", "on_demand")
            tm = QLabel(f"Schedule: {schedule}")
            tm.setFont(QFont("Segoe UI", 8))
            tm.setStyleSheet("color: #7b8c9f; background: transparent; border: none;")
            t_box.addWidget(tm)
            tri_l.addLayout(t_box, 1)

            check_mark = QLabel("✓")
            check_mark.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            check_mark.setStyleSheet("color: #66ff99; background: transparent; border: none;")
            tri_l.addWidget(check_mark)

            self._trig_list_layout.addWidget(tr_item)

        btn_manage = QPushButton("Manage Triggers")
        btn_manage.setFont(QFont("Segoe UI", 8))
        btn_manage.setCursor(Qt.PointingHandCursor)
        btn_manage.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid rgba(100, 150, 255, 0.25);
                color: #6496ff;
                padding: 6px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: rgba(100, 150, 255, 0.15);
                color: #ffffff;
            }
        """)
        btn_manage.clicked.connect(self._add_quick_trigger)
        self._trig_list_layout.addWidget(btn_manage)

    def _render_memory_context(self, mem: Dict[str, Any]):
        self._clear_layout(self._mem_list_layout)

        # 1. Preferences (from Memory.db)
        p_title = QLabel(f"PREFERENCES ({len(mem['preferences'])} ITEMS)")
        p_title.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        p_title.setStyleSheet("color: #7b8c9f; letter-spacing: 0.6px; background: transparent; border: none;")
        self._mem_list_layout.addWidget(p_title)

        p_chips = QHBoxLayout()
        p_chips.setSpacing(6)
        for pref in mem["preferences"][:4]:
            btn = self._create_memory_chip(pref)
            p_chips.addWidget(btn)
        p_chips.addStretch()
        self._mem_list_layout.addLayout(p_chips)

        # 2. Projects & Work (from Memory.db)
        pr_title = QLabel(f"PROJECTS & TOPICS ({len(mem['projects'])} ITEMS)")
        pr_title.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        pr_title.setStyleSheet("color: #7b8c9f; letter-spacing: 0.6px; background: transparent; border: none;")
        self._mem_list_layout.addWidget(pr_title)

        pr_chips = QHBoxLayout()
        pr_chips.setSpacing(6)
        for proj in mem["projects"][:4]:
            btn = self._create_memory_chip(proj)
            pr_chips.addWidget(btn)
        pr_chips.addStretch()
        self._mem_list_layout.addLayout(pr_chips)

        # 3. Procedural
        proc_title = QLabel("PROCEDURAL STORE")
        proc_title.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        proc_title.setStyleSheet("color: #7b8c9f; letter-spacing: 0.6px; background: transparent; border: none;")
        self._mem_list_layout.addWidget(proc_title)

        proc_chips = QHBoxLayout()
        proc_chips.setSpacing(6)
        for proc in mem["procedural"][:4]:
            btn = self._create_memory_chip(proc)
            proc_chips.addWidget(btn)
        proc_chips.addStretch()
        self._mem_list_layout.addLayout(proc_chips)

        # 4. Domain Providers
        dom_title = QLabel("DOMAIN PROVIDERS (ALL ACTIVE)")
        dom_title.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        dom_title.setStyleSheet("color: #7b8c9f; letter-spacing: 0.6px; background: transparent; border: none;")
        self._mem_list_layout.addWidget(dom_title)

        dom_grid = QHBoxLayout()
        dom_grid.setSpacing(6)
        for d in mem["domains"]:
            d_badge = QLabel(f"{d['name']} ✓")
            d_badge.setFont(QFont("Segoe UI", 8))
            d_badge.setStyleSheet("""
                QLabel {
                    background: rgba(102, 255, 153, 0.1);
                    border: 1px solid rgba(102, 255, 153, 0.25);
                    border-radius: 4px;
                    padding: 3px 8px;
                    color: #66ff99;
                }
            """)
            dom_grid.addWidget(d_badge)
        dom_grid.addStretch()
        self._mem_list_layout.addLayout(dom_grid)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _add_quick_trigger(self):
        try:
            from personal_os.state_store import PersonalOSStateStore, PersonalOSTrigger
            store = PersonalOSStateStore.get_instance()
            new_trig = PersonalOSTrigger(
                trigger_id=f"trig_user_{int(QDateTime.currentSecsSinceEpoch())}",
                name="Quick Auto-Trigger",
                goal_text="Periodic workspace audit and system memory consolidation",
                schedule="every 30m",
                enabled=True,
            )
            store.save_trigger(new_trig)
            self._refresh_data()
        except Exception as e:
            logger.debug(f"Trigger create: {e}")

    def _quick_capture(self):
        try:
            from personal_os.state_store import PersonalOSStateStore
            store = PersonalOSStateStore.get_instance()
            tasks = store.get_preference("personal_os_tasks", [])
            tasks.append({
                "id": f"T-{len(tasks) + 101}",
                "title": f"Captured task #{len(tasks) + 1}",
                "category": "QuickCapture",
                "status": "in_progress",
                "due": "Today",
                "completed": False,
            })
            store.set_preference("personal_os_tasks", tasks)
            self._refresh_data()
        except Exception as e:
            logger.debug(f"Task capture: {e}")

    # -------------------------------------------------------------------------
    # GEOMETRY PERSISTENCE (QSETTINGS)
    # -------------------------------------------------------------------------
    def _restore_geometry(self):
        screen = QApplication.primaryScreen().availableGeometry()
        pos = self._settings.value("pos", None)
        size = self._settings.value("size", None)

        auto_w = max(MIN_W, min(int(screen.width() * 0.58), screen.width() - 40))
        auto_h = max(MIN_H, min(int(screen.height() * 0.76), screen.height() - 40))

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
        if hasattr(self, "_clock_timer") and self._clock_timer.isActive():
            self._clock_timer.stop()
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
    overlay = PersonalOSDashboardOverlay()
    overlay.show()
    sys.exit(app.exec())
