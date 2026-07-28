from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizeGrip,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.animations import fade_in


class OverlayWindow(QWidget):
    submitted = Signal(str)
    live_screen_toggled = Signal(bool)

    def __init__(self):
        super().__init__()
        self._fade_animation = None
        self._drag_offset: QPoint | None = None
        self._has_custom_position = False
        self._last_prompt = ""
        self._live_screen_active = False
        self.setWindowTitle("Aura Overlay")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(460, 270)
        self.resize(620, 330)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)

        self.panel = QFrame(self)
        self.panel.setObjectName("overlayPanel")
        root.addWidget(self.panel)

        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        self.title = QLabel("Aura")
        self.title.setObjectName("overlayTitle")
        layout.addWidget(self.title)

        subtitle = QLabel("Ask anything or type a command")
        subtitle.setObjectName("overlaySubtitle")
        layout.addWidget(subtitle)

        input_row = QHBoxLayout()
        input_row.setSpacing(10)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask anything...")
        self.input.returnPressed.connect(self._submit)

        send_button = QPushButton("Go")
        send_button.clicked.connect(self._submit)

        input_row.addWidget(self.input, 1)
        input_row.addWidget(send_button)
        layout.addLayout(input_row)

        tools_row = QHBoxLayout()
        tools_row.setSpacing(10)

        self.live_screen_button = QPushButton("Live Screen")
        self.live_screen_button.setObjectName("secondaryButton")
        self.live_screen_button.setCheckable(True)
        self.live_screen_button.clicked.connect(self._toggle_live_screen)

        self.tools_status = QLabel("Attach  |  Voice  |  Send")
        self.tools_status.setObjectName("overlayTools")

        tools_row.addWidget(self.live_screen_button)
        tools_row.addWidget(self.tools_status, 1)
        layout.addLayout(tools_row)

        self.response = QTextEdit()
        self.response.setObjectName("overlayResponse")
        self.response.setReadOnly(True)
        self.response.setMinimumHeight(96)
        self.response.setPlainText("Ready.")
        layout.addWidget(self.response)

        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 0, 0)
        grip_row.addStretch(1)
        grip_row.addWidget(QSizeGrip(self))
        layout.addLayout(grip_row)

    def set_response(self, response: str) -> None:
        self.response.setPlainText(response)
        self.input.setFocus()

    def set_live_screen_state(
        self,
        is_active: bool,
        frame_count: int = 0,
        frame_path: str | None = None,
    ) -> None:
        self._live_screen_active = is_active
        self.live_screen_button.blockSignals(True)
        self.live_screen_button.setChecked(is_active)
        self.live_screen_button.setText("Stop Live" if is_active else "Live Screen")
        self.live_screen_button.blockSignals(False)

        if is_active:
            detail = f"Live screen on. Frames: {frame_count}"
            if frame_path:
                detail = f"{detail} | Latest: {frame_path}"
            self.tools_status.setText(detail)
        else:
            self.tools_status.setText("Live screen off | Attach  |  Voice  |  Send")

    def show_overlay(self) -> None:
        screen = QApplication.primaryScreen()
        geometry = screen.availableGeometry()
        width = min(620, max(460, int(geometry.width() * 0.42)))
        height = min(330, max(270, int(geometry.height() * 0.34)))
        self.resize(width, height)

        if not self._has_custom_position:
            self.move(
                geometry.center().x() - self.width() // 2,
                geometry.top() + max(54, geometry.height() // 9),
            )
        else:
            self._keep_inside_screen()
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()
        self.input.selectAll()
        self._fade_animation = fade_in(self)

    def toggle(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.show_overlay()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._can_drag_from(event.position().toPoint()):
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            self._has_custom_position = True
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._drag_offset is not None:
            self._drag_offset = None
            self._keep_inside_screen()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _submit(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self._last_prompt = text
        self.submitted.emit(text)
        self.input.clear()

    def _toggle_live_screen(self) -> None:
        requested_state = self.live_screen_button.isChecked()
        self.live_screen_toggled.emit(requested_state)

    def _can_drag_from(self, position: QPoint) -> bool:
        child = self.childAt(position)
        blocked = (self.input, self.response, self.live_screen_button)
        return child not in blocked and not isinstance(child, QPushButton)

    def _keep_inside_screen(self) -> None:
        screen = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        if screen is None:
            return

        geometry = screen.availableGeometry()
        x = min(max(self.x(), geometry.left()), geometry.right() - self.width())
        y = min(max(self.y(), geometry.top()), geometry.bottom() - self.height())
        self.move(x, y)
