"""
AuraAI — Voice Notch Overlay with Real Live Backend Voice Loop
==============================================================
Launches the VoiceOS-style Dynamic Island Notch overlay directly
connected to Aura's real backend voice engine:
- Continuous background wake-word listening ("Aura" / "Hey Aura")
- Live STT (Speech-to-Text) with real-time waveform visualization
- Real AuraCore reasoning / DAG execution / Desktop actions
- Always-on TTS (Text-to-Speech) spoken responses
- Automatic seamless wake-word re-arming loop

Usage:
    .\.venv\Scripts\python run_voice_notch.py
"""

# Silence third-party library progress bars and warnings in CLI
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TQDM_DISABLE"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["ENABLE_WAKE_WORD"] = "true"

# ── Ensure src/ is on sys.path ──
_PROJECT_ROOT = Path(__file__).resolve().parent
_SRC_DIR = _PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(1, str(_PROJECT_ROOT))

# Configure stdout and stderr to UTF-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Move logs to file and silence noisy HTTP / Hub loggers
import logging
_logs_dir = _PROJECT_ROOT / "logs"
_logs_dir.mkdir(exist_ok=True)
logging.basicConfig(
    filename=str(_logs_dir / "aura.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    encoding="utf-8",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import QApplication

from gui.signals import app_signals
from gui.widgets.voice_notch_overlay import NotchState, VoiceNotchOverlay


class VoiceBackendWorker(QThread):
    """
    Background worker thread that initializes AuraCore and starts
    the real continuous voice loop (Microphone, Wake-Word, STT, TTS, LLM).
    """

    status_message = Signal(str)
    ready = Signal()
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._voice_loop = None
        self._core = None
        self._running = True

    def run(self):
        try:
            self.status_message.emit("Initializing AuraCore neural backend...")
            from core.aura_core import AuraCore

            self._core = AuraCore.get_instance()
            self.status_message.emit("AuraCore initialized. Connecting continuous voice loop...")

            try:
                from voice.continuous_loop import ContinuousVoiceLoop
            except (ImportError, ModuleNotFoundError):
                from src.voice.continuous_loop import ContinuousVoiceLoop

            if hasattr(self._core, "voice_loop") and self._core.voice_loop:
                self._voice_loop = self._core.voice_loop
            else:
                self._voice_loop = ContinuousVoiceLoop(aura_core=self._core)
                setattr(self._core, "voice_loop", self._voice_loop)

            self._voice_loop._aura_core = self._core
            ContinuousVoiceLoop.set_global_aura_core(self._core)

            self.status_message.emit("Starting microphone stream & wake-word detector...")
            started = self._voice_loop.start()

            if started:
                self.status_message.emit("Voice Loop ACTIVE: Say 'Aura' or 'Hey Aura' to speak.")
                self.ready.emit()
            else:
                self.error.emit("Failed to activate microphone / wake-word detector.")
        except Exception as exc:
            self.error.emit(f"Voice backend initialization failed: {exc}")

    def stop(self):
        self._running = False
        if self._voice_loop:
            try:
                self._voice_loop.stop()
            except Exception:
                pass


def main():
    # Full HD & High-DPI crisp rendering policy
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("Aura Voice Notch")
    app.setOrganizationName("AuraAI")

    notch = VoiceNotchOverlay()
    notch.show()
    notch.raise_()
    notch.activateWindow()

    # Detect GPU hardware & display refresh rate
    gpu_info = "CPU (Default)"
    try:
        import torch
        if torch.cuda.is_available():
            gpu_info = f"{torch.cuda.get_device_name(0)} (CUDA FP16)"
    except Exception:
        pass

    from gui.widgets.voice_notch_overlay import get_display_refresh_rate
    hz = get_display_refresh_rate()
    fps_info = f"{hz:.0f} Hz (Auto-FPS Native)"

    geom = notch.geometry()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║      AURA AI — VOICE NOTCH (DYNAMIC ISLAND HUD)          ║")
    print(f"║      {fps_info:<12} · Full HD · GPU-Accelerated Voice      ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print(f"║  • Display Mode:          {fps_info:<30} ║")
    print(f"║  • Hardware Acceleration: {gpu_info:<30} ║")
    print(f"║  • Notch Position:        (X={geom.x()}, Y={geom.y()})                    ║")
    print("║  • Wake Word:             Say 'Aura' or 'Hey Aura'       ║")
    print("║  • Direct Talk:           Press Space when focused       ║")
    print("║  • Global Hotkey:         Alt + N to toggle              ║")
    print("║  • Exit:                  Right-click notch → Hide Notch ║")
    print("╚══════════════════════════════════════════════════════════╝\n")

    # Start the real voice backend in background
    worker = VoiceBackendWorker()
    worker.status_message.connect(lambda msg: print(f"  [VOICE OS] {msg}"))
    worker.ready.connect(lambda: print("  [VOICE OS] 🟢 Standby: Listening for 'Aura'...\n"))
    worker.error.connect(lambda err: print(f"  [ERROR] {err}"))
    worker.start()

    def _cleanup():
        print("\n  [VOICE OS] Shutting down voice backend...")
        worker.stop()
        worker.wait(2000)

    app.aboutToQuit.connect(_cleanup)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
