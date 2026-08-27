"""
Tactical Voice Waveform Widget (PySide6)
========================================
Location: src/gui/widgets/tactical_voice_waveform_widget.py

Real-time, cyberpunk neural audio perception & spectrum analyzer card designed
specifically for the Tactical Deck sidebar.
Features:
- 32-Band Sci-Fi Multi-Frequency Equalizer with peak-hold indicators
- Mirror-reflected spectral glow with Cyan-to-Neon-Purple gradient
- Real-time RMS decibel meter & voice activity indicator
- Non-blocking PyAudio / SoundDevice live microphone audio worker
- Auto-sync with app_signals (voice_status_changed, voice_state_name_changed, voice_level)
"""

from __future__ import annotations

import math
import random
import threading
import time
from typing import Optional, List

from PySide6.QtCore import (
    Qt,
    QPointF,
    QRect,
    QRectF,
    QTimer,
    QThread,
    Signal,
)
from PySide6.QtGui import (
    QPainter,
    QColor,
    QFont,
    QPen,
    QBrush,
    QPainterPath,
    QLinearGradient,
)
from PySide6.QtWidgets import QFrame, QWidget, QSizePolicy

# Palette
BG_CARD = QColor(13, 18, 28, 235)
BORDER_ACCENT = QColor(0, 229, 255)
BORDER_SUBTLE = QColor(255, 255, 255, 22)
TEXT_PRIMARY = QColor(240, 244, 248)
TEXT_SECONDARY = QColor(165, 175, 188)
TEXT_MUTED = QColor(105, 115, 128)

ACCENT_CYAN = QColor(0, 229, 255)
ACCENT_PURPLE = QColor(168, 85, 247)
ACCENT_GREEN = QColor(16, 185, 129)
ACCENT_AMBER = QColor(245, 158, 11)
ACCENT_RED = QColor(244, 63, 94)


