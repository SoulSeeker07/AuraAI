"""
Tactical Telemetry Widget (PySide6)
===================================
Location: src/gui/widgets/tactical_telemetry_widget.py

Real-time, embedded cyberpunk HUD system performance card for the Tactical Deck sidebar.
Features pixel-perfect bounding-box alignment, chamfered Sci-Fi tech card borders,
and razor-sharp anti-aliased live hardware telemetry:
- CPU Load (GHz, Threads, %, live sparkline graph with glow under-curve)
- GPU 0 (NVIDIA GTX 1650 / integrated, VRAM, Temp, %, live sparkline graph)
- Memory RAM (GB consumed, %, 16-block cyber segmented meter)
- Disk I/O (Read/Write MB/s, %, 16-block segmented meter)
- Network Bandwidth (Upload/Download throughput, live sparkline graph)
- WLAN Link (SSID, %, stepped signal ladder gauge)
- Live clock + dynamic scanline sweep
"""

from __future__ import annotations

import sys
import time
from collections import deque
from typing import Dict, List, Any, Optional

from PySide6.QtCore import (
    Qt,
    QPointF,
    QRect,
    QRectF,
    QTimer,
    QDateTime,
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

# ---- High-Contrast Cyber HUD Color Palette ---------------------------
BG_CARD = QColor(13, 18, 28, 235)
BORDER_ACCENT = QColor(0, 229, 255)
BORDER_SUBTLE = QColor(255, 255, 255, 22)
TEXT_PRIMARY = QColor(240, 244, 248)
TEXT_SECONDARY = QColor(165, 175, 188)
TEXT_MUTED = QColor(105, 115, 128)

ACCENT_CYAN = QColor(0, 220, 255)
ACCENT_BLUE = QColor(80, 160, 255)
ACCENT_GREEN = QColor(50, 225, 140)
ACCENT_AMBER = QColor(255, 180, 50)
ACCENT_RED = QColor(255, 80, 90)
BAR_DIM = QColor(80, 160, 255, 35)

HISTORY_LEN = 30


class TacticalTelemetryWidget(QFrame):
    """
    Embedded real-time hardware telemetry widget for the Tactical Deck sidebar.
    """

    def __init__(self, parent: Optional[QWidget] = None, chamfer_size: int = 6):
        super().__init__(parent)
        self.chamfer = chamfer_size
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMinimumHeight(470)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent; border: none;")

        self.cpu_history = deque([15.0] * HISTORY_LEN, maxlen=HISTORY_LEN)
        self.gpu0_history = deque([5.0] * HISTORY_LEN, maxlen=HISTORY_LEN)
        self.net_down_history = deque([0.0] * HISTORY_LEN, maxlen=HISTORY_LEN)

        self._scan_y = 0.0
        self._scan_dir = 1.0

        self.data: Dict[str, Any] = {
            "cpu_pct": 15.0,
            "cpu_freq_ghz": 2.5,
            "cpu_count": 8,
            "mem_used_gb": 8.0,
            "mem_total_gb": 16.0,
            "mem_pct": 50.0,
            "disk_used_gb": 120.0,
            "disk_total_gb": 512.0,
            "disk_pct": 45.0,
            "disk_read_mbs": 0.0,
            "disk_write_mbs": 0.0,
            "net_down_kb": 0.0,
            "net_up_kb": 0.0,
            "gpus": [],
            "wifi": {
                "ssid": "LINK // ACTIVE",
                "signal_pct": 80,
                "band": "5 GHz",
                "state": "CONNECTED",
            },
        }

        # 30 FPS animation timer for scanline sweep
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._on_anim_tick)
        self._anim_timer.start(33)

    def _on_anim_tick(self):
        h = self.height()
        self._scan_y += self._scan_dir * 1.8
        if self._scan_y >= h or self._scan_y <= 0:
            self._scan_dir *= -1
        self.update()

    def update_telemetry(self, telemetry: Dict[str, Any]):
        """Slot called when new live telemetry data arrives."""
        if not isinstance(telemetry, dict):
            return

        self.data.update(telemetry)

        cpu_val = float(telemetry.get("cpu_pct", self.data.get("cpu_pct", 0.0)))
        self.cpu_history.append(cpu_val)

        gpus = telemetry.get("gpus", [])
        if gpus and isinstance(gpus, list):
            gpu_val = float(gpus[0].get("util_pct", 0.0))
            self.gpu0_history.append(gpu_val)
        else:
            self.gpu0_history.append(0.0)

        net_d = float(telemetry.get("net_down_kb", 0.0))
        self.net_down_history.append(net_d)

        self.update()

    def _get_load_color(self, pct: float) -> QColor:
        if pct >= 85.0:
            return ACCENT_RED
        if pct >= 65.0:
            return ACCENT_AMBER
        return ACCENT_CYAN

    def paintEvent(self, event):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setRenderHint(QPainter.TextAntialiasing, True)

            w = self.width()
            h = self.height()
            c = self.chamfer

            # 1. Main Chamfered Sci-Fi Card Path
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

            # Background Glass Fill
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(BG_CARD))
            p.drawPath(path)

            # Subtle Cyber Border
            p.setPen(QPen(BORDER_SUBTLE, 1.0))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)

            # Tactical Tech Corner Brackets (Matches SciFiTechCard exactly)
            p.setPen(QPen(BORDER_ACCENT, 1.8))
            # Top-left notch
            p.drawLine(0, c + 14, 0, c)
            p.drawLine(0, c, c, 0)
            p.drawLine(c, 0, c + 18, 0)

            # Bottom-right notch
            p.drawLine(w, h - c - 14, w, h - c)
            p.drawLine(w, h - c, w - c, h)
            p.drawLine(w - c, h, w - c - 18, h)

            # Top-right and Bottom-left subtle corners
            p.setPen(QPen(QColor(0, 229, 255, 80), 1.0))
            p.drawLine(w - c, 0, w, c)
            p.drawLine(0, h - c, c, h)

            # 2. Scanline Sweep Animation
            p.save()
            p.setClipPath(path)
            scan_col = QColor(0, 220, 255, 25)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(scan_col))
            p.drawRect(0, int(self._scan_y), w, 2)
            p.restore()

            # 3. Content Layout Coordinates
            pad_x = 10
            mod_w = w - 2 * pad_x
            y = 12

            mono = QFont("Consolas")
            mono.setStyleHint(QFont.Monospace)

            # Header: SYS // TELEMETRY CORE + Clock
            p.setFont(QFont("Consolas", 8, QFont.Bold))
            p.setPen(QPen(ACCENT_CYAN))
            p.drawText(QRect(pad_x, y, mod_w - 65, 16), Qt.AlignLeft | Qt.AlignVCenter, "SYS // TELEMETRY CORE")

            clock_str = QDateTime.currentDateTime().toString("HH:mm:ss")
            p.setFont(QFont("Consolas", 7))
            p.setPen(QPen(TEXT_SECONDARY))
            p.drawText(QRect(pad_x + mod_w - 65, y, 65, 16), Qt.AlignRight | Qt.AlignVCenter, clock_str)

            y += 20
            p.setPen(QPen(BORDER_SUBTLE, 1))
            p.drawLine(pad_x, y, pad_x + mod_w, y)
            y += 8

            # Calculate module heights
            avail_h = h - y - 10
            item_h = max(44, int(avail_h / 6))

            # Render 6 Real-time Telemetry Modules
            self._draw_cpu_module(p, mono, pad_x, y, mod_w, item_h)
            y += item_h + 3

            self._draw_gpu_module(p, mono, pad_x, y, mod_w, item_h)
            y += item_h + 3

            self._draw_memory_module(p, mono, pad_x, y, mod_w, item_h)
            y += item_h + 3

            self._draw_disk_module(p, mono, pad_x, y, mod_w, item_h)
            y += item_h + 3

            self._draw_network_module(p, mono, pad_x, y, mod_w, item_h)
            y += item_h + 3

            self._draw_wifi_module(p, mono, pad_x, y, mod_w, item_h)
        finally:
            p.end()

    # ------------------------------------------------------------------
    # Telemetry Module Renderers
    # ------------------------------------------------------------------
    def _draw_cpu_module(self, p: QPainter, font: QFont, x: int, y: int, w: int, h: int):
        cpu_pct = float(self.data.get("cpu_pct", 0.0))
        ghz = float(self.data.get("cpu_freq_ghz", 0.0))
        cores = self.data.get("cpu_count", 8)
        color = self._get_load_color(cpu_pct)

        # Label & Value Header
        p.setFont(QFont("Consolas", 7, QFont.Bold))
        p.setPen(QPen(TEXT_MUTED))
        p.drawText(QRect(x, y, 68, 14), Qt.AlignLeft | Qt.AlignVCenter, "CPU LOAD")

        sub_info = f"{ghz:.1f}GHz // {cores}T" if ghz > 0 else f"{cores}T"
        p.setFont(QFont("Consolas", 7))
        p.setPen(QPen(TEXT_SECONDARY))
        p.drawText(QRect(x + 70, y, max(10, w - 120), 14), Qt.AlignRight | Qt.AlignVCenter, sub_info)

        p.setFont(QFont("Consolas", 8, QFont.Bold))
        p.setPen(QPen(color))
        p.drawText(QRect(x + w - 48, y, 48, 14), Qt.AlignRight | Qt.AlignVCenter, f"{cpu_pct:.1f}%")

        # Sparkline
        bar_y = y + 16
        bar_h = max(10, h - 20)
        self._draw_sparkline(p, x, bar_y, w, bar_h, list(self.cpu_history), color)

    def _draw_gpu_module(self, p: QPainter, font: QFont, x: int, y: int, w: int, h: int):
        gpus = self.data.get("gpus", [])
        gpu = gpus[0] if gpus and isinstance(gpus, list) else None

        name = "GPU 0"
        util_pct = 0.0
        vram_str = "N/A"
        temp_str = "--°C"
        color = ACCENT_CYAN

        if gpu:
            raw_name = gpu.get("name", "GPU 0")
            name = f"GPU: {raw_name[:10].upper()}"
            util_pct = float(gpu.get("util_pct", 0.0))
            mem_u = float(gpu.get("mem_used_mb", 0.0)) / 1024.0
            mem_t = float(gpu.get("mem_total_mb", 4096.0)) / 1024.0
            vram_str = f"{mem_u:.1f}/{mem_t:.1f}G"
            temp_str = f"{gpu.get('temp_c', 0):.0f}°C"
            color = self._get_load_color(util_pct)

        p.setFont(QFont("Consolas", 7, QFont.Bold))
        p.setPen(QPen(TEXT_MUTED))
        p.drawText(QRect(x, y, 78, 14), Qt.AlignLeft | Qt.AlignVCenter, name)

        p.setFont(QFont("Consolas", 7))
        p.setPen(QPen(TEXT_SECONDARY))
        p.drawText(QRect(x + 80, y, max(10, w - 126), 14), Qt.AlignRight | Qt.AlignVCenter, f"{vram_str} {temp_str}")

        p.setFont(QFont("Consolas", 8, QFont.Bold))
        p.setPen(QPen(color))
        p.drawText(QRect(x + w - 44, y, 44, 14), Qt.AlignRight | Qt.AlignVCenter, f"{util_pct:.0f}%")

        bar_y = y + 16
        bar_h = max(10, h - 20)
        self._draw_sparkline(p, x, bar_y, w, bar_h, list(self.gpu0_history), color)

    def _draw_memory_module(self, p: QPainter, font: QFont, x: int, y: int, w: int, h: int):
        used = float(self.data.get("mem_used_gb", 0.0))
        total = float(self.data.get("mem_total_gb", 16.0))
        pct = float(self.data.get("mem_pct", 0.0))
        color = self._get_load_color(pct)

        p.setFont(QFont("Consolas", 7, QFont.Bold))
        p.setPen(QPen(TEXT_MUTED))
        p.drawText(QRect(x, y, 76, 14), Qt.AlignLeft | Qt.AlignVCenter, "MEMORY (RAM)")

        p.setFont(QFont("Consolas", 7))
        p.setPen(QPen(TEXT_SECONDARY))
        p.drawText(QRect(x + 78, y, max(10, w - 124), 14), Qt.AlignRight | Qt.AlignVCenter, f"{used:.1f}/{total:.1f}G")

        p.setFont(QFont("Consolas", 8, QFont.Bold))
        p.setPen(QPen(color))
        p.drawText(QRect(x + w - 44, y, 44, 14), Qt.AlignRight | Qt.AlignVCenter, f"{pct:.0f}%")

        bar_y = y + 16
        bar_h = max(10, h - 20)
        self._draw_segmented_bar(p, x, bar_y, w, bar_h, pct, color)

    def _draw_disk_module(self, p: QPainter, font: QFont, x: int, y: int, w: int, h: int):
        pct = float(self.data.get("disk_pct", 0.0))
        rmb = float(self.data.get("disk_read_mbs", 0.0))
        wmb = float(self.data.get("disk_write_mbs", 0.0))

        p.setFont(QFont("Consolas", 7, QFont.Bold))
        p.setPen(QPen(TEXT_MUTED))
        p.drawText(QRect(x, y, 60, 14), Qt.AlignLeft | Qt.AlignVCenter, "DISK I/O")

        p.setFont(QFont("Consolas", 7))
        p.setPen(QPen(TEXT_SECONDARY))
        p.drawText(QRect(x + 62, y, max(10, w - 108), 14), Qt.AlignRight | Qt.AlignVCenter, f"R:{rmb:.1f} W:{wmb:.1f}M")

        p.setFont(QFont("Consolas", 8, QFont.Bold))
        p.setPen(QPen(ACCENT_BLUE))
        p.drawText(QRect(x + w - 44, y, 44, 14), Qt.AlignRight | Qt.AlignVCenter, f"{pct:.0f}%")

        bar_y = y + 16
        bar_h = max(10, h - 20)
        self._draw_segmented_bar(p, x, bar_y, w, bar_h, pct, ACCENT_BLUE)

    def _draw_network_module(self, p: QPainter, font: QFont, x: int, y: int, w: int, h: int):
        down_kb = float(self.data.get("net_down_kb", 0.0))
        up_kb = float(self.data.get("net_up_kb", 0.0))

        down_str = f"↓{down_kb/1024:.1f}M" if down_kb > 1024 else f"↓{down_kb:.0f}K"
        up_str = f"↑{up_kb/1024:.1f}M" if up_kb > 1024 else f"↑{up_kb:.0f}K"

        p.setFont(QFont("Consolas", 7, QFont.Bold))
        p.setPen(QPen(TEXT_MUTED))
        p.drawText(QRect(x, y, 60, 14), Qt.AlignLeft | Qt.AlignVCenter, "NETWORK")

        p.setFont(QFont("Consolas", 7))
        p.setPen(QPen(TEXT_SECONDARY))
        p.drawText(QRect(x + 62, y, max(10, w - 120), 14), Qt.AlignRight | Qt.AlignVCenter, up_str)

        p.setFont(QFont("Consolas", 8, QFont.Bold))
        p.setPen(QPen(ACCENT_GREEN))
        p.drawText(QRect(x + w - 56, y, 56, 14), Qt.AlignRight | Qt.AlignVCenter, down_str)

        bar_y = y + 16
        bar_h = max(10, h - 20)
        history = list(self.net_down_history)
        max_val = max(100.0, max(history) if history else 100.0)
        norm_history = [(v / max_val) * 100.0 for v in history]
        self._draw_sparkline(p, x, bar_y, w, bar_h, norm_history, ACCENT_GREEN)

    def _draw_wifi_module(self, p: QPainter, font: QFont, x: int, y: int, w: int, h: int):
        wifi = self.data.get("wifi", {})
        ssid = wifi.get("ssid", "WIFI // ETH")[:12]
        sig_pct = int(wifi.get("signal_pct", 80))

        p.setFont(QFont("Consolas", 7, QFont.Bold))
        p.setPen(QPen(TEXT_MUTED))
        p.drawText(QRect(x, y, 68, 14), Qt.AlignLeft | Qt.AlignVCenter, "WLAN LINK")

        p.setFont(QFont("Consolas", 7))
        p.setPen(QPen(TEXT_SECONDARY))
        p.drawText(QRect(x + 70, y, max(10, w - 116), 14), Qt.AlignRight | Qt.AlignVCenter, ssid)

        p.setFont(QFont("Consolas", 8, QFont.Bold))
        p.setPen(QPen(ACCENT_CYAN))
        p.drawText(QRect(x + w - 44, y, 44, 14), Qt.AlignRight | Qt.AlignVCenter, f"{sig_pct}%")

        bar_y = y + 16
        bar_h = max(10, h - 20)
        self._draw_signal_bars(p, x, bar_y, w, bar_h, sig_pct)

    # ------------------------------------------------------------------
    # Vector Primitives
    # ------------------------------------------------------------------
    def _draw_sparkline(self, p: QPainter, x: int, y: int, w: int, h: int, data: list, color: QColor):
        p.setPen(QPen(BORDER_SUBTLE, 1))
        p.setBrush(QBrush(QColor(255, 255, 255, 5)))
        p.drawRoundedRect(x, y, w, h, 2, 2)

        if not data:
            return

        p.save()
        p.setClipRect(QRect(x + 1, y + 1, w - 2, h - 2))

        step_x = (w - 4) / max(1, len(data) - 1)
        path = QPainterPath()
        fill_path = QPainterPath()

        pts = []
        for i, val in enumerate(data):
            clamped = max(0.0, min(100.0, float(val)))
            px = x + 2 + i * step_x
            py = y + h - 2 - (clamped / 100.0) * (h - 4)
            pts.append(QPointF(px, py))

        path.moveTo(pts[0])
        fill_path.moveTo(pts[0].x(), y + h - 2)
        fill_path.lineTo(pts[0])

        for pt in pts[1:]:
            path.lineTo(pt)
            fill_path.lineTo(pt)

        fill_path.lineTo(pts[-1].x(), y + h - 2)
        fill_path.closeSubpath()

        grad = QLinearGradient(0, y, 0, y + h)
        c_top = QColor(color)
        c_top.setAlpha(55)
        c_bot = QColor(color)
        c_bot.setAlpha(4)
        grad.setColorAt(0.0, c_top)
        grad.setColorAt(1.0, c_bot)

        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawPath(fill_path)

        p.setPen(QPen(color, 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)

        p.restore()

    def _draw_segmented_bar(self, p: QPainter, x: int, y: int, w: int, h: int, pct: float, color: QColor):
        num_blocks = 16
        gap = 2
        block_w = (w - (num_blocks - 1) * gap) / num_blocks
        active_count = int(round((pct / 100.0) * num_blocks))

        for i in range(num_blocks):
            bx = x + i * (block_w + gap)
            is_active = i < active_count

            if is_active:
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(color))
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(BAR_DIM))

            p.drawRoundedRect(QRectF(bx, y, block_w, h), 1, 1)

    def _draw_signal_bars(self, p: QPainter, x: int, y: int, w: int, h: int, sig_pct: int):
        num_bars = 16
        gap = 2
        bar_w = (w - (num_bars - 1) * gap) / num_bars
        active_count = int(round((sig_pct / 100.0) * num_bars))

        for i in range(num_bars):
            bx = x + i * (bar_w + gap)
            ratio = (i + 1) / num_bars
            bar_h = max(3.0, (h - 2) * (0.25 + 0.75 * ratio))
            by = y + h - 1 - bar_h

            is_active = i < active_count
            if is_active:
                bar_color = ACCENT_GREEN if ratio >= 0.85 else ACCENT_CYAN
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(bar_color))
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(BAR_DIM))

            p.drawRoundedRect(QRectF(bx, by, bar_w, bar_h), 1, 1)
