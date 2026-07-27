from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QSystemTrayIcon


class AuraTrayIcon(QSystemTrayIcon):
    show_overlay_requested = Signal()
    live_screen_toggled = Signal(bool)

    def __init__(self, main_window, overlay_window, app: QApplication):
        super().__init__(main_window)
        self.main_window = main_window
        self.overlay_window = overlay_window
        self.app = app
        self.setToolTip("Aura")
        self.setIcon(self._create_icon())

        menu = self.contextMenu()
        if menu is None:
            from PySide6.QtWidgets import QMenu

            menu = QMenu()
            self.setContextMenu(menu)

        show_action = QAction("Open Aura", self)
        show_action.triggered.connect(self.show_main_window)

        overlay_action = QAction("Show Overlay", self)
        overlay_action.triggered.connect(self.show_overlay_requested.emit)

        self.live_screen_action = QAction("Live Screen", self)
        self.live_screen_action.setCheckable(True)
        self.live_screen_action.toggled.connect(self.live_screen_toggled.emit)

        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.show_main_window)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_app)

        menu.addAction(show_action)
        menu.addAction(overlay_action)
        menu.addAction(self.live_screen_action)
        menu.addAction(settings_action)
        menu.addSeparator()
        menu.addAction(quit_action)

        self.activated.connect(self._handle_activation)

    def show_main_window(self) -> None:
        self.main_window.showNormal()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def quit_app(self) -> None:
        self.app.setProperty("force_quit", True)
        self.app.quit()

    def _handle_activation(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_main_window()

    def set_live_screen_state(self, is_active: bool) -> None:
        self.live_screen_action.blockSignals(True)
        self.live_screen_action.setChecked(is_active)
        self.live_screen_action.setText("Stop Live Screen" if is_active else "Live Screen")
        self.live_screen_action.blockSignals(False)

    def _create_icon(self) -> QIcon:
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#74d7c4"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(8, 8, 48, 48)
        painter.setBrush(QColor("#0f1217"))
        painter.drawEllipse(23, 20, 18, 24)
        painter.end()

        return QIcon(pixmap)
