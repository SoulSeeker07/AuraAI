"""
Standalone Launcher for AuraAI Neural Chat Window HUD
======================================================
Location: run_chat_window.py

Directly launches the futuristic Holographic Chat Window HUD and connects
it to the real AuraCore backend intelligence engine (Executive Brain, Groq LLM,
Memory Vault, and Multi-Agent Orchestration).
"""

import sys
import time
import asyncio
import logging
from pathlib import Path

# Configure sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from gui.webengine_init import ensure_webengine_flags
ensure_webengine_flags()

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication

from gui.widgets.chat_window_overlay import ChatWindowOverlay
from gui.signals import app_signals, ExecutionStep, StepStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_chat_window")


class ChatBackendWorker(QThread):
    """Executes AuraCore tasks asynchronously in a background thread."""

    finished_signal = Signal(str, str)  # task_id, response_text
    error_signal = Signal(str, str)     # task_id, error_message
    step_signal = Signal(object)        # ExecutionStep

    def __init__(self, aura_core, command: str, parent=None):
        super().__init__(parent)
        self.aura_core = aura_core
        self.command = command

    def run(self):
        task_id = f"task_{int(time.time())}"
        start_time = time.time()

        try:
            # Emit step 1: Parsing
            step1 = ExecutionStep(
                index=0,
                title="Analyzing Intent",
                description=f"Routing goal to ACA Cognitive Pipeline: '{self.command}'",
                status=StepStatus.RUNNING,
                timestamp=start_time,
            )
            self.step_signal.emit(step1)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            step1.status = StepStatus.COMPLETED
            self.step_signal.emit(step1)

            # Emit step 2: Cognitive Reasoning
            step2 = ExecutionStep(
                index=1,
                title="Executive Brain Reasoning",
                description="Evaluating tools, memory, and cognitive plan...",
                status=StepStatus.RUNNING,
                timestamp=time.time(),
            )
            self.step_signal.emit(step2)

            if self.aura_core and hasattr(self.aura_core, "process_request"):
                response_text = loop.run_until_complete(
                    self.aura_core.process_request(self.command)
                )
            elif self.aura_core and hasattr(self.aura_core, "process_via_executive_brain"):
                response_text = loop.run_until_complete(
                    self.aura_core.process_via_executive_brain(self.command)
                )
            else:
                # Fast-path direct neural inference (zero waiting time)
                from ai.fast_client import FastLLMClient
                response_text = FastLLMClient.query(self.command)

            loop.close()

            step2.status = StepStatus.COMPLETED
            self.step_signal.emit(step2)

            self.finished_signal.emit(task_id, str(response_text))

        except Exception as exc:
            logger.error(f"Chat command execution error: {exc}", exc_info=True)
            self.error_signal.emit(task_id, str(exc))


class BackendWarmupWorker(QThread):
    """Loads AuraCore neural engine concurrently in the background."""

    ready_signal = Signal(object)

    def run(self):
        try:
            from main import get_aura_core
            core = get_aura_core()
            logger.info("✓ AuraCore backend loaded successfully in background.")
            self.ready_signal.emit(core)
        except Exception as e:
            logger.warning(f"AuraCore background initialization notice: {e}")
            self.ready_signal.emit(None)


