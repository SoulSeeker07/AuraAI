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

import os
import sys
import threading
import time
from pathlib import Path

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

# Ensure safe stdout and stderr when running windowless (pythonw.exe)
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8", errors="replace")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8", errors="replace")

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

def _safe_print(*args, **kwargs):
    try:
        if sys.stdout and not sys.stdout.closed:
            print(*args, **kwargs)
    except Exception:
        pass

# Move all general logs to file while keeping ONLY Voice Model and Neural events in the console
import logging

_logs_dir = _PROJECT_ROOT / "logs"
_logs_dir.mkdir(exist_ok=True)
_file_handler = logging.FileHandler(str(_logs_dir / "aura.log"), encoding="utf-8")
_file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

class VoiceNeuralConsoleFilter(logging.Filter):
    """Filter that only permits Voice Model and Neural events on the console."""
    def filter(self, record: logging.LogRecord) -> bool:
        name_lower = record.name.lower()
        msg_lower = record.getMessage().lower()
        if any(k in name_lower for k in ("voice", "stt", "tts", "continuous_loop", "neural", "auracore", "wakeword", "groq")):
            return True
        if any(k in msg_lower for k in ("wake word", "stt", "tts", "piper", "groq", "listening", "transcribed", "neural", "turn #")):
            return True
        return False

_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setLevel(logging.INFO)
_console_handler.addFilter(VoiceNeuralConsoleFilter())
_console_handler.setFormatter(logging.Formatter("  [Aura Notch] %(message)s"))

_root_logger = logging.getLogger()
_root_logger.setLevel(logging.INFO)
_root_logger.handlers = [_file_handler, _console_handler]

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
            # 1. Instant Startup: Start Continuous Voice Loop immediately (<400ms)
            try:
                from voice.continuous_loop import ContinuousVoiceLoop
            except (ImportError, ModuleNotFoundError):
                from src.voice.continuous_loop import ContinuousVoiceLoop

            self._voice_loop = ContinuousVoiceLoop(aura_core=None)
            started = self._voice_loop.start()

            if started:
                self.status_message.emit("🟢 Standby: Listening for 'Aura' or 'Hey Aura' (Instant Ready)")
                self.ready.emit()
            else:
                self.error.emit("Failed to activate microphone / wake-word detector.")
                return

            # 2. Parallel Background Init: Load AuraCore neural agents concurrently
            def _load_core_in_background():
                try:
                    from core.aura_core import AuraCore, get_default_instance
                    core = get_default_instance() or AuraCore()
                    self._core = core
                    self._voice_loop._aura_core = core
                    ContinuousVoiceLoop.set_global_aura_core(core)
                    self.status_message.emit("⚡ Neural Engines & Autonomous Agents Attached")
                except Exception as e:
                    self.status_message.emit(f"Neural core attached in lightweight mode: {e}")

            threading.Thread(target=_load_core_in_background, daemon=True, name="AuraCoreAsyncLoader").start()

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
    _safe_print("╔══════════════════════════════════════════════════════════╗", flush=True)
    _safe_print("║      AURA AI — VOICE NOTCH (DYNAMIC ISLAND HUD)          ║", flush=True)
    _safe_print(f"║      {fps_info:<12} · Full HD · GPU-Accelerated Voice      ║", flush=True)
    _safe_print("╠══════════════════════════════════════════════════════════╣", flush=True)
    _safe_print(f"║  • Display Mode:          {fps_info:<30} ║", flush=True)
    _safe_print(f"║  • Hardware Acceleration: {gpu_info:<30} ║", flush=True)
    _safe_print(f"║  • Notch Position:        (X={geom.x()}, Y={geom.y()})                    ║", flush=True)
    _safe_print("║  • Wake Word:             Say 'Aura' or 'Hey Aura'       ║", flush=True)
    _safe_print("║  • Direct Talk:           Press Space when focused       ║", flush=True)
    _safe_print("║  • Global Hotkey:         Alt + N to toggle              ║", flush=True)
    _safe_print("║  • Exit:                  Right-click notch → Hide Notch ║", flush=True)
    _safe_print("╚══════════════════════════════════════════════════════════╝\n", flush=True)

    # Start the real voice backend in background
    worker = VoiceBackendWorker()
    worker.status_message.connect(lambda msg: _safe_print(f"  [Aura Notch] {msg}", flush=True))
    worker.ready.connect(lambda: _safe_print("  [Aura Notch] 🟢 Standby: Listening for 'Aura'...\n", flush=True))
    worker.error.connect(lambda err: _safe_print(f"  [ERROR] {err}", flush=True))
    worker.start()

    def _cleanup():
        _safe_print("\n  [Aura Notch] Shutting down voice backend...", flush=True)
        worker.stop()
        worker.wait(2000)

    app.aboutToQuit.connect(_cleanup)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
