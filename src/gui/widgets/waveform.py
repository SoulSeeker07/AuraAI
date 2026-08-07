"""
VoiceWaveform Widget
====================
Real-time audio waveform visualization for voice input status.
Used in the Overlay HUD as a perception pill.
"""


from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont

from src.gui.theme import Colors, Typography
import random
import math


class VoiceWaveform(QWidget):
    """
    Animated audio waveform bars that respond to voice_level signals.
    
    Args:
        bar_count: Number of bars in the waveform
        bar_width: Width of each bar in pixels
        bar_gap: Gap between bars in pixels
    """
    
    def __init__(self, bar_count: int = 20, bar_width: int = 3, bar_gap: int = 2, parent=None):
        super().__init__(parent)
        self._bar_count = bar_count
        self._bar_width = bar_width
        self._bar_gap = bar_gap
        self._levels = [0.1] * bar_count
        self._target_levels = [0.1] * bar_count
        self._active = False
        self._current_level = 0.0
        
        self.setFixedSize(bar_count * (bar_width + bar_gap) + 4, 32)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        
        # Animation timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(50)  # 20fps
        
        # Connect to app signals
        from src.gui.signals import app_signals
        app_signals.voice_level.connect(self._on_voice_level)
        app_signals.voice_status_changed.connect(self._on_voice_status)
    
    def _on_voice_level(self, level: float):
        self._current_level = level
        if self._active:
            # Update target levels with some randomness for organic feel
            for i in range(self._bar_count):
                base = level * (0.5 + 0.5 * math.sin(i * 0.5 + self._timer.timerId() * 0.1))
                noise = random.uniform(-0.1, 0.1)
                self._target_levels[i] = max(0.05, min(1.0, base + noise))
    
    def _on_voice_status(self, active: bool):
        self._active = active
        if not active:
            self._target_levels = [0.1] * self._bar_count
    
    def _animate(self):
        # Smooth interpolation toward targets
        changed = False
        for i in range(self._bar_count):
            diff = self._target_levels[i] - self._levels[i]
            if abs(diff) > 0.01:
                self._levels[i] += diff * 0.3
                changed = True
        if changed or self._active:
            self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        center_y = h / 2
        
        for i, level in enumerate(self._levels):
            x = 2 + i * (self._bar_width + self._bar_gap)
            bar_h = max(4, level * (h - 4))
            
            # Color gradient from cyan to purple based on level
            if level > 0.7:
                color = QColor(Colors.PURPLE_GLOW)
            elif level > 0.4:
                color = QColor(Colors.CYAN)
            else:
                color = QColor(Colors.TEXT_MUTED)
            
            color.setAlphaF(0.6 + level * 0.4)
            
            rect = QRectF(x, center_y - bar_h / 2, self._bar_width, bar_h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawRoundedRect(rect, 1.5, 1.5)
    
    def set_active(self, active: bool):
        self._active = active
        if not active:
            self._target_levels = [0.1] * self._bar_count