class ChatWindowApp:
    """Standalone manager connecting ChatWindowOverlay to real backend with instant launch."""

    def __init__(self):
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setStyle("Fusion")

        # 1. Instantiate & show Chat Window Overlay IMMEDIATELY (<400ms)
        self.chat_overlay = ChatWindowOverlay()
        self.aura_core = None

        self._active_worker = None
        self._is_executing = False
        self._last_was_voice = False

        # 2. Concurrently warm up AuraCore in the background (matching Voice Notch pattern)
        self._warmup_worker = BackendWarmupWorker(parent=self.chat_overlay)
        self._warmup_worker.ready_signal.connect(self._on_backend_warmed)
        self._warmup_worker.start()

        # Connect user message signal to core runner
        app_signals.message_received.connect(self._on_message_received)
        app_signals.toggle_chat_overlay.connect(self.chat_overlay.toggle)
        self.app.aboutToQuit.connect(self._cleanup)

        # Start Global Hotkey Service (Alt+Space anywhere, Ctrl+Q in terminal)
        try:
            from tools.hotkey_service import GlobalHotkeyService
            self._hotkeys = GlobalHotkeyService.get_instance(on_toggle_chat=self.chat_overlay.toggle)
            self._hotkeys.start()
        except Exception as e:
            logger.warning(f"GlobalHotkeyService startup notice: {e}")

    def _on_backend_warmed(self, core):
        self.aura_core = core
        if hasattr(self.chat_overlay, "_groq_pill"):
            self.chat_overlay._groq_pill.setText("⚡ Groq / GPT-OSS 120B (Active)")
            self.chat_overlay._groq_pill.setStyleSheet("""
                color: #10b981;
                background: rgba(16, 185, 129, 0.12);
                border: 1px solid rgba(16, 185, 129, 0.35);
                border-radius: 6px;
                padding: 4px 10px;
            """)

    def _cleanup(self):
        if hasattr(self, "_hotkeys") and self._hotkeys:
            self._hotkeys.stop()
        if self._active_worker and self._active_worker.isRunning():
            self._active_worker.quit()
            self._active_worker.wait(1000)

    def _on_message_received(self, sender: str, content: str, is_user: bool):
        if is_user and not self._is_executing:
            # Check if this was a voice-transcribed command
            self._last_was_voice = (sender == "voice")
            self.execute_command(content)

    def execute_command(self, text: str):
        if not text or self._is_executing:
            return

        self._is_executing = True
        app_signals.execution_started.emit("user-task")

        if self._active_worker and not self._active_worker.isRunning():
            self._active_worker = None

        self._active_worker = ChatBackendWorker(
            self.aura_core, text, parent=self.chat_overlay
        )
        self._active_worker.step_signal.connect(
            lambda step: app_signals.step_updated.emit(step)
        )
        self._active_worker.finished_signal.connect(self._on_command_finished)
        self._active_worker.error_signal.connect(self._on_command_error)
        self._active_worker.start()

    def _on_command_finished(self, task_id: str, response: str):
        self._is_executing = False
        app_signals.message_received.emit("agent", response, False)
        app_signals.execution_finished.emit(task_id, True)

        # If user spoke using mic, play spoken TTS response aloud
        if self._last_was_voice and response:
            try:
                import threading
                def _speak():
                    from voice.tts_manager import TTSManager
                    tts = TTSManager()
                    if tts.initialize():
                        # Speak clean text (strip markdown fences)
                        import re
                        clean_text = re.sub(r"```.*?```", "", response, flags=re.DOTALL)
                        clean_text = re.sub(r"[*#_`]", "", clean_text).strip()
                        if clean_text:
                            tts.add_text(clean_text[:400])
                            tts.speak()
                threading.Thread(target=_speak, daemon=True).start()
            except Exception as e:
                logger.debug(f"[ChatWindowApp] TTS notice: {e}")

    def _on_command_error(self, task_id: str, error: str):
        self._is_executing = False
        app_signals.message_received.emit(
            "agent", f"⚠️ Error executing command: {error}", False
        )
        app_signals.execution_finished.emit(task_id, False)

    def run(self):
        from PySide6.QtCore import Qt
        self.chat_overlay.showNormal()
        self.chat_overlay.setWindowState(
            (self.chat_overlay.windowState() & ~Qt.WindowState.WindowMinimized)
            | Qt.WindowState.WindowActive
        )
        self.chat_overlay.raise_()
        self.chat_overlay.activateWindow()

        # Check if recovering from previous restart
        try:
            from core.agent_lifecycle import AgentLifecycleManager
            lm = AgentLifecycleManager()
            state = lm.recover_state()
            if state and state.get("active_agent_id"):
                agent_id = state.get("active_agent_id")
                app_signals.message_received.emit(
                    "agent",
                    f"✦ Context memory restored for session [{agent_id}]. Standing by.",
                    False,
                )
        except Exception:
            pass

        return self.app.exec()


if __name__ == "__main__":
    app_runner = ChatWindowApp()
    sys.exit(app_runner.run())
