"""
Verification Script: Webview VRAM & Memory Footprint Audit (Isolated)
=====================================================================
Measures:
1. Baseline: PyQt GUI Window shown (Home tab active, DWM surface allocated).
2. WebEngine Load: Switch to Preview Tab, load Tailwind CSS HTML in QWebEngineView.
3. Quantifies exact isolated VRAM delta caused by Chromium WebEngine.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(1, str(_PROJECT_ROOT))

import psutil
from gui.webengine_init import ensure_webengine_flags
ensure_webengine_flags()

from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow
from engineering.preview_server import get_preview_server


def get_gpu_vram_mb() -> float:
    """Queries dedicated GPU memory used in MB via nvidia-smi."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            encoding="utf-8",
        )
        return float(out.strip())
    except Exception as e:
        print(f"nvidia-smi query failed: {e}")
        return 0.0


def main():
    print("=== AURA ISOLATED VRAM & WEBVIEW AUDIT ===")

    # 1. Boot QApplication & MainWindow (Tab 0: Home)
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.processEvents()
    time.sleep(0.5)

    proc = psutil.Process(os.getpid())
    vram_window_open = get_gpu_vram_mb()
    ram_window_open = proc.memory_info().rss / (1024 * 1024)

    print(f"1. MainWindow Shown (Tab 0 Home active, Qt DWM window surface allocated):")
    print(f"   • Dedicated GPU VRAM: {vram_window_open:.1f} MB / 4096 MB")
    print(f"   • Process Host RAM:   {ram_window_open:.1f} MB")

    # 2. Switch to Preview Tab (Index 2) and load heavy HTML
    window._on_tab_selected(2)
    server = get_preview_server()
    heavy_html = """<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-white p-8">
    <h1 class="text-3xl font-bold text-cyan-400">VRAM Audit Page</h1>
    <div class="grid grid-cols-4 gap-4 mt-6">
        <div class="p-4 bg-slate-800 rounded border border-slate-700">Card 1</div>
        <div class="p-4 bg-slate-800 rounded border border-slate-700">Card 2</div>
        <div class="p-4 bg-slate-800 rounded border border-slate-700">Card 3</div>
        <div class="p-4 bg-slate-800 rounded border border-slate-700">Card 4</div>
    </div>
</body>
</html>"""
    preview_url = server.serve_html(heavy_html, "vram_audit.html")
    window.webview_panel.load_url(preview_url)

    # Process events for 2.5 seconds to let Chromium initialize & render
    t_end = time.time() + 2.5
    while time.time() < t_end:
        app.processEvents()
        time.sleep(0.05)

    # 3. Measure post-render delta
    vram_webengine_active = get_gpu_vram_mb()
    ram_webengine_active = proc.memory_info().rss / (1024 * 1024)
    vram_webengine_delta = vram_webengine_active - vram_window_open
    ram_webengine_delta = ram_webengine_active - ram_window_open

    print(f"\n2. Preview Tab Active (QWebEngineView + Tailwind CSS rendered):")
    print(f"   • Dedicated GPU VRAM: {vram_webengine_active:.1f} MB (WebEngine Delta: {vram_webengine_delta:+.1f} MB)")
    print(f"   • Process Host RAM:   {ram_webengine_active:.1f} MB (WebEngine Delta: {ram_webengine_delta:+.1f} MB)")

    print(f"\n3. Audit Verdict:")
    print(f"   • Isolated WebEngine VRAM Impact: {vram_webengine_delta:+.1f} MB")
    print(f"   • Isolated WebEngine Host RAM Footprint: {ram_webengine_delta:+.1f} MB")

    window.close()
    server.stop()
    print("=== AUDIT COMPLETE ===")


if __name__ == "__main__":
    main()
