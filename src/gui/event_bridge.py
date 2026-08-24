"""
Execution Event Bridge for Desktop GUI
Location: src/gui/event_bridge.py

Provides thread-safe marshaling of core ExecutionEvents from background orchestration threads
to the Qt main/GUI thread via Qt's native cross-thread QueuedConnection signal mechanism.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from PySide6.QtCore import QObject, Qt, Signal

from core.orchestration.execution_events import ExecutionEvent
from gui.models.execution_trace_model import ExecutionTraceModel

logger = logging.getLogger(__name__)


class ExecutionEventBridge(QObject):
    """
    Thread-Safe Qt Signal Bridge for Orchestrator Telemetry.

    Architectural Invariants:
    1. Background Thread Safety: The `sink_callback` method does the absolute minimum:
       `self.execution_event.emit(event)`. Qt's `Signal.emit()` is re-entrant and thread-safe.
    2. Automatic Thread Marshaling: When `ExecutionTraceModel.on_event` is connected via
       `Qt.AutoConnection` (or `Qt.QueuedConnection`), Qt automatically queues the slot invocation
       into the main GUI thread's event loop if emitted from a worker thread (e.g. QThread or asyncio thread).
    3. GUI Thread Affinity: The bridge and model must be instantiated on the GUI thread to ensure
       proper QObject thread affinity.
    4. Error Containment Boundary: MasterOrchestrator's 3-strike circuit breaker protects against
       synchronous sink failures; asynchronous slot exceptions on the Qt main thread are contained
       locally by ExecutionTraceModel.on_event.
    """

    # Primary event signal carrying typed ExecutionEvent instances
    execution_event = Signal(object)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)

    def sink_callback(self, event: ExecutionEvent) -> None:
        """
        Sink entry point registered with `MasterOrchestrator.set_execution_sink()`.

        INVARIANT: Performs zero model mutation or state manipulation on the caller thread.
        Purely re-emits the event via Qt Signal for cross-thread dispatch.
        """
        try:
            self.execution_event.emit(event)
        except Exception as exc:
            logger.error(f"[ExecutionEventBridge] Failed to emit execution event: {exc}", exc_info=True)

    def connect_model(self, model: ExecutionTraceModel) -> None:
        """Connect the trace model's on_event handler to the bridge signal with AutoConnection."""
        self.execution_event.connect(model.on_event, Qt.AutoConnection)

    def disconnect_model(self, model: ExecutionTraceModel) -> None:
        """Disconnect the trace model from the bridge signal."""
        try:
            self.execution_event.disconnect(model.on_event)
        except (RuntimeError, TypeError) as exc:
            logger.debug(f"[ExecutionEventBridge] Disconnect model note: {exc}")
