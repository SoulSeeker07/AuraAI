"""
AuraAI — Futuristic HUD weather overlay widget (PySide6)
----------------------------------------------------------
- Frameless, translucent, always-on-top overlay
- Draggable (click + drag anywhere on the card body)
- Resizable (drag the bottom-right corner handle)
- Remembers last position + size across runs (QSettings -> a small
  local ini/registry entry, not a text file you have to manage)
- Designed against a 1920x1080 reference canvas; scales cleanly on
  other resolutions since everything is laid out with relative
  proportions inside the QWidget, not hardcoded pixel positions.

Usage:
    from gui.widgets.weather_overlay import WeatherOverlay
    app = QApplication(sys.argv)
    overlay = WeatherOverlay()
    overlay.update_data(
        location="BLR // SECTOR 12.97N",
        temp_c=24,
        condition="PARTLY_CLOUDY.STATUS",
        high=27, low=19, humidity=68, wind_kmh=11,
        aqi=42, uv=4,
    )
    overlay.show()
    sys.exit(app.exec())
"""

import sys
from PySide6.QtCore import Qt, QPoint, QSize, QSettings, QRect, QTimer, QDateTime, QThread, Signal
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush
from PySide6.QtWidgets import QApplication, QWidget

ORG_NAME = "AuraAI"
APP_NAME = "WeatherOverlay"

# Reference canvas the design was built against — used only to scale
# proportional layout math, not to force a fixed window size.
REF_W, REF_H = 1920, 1080

# ---- palette (flat, HUD-accent) --------------------------------------
BG = QColor(20, 22, 26, 235)          # near-opaque dark surface
BORDER_ACCENT = QColor(80, 170, 255, 220)
BORDER = QColor(255, 255, 255, 28)
TEXT_PRIMARY = QColor(235, 238, 242)
TEXT_SECONDARY = QColor(160, 170, 182)
TEXT_MUTED = QColor(110, 120, 132)
ACCENT = QColor(90, 180, 255)
BAR_DIM = QColor(90, 180, 255, 110)

MIN_W, MIN_H = 300, 340
GRIP_SIZE = 16


class WeatherWorker(QThread):
    """Background worker to fetch real-time location & meteorological data."""
    data_ready = Signal(dict)

    def run(self):
        try:
            from tools.weather_service import LiveWeatherService
            data = LiveWeatherService.get_live_weather()
            self.data_ready.emit(data)
        except Exception:
            pass


class WeatherOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool  # keeps it off the taskbar, HUD-style
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)

        self._settings = QSettings(ORG_NAME, APP_NAME)

        # drag / resize state
        self._drag_pos = None
        self._resizing = False
        self._resize_start_pos = None
        self._resize_start_size = None

        # scan-line animation state
        self._scan_y = 0.0
        self._scan_dir = 1
        self._scan_timer = QTimer(self)
        self._scan_timer.timeout.connect(self._advance_scan)
        self._scan_timer.start(16)  # ~60fps

        # clock refresh
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self.update)
        self._clock_timer.start(1000)

        # default data
        self.data = dict(
            location="LOCATING // SECTOR GPS",
            temp_c=24,
            condition="SCANNING_METEOROLOGY.STATUS",
            icon="☁",
            high=27,
            low=19,
            humidity=68,
            wind_kmh=11,
            aqi=42,
            uv=4,
        )

        self._restore_geometry()

        # Background live weather worker
        self._worker: Optional[WeatherWorker] = None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh_weather)
        self._refresh_timer.start(600000)  # Refresh every 10 minutes
        self.refresh_weather()

    def refresh_weather(self):
        """Trigger background live weather fetch."""
        if self._worker is not None and self._worker.isRunning():
            return
        self._worker = WeatherWorker()
        self._worker.data_ready.connect(self._on_weather_fetched)
        self._worker.start()

    def _on_weather_fetched(self, data: dict):
        if data:
            self.data.update(data)
            self.update()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def update_data(self, **kwargs):
        self.data.update(kwargs)
        self.update()

    # ------------------------------------------------------------------
    # Geometry persistence
    # ------------------------------------------------------------------
    def _restore_geometry(self):
        pos = self._settings.value("pos", None)
        size = self._settings.value("size", None)

        if size is not None:
            try:
                w, h = int(size.width()), int(size.height())
            except AttributeError:
                w, h = int(size[0]), int(size[1])
            self.resize(max(w, MIN_W), max(h, MIN_H))
        else:
            # first-ever launch: proportional default vs 1920x1080
            self.resize(int(REF_W * 0.20), int(REF_H * 0.34))

        if pos is not None:
            try:
                self.move(pos)
            except TypeError:
                self.move(QPoint(pos[0], pos[1]))
        else:
            # first-ever launch only — after this, position is always
            # restored, never re-centered.
            screen = QApplication.primaryScreen().availableGeometry()
            self.move(screen.right() - self.width() - 40, screen.top() + 60)

    def _save_geometry(self):
        self._settings.setValue("pos", self.pos())
        self._settings.setValue("size", self.size())



    # ------------------------------------------------------------------
    # Drag to move
    # ------------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._in_resize_grip(event.position().toPoint()):
                self._resizing = True
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_size = self.size()
            else:
                self._drag_pos = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
            event.accept()

    def mouseMoveEvent(self, event):
        if self._resizing and self._resize_start_pos is not None:
            delta = event.globalPosition().toPoint() - self._resize_start_pos
            new_w = max(MIN_W, self._resize_start_size.width() + delta.x())
            new_h = max(MIN_H, self._resize_start_size.height() + delta.y())
            self.resize(new_w, new_h)
            event.accept()
        elif self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        else:
            # hover feedback for resize cursor
            if self._in_resize_grip(event.position().toPoint()):
                self.setCursor(Qt.SizeFDiagCursor)
            else:
                self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._resizing = False
        self._resize_start_pos = None
        self._save_geometry()  # persist immediately after every drag/resize
        event.accept()

    def _in_resize_grip(self, pos: QPoint) -> bool:
        grip_rect = QRect(
            self.width() - GRIP_SIZE - 6,
            self.height() - GRIP_SIZE - 6,
            GRIP_SIZE,
            GRIP_SIZE,
        )
        return grip_rect.contains(pos)

    def closeEvent(self, event):
        self._save_geometry()
        if hasattr(self, "_scan_timer") and self._scan_timer.isActive():
            self._scan_timer.stop()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Scan-line animation
    # ------------------------------------------------------------------
    def _advance_scan(self):
        h = self.height()
        self._scan_y += self._scan_dir * 2
        if self._scan_y >= h or self._scan_y <= 0:
            self._scan_dir *= -1
        self.update()

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        pad = int(w * 0.055)
        r = QRect(0, 0, w, h)

        # card background
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(BG))
        p.drawRoundedRect(r.adjusted(1, 1, -1, -1), 8, 8)

        # accent border
        p.setPen(QPen(BORDER_ACCENT, 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(1, 1, -1, -1), 8, 8)

        # corner brackets
        bl = 14
        p.setPen(QPen(ACCENT, 2))
        # top-left
        p.drawLine(2, 2, 2 + bl, 2)
        p.drawLine(2, 2, 2, 2 + bl)
        # top-right
        p.drawLine(w - 2, 2, w - 2 - bl, 2)
        p.drawLine(w - 2, 2, w - 2, 2 + bl)
        # bottom-left
        p.drawLine(2, h - 2, 2 + bl, h - 2)
        p.drawLine(2, h - 2, 2, h - 2 - bl)
        # bottom-right
        p.drawLine(w - 2, h - 2, w - 2 - bl, h - 2)
        p.drawLine(w - 2, h - 2, w - 2, h - 2 - bl)

        # scan line (clipped to card interior)
        p.save()
        p.setClipRect(r.adjusted(2, 2, -2, -2))
        scan_color = QColor(ACCENT)
        scan_color.setAlpha(60)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(scan_color))
        p.drawRect(2, int(self._scan_y), w - 4, 2)
        p.restore()

        mono = QFont("Consolas")
        mono.setStyleHint(QFont.Monospace)

        y = pad
        # header row: location + clock
        p.setFont(self._font(mono, w, 0.028, letter_spacing=1.2))
        p.setPen(QPen(ACCENT))
        p.drawText(QRect(pad, y, w - 2 * pad - 90, 20), Qt.AlignLeft | Qt.AlignVCenter, self.data["location"])
        clock_str = QDateTime.currentDateTime().toString("HH:mm:ss")
        p.drawText(QRect(w - pad - 90, y, 90, 20), Qt.AlignRight | Qt.AlignVCenter, clock_str)

        y += int(h * 0.06)

        # divider
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.drawLine(pad, y, w - pad, y)
        y += int(h * 0.03)

        # big temp
        temp_font = self._font(mono, w, 0.11, bold=True)
        p.setFont(temp_font)
        p.setPen(QPen(TEXT_PRIMARY))
        temp_text = f'{self.data["temp_c"]}°C'
        p.drawText(QRect(pad, y, int(w * 0.55), int(h * 0.14)), Qt.AlignLeft | Qt.AlignVCenter, temp_text)

        # condition icon well (simple circle + glyph substitute)
        circ = int(h * 0.13)
        cx = w - pad - circ
        cy = y
        p.setPen(QPen(BORDER_ACCENT, 1))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(cx, cy, circ, circ)
        p.setFont(self._font(mono, w, 0.05))
        p.setPen(QPen(ACCENT))
        icon_glyph = self.data.get("icon", "☁")
        p.drawText(QRect(cx, cy, circ, circ), Qt.AlignCenter, icon_glyph)

        y += int(h * 0.15)
        p.setFont(self._font(mono, w, 0.026, letter_spacing=1.0))
        p.setPen(QPen(TEXT_SECONDARY))
        p.drawText(QRect(pad, y, w - 2 * pad, 18), Qt.AlignLeft | Qt.AlignVCenter, self.data["condition"])

        y += int(h * 0.06)
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.drawLine(pad, y, w - pad, y)
        y += int(h * 0.03)

        # stat grid: HIGH / LOW / HUMID / WIND
        stats = [
            ("HIGH", f'{self.data["high"]}°'),
            ("LOW", f'{self.data["low"]}°'),
            ("HUMID", f'{self.data["humidity"]}%'),
            ("WIND", f'{self.data["wind_kmh"]}k/h'),
        ]
        cell_w = (w - 2 * pad - 3 * 8) / 4
        cell_h = int(h * 0.11)
        for i, (label, value) in enumerate(stats):
            cx0 = int(pad + i * (cell_w + 8))
            cell_rect = QRect(cx0, y, int(cell_w), cell_h)
            p.setPen(QPen(BORDER, 1))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(cell_rect, 4, 4)
            p.setFont(self._font(mono, w, 0.020, letter_spacing=1.0))
            p.setPen(QPen(TEXT_MUTED))
            p.drawText(QRect(cell_rect.x(), cell_rect.y() + 6, cell_rect.width(), 16), Qt.AlignCenter, label)
            p.setFont(self._font(mono, w, 0.030))
            p.setPen(QPen(TEXT_PRIMARY))
            p.drawText(QRect(cell_rect.x(), cell_rect.y() + 20, cell_rect.width(), 20), Qt.AlignCenter, value)

        y += cell_h + int(h * 0.04)

        # AQI / UV signal bars
        p.setFont(self._font(mono, w, 0.022, letter_spacing=1.0))
        p.setPen(QPen(TEXT_MUTED))
        p.drawText(QRect(pad, y, w - 2 * pad, 16), Qt.AlignLeft | Qt.AlignVCenter, "AIR_QUALITY // UV_INDEX")
        y += 22

        bar_heights = [0.4, 0.55, 0.7, 0.85, 0.6, 0.45, 0.3, 0.2]
        n = len(bar_heights)
        bar_area_h = int(h * 0.06)
        bar_w = (w - 2 * pad - (n - 1) * 4) / n
        for i, bh in enumerate(bar_heights):
            bx = int(pad + i * (bar_w + 4))
            bh_px = int(bar_area_h * bh)
            by = y + (bar_area_h - bh_px)
            color = ACCENT if bh >= 0.7 else BAR_DIM
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(color))
            p.drawRoundedRect(int(bx), int(by), int(bar_w), bh_px, 2, 2)

        y += bar_area_h + 8
        p.setFont(self._font(mono, w, 0.020))
        p.setPen(QPen(TEXT_MUTED))
        p.drawText(
            QRect(pad, y, int((w - 2 * pad) / 2), 16),
            Qt.AlignLeft | Qt.AlignVCenter,
            f'AQI {self.data["aqi"]} // GOOD',
        )
        p.drawText(
            QRect(pad, y, w - 2 * pad, 16),
            Qt.AlignRight | Qt.AlignVCenter,
            f'UV {self.data["uv"]} // MODERATE',
        )

        # resize grip hint (bottom-right dots)
        p.setPen(QPen(TEXT_MUTED, 1))
        for i in range(3):
            for j in range(i, 3):
                dx = w - 6 - j * 4
                dy = h - 6 - i * 4
                p.drawPoint(dx, dy)

        p.end()

    def _font(
        self,
        base: QFont,
        ref_w: int,
        ratio: float,
        bold: bool = False,
        letter_spacing: float = 0.0,
    ) -> QFont:
        f = QFont(base)
        px = max(9, int(ref_w * ratio))
        f.setPixelSize(px)
        f.setBold(bold)
        if letter_spacing:
            f.setLetterSpacing(QFont.AbsoluteSpacing, letter_spacing)
        return f


if __name__ == "__main__":
    app = QApplication(sys.argv)
    overlay = WeatherOverlay()
    overlay.show()
    sys.exit(app.exec())
