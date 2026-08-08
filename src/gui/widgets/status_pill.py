"""
StatusPill Widget
=================
Compact pill-shaped status indicator with optional pulse animation.
Used in Overlay and MainWindow for voice/screen/engine status.
"""

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

from gui.theme import Colors, Radius, Typography


class StatusPill(QWidget):
    """
    A pill-shaped status badge with an optional animated dot indicator.

    Args:
        icon: Emoji or short text prefix (e.g., "🎙️", "👁️", "⚡")
        label: Status text (e.g., "Active", "Sharing", "Groq")
        active: Whether the status is currently active (affects styling)
        animate: Whether to show a pulsing dot when active
    """

    def __init__(
        self,
        icon: str,
        label: str,
        active: bool = False,
        animate: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._icon = icon
        self._label = label
        self._active = active
        self._animate = animate
        self._pulse_opacity = 1.0

        self.setObjectName("StatusPill")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self._setup_ui()
        self._setup_animation()
        self._update_style()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 14, 5)
        layout.setSpacing(6)

        # Animated dot
        self._dot = QLabel("●")
        self._dot.setFixedSize(8, 8)
        self._dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dot.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 6px;")
        layout.addWidget(self._dot)

        # Icon
        self._icon_label = QLabel(self._icon)
        self._icon_label.setStyleSheet(
            "font-size: 12px; background: transparent; border: none;"
        )
        layout.addWidget(self._icon_label)

        # Text
        self._text_label = QLabel(self._label)
        self._text_label.setFont(Typography.CAPTION())
        self._text_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;"
        )
        layout.addWidget(self._text_label)

        self.setFixedHeight(32)

    def _setup_animation(self):
        if self._animate and self._active:
            self._anim = QPropertyAnimation(self, b"pulse_opacity")
            self._anim.setDuration(1200)
            self._anim.setStartValue(0.3)
            self._anim.setEndValue(1.0)
            self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
            self._anim.setLoopCount(-1)
            self._anim.valueChanged.connect(self._on_pulse)
            self._anim.start()

    def _on_pulse(self, value):
        self._pulse_opacity = value
        self._dot.update()

    def _update_style(self):
        if self._active:
            self.setStyleSheet(f"""
                StatusPill {{
                    background: rgba(6, 182, 212, 0.08);
                    border: 1px solid {Colors.CYAN};
                    border-radius: {Radius.PILL};
                }}
            """)
            self._text_label.setStyleSheet(
                f"color: {Colors.CYAN_GLOW}; background: transparent; border: none; font-weight: 600;"
            )
            dot_color = (
                Colors.CYAN
                if not self._animate
                else f"rgba(6, 182, 212, {self._pulse_opacity})"
            )
            self._dot.setStyleSheet(
                f"color: {dot_color}; font-size: 8px; background: transparent; border: none;"
            )
        else:
            self.setStyleSheet(f"""
                StatusPill {{
                    background: {Colors.BG_CARD};
                    border: 1px solid {Colors.BORDER_SUBTLE};
                    border-radius: {Radius.PILL};
                }}
            """)
            self._text_label.setStyleSheet(
                f"color: {Colors.TEXT_MUTED}; background: transparent; border: none;"
            )
            self._dot.setStyleSheet(
                f"color: {Colors.TEXT_MUTED}; font-size: 6px; background: transparent; border: none;"
            )

    def set_active(self, active: bool):
        if self._active == active:
            return
        self._active = active
        self._update_style()
        if self._animate:
            if active and hasattr(self, "_anim"):
                self._anim.start()
            elif hasattr(self, "_anim"):
                self._anim.stop()

    def set_label(self, label: str):
        self._label = label
        self._text_label.setText(label)

    @property
    def pulse_opacity(self):
        return self._pulse_opacity

    @pulse_opacity.setter
    def pulse_opacity(self, value):
        self._pulse_opacity = value
        if self._active:
            self._dot.setStyleSheet(
                f"color: rgba(6, 182, 212, {value}); font-size: 8px; background: transparent; border: none;"
            )
