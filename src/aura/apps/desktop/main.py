from __future__ import annotations

from PySide6.QtGui import QGuiApplication

from .app import AuraDesktopApp


def main() -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    desktop_app = AuraDesktopApp()
    desktop_app.run()


if __name__ == "__main__":
    main()
