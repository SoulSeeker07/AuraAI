from __future__ import annotations

from PySide6.QtGui import QGuiApplication

from .app import AuraOverlayApp


def main() -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    overlay_app = AuraOverlayApp()
    overlay_app.run()


if __name__ == "__main__":
    main()
