"""
Agent Runtime Models

Central model definitions for the Agent Runtime.
This file provides the core types and enums used across all agent modules.

This file fixes the missing models import that was causing "No module named 'src.agents.models'"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

# ============================================================================
# Task Models
# ============================================================================


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

    RESEARCH_WEB = "research_web"
    RESEARCH_DOCUMENT = "research_document"
    DEEP_RESEARCH = "deep_research"
    CODE_ANALYSIS = "code_analysis"
    CODE_REFACTOR = "code_refactor"
    CODE_DEBUG = "code_debug"
    CODE_GENERATE = "code_generate"
    TEST_GENERATE = "test_generate"
    CODE_DOCUMENT = "code_documentation"
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
    IMAGE_ANALYSIS = "image_analysis"
    DOCUMENT_READ = "document_read"
    DIAGRAM_UNDERSTAND = "diagram_understand"
    UI_EXPLANATION = "ui_explanation"
    SPEECH_TO_TEXT = "speech_to_text"
    TEXT_TO_SPEECH = "text_to_speech"
    VOICE_INTERACTION = "voice_interaction"
    WORKFLOW_STORE = "workflow_store"
    WORKFLOW_RETRIEVE = "workflow_retrieve"
    LEARN_SUCCESS = "learn_success"
    LEARN_FAILURE = "learn_failure"
    FACT_RETRIEVE = "fact_retrieve"
    FACT_ADD = "fact_add"
    FACT_UPDATE = "fact_update"
    NEWS_MONITOR = "news_monitor"
    WEATHER_CHECK = "weather_check"
    STOCK_MONITOR = "stock_monitor"
    SYSTEM_HEALTH = "system_health"
    GENERAL = "general"


class TaskRiskLevel(Enum):
    """Risk levels for tasks."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TaskInput:
    """Input parameters for a task."""

    data: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    goal_id: str | None = None
    task_id: str | None = None


@dataclass
class TaskOutput:
    """Output from a task execution."""

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskError:
    """Error information for a task."""

    task_id: str
    error: str
    occurred_at: datetime = field(default_factory=datetime.now)
    retry_count: int = 0
    max_retries: int = 3


# ============================================================================
# Goal Models
# ============================================================================


class GoalStatus(Enum):
    """Goal status states."""

    CREATED = "created"
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GoalPriority(Enum):
    """Goal priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


# ============================================================================
# Execution Models
# ============================================================================


class ApprovalRequired(Enum):
    """Approval requirements for goals/tasks."""

    AUTO = "auto"  # No approval needed, automatic
    MANUAL = "manual"  # Requires user approval
    NONE = "none"  # Not applicable


class RetryPolicy(Enum):
    """Retry policies for tasks."""

    DEFAULT = "default"
    IMMEDIATE = "immediate"
    DELAYED = "delayed"
    OFF = "off"


# ============================================================================
# Execution State Models
# ============================================================================


class ExecutionState(Enum):
    """Execution state for tasks/goals."""

    IDLE = "idle"
    INITIALIZING = "initializing"
    EXECUTING = "executing"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionPriority(Enum):
    """Execution priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


# ============================================================================
# Execution Context Models
# ============================================================================


@dataclass
class ExecutionContext:
    """Context for task execution."""

    goal_id: str | None = None
    task_id: str | None = None
    parent_task_id: str | None = None
    workspace_path: str | None = None
    user_context: dict[str, Any] = field(default_factory=dict)
    system_context: dict[str, Any] = field(default_factory=dict)
    execution_metadata: dict[str, Any] = field(default_factory=dict)
