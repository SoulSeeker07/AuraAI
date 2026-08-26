"""
AuraAI — Futuristic HUD System Performance Overlay Widget (PySide6)
---------------------------------------------------------------------
- Frameless, translucent, always-on-top HUD performance overlay
- Draggable (click + drag anywhere on the card body)
- Resizable (drag the bottom-right corner handle)
- Remembers last position + size across runs (QSettings -> registry/ini)
- Live real-time telemetry sampler (CPU, GPU0, GPU1, RAM, Disk, Net, Wi-Fi)
- Dynamic HUD sparkline graphs, signal bars, and scan-line sweep
- Filterable: render all metrics at once or customize active components

Usage:
    from src.gui.widgets.system_monitor_overlay import SystemMonitorOverlay
    app = QApplication(sys.argv)
    overlay = SystemMonitorOverlay()
    # overlay.set_visible_metrics(["cpu", "gpu0", "memory", "network", "wifi"])
    overlay.show()
    sys.exit(app.exec())
"""

import sys
import time
import subprocess
import shutil
from collections import deque
from typing import Dict, List, Any, Optional

import psutil

from PySide6.QtCore import (
    Qt,
    QPoint,
    QPointF,
    QSize,
    QSettings,
    QRect,
    QRectF,
    QTimer,
    QDateTime,
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
from PySide6.QtWidgets import QApplication, QWidget

ORG_NAME = "AuraAI"
APP_NAME = "SystemPerformanceOverlay"

REF_W, REF_H = 1920, 1080

# ---- Color Palette (Cyber HUD) ---------------------------------------
BG = QColor(16, 18, 22, 238)
BORDER_ACCENT = QColor(80, 170, 255, 220)
BORDER_SUBTLE = QColor(255, 255, 255, 24)
TEXT_PRIMARY = QColor(240, 243, 248)
TEXT_SECONDARY = QColor(165, 175, 188)
TEXT_MUTED = QColor(105, 115, 128)

ACCENT_CYAN = QColor(0, 220, 255)
ACCENT_BLUE = QColor(80, 160, 255)
ACCENT_GREEN = QColor(50, 225, 140)
ACCENT_AMBER = QColor(255, 180, 50)
ACCENT_RED = QColor(255, 80, 90)
BAR_DIM = QColor(80, 160, 255, 70)

MIN_W, MIN_H = 340, 480
GRIP_SIZE = 16
HISTORY_LEN = 30


class TelemetryWorker(QThread):
    """Background sampler thread to prevent any UI micro-stutters during I/O & GPU queries."""

    data_ready = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True
        self._last_net_io = psutil.net_io_counters()
        self._last_disk_io = psutil.disk_io_counters()
        self._last_time = time.time()
        self._has_nvidia_smi = shutil.which("nvidia-smi") is not None

    def run(self):
        while self._running:
            try:
                metrics = self._sample_all()
                self.data_ready.emit(metrics)
            except Exception:
                pass
            time.sleep(1.0)

    def stop(self):
        self._running = False
        self.wait(1500)

    def _sample_all(self) -> Dict[str, Any]:
        now = time.time()
        dt = max(0.1, now - self._last_time)
        self._last_time = now

        # CPU
        cpu_pct = psutil.cpu_percent(interval=None)
        cpu_freq = psutil.cpu_freq()
        cpu_freq_ghz = (cpu_freq.current / 1000.0) if cpu_freq else 0.0
        cpu_count = psutil.cpu_count(logical=True) or 1

        # Memory
        mem = psutil.virtual_memory()
        mem_used_gb = mem.used / (1024 ** 3)
        mem_total_gb = mem.total / (1024 ** 3)
        mem_pct = mem.percent

        # Disk
        try:
            disk = psutil.disk_usage("C:\\" if sys.platform == "win32" else "/")
            disk_used_gb = disk.used / (1024 ** 3)
            disk_total_gb = disk.total / (1024 ** 3)
            disk_pct = disk.percent
        except Exception:
            disk_used_gb, disk_total_gb, disk_pct = 0, 0, 0

        # Disk I/O speed
        current_disk_io = psutil.disk_io_counters()
        disk_read_mbs = 0.0
        disk_write_mbs = 0.0
        if current_disk_io and self._last_disk_io:
            read_bytes = current_disk_io.read_bytes - self._last_disk_io.read_bytes
            write_bytes = current_disk_io.write_bytes - self._last_disk_io.write_bytes
            disk_read_mbs = max(0.0, (read_bytes / (1024 * 1024)) / dt)
            disk_write_mbs = max(0.0, (write_bytes / (1024 * 1024)) / dt)
        self._last_disk_io = current_disk_io

        # Network Throughput
        current_net_io = psutil.net_io_counters()
        net_down_kb = 0.0
        net_up_kb = 0.0
        if current_net_io and self._last_net_io:
            recv_bytes = current_net_io.bytes_recv - self._last_net_io.bytes_recv
            sent_bytes = current_net_io.bytes_sent - self._last_net_io.bytes_sent
            net_down_kb = max(0.0, (recv_bytes / 1024.0) / dt)
            net_up_kb = max(0.0, (sent_bytes / 1024.0) / dt)
        self._last_net_io = current_net_io

        # GPUs (GPU0 and GPU1)
        gpus = self._sample_gpus()

        # Wi-Fi / Connection Info
        wifi_info = self._sample_wifi()

        return {
            "cpu_pct": cpu_pct,
            "cpu_freq_ghz": cpu_freq_ghz,
            "cpu_count": cpu_count,
            "mem_used_gb": mem_used_gb,
            "mem_total_gb": mem_total_gb,
            "mem_pct": mem_pct,
            "disk_used_gb": disk_used_gb,
            "disk_total_gb": disk_total_gb,
            "disk_pct": disk_pct,
            "disk_read_mbs": disk_read_mbs,
            "disk_write_mbs": disk_write_mbs,
            "net_down_kb": net_down_kb,
            "net_up_kb": net_up_kb,
            "gpus": gpus,
            "wifi": wifi_info,
        }

    def _sample_gpus(self) -> List[Dict[str, Any]]:
        gpus = []
        if self._has_nvidia_smi:
            try:
                res = subprocess.run(
                    [
                        "nvidia-smi",
                        "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                        "--format=csv,noheader,nounits",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=1.5,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if res.returncode == 0 and res.stdout.strip():
                    lines = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
                    for line in lines:
                        parts = [p.strip() for p in line.split(",")]
                        if len(parts) >= 6:
                            idx = parts[0]
                            name = parts[1]
                            util = float(parts[2])
                            mem_used = float(parts[3])
                            mem_total = float(parts[4])
                            temp = float(parts[5])
                            gpus.append({
                                "index": idx,
                                "name": name,
                                "util_pct": util,
                                "mem_used_mb": mem_used,
                                "mem_total_mb": mem_total,
                                "temp_c": temp,
                            })
            except Exception:
                pass

        # If no dedicated GPU detected or only 1 detected, populate placeholder or fallback
        if not gpus:
            gpus.append({
                "index": "0",
                "name": "INTEGRATED GPU",
                "util_pct": 0.0,
                "mem_used_mb": 0.0,
                "mem_total_mb": 1024.0,
                "temp_c": 38.0,
            })
        return gpus

    def _sample_wifi(self) -> Dict[str, Any]:
        info = {
            "ssid": "LINK // ACTIVE",
            "signal_pct": 80,
            "band": "5 GHz",
            "state": "CONNECTED",
            "ip": "127.0.0.1",
        }
        if sys.platform == "win32":
            try:
                res = subprocess.run(
                    ["netsh", "wlan", "show", "interfaces"],
                    capture_output=True,
                    text=True,
                    timeout=1.5,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if res.returncode == 0:
                    text = res.stdout
                    for line in text.splitlines():
                        line_str = line.strip()
                        if line_str.startswith("SSID") and ":" in line_str and not line_str.startswith("BSSID"):
                            info["ssid"] = line_str.split(":", 1)[1].strip()
                        elif line_str.startswith("Signal") and ":" in line_str:
                            sig_val = line_str.split(":", 1)[1].replace("%", "").strip()
                            info["signal_pct"] = int(sig_val)
                        elif line_str.startswith("Band") and ":" in line_str:
                            info["band"] = line_str.split(":", 1)[1].strip()
                        elif line_str.startswith("State") and ":" in line_str:
                            info["state"] = line_str.split(":", 1)[1].strip().upper()
            except Exception:
                pass
        return info


class SystemMonitorOverlay(QWidget):
    """
    Live Cyber-HUD System Performance Overlay
    Visualizes CPU, GPU 0, GPU 1, RAM, Disk, Net, Wi-Fi with live sparklines and scan sweep.
    """

    def __init__(
        self,
        parent=None,
        active_metrics: Optional[List[str]] = None,
        auto_poll: bool = True,
    ):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)

        self._settings = QSettings(ORG_NAME, APP_NAME)

        # Active metric sections: 'cpu', 'gpu0', 'gpu1', 'memory', 'disk', 'network', 'wifi'
        self._all_metrics = ["cpu", "gpu0", "gpu1", "memory", "disk", "network", "wifi"]
        self.active_metrics = active_metrics or list(self._all_metrics)

        # Drag & resize state
        self._drag_pos = None
        self._resizing = False
        self._resize_start_pos = None
        self._resize_start_size = None

        # Scan-line sweep
        self._scan_y = 0.0
        self._scan_dir = 1
        self._scan_timer = QTimer(self)
        self._scan_timer.timeout.connect(self._advance_scan)
        self._scan_timer.start(16)  # 60 FPS

        # Fast UI redraw for clocks/animations
        self._ui_timer = QTimer(self)
        self._ui_timer.timeout.connect(self.update)
        self._ui_timer.start(1000)

        # Historical rolling buffers for mini graphs
        self.cpu_history = deque([0.0] * HISTORY_LEN, maxlen=HISTORY_LEN)
        self.gpu0_history = deque([0.0] * HISTORY_LEN, maxlen=HISTORY_LEN)
        self.gpu1_history = deque([0.0] * HISTORY_LEN, maxlen=HISTORY_LEN)
        self.net_down_history = deque([0.0] * HISTORY_LEN, maxlen=HISTORY_LEN)

        # Current telemetry state
        self.data: Dict[str, Any] = {
            "cpu_pct": 14.0,
            "cpu_freq_ghz": 3.2,
            "cpu_count": 8,
            "mem_used_gb": 8.4,
            "mem_total_gb": 16.0,
            "mem_pct": 52.5,
            "disk_used_gb": 180.0,
            "disk_total_gb": 512.0,
            "disk_pct": 35.1,
            "disk_read_mbs": 0.2,
            "disk_write_mbs": 0.6,
            "net_down_kb": 250.0,
            "net_up_kb": 45.0,
            "gpus": [
                {
                    "index": "0",
                    "name": "NVIDIA GPU 0",
                    "util_pct": 8.0,
                    "mem_used_mb": 720.0,
                    "mem_total_mb": 4096.0,
                    "temp_c": 44.0,
                },
                {
                    "index": "1",
                    "name": "INTEGRATED GPU 1",
                    "util_pct": 2.0,
                    "mem_used_mb": 256.0,
                    "mem_total_mb": 2048.0,
                    "temp_c": 40.0,
                },
            ],
            "wifi": {
                "ssid": "JIO_FIBER_5G // SYS_NET",
                "signal_pct": 85,
                "band": "5 GHz",
                "state": "CONNECTED",
            },
        }

        self._restore_geometry()

        # Background worker thread
        self._worker = TelemetryWorker(self)
        self._worker.data_ready.connect(self._on_telemetry_update)
        if auto_poll:
            self._worker.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_visible_metrics(self, metrics: List[str]):
        """Filter which metrics to render: ['cpu', 'gpu0', 'gpu1', 'memory', 'disk', 'network', 'wifi']."""
        self.active_metrics = [m.lower() for m in metrics if m.lower() in self._all_metrics]
        self.update()

    def update_data(self, **kwargs):
        """Manually inject custom telemetry metrics."""
        self.data.update(kwargs)
        if "cpu_pct" in kwargs:
            self.cpu_history.append(float(kwargs["cpu_pct"]))
        if "net_down_kb" in kwargs:
            self.net_down_history.append(float(kwargs["net_down_kb"]))
        self.update()

    def _on_telemetry_update(self, new_data: dict):
        self.data.update(new_data)
        self.cpu_history.append(float(new_data.get("cpu_pct", 0.0)))
        self.net_down_history.append(float(new_data.get("net_down_kb", 0.0)))

        gpus = new_data.get("gpus", [])
        if len(gpus) > 0:
            self.gpu0_history.append(float(gpus[0].get("util_pct", 0.0)))
        if len(gpus) > 1:
            self.gpu1_history.append(float(gpus[1].get("util_pct", 0.0)))
        self.update()

    # ------------------------------------------------------------------
    # Geometry & Drag/Resize Management
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
            # Default HUD proportions
            self.resize(int(REF_W * 0.20), int(REF_H * 0.54))

        if pos is not None:
            try:
                self.move(pos)
            except TypeError:
                self.move(QPoint(pos[0], pos[1]))
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            self.move(screen.right() - self.width() - 30, screen.top() + 40)

    def _save_geometry(self):
        self._settings.setValue("pos", self.pos())
        self._settings.setValue("size", self.size())

    def closeEvent(self, event):
        self._save_geometry()
        if self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(1000)
        super().closeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._in_resize_grip(event.position().toPoint()):
                self._resizing = True
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_size = self.size()
            else:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
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
            if self._in_resize_grip(event.position().toPoint()):
                self.setCursor(Qt.SizeFDiagCursor)
            else:
                self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._resizing = False
        self._resize_start_pos = None
        self._save_geometry()
        event.accept()

    def _in_resize_grip(self, pos: QPoint) -> bool:
        grip_rect = QRect(
            self.width() - GRIP_SIZE - 6,
            self.height() - GRIP_SIZE - 6,
            GRIP_SIZE,
            GRIP_SIZE,
        )
        return grip_rect.contains(pos)

    def _advance_scan(self):
        h = self.height()
        self._scan_y += self._scan_dir * 2.2
        if self._scan_y >= h or self._scan_y <= 0:
            self._scan_dir *= -1
        self.update()

    # ------------------------------------------------------------------
    # Rendering Pipeline
    # ------------------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        w, h = self.width(), self.height()
        pad = int(w * 0.05)
        r = QRect(0, 0, w, h)

        # 1. Main translucent HUD surface
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(BG))
        p.drawRoundedRect(r.adjusted(1, 1, -1, -1), 8, 8)

        # 2. Glowing Accent Border
        p.setPen(QPen(BORDER_ACCENT, 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(1, 1, -1, -1), 8, 8)

        # 3. Corner Brackets
        bl = 14
        p.setPen(QPen(ACCENT_CYAN, 2))
        p.drawLine(2, 2, 2 + bl, 2)
        p.drawLine(2, 2, 2, 2 + bl)
        p.drawLine(w - 2, 2, w - 2 - bl, 2)
        p.drawLine(w - 2, 2, w - 2, 2 + bl)
        p.drawLine(2, h - 2, 2 + bl, h - 2)
        p.drawLine(2, h - 2, 2, h - 2 - bl)
        p.drawLine(w - 2, h - 2, w - 2 - bl, h - 2)
        p.drawLine(w - 2, h - 2, w - 2, h - 2 - bl)

        # 4. Scan line sweep
        p.save()
        p.setClipRect(r.adjusted(2, 2, -2, -2))
        scan_col = QColor(ACCENT_CYAN)
        scan_col.setAlpha(45)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(scan_col))
        p.drawRect(2, int(self._scan_y), w - 4, 2)
        p.restore()

        mono = QFont("Consolas")
        mono.setStyleHint(QFont.Monospace)

        # 5. Header: System Title & Live Clock
        y = pad
        p.setFont(self._font(mono, w, 0.027, bold=True, letter_spacing=1.2))
        p.setPen(QPen(ACCENT_CYAN))
        p.drawText(
            QRect(pad, y, w - 2 * pad - 90, 18),
            Qt.AlignLeft | Qt.AlignVCenter,
            "SYS // TELEMETRY CORE",
        )
        clock_str = QDateTime.currentDateTime().toString("HH:mm:ss")
        p.setFont(self._font(mono, w, 0.026))
        p.setPen(QPen(TEXT_SECONDARY))
        p.drawText(
            QRect(w - pad - 90, y, 90, 18),
            Qt.AlignRight | Qt.AlignVCenter,
            clock_str,
        )

        y += int(h * 0.045)
        p.setPen(QPen(BORDER_SUBTLE, 1))
        p.drawLine(pad, y, w - pad, y)
        y += int(h * 0.022)

        # Compute dynamic module heights based on active items
        active_count = len(self.active_metrics)
        avail_h = h - y - pad - 20
        item_h = max(42, int(avail_h / max(1, active_count)))

        # 6. Render active telemetry modules
        for metric in self.active_metrics:
            if metric == "cpu":
                self._draw_cpu_module(p, mono, pad, y, w - 2 * pad, item_h)
            elif metric == "gpu0":
                self._draw_gpu_module(p, mono, pad, y, w - 2 * pad, item_h, gpu_idx=0)
            elif metric == "gpu1":
                self._draw_gpu_module(p, mono, pad, y, w - 2 * pad, item_h, gpu_idx=1)
            elif metric == "memory":
                self._draw_memory_module(p, mono, pad, y, w - 2 * pad, item_h)
            elif metric == "disk":
                self._draw_disk_module(p, mono, pad, y, w - 2 * pad, item_h)
            elif metric == "network":
                self._draw_network_module(p, mono, pad, y, w - 2 * pad, item_h)
            elif metric == "wifi":
                self._draw_wifi_module(p, mono, pad, y, w - 2 * pad, item_h)
            y += item_h + 6

        # 7. Resize Grip Dots (Bottom-Right)
        p.setPen(QPen(TEXT_MUTED, 1))
        for i in range(3):
            for j in range(i, 3):
                dx = w - 6 - j * 4
                dy = h - 6 - i * 4
                p.drawPoint(dx, dy)

        p.end()

    # ------------------------------------------------------------------
    # Sub-Module Renderers
    # ------------------------------------------------------------------
    def _draw_cpu_module(self, p: QPainter, font: QFont, x: int, y: int, w: int, h: int):
        cpu_pct = self.data.get("cpu_pct", 0.0)
        ghz = self.data.get("cpu_freq_ghz", 0.0)
        cores = self.data.get("cpu_count", 8)
        color = self._get_load_color(cpu_pct)

        # Label & Value Header
        p.setFont(self._font(font, w, 0.026, letter_spacing=0.8))
        p.setPen(QPen(TEXT_MUTED))
        p.drawText(QRect(x, y, int(w * 0.45), 16), Qt.AlignLeft | Qt.AlignVCenter, "CPU LOAD")

        sub_info = f"{ghz:.1f}GHz // {cores}T" if ghz > 0 else f"{cores} THREADS"
        p.drawText(QRect(x + int(w * 0.40), y, int(w * 0.35), 16), Qt.AlignRight | Qt.AlignVCenter, sub_info)

        p.setFont(self._font(font, w, 0.030, bold=True))
        p.setPen(QPen(color))
        p.drawText(QRect(x + w - 75, y, 75, 16), Qt.AlignRight | Qt.AlignVCenter, f"{cpu_pct:.1f}%")

        # Sparkline / Bar Area
        bar_y = y + 20
        bar_h = max(8, h - 26)
        self._draw_sparkline(p, x, bar_y, w, bar_h, list(self.cpu_history), color)

    def _draw_gpu_module(self, p: QPainter, font: QFont, x: int, y: int, w: int, h: int, gpu_idx: int):
        gpus = self.data.get("gpus", [])
        gpu = gpus[gpu_idx] if len(gpus) > gpu_idx else None

        name = f"GPU {gpu_idx}"
        util_pct = 0.0
        vram_str = "N/A"
        temp_str = "--°C"
        color = ACCENT_BLUE

        if gpu:
            raw_name = gpu.get("name", f"GPU {gpu_idx}")
            name = f"GPU {gpu_idx}: {raw_name[:16].upper()}"
            util_pct = gpu.get("util_pct", 0.0)
            mem_u = gpu.get("mem_used_mb", 0.0) / 1024.0
            mem_t = gpu.get("mem_total_mb", 1024.0) / 1024.0
            vram_str = f"{mem_u:.1f}/{mem_t:.1f}G"
            temp_str = f"{gpu.get('temp_c', 0):.0f}°C"
            color = self._get_load_color(util_pct)

        # Header
        p.setFont(self._font(font, w, 0.025, letter_spacing=0.8))
        p.setPen(QPen(TEXT_MUTED))
        p.drawText(QRect(x, y, int(w * 0.50), 16), Qt.AlignLeft | Qt.AlignVCenter, name)

        p.setFont(self._font(font, w, 0.024))
        p.setPen(QPen(TEXT_SECONDARY))
        p.drawText(QRect(x + int(w * 0.46), y, int(w * 0.32), 16), Qt.AlignRight | Qt.AlignVCenter, f"{vram_str} {temp_str}")

        p.setFont(self._font(font, w, 0.028, bold=True))
        p.setPen(QPen(color))
        p.drawText(QRect(x + w - 65, y, 65, 16), Qt.AlignRight | Qt.AlignVCenter, f"{util_pct:.0f}%")

        # Bar Area
        bar_y = y + 20
        bar_h = max(8, h - 26)
        history = list(self.gpu0_history if gpu_idx == 0 else self.gpu1_history)
        self._draw_sparkline(p, x, bar_y, w, bar_h, history, color)

    def _draw_memory_module(self, p: QPainter, font: QFont, x: int, y: int, w: int, h: int):
        used = self.data.get("mem_used_gb", 0.0)
        total = self.data.get("mem_total_gb", 16.0)
        pct = self.data.get("mem_pct", 0.0)
        color = self._get_load_color(pct)

        p.setFont(self._font(font, w, 0.026, letter_spacing=0.8))
        p.setPen(QPen(TEXT_MUTED))
        p.drawText(QRect(x, y, int(w * 0.40), 16), Qt.AlignLeft | Qt.AlignVCenter, "MEMORY (RAM)")

        p.setFont(self._font(font, w, 0.025))
        p.setPen(QPen(TEXT_SECONDARY))
        p.drawText(QRect(x + int(w * 0.38), y, int(w * 0.38), 16), Qt.AlignRight | Qt.AlignVCenter, f"{used:.1f} / {total:.1f} GB")

        p.setFont(self._font(font, w, 0.028, bold=True))
        p.setPen(QPen(color))
        p.drawText(QRect(x + w - 65, y, 65, 16), Qt.AlignRight | Qt.AlignVCenter, f"{pct:.0f}%")

        bar_y = y + 20
        bar_h = max(8, h - 26)
        self._draw_segmented_bar(p, x, bar_y, w, bar_h, pct, color)

    def _draw_disk_module(self, p: QPainter, font: QFont, x: int, y: int, w: int, h: int):
        used = self.data.get("disk_used_gb", 0.0)
        total = self.data.get("disk_total_gb", 512.0)
        pct = self.data.get("disk_pct", 0.0)
        rmb = self.data.get("disk_read_mbs", 0.0)
        wmb = self.data.get("disk_write_mbs", 0.0)

        p.setFont(self._font(font, w, 0.026, letter_spacing=0.8))
        p.setPen(QPen(TEXT_MUTED))
        p.drawText(QRect(x, y, int(w * 0.30), 16), Qt.AlignLeft | Qt.AlignVCenter, "DISK I/O")

        p.setFont(self._font(font, w, 0.023))
        p.setPen(QPen(TEXT_SECONDARY))
        p.drawText(QRect(x + int(w * 0.28), y, int(w * 0.48), 16), Qt.AlignRight | Qt.AlignVCenter, f"R:{rmb:.1f} W:{wmb:.1f}MB/s")

        p.setFont(self._font(font, w, 0.028, bold=True))
        p.setPen(QPen(ACCENT_BLUE))
        p.drawText(QRect(x + w - 65, y, 65, 16), Qt.AlignRight | Qt.AlignVCenter, f"{pct:.0f}%")

        bar_y = y + 20
        bar_h = max(8, h - 26)
        self._draw_segmented_bar(p, x, bar_y, w, bar_h, pct, ACCENT_BLUE)

    def _draw_network_module(self, p: QPainter, font: QFont, x: int, y: int, w: int, h: int):
        down_kb = self.data.get("net_down_kb", 0.0)
        up_kb = self.data.get("net_up_kb", 0.0)

        # Format throughput
        down_str = f"↓ {down_kb/1024:.1f}M/s" if down_kb > 1024 else f"↓ {down_kb:.0f}K/s"
        up_str = f"↑ {up_kb/1024:.1f}M/s" if up_kb > 1024 else f"↑ {up_kb:.0f}K/s"

        p.setFont(self._font(font, w, 0.026, letter_spacing=0.8))
        p.setPen(QPen(TEXT_MUTED))
        p.drawText(QRect(x, y, int(w * 0.35), 16), Qt.AlignLeft | Qt.AlignVCenter, "NETWORK")

        p.setFont(self._font(font, w, 0.025))
        p.setPen(QPen(TEXT_SECONDARY))
        p.drawText(QRect(x + int(w * 0.32), y, int(w * 0.40), 16), Qt.AlignRight | Qt.AlignVCenter, up_str)

        p.setFont(self._font(font, w, 0.028, bold=True))
        p.setPen(QPen(ACCENT_GREEN))
        p.drawText(QRect(x + w - 90, y, 90, 16), Qt.AlignRight | Qt.AlignVCenter, down_str)

        bar_y = y + 20
        bar_h = max(8, h - 26)
        # Normalize net sparkline
        history = list(self.net_down_history)
        max_val = max(100.0, max(history) if history else 100.0)
        norm_history = [(v / max_val) * 100.0 for v in history]
        self._draw_sparkline(p, x, bar_y, w, bar_h, norm_history, ACCENT_GREEN)

    def _draw_wifi_module(self, p: QPainter, font: QFont, x: int, y: int, w: int, h: int):
        wifi = self.data.get("wifi", {})
        ssid = wifi.get("ssid", "WIFI // ETH")[:18]
        sig_pct = wifi.get("signal_pct", 75)
        band = wifi.get("band", "5 GHz")

        p.setFont(self._font(font, w, 0.025, letter_spacing=0.8))
        p.setPen(QPen(TEXT_MUTED))
        p.drawText(QRect(x, y, int(w * 0.45), 16), Qt.AlignLeft | Qt.AlignVCenter, "WLAN LINK")

        p.setFont(self._font(font, w, 0.024))
        p.setPen(QPen(TEXT_SECONDARY))
        p.drawText(QRect(x + int(w * 0.40), y, int(w * 0.38), 16), Qt.AlignRight | Qt.AlignVCenter, f"{ssid}")

        p.setFont(self._font(font, w, 0.028, bold=True))
        p.setPen(QPen(ACCENT_CYAN))
        p.drawText(QRect(x + w - 65, y, 65, 16), Qt.AlignRight | Qt.AlignVCenter, f"{sig_pct}%")

        # Multi-bar signal strength gauge
        bar_y = y + 20
        bar_h = max(8, h - 26)
        self._draw_signal_bars(p, x, bar_y, w, bar_h, sig_pct)

    # ------------------------------------------------------------------
    # Custom Vector Drawing Helpers
    # ------------------------------------------------------------------
    def _draw_sparkline(self, p: QPainter, x: int, y: int, w: int, h: int, data: list, color: QColor):
        # Draw background container
        p.setPen(QPen(BORDER_SUBTLE, 1))
        p.setBrush(QBrush(QColor(255, 255, 255, 6)))
        p.drawRoundedRect(x, y, w, h, 3, 3)

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

        # Gradient Fill Under Curve
        grad = QLinearGradient(0, y, 0, y + h)
        c_top = QColor(color)
        c_top.setAlpha(60)
        c_bot = QColor(color)
        c_bot.setAlpha(5)
        grad.setColorAt(0.0, c_top)
        grad.setColorAt(1.0, c_bot)

        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawPath(fill_path)

        # Line Curve
        p.setPen(QPen(color, 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)

        p.restore()

    def _draw_segmented_bar(self, p: QPainter, x: int, y: int, w: int, h: int, pct: float, color: QColor):
        num_blocks = 20
        gap = 3
        block_w = (w - (num_blocks - 1) * gap) / num_blocks
        filled_count = int(round((pct / 100.0) * num_blocks))

        for i in range(num_blocks):
            bx = int(x + i * (block_w + gap))
            b_rect = QRectF(bx, y + 1, block_w, h - 2)
            if i < filled_count:
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(color))
                p.drawRoundedRect(b_rect, 1.5, 1.5)
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(QColor(255, 255, 255, 14)))
                p.drawRoundedRect(b_rect, 1.5, 1.5)

    def _draw_signal_bars(self, p: QPainter, x: int, y: int, w: int, h: int, signal_pct: float):
        num_bars = 16
        gap = 4
        bar_w = (w - (num_bars - 1) * gap) / num_bars
        active_bars = int(round((signal_pct / 100.0) * num_bars))

        for i in range(num_bars):
            ratio = (i + 1) / num_bars
            bar_h = max(3.0, (h - 2) * (0.3 + 0.7 * ratio))
            bx = int(x + i * (bar_w + gap))
            by = y + h - 1 - bar_h

            if i < active_bars:
                col = ACCENT_CYAN if ratio <= 0.8 else ACCENT_GREEN
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(col))
                p.drawRoundedRect(QRectF(bx, by, bar_w, bar_h), 1.5, 1.5)
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(BAR_DIM))
                p.drawRoundedRect(QRectF(bx, by, bar_w, bar_h), 1.5, 1.5)

    def _get_load_color(self, pct: float) -> QColor:
        if pct >= 88.0:
            return ACCENT_RED
        if pct >= 70.0:
            return ACCENT_AMBER
        return ACCENT_CYAN

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
    overlay = SystemMonitorOverlay()
    overlay.show()
    sys.exit(app.exec())
