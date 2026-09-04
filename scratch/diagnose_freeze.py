import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(".").resolve()
_SRC_DIR = _PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(1, str(_PROJECT_ROOT))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

def main():
    print("=== STARTING DIAGNOSTIC PROBE ===")
    app = QApplication.instance() or QApplication(sys.argv)
    
    print("[1] Testing VoiceNotchOverlay instantiation...")
    from gui.widgets.voice_notch_overlay import VoiceNotchOverlay, NotchState
    notch = VoiceNotchOverlay()
    notch._is_test_env = True
    notch.show()
    app.processEvents()
    print("    Notch shown successfully.")
    
    print("[2] Testing GlobalHotkeyService...")
    t0 = time.time()
    try:
        from tools.hotkey_service import GlobalHotkeyService
        hotkey_svc = GlobalHotkeyService()
        hotkey_svc.start()
        print(f"    GlobalHotkeyService started in {time.time() - t0:.3f}s.")
        hotkey_svc.stop()
        print("    GlobalHotkeyService stopped.")
    except Exception as e:
        print(f"    GlobalHotkeyService error: {e}")

    print("[3] Testing VoiceBackendWorker...")
    from run_voice_notch import VoiceBackendWorker
    worker = VoiceBackendWorker()
    t0 = time.time()
    worker.start()
    
    for i in range(50):
        t_before = time.perf_counter()
        app.processEvents()
        time.sleep(0.1)
        latency = (time.perf_counter() - t_before) * 1000
        if latency > 100:
            print(f"    WARNING: Event pump latency spiked: {latency:.1f}ms at step {i}")
    
    print("    50 event loops completed successfully.")
    worker.stop()
    notch.close()
    app.processEvents()
    print("=== DIAGNOSTIC PROBE FINISHED ===")

if __name__ == "__main__":
    main()
