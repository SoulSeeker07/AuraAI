from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QWidget


def fade_in(widget: QWidget, duration_ms: int = 110) -> QPropertyAnimation:
    animation = QPropertyAnimation(widget, b"windowOpacity", widget)
    animation.setDuration(duration_ms)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.start()
    return animation
