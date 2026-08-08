"""
StepCard & StepListWidget
=========================
Real-time execution step cards with status indicators.
Used in the Overlay spotlight HUD.
"""

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui.signals import ExecutionStep, StepStatus, app_signals
from gui.theme import Colors, Radius, Typography


class StepCard(QWidget):
    """
    Individual execution step card showing status, title, and description.
    Animates in when added to the list.
    """

    STATUS_ICONS = {
        StepStatus.PENDING: "○",
        StepStatus.RUNNING: "⚙️",
        StepStatus.COMPLETED: "✓",
        StepStatus.FAILED: "✗",
        StepStatus.SKIPPED: "⊘",
    }

    STATUS_COLORS = {
        StepStatus.PENDING: Colors.TEXT_MUTED,
        StepStatus.RUNNING: Colors.WARNING,
        StepStatus.COMPLETED: Colors.SUCCESS,
        StepStatus.FAILED: Colors.ERROR,
        StepStatus.SKIPPED: Colors.TEXT_DISABLED,
    }

    def __init__(self, step: ExecutionStep, parent=None):
        super().__init__(parent)
        self._step = step
        self.setObjectName("StepCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(48)

        self._setup_ui()
        self._update_appearance()

        # Entrance animation
        self.setMaximumHeight(0)
        self._anim = QPropertyAnimation(self, b"maximumHeight")
        self._anim.setDuration(250)
        self._anim.setStartValue(0)
        self._anim.setEndValue(self.sizeHint().height() + 20)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(lambda: self.setMaximumHeight(16777215))

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        # Status icon
        self._icon_label = QLabel(self.STATUS_ICONS[self._step.status])
        self._icon_label.setFixedWidth(24)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setStyleSheet(
            "font-size: 14px; background: transparent; border: none;"
        )
        layout.addWidget(self._icon_label)

        # Text column
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 0, 0, 0)

        self._title_label = QLabel(self._step.title)
        self._title_label.setFont(Typography.BODY())
        self._title_label.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; background: transparent; border: none;"
        )
        text_layout.addWidget(self._title_label)

        if self._step.description:
            self._desc_label = QLabel(self._step.description)
            self._desc_label.setFont(Typography.CAPTION())
            self._desc_label.setStyleSheet(
                f"color: {Colors.TEXT_MUTED}; background: transparent; border: none;"
            )
            self._desc_label.setWordWrap(True)
            text_layout.addWidget(self._desc_label)

        layout.addLayout(text_layout, 1)

        # Step number
        self._num_label = QLabel(f"{self._step.index + 1}")
        self._num_label.setFont(Typography.CAPTION())
        self._num_label.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; background: transparent; border: none;"
        )
        self._num_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self._num_label)

    def _update_appearance(self):
        color = self.STATUS_COLORS[self._step.status]
        self._icon_label.setText(self.STATUS_ICONS[self._step.status])
        self._icon_label.setStyleSheet(
            f"color: {color}; font-size: 14px; background: transparent; border: none;"
        )

        if self._step.status == StepStatus.RUNNING:
            self.setStyleSheet(f"""
                StepCard {{
                    background: rgba(245, 158, 11, 0.05);
                    border: 1px solid {Colors.WARNING};
                    border-radius: {Radius.MD};
                }}
            """)
        elif self._step.status == StepStatus.COMPLETED:
            self.setStyleSheet(f"""
                StepCard {{
                    background: rgba(16, 185, 129, 0.05);
                    border: 1px solid {Colors.SUCCESS};
                    border-radius: {Radius.MD};
                }}
            """)
        elif self._step.status == StepStatus.FAILED:
            self.setStyleSheet(f"""
                StepCard {{
                    background: rgba(244, 63, 94, 0.05);
                    border: 1px solid {Colors.ERROR};
                    border-radius: {Radius.MD};
                }}
            """)
        else:
            self.setStyleSheet(f"""
                StepCard {{
                    background: {Colors.BG_CARD};
                    border: 1px solid {Colors.BORDER_SUBTLE};
                    border-radius: {Radius.MD};
                }}
            """)

    def update_step(self, step: ExecutionStep):
        self._step = step
        self._title_label.setText(step.title)
        if hasattr(self, "_desc_label") and step.description:
            self._desc_label.setText(step.description)
        self._update_appearance()

    def animate_in(self):
        self._anim.start()


class StepListWidget(QScrollArea):
    """
    Scrollable container for execution step cards.
    Automatically connects to app_signals for live updates.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._steps: dict[int, StepCard] = {}

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background: transparent; border: none;")

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, 0, 8, 0)
        self._layout.setSpacing(8)
        self._layout.addStretch()

        self.setWidget(self._container)

        # Connect signals
        app_signals.step_updated.connect(self._on_step_updated)
        app_signals.steps_cleared.connect(self._clear_steps)

    def _on_step_updated(self, step: ExecutionStep):
        if step.index in self._steps:
            self._steps[step.index].update_step(step)
        else:
            card = StepCard(step)
            self._steps[step.index] = card
            # Insert before the stretch
            self._layout.insertWidget(self._layout.count() - 1, card)
            card.animate_in()
            self._scroll_to_bottom()

    def _clear_steps(self):
        for i in reversed(range(self._layout.count() - 1)):
            widget = self._layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        self._steps.clear()

    def _scroll_to_bottom(self):
        vsb = self.verticalScrollBar()
        vsb.setValue(vsb.maximum())

    def add_step(self, step: ExecutionStep):
        app_signals.step_updated.emit(step)

    def clear(self):
        app_signals.steps_cleared.emit()
