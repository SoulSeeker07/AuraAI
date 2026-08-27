import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from core.config import APP_NAME, PROJECT_ROOT
from core.logger import get_logger
from core.settings import Settings

logger = get_logger("tray")


class AuraTrayIcon(QSystemTrayIcon):
    show_overlay_requested = Signal()
    live_screen_toggled = Signal(bool)

    def __init__(
        self, main_window, overlay_window, app: QApplication, settings: Settings
    ):
        super().__init__(main_window)
        self.main_window = main_window
        self.overlay_window = overlay_window
        self.app = app
        self.settings = settings
        self.setToolTip("Aura")
        self.setIcon(self._create_icon())

        menu = QMenu()
        self.setContextMenu(menu)
        menu.aboutToShow.connect(self.sync_visibility_actions)

        self.show_action = QAction("Show Desktop", self)
        self.show_action.triggered.connect(self.show_main_window)

        self.hide_action = QAction("Hide Desktop", self)
        self.hide_action.triggered.connect(self.hide_main_window)

        overlay_action = QAction("Show Overlay", self)
        overlay_action.triggered.connect(self.show_overlay_requested.emit)

        chat_action = QAction("Chat HUD", self)
        chat_action.triggered.connect(self._toggle_chat_overlay)

        notch_action = QAction("Voice Notch", self)
        notch_action.triggered.connect(self._toggle_voice_notch)

        self.live_screen_action = QAction("Live Screen", self)
        self.live_screen_action.setCheckable(True)
        self.live_screen_action.toggled.connect(self.live_screen_toggled.emit)

        self.startup_action = QAction("Start with Windows", self)
        self.startup_action.setCheckable(True)
        self.startup_action.setChecked(bool(self.settings.get("auto_start", False)))
        self.startup_action.toggled.connect(self.set_start_with_windows)

        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.show_main_window)

        restart_action = QAction("Restart Aura", self)
        restart_action.triggered.connect(self.restart_app)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_app)

        menu.addAction(self.show_action)
        menu.addAction(self.hide_action)
        menu.addAction(overlay_action)
        menu.addAction(chat_action)
        menu.addAction(notch_action)
        menu.addAction(self.live_screen_action)
        menu.addSeparator()
        menu.addAction(self.startup_action)
        menu.addAction(settings_action)
        menu.addSeparator()
        menu.addAction(restart_action)
        menu.addAction(quit_action)

        self.activated.connect(self._handle_activation)
        self.sync_visibility_actions()

    def show_main_window(self) -> None:
        self.main_window.showNormal()
        self.main_window.raise_()
        self.main_window.activateWindow()
        self.sync_visibility_actions()

    def hide_main_window(self) -> None:
        self.main_window.hide()
        self.sync_visibility_actions()

    def _toggle_chat_overlay(self) -> None:
        if hasattr(self.main_window, "toggle_chat_overlay"):
            self.main_window.toggle_chat_overlay()

    def _toggle_voice_notch(self) -> None:
        if hasattr(self.main_window, "toggle_voice_notch"):
            self.main_window.toggle_voice_notch()

    def restart_app(self) -> None:
        executable = sys.executable
        script_path = PROJECT_ROOT / "main.py"
        launched = False

        if script_path.exists():
            from PySide6.QtCore import QProcess

            launched = QProcess.startDetached(
                executable, [str(script_path)], str(PROJECT_ROOT)
            )

        if launched:
            self.quit_app()
            return

        logger.warning("Could not restart Aura")
        self.showMessage("Aura", "Restart failed. Please start Aura again manually.")

    def set_start_with_windows(self, enabled: bool) -> None:
        applied = self._set_windows_startup(enabled)
        if not applied:
            self.startup_action.blockSignals(True)
            self.startup_action.setChecked(bool(self.settings.get("auto_start", False)))
            self.startup_action.blockSignals(False)
            self.showMessage("Aura", "Could not update Windows startup setting.")
            return

        self.settings.set("auto_start", enabled)
        status = "enabled" if enabled else "disabled"
        self.showMessage("Aura", f"Start with Windows {status}.")

    def quit_app(self) -> None:
        self.app.setProperty("force_quit", True)
        self.app.quit()

    def _handle_activation(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.main_window.isVisible():
                self.hide_main_window()
            else:
                self.show_main_window()

    def set_live_screen_state(self, is_active: bool) -> None:
        self.live_screen_action.blockSignals(True)
        self.live_screen_action.setChecked(is_active)
        self.live_screen_action.setText(
            "Stop Live Screen" if is_active else "Live Screen"
        )
        self.live_screen_action.blockSignals(False)

    def sync_visibility_actions(self) -> None:
        visible = self.main_window.isVisible()
        self.show_action.setEnabled(not visible)
        self.hide_action.setEnabled(visible)

    def _set_windows_startup(self, enabled: bool) -> bool:
        if sys.platform != "win32":
            return False

        try:
            import winreg

            command = f'"{sys.executable}" "{PROJECT_ROOT / "main.py"}"'
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                if enabled:
                    winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
                else:
                    try:
                        winreg.DeleteValue(key, APP_NAME)
                    except FileNotFoundError:
                        pass
            return True
        except OSError as exc:
            logger.warning("Could not update Windows startup setting: %s", exc)
            return False

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
