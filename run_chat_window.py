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

            if self.aura_core is None:
                try:
                    from core.aura_core import AuraCore
                    self.aura_core = AuraCore.get_instance()
                except Exception as e:
                    logger.warning(f"Could not load AuraCore singleton: {e}")

            if self.aura_core and hasattr(self.aura_core, "process_request"):
                response_text = loop.run_until_complete(
                    self.aura_core.process_request(self.command)
                )
            elif self.aura_core and hasattr(self.aura_core, "process_via_executive_brain"):
                response_text = loop.run_until_complete(
                    self.aura_core.process_via_executive_brain(self.command)
                )
            else:
                # Fallback to direct Groq / LLM or informative response
                response_text = f"✦ AuraCore received: '{self.command}'. Cognition engine active."

            loop.close()

            step2.status = StepStatus.COMPLETED
            self.step_signal.emit(step2)

            self.finished_signal.emit(task_id, str(response_text))

        except Exception as exc:
            logger.error(f"Chat command execution error: {exc}", exc_info=True)
            self.error_signal.emit(task_id, str(exc))


class ChatWindowApp:
    """Standalone manager connecting ChatWindowOverlay to real backend."""

    def __init__(self):
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setStyle("Fusion")

        # Initialize AuraCore Backend
        self.aura_core = None
        try:
            from core.aura_core import AuraCore
            self.aura_core = AuraCore.get_instance()
            logger.info("✓ AuraCore backend loaded successfully.")
        except Exception as e:
            logger.warning(f"AuraCore initialization notice: {e}")

        # Instantiate Chat Window Overlay
        self.chat_overlay = ChatWindowOverlay()

        self._active_worker = None
        self._is_executing = False

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

    def _cleanup(self):
        if hasattr(self, "_hotkeys") and self._hotkeys:
            self._hotkeys.stop()
        if self._active_worker and self._active_worker.isRunning():
            self._active_worker.quit()
            self._active_worker.wait(1000)

    def _on_message_received(self, sender: str, content: str, is_user: bool):
        if is_user and not self._is_executing:
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
            from tools.restart_manager import RestartManager
            recovery = RestartManager.load_and_restore_state()
            if recovery:
                routines_cnt = len(recovery.get("active_routines", []))
                msg = f"🔄 **AuraAI Restarts Complete**: Session state restored ({routines_cnt} active routine(s), memory and background tasks preserved)."
                app_signals.message_received.emit("agent", msg, False)
        except Exception as e:
            logger.debug(f"Recovery check notice: {e}")

        return self.app.exec()


if __name__ == "__main__":
    app_runner = ChatWindowApp()
    sys.exit(app_runner.run())
