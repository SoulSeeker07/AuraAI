"""
AuraAI GUI Application Entry Point
==================================
Bootstraps both Overlay and MainWindow with the global signal bus,
and connects UI inputs to the real AuraCore intelligence.
"""

import asyncio
import logging
import sys
import time

from gui.webengine_init import ensure_webengine_flags
ensure_webengine_flags()

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow
from gui.overlay import OverlayWindow
from gui.signals import ExecutionStep, StepStatus, app_signals

logger = logging.getLogger(__name__)


class CommandWorker(QThread):
    """Executes AuraCore tasks asynchronously in a background thread."""

    finished_signal = Signal(str, str)  # task_id, response_text
    error_signal = Signal(str, str)  # task_id, error_message
    step_signal = Signal(object)  # ExecutionStep

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

            # Create event loop for async AuraCore execution
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
                    logger.error(f"CommandWorker failed to load AuraCore: {e}")

            if self.aura_core and hasattr(self.aura_core, "process_request"):
                response_text = loop.run_until_complete(
                    self.aura_core.process_request(self.command)
                )
            elif self.aura_core and hasattr(
                self.aura_core, "process_via_executive_brain"
            ):
                response_text = loop.run_until_complete(
                    self.aura_core.process_via_executive_brain(self.command)
                )
            else:
                response_text = f"Aura Core received: {self.command}"

            loop.close()

            step2.status = StepStatus.COMPLETED
            self.step_signal.emit(step2)

            self.finished_signal.emit(task_id, str(response_text))

        except Exception as exc:
            logger.error(f"Command execution error: {exc}", exc_info=True)
            self.error_signal.emit(task_id, str(exc))


class AuraGUI:
    def __init__(self, aura_core=None):
        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication(sys.argv)
        self.app.setStyle("Fusion")

        self.aura_core = aura_core
        if self.aura_core is None:
            try:
                from core.aura_core import AuraCore
                self.aura_core = AuraCore.get_instance()
            except Exception as e:
                logger.error(f"Failed to load AuraCore singleton: {e}")
        self.main_window = MainWindow()
        self.overlay = OverlayWindow()

        self._active_worker = None
        self._is_executing = False

        # Connect user message signal to core runner
        app_signals.message_received.connect(self._on_message_received)
        app_signals.toggle_overlay.connect(self.overlay.toggle)
        self.app.aboutToQuit.connect(self._cleanup)

        # Global Hotkeys (Alt+Space anywhere, Ctrl+Q in terminal)
        try:
            from tools.hotkey_service import GlobalHotkeyService
            self._hotkeys = GlobalHotkeyService.get_instance(on_toggle_chat=self.main_window.toggle_chat_overlay)
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

        if self.aura_core is None:
            try:
                from core.aura_core import AuraCore

                self.aura_core = AuraCore.get_instance()
            except Exception as e:
                logger.error(f"Failed to load AuraCore: {e}")

        # Clean up old worker if finished
        if self._active_worker and not self._active_worker.isRunning():
            self._active_worker = None

        self._active_worker = CommandWorker(self.aura_core, text, parent=self.main_window)
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
            "agent", f"Error executing task: {error}", False
        )
        app_signals.execution_finished.emit(task_id, False)

    def run(self):
        self.main_window.show()
        return self.app.exec()


if __name__ == "__main__":
    gui = AuraGUI()
    sys.exit(gui.run())
