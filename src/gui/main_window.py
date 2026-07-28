from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.theme import PALETTE
from gui.titlebar import TitleBar


class MainWindow(QMainWindow):
    show_overlay_requested = Signal()
    settings_requested = Signal()
    hidden_to_tray = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Aura")
        self.resize(1040, 720)
        self.setMinimumSize(900, 620)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._build_actions()
        self._build_ui()

        shortcut = QShortcut(QKeySequence("Alt+Space"), self)
        shortcut.activated.connect(self.show_overlay_requested.emit)

    def add_history_entry(self, prompt: str) -> None:
        prefix = "Command" if prompt.startswith(">") else "Prompt"
        self.history_list.insertItem(0, f"{prefix}: {prompt}")
        self.status_label.setText("Captured from overlay. Aura brain is thinking.")

    def add_response_entry(self, response: str) -> None:
        first_line = response.splitlines()[0] if response else "Response ready."
        self.history_list.insertItem(0, f"Aura: {first_line}")
        self.status_label.setText(first_line)

    def set_live_screen_status(self, is_active: bool, frame_count: int = 0) -> None:
        if is_active:
            self.status_label.setText(f"Live screen mode active. Frames captured: {frame_count}.")
            return
        self.status_label.setText("Live screen mode stopped.")

    def close_to_tray(self) -> None:
        self.hide()
        self.hidden_to_tray.emit()

    def toggle_maximized(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def closeEvent(self, event: QCloseEvent) -> None:
        if QApplication.instance().property("force_quit"):
            event.accept()
            return

        event.ignore()
        self.close_to_tray()

    def _build_actions(self) -> None:
        overlay_action = QAction("Show Overlay", self)
        overlay_action.setShortcut("Alt+Space")
        overlay_action.triggered.connect(self.show_overlay_requested.emit)
        self.addAction(overlay_action)

    def _build_ui(self) -> None:
        outer = QWidget(self)
        outer.setObjectName("windowShadowHost")
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(16, 16, 16, 16)

        self.window_frame = QFrame()
        self.window_frame.setObjectName("windowFrame")
        shadow = QGraphicsDropShadowEffect(self.window_frame)
        shadow.setBlurRadius(34)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 185))
        self.window_frame.setGraphicsEffect(shadow)
        outer_layout.addWidget(self.window_frame)

        frame_layout = QVBoxLayout(self.window_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        self.title_bar = TitleBar("Aura")
        self.title_bar.minimize_requested.connect(self.showMinimized)
        self.title_bar.maximize_requested.connect(self.toggle_maximized)
        self.title_bar.close_requested.connect(self.close)
        self.title_bar.settings_button.clicked.connect(self.settings_requested.emit)
        frame_layout.addWidget(self.title_bar)

        shell = QHBoxLayout()
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        frame_layout.addLayout(shell, 1)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(230)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(22, 22, 22, 24)
        sidebar_layout.setSpacing(12)

        brand = QLabel("Aura")
        brand.setObjectName("brand")
        sidebar_layout.addWidget(brand)

        subtitle = QLabel("OS companion")
        subtitle.setObjectName("muted")
        sidebar_layout.addWidget(subtitle)

        self.overlay_button = QPushButton("Show Overlay")
        self.overlay_button.clicked.connect(self.show_overlay_requested.emit)
        sidebar_layout.addWidget(self.overlay_button)

        sidebar_layout.addSpacing(14)
        for label in ("History", "Plugins", "AI Providers", "Settings"):
            item = QLabel(label)
            item.setObjectName("navItem")
            sidebar_layout.addWidget(item)

        sidebar_layout.addStretch(1)
        hint = QLabel("Alt + Space opens Aura from anywhere when global hotkeys are available.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        sidebar_layout.addWidget(hint)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(34, 30, 34, 30)
        content_layout.setSpacing(18)

        header = QLabel("Control Center")
        header.setObjectName("pageTitle")
        content_layout.addWidget(header)

        self.status_label = QLabel("Aura brain ready. Open the overlay to chat with memory.")
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        content_layout.addWidget(self.status_label)

        cards = QHBoxLayout()
        cards.setSpacing(14)
        cards.addWidget(self._metric_card("Main Window", "Frameless", "Custom title bar and rounded frame"))
        cards.addWidget(self._metric_card("Overlay", "Alt + Space", "Instant prompt surface"))
        cards.addWidget(self._metric_card("Tray", "Enabled", "Close keeps Aura running"))
        content_layout.addLayout(cards)

        history_title = QLabel("Recent Activity")
        history_title.setObjectName("sectionTitle")
        content_layout.addWidget(history_title)

        self.history_list = QListWidget()
        self.history_list.setAlternatingRowColors(True)
        self.history_list.addItem("Aura started. Open the overlay to capture your first prompt.")
        content_layout.addWidget(self.history_list, 1)

        shell.addWidget(sidebar)
        shell.addWidget(content, 1)
        self.setCentralWidget(outer)

    def _metric_card(self, title: str, value: str, detail: str) -> QFrame:
        card = QFrame()
        card.setObjectName("metricCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        value_label = QLabel(value)
        value_label.setObjectName("cardValue")
        detail_label = QLabel(detail)
        detail_label.setObjectName("muted")
        detail_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(detail_label)
        return card
