"""
AuraAI — Multi-HUD Overlay Launcher
Launches both WeatherOverlay and SystemMonitorOverlay side-by-side.
"""

import sys
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication
from src.gui.widgets.weather_overlay import WeatherOverlay
from src.gui.widgets.system_monitor_overlay import SystemMonitorOverlay


def main():
    app = QApplication.instance() or QApplication(sys.argv)

    # 1. Initialize System Monitor Overlay
    sys_overlay = SystemMonitorOverlay(auto_poll=True)

    # 2. Initialize Weather Overlay
    weather_overlay = WeatherOverlay()
    weather_overlay.update_data(
        location="BLR // SECTOR 12.97N",
        temp_c=26,
        condition="PARTLY_CLOUDY.STATUS",
        high=28,
        low=19,
        humidity=64,
        wind_kmh=12,
        aqi=38,
        uv=5,
    )

    # Position side-by-side on first run if needed
    screen = QApplication.primaryScreen().availableGeometry()
    if not sys_overlay._settings.contains("pos"):
        sys_overlay.move(screen.right() - sys_overlay.width() - 30, screen.top() + 40)
    if not weather_overlay._settings.contains("pos"):
        weather_overlay.move(
            sys_overlay.x() - weather_overlay.width() - 20,
            screen.top() + 40,
        )

    sys_overlay.show()
    weather_overlay.show()

    print("HUD Overlays active. Close or terminate to stop.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