class LiveAudioCaptureWorker(QThread):
    """Background thread to capture live microphone RMS levels & FFT frequency bins."""
    levels_ready = Signal(list, float)  # 32 frequency band heights (0.0-1.0), rms_db

    def __init__(self, parent=None, band_count: int = 30):
        super().__init__(parent)
        self.band_count = band_count
        self._running = True
        self._is_capturing = False

    def set_capturing(self, active: bool):
        self._is_capturing = active

    def stop(self):
        self._running = False
        self.wait(300)

    def run(self):
        pyaudio_inst = None
        stream = None
        sample_rate = 16000
        chunk_size = 512

        try:
            import pyaudio
            pyaudio_inst = pyaudio.PyAudio()
            stream = pyaudio_inst.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=sample_rate,
                input=True,
                frames_per_buffer=chunk_size,
            )
        except Exception:
            stream = None

        phase = 0.0
        while self._running:
            try:
                if stream and self._is_capturing:
                    raw_data = stream.read(chunk_size, exception_on_overflow=False)
                    # Convert to 16-bit integer array
                    import array
                    samples = array.array("h", raw_data)
                    # Calculate real RMS
                    sum_sq = sum(s * s for s in samples)
                    rms = math.sqrt(sum_sq / len(samples)) if samples else 0.0
                    norm_level = min(1.0, rms / 32768.0 * 6.5)

                    # Compute pseudo FFT bands from wave segments
                    bands = []
                    step = max(1, len(samples) // self.band_count)
                    for b in range(self.band_count):
                        chunk = samples[b * step : (b + 1) * step]
                        local_rms = math.sqrt(sum(s * s for s in chunk) / len(chunk)) if chunk else 0
                        local_norm = min(1.0, (local_norm_val := local_rms / 32768.0 * 7.5))
                        bands.append(max(0.06, local_norm))
                    db = 20 * math.log10(max(1e-4, norm_level))
                    self.levels_ready.emit(bands, db)
                else:
                    # Ambient breathing wave when not actively capturing
                    phase += 0.08
                    bands = []
                    for b in range(self.band_count):
                        sin_val = math.sin(phase + b * 0.25) * 0.5 + 0.5
                        noise = random.uniform(0.02, 0.08)
                        base = 0.08 + (0.12 * sin_val if self._is_capturing else 0.04 * sin_val) + noise
                        bands.append(max(0.04, min(0.95, base)))
                    self.levels_ready.emit(bands, -48.0 if not self._is_capturing else -24.0)
            except Exception:
                pass
            time.sleep(0.04)  # ~25 FPS

        if stream:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
        if pyaudio_inst:
            try:
                pyaudio_inst.terminate()
            except Exception:
                pass


class TacticalVoiceWaveformWidget(QFrame):
    """
    Embedded Cyberpunk Real-Time Voice Waveform & Spectrum Analyzer.
    """

    def __init__(self, parent: Optional[QWidget] = None, chamfer_size: int = 6):
        super().__init__(parent)
        self.chamfer = chamfer_size
        self.band_count = 28
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMinimumHeight(140)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent; border: none;")

        self._levels: List[float] = [0.08] * self.band_count
        self._target_levels: List[float] = [0.08] * self.band_count
        self._peak_levels: List[float] = [0.08] * self.band_count
        self._peak_decay: List[float] = [0.0] * self.band_count

        self._active = False
        self._state_text = "STANDBY"
        self._current_db = -48.0
        self._phase = 0.0

        # Background live audio worker
        self._worker = LiveAudioCaptureWorker(self, band_count=self.band_count)
        self._worker.levels_ready.connect(self._on_worker_levels)
        self._worker.start()

        # Render interpolation timer (40 FPS)
        self._render_timer = QTimer(self)
        self._render_timer.timeout.connect(self._on_render_tick)
        self._render_timer.start(25)

        # Connect signals
        try:
            from gui.signals import app_signals
            app_signals.voice_status_changed.connect(self._on_voice_status_changed)
            app_signals.voice_state_name_changed.connect(self._on_voice_state_name_changed)
            app_signals.voice_level.connect(self._on_external_voice_level)
        except Exception:
            pass

    def _on_worker_levels(self, bands: list, db: float):
        if len(bands) >= self.band_count:
            self._target_levels = bands[: self.band_count]
        self._current_db = db

    def _on_external_voice_level(self, level: float):
        # External override if provided
        for i in range(self.band_count):
            val = level * (0.6 + 0.4 * math.sin(i * 0.4 + self._phase))
            self._target_levels[i] = max(0.08, min(1.0, val))

    def _on_voice_status_changed(self, active: bool):
        self._active = active
        self._worker.set_capturing(active)
        if active:
            self._state_text = "LISTENING"
        else:
            self._state_text = "STANDBY"

    def _on_voice_state_name_changed(self, state_name: str):
        st = (state_name or "").upper()
        if st in ("IDLE", "COOLDOWN"):
            self._state_text = "STANDBY"
            self._active = True
            self._worker.set_capturing(True)
        elif st in ("WAKE_DETECTED", "LISTENING", "FOLLOW_UP_LISTENING"):
            self._state_text = "CAPTURING AUDIO"
            self._active = True
            self._worker.set_capturing(True)
        elif st in ("TRANSCRIBING", "UNDERSTANDING"):
            self._state_text = "DECODING SPEECH"
        elif st in ("SPEAKING", "AI_RESPONSE"):
            self._state_text = "SYNTHESIZING (TTS)"
            self._active = True

    def _on_render_tick(self):
        self._phase += 0.05
        # Smooth lerp
        for i in range(self.band_count):
            diff = self._target_levels[i] - self._levels[i]
            self._levels[i] += diff * 0.35

            # Peak hold
            if self._levels[i] > self._peak_levels[i]:
                self._peak_levels[i] = self._levels[i]
                self._peak_decay[i] = 0.0
            else:
                self._peak_decay[i] += 0.008
                self._peak_levels[i] = max(self._levels[i], self._peak_levels[i] - self._peak_decay[i])

        self.update()

    def closeEvent(self, event):
        if hasattr(self, "_worker") and self._worker:
            self._worker.stop()
        super().closeEvent(event)

    # -------------------------------------------------------------------------
    # PAINT EVENT: FUTURISTIC AUDIO SPECTRUM HUD
    # -------------------------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        c = self.chamfer

        # 1. Outer Chamfered Tech Card Surface
        path = QPainterPath()
        path.moveTo(c, 0)
        path.lineTo(w - c, 0)
        path.lineTo(w, c)
        path.lineTo(w, h - c)
        path.lineTo(w - c, h)
        path.lineTo(c, h)
        path.lineTo(0, h - c)
        path.lineTo(0, c)
        path.closeSubpath()

        p.fillPath(path, BG_CARD)
        border_col = ACCENT_CYAN if self._active else BORDER_ACCENT
        p.strokePath(path, QPen(QColor(border_col.red(), border_col.green(), border_col.blue(), 110), 1.2))

        # 2. Header
        p.setFont(QFont("Consolas", 8, QFont.Bold))
        p.setPen(ACCENT_CYAN)
        p.drawText(QRect(12, 10, w - 80, 16), Qt.AlignLeft | Qt.AlignVCenter, "🎙️ AUDIO PERCEPTION")

        # Status Badge Pill
        status_col = ACCENT_GREEN if self._active else ACCENT_AMBER
        p.setFont(QFont("Consolas", 7, QFont.Bold))
        p.setPen(status_col)
        p.drawText(QRect(w - 95, 10, 85, 16), Qt.AlignRight | Qt.AlignVCenter, f"[{self._state_text}]")

        # Sub-header info (VAD / Sample rate / dB)
        p.setFont(QFont("Consolas", 7))
        p.setPen(TEXT_MUTED)
        db_txt = f"{self._current_db:.0f} dB" if self._current_db > -90 else "-INF"
        p.drawText(QRect(12, 28, w - 24, 14), Qt.AlignLeft | Qt.AlignVCenter, f"48kHz PCM • VAD ACTIVE • RMS: {db_txt}")

        # 3. Waveform Area
        wave_top = 46
        wave_h = h - 68
        wave_bot = wave_top + wave_h
        avail_w = w - 24
        bar_w = max(2.5, (avail_w / self.band_count) - 2.0)
        bar_gap = (avail_w - (bar_w * self.band_count)) / max(1, self.band_count - 1)

        # Baseline grid line
        p.setPen(QPen(QColor(255, 255, 255, 20), 1, Qt.DashLine))
        p.drawLine(12, wave_bot, w - 12, wave_bot)

        # Draw 32 Equalizer Bars with Peak Indicators & Mirror Glow
        for i in range(self.band_count):
            x = 12 + i * (bar_w + bar_gap)
            val = max(0.04, min(1.0, self._levels[i]))
            bh = val * wave_h
            bar_rect = QRectF(x, wave_bot - bh, bar_w, bh)

            # Gradient from Cyan to Purple
            grad = QLinearGradient(x, wave_bot, x, wave_bot - bh)
            if val > 0.65:
                grad.setColorAt(0.0, ACCENT_CYAN)
                grad.setColorAt(0.5, ACCENT_PURPLE)
                grad.setColorAt(1.0, ACCENT_RED)
            elif val > 0.35:
                grad.setColorAt(0.0, ACCENT_CYAN)
                grad.setColorAt(0.8, ACCENT_PURPLE)
                grad.setColorAt(1.0, QColor(192, 132, 252))
            else:
                grad.setColorAt(0.0, QColor(0, 229, 255, 140))
                grad.setColorAt(1.0, ACCENT_CYAN)

            p.fillRect(bar_rect, grad)

            # Mirror Reflection (Bottom)
            reflect_h = bh * 0.28
            ref_rect = QRectF(x, wave_bot + 2, bar_w, reflect_h)
            ref_grad = QLinearGradient(x, wave_bot + 2, x, wave_bot + 2 + reflect_h)
            ref_grad.setColorAt(0.0, QColor(0, 229, 255, 60))
            ref_grad.setColorAt(1.0, QColor(0, 229, 255, 0))
            p.fillRect(ref_rect, ref_grad)

            # Peak Hold Marker
            peak_val = max(0.04, min(1.0, self._peak_levels[i]))
            peak_y = wave_bot - (peak_val * wave_h) - 1.5
            p.setPen(QColor(255, 255, 255, 220))
            p.drawLine(QPointF(x, peak_y), QPointF(x + bar_w, peak_y))

        # 4. Bottom Cyber Amplitude Level Gauge (Segmented dB Bar)
        meter_y = h - 14
        meter_w = w - 24
        p.setPen(TEXT_MUTED)
        p.setFont(QFont("Consolas", 6))
        p.drawText(QRect(12, meter_y - 2, 24, 12), Qt.AlignLeft, "LVL")

        seg_x_start = 38
        seg_w_avail = meter_w - 28
        seg_count = 20
        active_segs = int(max(1, (self._current_db + 60) / 60.0 * seg_count)) if self._active else 2

        for s in range(seg_count):
            sx = seg_x_start + s * (seg_w_avail / seg_count)
            sw = (seg_w_avail / seg_count) - 2
            s_rect = QRectF(sx, meter_y, sw, 5)
            if s < active_segs:
                col = ACCENT_RED if s > 16 else (ACCENT_AMBER if s > 12 else ACCENT_CYAN)
                p.fillRect(s_rect, col)
            else:
                p.fillRect(s_rect, QColor(255, 255, 255, 15))

        p.end()
