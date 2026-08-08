"""
InspectorDrawer Widget
======================
Collapsible right-side panel showing live TaskWorkingMemory,
WorldStateObserver snapshots, and execution telemetry.
Used in MainWindow.
"""

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.signals import WorldStateSnapshot, app_signals
from gui.theme import Colors, Radius, Spacing, Typography


class _SectionHeader(QLabel):
    """Styled section header for the inspector."""

    def __init__(self, text: str, parent=None):
        super().__init__(text.upper(), parent)
        self.setFont(Typography.CAPTION())
        self.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; background: transparent; border: none; font-weight: bold; letter-spacing: 1px;"
        )
        self.setContentsMargins(0, Spacing.LG, 0, Spacing.SM)


class _MetricRow(QWidget):
    """Key-value metric row."""

    def __init__(self, label: str, value: str = "--", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(Spacing.MD)

        self._label = QLabel(label)
        self._label.setFont(Typography.CAPTION())
        self._label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;"
        )

        self._value = QLabel(value)
        self._value.setFont(Typography.CAPTION())
        self._value.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; background: transparent; border: none; font-weight: 600;"
        )
        self._value.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout.addWidget(self._label)
        layout.addWidget(self._value, 1)

    def set_value(self, value: str):
        self._value.setText(value)


class InspectorDrawer(QFrame):
    """
    Right-side collapsible inspector panel.

    Displays:
      - Current Hypothesis
      - Step Counter & Progress
      - World State (focused window, URL, mouse pos)
      - System Metrics (CPU, RAM)
      - Observation History stream
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("InspectorDrawer")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(280)
        self.setMaximumWidth(320)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        self._collapsed = False
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        layout.setSpacing(0)

        # ── Header ──
        header = QHBoxLayout()
        header_title = QLabel("🔍 Live Inspector")
        header_title.setFont(Typography.H3())
        header_title.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; background: transparent; border: none;"
        )
        header.addWidget(header_title)

        self._collapse_btn = QPushButton("◀")
        self._collapse_btn.setFixedSize(28, 28)
        self._collapse_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: {Radius.SM};
                color: {Colors.TEXT_MUTED};
                font-size: 10px;
            }}
            QPushButton:hover {{
                background: {Colors.BG_CARD_HOVER};
                color: {Colors.TEXT_PRIMARY};
            }}
        """)
        self._collapse_btn.setToolTip("Collapse inspector")
        self._collapse_btn.clicked.connect(self.toggle)
        header.addWidget(self._collapse_btn)
        layout.addLayout(header)

        layout.addSpacing(Spacing.MD)

        # ── Scrollable Content ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Current Hypothesis
        content_layout.addWidget(_SectionHeader("Current Hypothesis"))
        self._hypothesis = QTextEdit()
        self._hypothesis.setReadOnly(True)
        self._hypothesis.setFrameShape(QFrame.Shape.NoFrame)
        self._hypothesis.setStyleSheet(f"""
            QTextEdit {{
                background: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: {Radius.MD};
                padding: 10px;
                font-size: 12px;
                color: {Colors.CYAN_GLOW};
                font-style: italic;
            }}
        """)
        self._hypothesis.setFixedHeight(80)
        self._hypothesis.setPlaceholderText("No active hypothesis...")
        content_layout.addWidget(self._hypothesis)

        content_layout.addSpacing(Spacing.XL)

        # Step Counter
        content_layout.addWidget(_SectionHeader("Progress"))
        step_layout = QHBoxLayout()
        self._step_counter = QLabel("0 / 0")
        self._step_counter.setFont(Typography.H2())
        self._step_counter.setStyleSheet(
            f"color: {Colors.CYAN}; background: transparent; border: none;"
        )
        step_layout.addWidget(self._step_counter)
        step_layout.addStretch()
        content_layout.addLayout(step_layout)

        self._progress_bar = QProgressBar()
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(6)
        content_layout.addWidget(self._progress_bar)

        content_layout.addSpacing(Spacing.XL)

        # World State
        content_layout.addWidget(_SectionHeader("World Observer"))
        self._focused_window = _MetricRow("Focused Window")
        self._active_url = _MetricRow("Active URL")
        self._mouse_pos = _MetricRow("Mouse Position")
        content_layout.addWidget(self._focused_window)
        content_layout.addWidget(self._active_url)
        content_layout.addWidget(self._mouse_pos)

        content_layout.addSpacing(Spacing.XL)

        # System Metrics
        content_layout.addWidget(_SectionHeader("System Metrics"))
        self._cpu_metric = _MetricRow("CPU Usage")
        self._ram_metric = _MetricRow("RAM Usage")
        content_layout.addWidget(self._cpu_metric)
        content_layout.addWidget(self._ram_metric)

        content_layout.addSpacing(Spacing.XL)

        # Observation History
        content_layout.addWidget(_SectionHeader("Observations"))
        self._obs_stream = QTextEdit()
        self._obs_stream.setReadOnly(True)
        self._obs_stream.setFrameShape(QFrame.Shape.NoFrame)
        self._obs_stream.setStyleSheet(f"""
            QTextEdit {{
                background: transparent;
                border: none;
                font-family: monospace;
                font-size: 11px;
                color: {Colors.TEXT_MUTED};
                line-height: 1.4;
            }}
        """)
        self._obs_stream.setMaximumHeight(200)
        content_layout.addWidget(self._obs_stream)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _connect_signals(self):
        app_signals.world_state_changed.connect(self._on_world_state)
        app_signals.system_metrics.connect(self._on_system_metrics)
        app_signals.execution_started.connect(self._on_execution_started)
        app_signals.execution_finished.connect(self._on_execution_finished)

    def _on_world_state(self, snapshot: WorldStateSnapshot):
        self._focused_window.set_value(snapshot.focused_window or "—")
        self._active_url.set_value(snapshot.active_url or "—")
        self._mouse_pos.set_value(
            f"{snapshot.mouse_position[0]}, {snapshot.mouse_position[1]}"
        )

        # Append to observation stream
        ts = f"[{snapshot.timestamp:.1f}]" if snapshot.timestamp else "[--]"
        obs = f"{ts} Window: {snapshot.focused_window or 'N/A'}"
        self._obs_stream.append(obs)
        # Keep last 50 lines
        text = self._obs_stream.toPlainText()
        lines = text.split("\n")
        if len(lines) > 50:
            self._obs_stream.setPlainText("\n".join(lines[-50:]))
        self._obs_stream.verticalScrollBar().setValue(
            self._obs_stream.verticalScrollBar().maximum()
        )

    def _on_system_metrics(self, metrics: dict):
        cpu = metrics.get("cpu", 0)
        ram = metrics.get("ram", 0)
        self._cpu_metric.set_value(f"{cpu:.1f}%")
        self._ram_metric.set_value(f"{ram:.1f}%")

    def _on_execution_started(self, task_id: str):
        self._hypothesis.setPlainText(f"Task started: {task_id}")
        self._step_counter.setText("0 / ?")
        self._progress_bar.setValue(0)

    def _on_execution_finished(self, task_id: str, success: bool):
        color = Colors.SUCCESS if success else Colors.ERROR
        self._hypothesis.setStyleSheet(f"""
            QTextEdit {{
                background: {Colors.BG_CARD};
                border: 1px solid {color};
                border-radius: {Radius.MD};
                padding: 10px;
                font-size: 12px;
                color: {color};
                font-style: italic;
            }}
        """)
        self._hypothesis.setPlainText(
            f"Task {'completed' if success else 'failed'}: {task_id}"
        )

    def set_hypothesis(self, text: str):
        self._hypothesis.setPlainText(text)

    def set_progress(self, current: int, total: int):
        self._step_counter.setText(f"{current} / {total}")
        pct = int((current / max(total, 1)) * 100)
        self._progress_bar.setValue(pct)

    def toggle(self):
        self._collapsed = not self._collapsed
        target_width = 48 if self._collapsed else 320

        self._anim = QPropertyAnimation(self, b"maximumWidth")
        self._anim.setDuration(250)
        self._anim.setStartValue(self.width())
        self._anim.setEndValue(target_width)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim.start()

        self._collapse_btn.setText("▶" if self._collapsed else "◀")
        self._collapse_btn.setToolTip(
            "Expand inspector" if self._collapsed else "Collapse inspector"
        )
