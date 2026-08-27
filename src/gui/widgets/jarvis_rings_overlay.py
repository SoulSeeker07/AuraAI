"""
AuraAI — Jarvis-Style Voice-Reactive Glowing Rings HUD Overlay (PySide6)
-------------------------------------------------------------------------
- Concentric multi-layered HUD rings (Outer arc segments, compass ticks, inner core).
- Audio & TTS reactive: Dynamically accelerates rotation and flares neon glow when Aura speaks.
- Ambient cybernetic breathing when idle.
- Frameless, translucent, always-on-top, draggable overlay.
- Position persistence across sessions via QSettings.
"""

import math
import sys
from PySide6.QtCore import Qt, QPoint, QSettings, QRectF, QTimer, QThread, Signal
from PySide6.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QRadialGradient,
    QPainterPath, QLinearGradient
)
from PySide6.QtWidgets import QApplication, QWidget

ORG_NAME = "AuraAI"
APP_NAME = "JarvisRingsOverlay"

# Palette: Electric Cyan, Deep Plasma Blue, Neon Gold, Dark Carbon
CYAN_BRIGHT = QColor(0, 240, 255, 240)
CYAN_DIM = QColor(0, 200, 240, 90)
BLUE_GLOW = QColor(0, 100, 255, 160)
GOLD_ACCENT = QColor(255, 200, 50, 220)
BG_TRANSLUCENT = QColor(10, 14, 20, 180)
TEXT_HUD = QColor(0, 240, 255, 220)
TEXT_MUTED = QColor(130, 150, 180, 180)


