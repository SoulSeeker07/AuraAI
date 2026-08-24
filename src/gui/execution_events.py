"""
Forwarder / Backward-Compatibility Alias
Location: src/gui/execution_events.py

Re-exports canonical execution events from core.orchestration.execution_events.
The core execution events contract is owned by core.orchestration to guarantee
that core orchestration code never imports from the GUI subsystem.
"""

from src.core.orchestration.execution_events import (
    NodeState,
    ExecutionEvent,
    SubTaskNodeInfo,
    GraphInitializedEvent,
    NodeStateChangedEvent,
    ConfirmationRequiredEvent,
    ExecutionStartedEvent,
    ExecutionFinishedEvent,
    ReplanTriggeredEvent,
)

__all__ = [
    "NodeState",
    "ExecutionEvent",
    "SubTaskNodeInfo",
    "GraphInitializedEvent",
    "NodeStateChangedEvent",
    "ConfirmationRequiredEvent",
    "ExecutionStartedEvent",
    "ExecutionFinishedEvent",
    "ReplanTriggeredEvent",
]
