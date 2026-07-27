from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class TitleBar(QWidget):
    minimize_requested = Signal()
    maximize_requested = Signal()
    close_requested = Signal()

    def __init__(self, title: str = "Aura", parent=None):
        super().__init__(parent)
        self._drag_position: QPoint | None = None
        self.setObjectName("titleBar")
        self.setFixedHeight(46)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 10, 8)
        layout.setSpacing(8)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("titleLabel")

        self.settings_button = QPushButton("...")
        self.settings_button.setObjectName("titleButton")
        self.settings_button.setToolTip("Settings")

        self.minimize_button = QPushButton("-")
        self.minimize_button.setObjectName("titleButton")
        self.minimize_button.setToolTip("Minimize")
        self.minimize_button.clicked.connect(self.minimize_requested.emit)

        self.maximize_button = QPushButton("□")
        self.maximize_button.setObjectName("titleButton")
        self.maximize_button.setToolTip("Maximize")
        self.maximize_button.clicked.connect(self.maximize_requested.emit)

        self.close_button = QPushButton("x")
        self.close_button.setObjectName("closeButton")
        self.close_button.setToolTip("Close to tray")
        self.close_button.clicked.connect(self.close_requested.emit)

        layout.addWidget(self.title_label)
        layout.addStretch(1)
        layout.addWidget(self.settings_button)
        layout.addWidget(self.minimize_button)
        layout.addWidget(self.maximize_button)
        layout.addWidget(self.close_button)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_position is not None and event.buttons() & Qt.MouseButton.LeftButton:
            if not self.window().isMaximized():
                self.window().move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_position = None
        super().mouseReleaseEvent(event)