class AudioLevelWorker(QThread):
    """Monitors live audio output / TTS speech activity to drive ring reactivity."""
    level_ready = Signal(float, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        while self._running:
            peak = 0.0
            is_speaking = False
            try:
                # 1. Check direct TTS manager state
                from voice.tts_manager import TTSManager
                tts = getattr(TTSManager, "_instance", None)
                if tts and getattr(tts, "_is_speaking", False):
                    is_speaking = True
                    peak = 0.85
            except Exception:
                pass

            # 2. Check Windows WASAPI live audio peak level
            if not is_speaking:
                try:
                    from desktop.native.adapters.audio_adapter import PyCAWAudioAdapter
                    adapter = PyCAWAudioAdapter()
                    meter = adapter.get_peak_meter() if hasattr(adapter, "get_peak_meter") else None
                    if meter is not None and meter > 0.02:
                        peak = min(1.0, float(meter) * 2.5)
                        is_speaking = peak > 0.15
                except Exception:
                    pass

            self.level_ready.emit(peak, is_speaking)
            self.msleep(30)  # ~33 Hz polling


class JarvisRingsOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)

        self._settings = QSettings(ORG_NAME, APP_NAME)
        self._drag_pos = None

        # Ring Rotation Angles & Physics
        self._angle_outer = 0.0
        self._angle_mid = 0.0
        self._angle_inner = 0.0
        self._pulse_phase = 0.0

        # Audio state
        self._audio_level = 0.0
        self._target_audio_level = 0.0
        self._is_speaking = False
        self._status_text = "STANDBY"

        # Frame Animation Timer (~60 FPS)
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._advance_animation)
        self._anim_timer.start(16)

        # Audio Worker Thread
        self._audio_worker = AudioLevelWorker(self)
        self._audio_worker.level_ready.connect(self._on_audio_level)
        self._audio_worker.start()

        # Geometry Setup
        self._init_geometry()

    def _init_geometry(self):
        saved_pos = self._settings.value("pos")
        saved_size = self._settings.value("size")
        if saved_pos:
            self.move(saved_pos)
        else:
            screen = QApplication.primaryScreen()
            if screen:
                geom = screen.geometry()
                self.move(geom.width() - 360, 60)
            else:
                self.move(1400, 60)

        if saved_size:
            self.resize(saved_size)
        else:
            self.resize(320, 350)

    def _on_audio_level(self, peak: float, is_speaking: bool):
        self._target_audio_level = peak
        self._is_speaking = is_speaking
        if is_speaking:
            self._status_text = "VOICE // ACTIVE"
        else:
            self._status_text = "STANDBY // MONITORING"

    def _advance_animation(self):
        # Smooth audio level transition (decay/attack)
        self._audio_level += (self._target_audio_level - self._audio_level) * 0.25

        # Angular velocity scales with speech amplitude
        speed_mult = 1.0 + (self._audio_level * 4.0 if self._is_speaking else 0.0)
        self._angle_outer = (self._angle_outer + 0.65 * speed_mult) % 360.0
        self._angle_mid = (self._angle_mid - 0.95 * speed_mult) % 360.0
        self._angle_inner = (self._angle_inner + 1.4 * speed_mult) % 360.0
        self._pulse_phase = (self._pulse_phase + 0.06 * speed_mult) % (2.0 * math.pi)

        self.update()

    # ---- Mouse Dragging Handlers ----------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._settings.setValue("pos", self.pos())
        self._settings.setValue("size", self.size())
        event.accept()

    # ---- Rendering Pipeline (QPainter) -----------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = (h - 30) / 2.0
        max_radius = min(cx, cy) - 16

        # 1. Subtle Translucent Base Glow
        pulse_scale = math.sin(self._pulse_phase) * 0.5 + 0.5
        glow_rad = max_radius * (1.0 + self._audio_level * 0.12)
        grad = QRadialGradient(cx, cy, glow_rad)
        glow_alpha = int(40 + 70 * self._audio_level + 20 * pulse_scale)
        grad.setColorAt(0.0, QColor(0, 240, 255, glow_alpha))
        grad.setColorAt(0.6, QColor(0, 100, 255, int(glow_alpha * 0.4)))
        grad.setColorAt(1.0, QColor(10, 14, 20, 0))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(cx - glow_rad, cy - glow_rad, glow_rad * 2, glow_rad * 2))

        # 2. Outer Segmented Tech Ring
        r_outer = max_radius * 0.92
        self._draw_segmented_arc_ring(painter, cx, cy, r_outer, self._angle_outer)

        # 3. Middle Compass Radar Ring
        r_mid = max_radius * 0.72
        self._draw_compass_ring(painter, cx, cy, r_mid, self._angle_mid)

        # 4. Inner Frequency Orbit & Reticle
        r_inner = max_radius * 0.48
        self._draw_inner_reticle(painter, cx, cy, r_inner, self._angle_inner)

        # 5. Pulsing Neural Core
        self._draw_neural_core(painter, cx, cy, max_radius * 0.26, pulse_scale)

        # 6. Futuristic HUD Caption
        self._draw_hud_caption(painter, w, h)

    def _draw_segmented_arc_ring(self, p: QPainter, cx: float, cy: float, r: float, angle: float):
        p.save()
        p.translate(cx, cy)
        p.rotate(angle)

        pen = QPen(CYAN_BRIGHT, 2.5)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)

        num_segments = 4
        span = 65.0
        step = 360.0 / num_segments

        rect = QRectF(-r, -r, r * 2, r * 2)
        for i in range(num_segments):
            start_deg = i * step
            p.drawArc(rect, int(start_deg * 16), int(span * 16))

        # Orbital satellite nodes on outer perimeter
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(GOLD_ACCENT if self._is_speaking else CYAN_BRIGHT))
        for i in range(num_segments):
            rad = math.radians(i * step + span)
            nx = math.cos(rad) * r
            ny = math.sin(rad) * r
            node_r = 3.5 + self._audio_level * 2.0
            p.drawEllipse(QPoint(int(nx), int(ny)), node_r, node_r)

        p.restore()

    def _draw_compass_ring(self, p: QPainter, cx: float, cy: float, r: float, angle: float):
        p.save()
        p.translate(cx, cy)
        p.rotate(angle)

        pen_dim = QPen(CYAN_DIM, 1.0)
        p.setPen(pen_dim)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(-r, -r, r * 2, r * 2))

        # Compass tick marks
        num_ticks = 24
        for i in range(num_ticks):
            is_major = (i % 6 == 0)
            t_len = 7.0 if is_major else 3.5
            rad = math.radians(i * (360.0 / num_ticks))
            x1 = math.cos(rad) * r
            y1 = math.sin(rad) * r
            x2 = math.cos(rad) * (r - t_len)
            y2 = math.sin(rad) * (r - t_len)
            pen_tick = QPen(CYAN_BRIGHT if is_major else CYAN_DIM, 1.5 if is_major else 1.0)
            p.setPen(pen_tick)
            p.drawLine(QPoint(int(x1), int(y1)), QPoint(int(x2), int(y2)))

        p.restore()

    def _draw_inner_reticle(self, p: QPainter, cx: float, cy: float, r: float, angle: float):
        p.save()
        p.translate(cx, cy)
        p.rotate(angle)

        # Draw hexagon reticle
        pen_reticle = QPen(CYAN_BRIGHT if not self._is_speaking else GOLD_ACCENT, 1.5)
        p.setPen(pen_reticle)
        p.setBrush(Qt.NoBrush)

        points = []
        for i in range(6):
            rad = math.radians(i * 60.0)
            points.append(QPoint(int(math.cos(rad) * r), int(math.sin(rad) * r)))
        
        path = QPainterPath()
        path.moveTo(points[0])
        for pt in points[1:]:
            path.lineTo(pt)
        path.closeSubpath()
        p.drawPath(path)

        p.restore()

    def _draw_neural_core(self, p: QPainter, cx: float, cy: float, r: float, pulse: float):
        dynamic_r = r * (0.8 + 0.2 * pulse + 0.3 * self._audio_level)
        grad = QRadialGradient(cx, cy, dynamic_r)
        if self._is_speaking:
            grad.setColorAt(0.0, QColor(255, 255, 255, 255))
            grad.setColorAt(0.4, QColor(255, 215, 0, 230))
            grad.setColorAt(1.0, QColor(0, 240, 255, 0))
        else:
            grad.setColorAt(0.0, QColor(255, 255, 255, 230))
            grad.setColorAt(0.35, CYAN_BRIGHT)
            grad.setColorAt(0.8, BLUE_GLOW)
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))

        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(cx - dynamic_r, cy - dynamic_r, dynamic_r * 2, dynamic_r * 2))

    def _draw_hud_caption(self, p: QPainter, w: int, h: int):
        font_title = QFont("Consolas", 8, QFont.Bold)
        p.setFont(font_title)
        p.setPen(TEXT_HUD if self._is_speaking else TEXT_MUTED)
        caption_rect = QRectF(0, h - 32, w, 24)
        p.drawText(caption_rect, Qt.AlignCenter, f"AURA // {self._status_text}")

    def closeEvent(self, event):
        if self._audio_worker:
            self._audio_worker.stop()
            self._audio_worker.wait(200)
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    overlay = JarvisRingsOverlay()
    overlay.show()
    sys.exit(app.exec())
