"""
AuraAI GUI Signals
==================
Centralized signal bus for decoupled communication between GUI components
and the AuraCore backend.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from PySide6.QtCore import QObject, Signal


class StepStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    SKIPPED = auto()


class TaskNodeStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExecutionStep:
    """Represents a single step in the execution pipeline."""

    index: int
    title: str
    description: str = ""
    status: StepStatus = StepStatus.PENDING
    timestamp: float | None = None
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class TaskNode:
    """Represents a node in the Task DAG."""

    id: str
    label: str
    status: TaskNodeStatus = TaskNodeStatus.PENDING
    parent_ids: list[str] = None
    progress: float = 0.0

    def __post_init__(self):
        if self.parent_ids is None:
            self.parent_ids = []


@dataclass
class WorldStateSnapshot:
    """Live snapshot from WorldStateObserver."""

    focused_window: str = ""
    active_url: str = ""
    mouse_position: tuple = (0, 0)
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    timestamp: float = 0.0


@dataclass
class MemoryEntry:
    """A single knowledge/memory entry."""

    id: str
    content: str
    category: str = "general"
    confidence: float = 1.0
    created_at: float | None = None


class AppSignals(QObject):
    """
    Singleton signal bus.

    Usage:
        from gui.signals import app_signals
        app_signals.step_updated.emit(step)
    """

    # ── Execution Pipeline ──
    step_updated = Signal(ExecutionStep)  # Single step changed
    steps_cleared = Signal()  # Clear all steps
    execution_started = Signal(str)  # task_id
    execution_finished = Signal(str, bool)  # task_id, success

    # ── Task DAG ──
    dag_node_added = Signal(TaskNode)
    dag_node_updated = Signal(TaskNode)
    dag_cleared = Signal()

    # ── Chat / Messages ──
    message_received = Signal(str, str, bool)  # sender, content, is_user
    message_stream = Signal(str)  # Streaming token

    # ── World State ──
    world_state_changed = Signal(WorldStateSnapshot)

    # ── Voice ──
    voice_status_changed = Signal(bool)  # is_active
    voice_level = Signal(float)  # Audio level 0.0-1.0

    # ── Screen / Vision ──
    screen_status_changed = Signal(bool, str)  # is_sharing, window_title
    screen_captured = Signal(object)  # QPixmap / image data

    # ── Memory ──
    memory_entry_added = Signal(MemoryEntry)
    memory_entry_removed = Signal(str)  # entry_id

    # ── System / Provider ──
    provider_changed = Signal(str)  # provider_name
    system_metrics = Signal(dict)  # cpu, ram, disk dict

    # ── UI Commands ──
    toggle_overlay = Signal()
    toggle_inspector = Signal()
    toggle_chat_overlay = Signal()
    toggle_weather_overlay = Signal()
    toggle_system_overlay = Signal()
    toggle_system_status_overlay = Signal()
    toggle_agent_task_overlay = Signal()
    toggle_personal_os_overlay = Signal()
    show_notification = Signal(str, str)  # title, message


# Global singleton instance
app_signals = AppSignals()
