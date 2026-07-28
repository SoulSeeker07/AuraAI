import os
import sys

# Ensure local package path is importable when running as script
HERE = os.path.dirname(__file__)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

try:
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtCore import QObject
except Exception as exc:
    print("PySide6 is required to run the desktop app:", exc)
    raise

from src.aura.client.desktop_controller import DesktopController


def main():
    app = QGuiApplication(sys.argv)

    engine = QQmlApplicationEngine()

    # instantiate controller and expose to QML
    controller = DesktopController()
    engine.rootContext().setContextProperty("DesktopController", controller)

    qml_path = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "desktop", "Main.qml")
    qml_path = os.path.normpath(qml_path)

    engine.load(f"file:///{qml_path}")

    if not engine.rootObjects():
        print("Failed to load QML UI. Check that frontend/desktop/Main.qml exists and is valid.")
        sys.exit(-1)

    # Start websocket connection after QML is loaded
    controller.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
