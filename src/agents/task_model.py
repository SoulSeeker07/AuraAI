"""
Task Model - Shared state for all agents.

Defines the Task class that represents a unit of work that agents can execute.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from typing import Any, Callable, Optional
from uuid import uuid4


class TaskStatus(Enum):
    """Task status lifecycle."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskType(Enum):
    """Types of tasks agents can execute."""
    # Research tasks
    RESEARCH_WEB = "research_web"
    RESEARCH_DOCUMENT = "research_document"
    DEEP_RESEARCH = "deep_research"

    # Coding tasks
    CODE_ANALYSIS = "code_analysis"
    CODE_REFACTOR = "code_refactor"
    CODE_DEBUG = "code_debug"
    CODE_GENERATE = "code_generate"
    TEST_GENERATE = "test_generate"
    CODE_DOCUMENT = "code_documentation"

    # Desktop tasks
    APP_OPEN = "app_open"
    APP_CLOSE = "app_close"
    FILE_SEARCH = "file_search"
    FILE_RENAME = "file_rename"
    FILE_MOVE = "file_move"
    SCREENSHOT = "screenshot"
    CLIPBOARD_READ = "clipboard_read"
    SYSTEM_VOLUME = "system_volume"
    LOCK_WORKSTATION = "lock_workstation"
    BROWSER_OPEN = "browser_open"
    WINDOW_MAXIMIZE = "window_maximize"
    WINDOW_MINIMIZE = "window_minimize"

    # Process management tasks
    PROCESS_LIST = "process_list"
    PROCESS_GET = "process_get"
    PROCESS_START = "process_start"
    PROCESS_STOP = "process_stop"
    PROCESS_KILL = "process_kill"
    PROCESS_SEARCH = "process_search"

    # Vision tasks
    IMAGE_ANALYSIS = "image_analysis"
    DOCUMENT_READ = "document_read"
    DIAGRAM_UNDERSTAND = "diagram_understand"
    UI_EXPLANATION = "ui_explanation"

    # Voice tasks
    SPEECH_TO_TEXT = "speech_to_text"
    TEXT_TO_SPEECH = "text_to_speech"
    VOICE_INTERACTION = "voice_interaction"

    # Learning tasks
    WORKFLOW_STORE = "workflow_store"
    WORKFLOW_RETRIEVE = "workflow_retrieve"
    LEARN_SUCCESS = "learn_success"
    LEARN_FAILURE = "learn_failure"

    # Memory tasks
    FACT_RETRIEVE = "fact_retrieve"
    FACT_ADD = "fact_add"
    FACT_UPDATE = "fact_update"

    # Background services
    NEWS_MONITOR = "news_monitor"
    WEATHER_CHECK = "weather_check"
    STOCK_MONITOR = "stock_monitor"
    SYSTEM_HEALTH = "system_health"

    # General tasks
    GENERAL = "general"


@dataclass
class TaskInput:
    """Input parameters for a task."""
    data: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.MEDIUM
    metadata: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from input data."""
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value in input data."""
        self.data[key] = value

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "data": self.data,
            "context": self.context,
            "priority": self.priority.value,
            "metadata": self.metadata
        }


@dataclass
class TaskOutput:
    """Output from task execution."""
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    error: str = ""
    execution_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "data": self.data,
            "message": self.message,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata
        }


@dataclass
class Task:
    """
    Represents a unit of work that an agent can execute.

    Tasks are the fundamental building block of autonomous operation.
    They have a lifecycle, can be prioritized, and track progress.
    """

    id: str
    type: TaskType
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    input: TaskInput = field(default_factory=TaskInput)
    output: TaskOutput | None = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    agent_id: str = ""
    error_count: int = 0
    max_retries: int = 3
    retry_delay_seconds: int = 10
    parent_task_id: str | None = None
    subtasks: list[str] = field(default_factory=list)
    progress: float = 0.0  # 0.0 to 1.0
    steps_completed: int = 0
    total_steps: int = 0
    result_callback: Optional[Callable[[Task], None]] = None
    on_progress_callback: Optional[Callable[[float], None]] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert task to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "input": self.input.to_dict(),
            "output": self.output.to_dict() if self.output else None,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "agent_id": self.agent_id,
            "error_count": self.error_count,
            "max_retries": self.max_retries,
            "parent_task_id": self.parent_task_id,
            "subtasks": self.subtasks,
            "progress": self.progress,
            "steps_completed": self.steps_completed,
            "total_steps": self.total_steps
        }

    def update_progress(self, progress: float) -> None:
        """Update task progress."""
        self.progress = max(0.0, min(1.0, progress))
        if self.on_progress_callback:
            self.on_progress_callback(self.progress)

    def mark_running(self) -> None:
        """Mark task as running."""
        if self.status == TaskStatus.PENDING:
            self.status = TaskStatus.RUNNING
            self.started_at = datetime.now()

    def mark_completed(self) -> None:
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
        if self.output and self.output.execution_time_ms == 0:
            # Calculate execution time if not set
            if self.started_at and self.completed_at:
                self.output.execution_time_ms = (
                        (self.completed_at - self.started_at).total_seconds() * 1000
                    )

    def mark_failed(self, error: str = "") -> None:
        """Mark task as failed."""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now()
        if self.output:
            self.output.error = error
        self.error_count += 1

    def mark_cancelled(self) -> None:
        """Mark task as cancelled."""
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.now()

    def should_retry(self) -> bool:
        """Check if task should be retried."""
        return (
            self.status == TaskStatus.FAILED
            and self.error_count < self.max_retries
            and self.status != TaskStatus.CANCELLED
        )

    def to_dict_summary(self) -> dict[str, Any]:
        """Get task summary without sensitive data."""
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "status": self.status.value,
            "priority": self.priority.value,
            "progress": self.progress,
            "steps_completed": self.steps_completed,
            "total_steps": self.total_steps,
            "error_count": self.error_count
        }


def create_task(
    task_type: TaskType,
    title: str,
    description: str = "",
    **kwargs
) -> Task:
    """
    Factory function to create a new task.

    Args:
        task_type: Type of task to create
        title: Human-readable title
        description: Detailed description
        **kwargs: Additional task parameters

    Returns:
        Newly created Task instance
    """
    task = Task(
        id=kwargs.get("id") or str(uuid4()),
        type=task_type,
        title=title,
        description=description,
        status=TaskStatus(kwargs.get("status", TaskStatus.PENDING).value),
        priority=TaskPriority(kwargs.get("priority", TaskPriority.MEDIUM).value),
        input=TaskInput(
            data=kwargs.get("input", {}),
            context=kwargs.get("context", {}),
            priority=TaskPriority(kwargs.get("priority", TaskPriority.MEDIUM).value),
            metadata=kwargs.get("metadata", {})
        ),
        parent_task_id=kwargs.get("parent_task_id"),
        subtasks=kwargs.get("subtasks", []),
        max_retries=kwargs.get("max_retries", 3),
        retry_delay_seconds=kwargs.get("retry_delay_seconds", 10),
        total_steps=kwargs.get("total_steps", 0),
        result_callback=kwargs.get("result_callback"),
        on_progress_callback=kwargs.get("on_progress_callback")
    )
    return task
