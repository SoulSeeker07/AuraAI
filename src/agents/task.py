"""
Task Model

Represents a single executable task in the Agent Runtime.
"""


import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
import uuid

from .models import (
    TaskStatus, TaskPriority, TaskRiskLevel,
    RetryPolicy, ApprovalRequired
)


logger = logging.getLogger(__name__)


class Task:
    """
    A single executable task in the execution graph.

    Tasks are the fundamental unit of work in the Agent Runtime.
    Each task represents a logical step toward achieving a goal.
    """

    def __init__(
        self,
        goal: str,
        task_type: str = "general",
        priority: TaskPriority = TaskPriority.NORMAL,
        dependencies: Optional[List[str]] = None,
        required_tools: Optional[List[str]] = None,
        estimated_duration: timedelta = timedelta(minutes=5),
        risk_level: TaskRiskLevel = TaskRiskLevel.MEDIUM,
        retry_policy: RetryPolicy = RetryPolicy.DEFAULT,
        approval_required: ApprovalRequired = ApprovalRequired.AUTO,
        description: str = "",
        retry_count: int = 0,
        max_retries: int = 3,
        timeout: Optional[timedelta] = None,
        metadata: Optional[Dict[str, Any]] = None,
        status: TaskStatus = TaskStatus.CREATED,
        task_id: Optional[str] = None,
        parent_goal_id: Optional[str] = None
    ):
        """
        Initialize a task.

        Args:
            goal: The description of what this task accomplishes
            task_type: Category of task (e.g., "file", "git", "network")
            priority: Priority level (HIGH, NORMAL, LOW)
            dependencies: List of task IDs this depends on
            required_tools: List of tool names required to execute this task
            estimated_duration: Expected execution time
            risk_level: Risk level of execution (LOW, MEDIUM, HIGH, CRITICAL)
            retry_policy: How to handle failures
            approval_required: Whether this task requires user approval
            description: Detailed task description
            retry_count: Current retry count
            max_retries: Maximum number of retry attempts
            timeout: Maximum time to wait for this task
            metadata: Additional task metadata
            status: Current status
            task_id: Unique task identifier
            parent_goal_id: ID of the parent goal
        """
        self.goal = goal
        self.task_type = task_type
        self.priority = priority
        self.dependencies = dependencies or []
        self.required_tools = required_tools or []
        self.estimated_duration = estimated_duration
        self.risk_level = risk_level
        self.retry_policy = retry_policy
        self.approval_required = approval_required
        self.description = description or goal
        self.retry_count = retry_count
        self.max_retries = max_retries
        self.timeout = timeout
        self.metadata = metadata or {}
        self.status = status
        self.task_id = task_id or str(uuid.uuid4())
        self.parent_goal_id = parent_goal_id

        # Execution tracking
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.duration: Optional[timedelta] = None
        self.output: Any = None
        self.error: Optional[str] = None
        self.retry_queue: List[dict] = []

        # Callbacks
        self.on_complete: Optional[Callable[[Task], None]] = None
        self.on_fail: Optional[Callable[[Task], None]] = None
        self.on_progress: Optional[Callable[[Task, float], None]] = None
        self.on_approval_required: Optional[Callable[[Task], bool]] = None

        logger.debug(f"Created task: {self.task_id[:8]} - {goal[:50]}")

    @property
    def is_ready(self) -> bool:
        """Check if task is ready to execute (all dependencies complete)."""
        return self.status in [TaskStatus.QUEUED, TaskStatus.CREATED] and self._are_dependencies_complete()

    @property
    def is_running(self) -> bool:
        """Check if task is currently running."""
        return self.status == TaskStatus.RUNNING

    @property
    def is_complete(self) -> bool:
        """Check if task is complete."""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]

    @property
    def should_retry(self) -> bool:
        """Check if task should be retried."""
        return (
            self.status == TaskStatus.FAILED and
            self.retry_count < self.max_retries and
            self.retry_policy != RetryPolicy.NO_RETRY
        )

    @property
    def requires_approval(self) -> bool:
        """Check if task requires user approval."""
        return self.approval_required != ApprovalRequired.NO

    def _are_dependencies_complete(self) -> bool:
        """Check if all dependencies are complete."""
        if not self.dependencies:
            return True

        for dep_id in self.dependencies:
            dep_status = self.metadata.get(f"dependency_{dep_id}", None)
            if dep_status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
                return False

        return True

    def get_progress(self) -> float:
        """
        Get current progress (0.0 - 1.0).

        Returns:
            Progress as float between 0 and 1
        """
        if self.status == TaskStatus.CREATED or self.status == TaskStatus.QUEUED:
            return 0.0
        elif self.status == TaskStatus.RUNNING:
            return self.metadata.get('progress', 0.5)
        elif self.status == TaskStatus.COMPLETED:
            return 1.0
        elif self.status == TaskStatus.FAILED:
            return self.retry_count / self.max_retries
        else:
            return 0.0

    def update_progress(self, progress: float, detail: str = ""):
        """
        Update task progress.

        Args:
            progress: Progress value (0.0 - 1.0)
            detail: Progress description
        """
        self.metadata['progress'] = max(0.0, min(1.0, progress))
        self.metadata['last_progress_update'] = datetime.now().isoformat()
        if detail:
            self.metadata['last_progress_detail'] = detail

        logger.debug(f"Task {self.task_id[:8]} progress: {progress*100:.1f}% - {detail}")

        if self.on_progress:
            self.on_progress(self, progress)

    def mark_started(self):
        """Mark task as started."""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now()
        logger.debug(f"Task {self.task_id[:8]} started")

    def mark_completed(self, output: Any = None):
        """
        Mark task as completed.

        Args:
            output: Task output
        """
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
        self.duration = self.completed_at - self.started_at
        self.output = output

        logger.info(f"Task {self.task_id[:8]} completed in {self.duration}")

        if self.on_complete:
            self.on_complete(self)

    def mark_failed(self, error: str):
        """
        Mark task as failed.

        Args:
            error: Error description
        """
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now()
        self.duration = self.completed_at - self.started_at
        self.error = error

        logger.warning(f"Task {self.task_id[:8]} failed: {error}")

        if self.on_fail:
            self.on_fail(self)

    def mark_cancelled(self):
        """Mark task as cancelled."""
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.now()
        self.duration = self.completed_at - self.started_at
        self.error = "Task cancelled by user"

        logger.info(f"Task {self.task_id[:8]} cancelled")

    def check_timeout(self) -> bool:
        """
        Check if task has timed out.

        Returns:
            True if timed out
        """
        if self.started_at and self.timeout and self.status == TaskStatus.RUNNING:
            elapsed = datetime.now() - self.started_at
            if elapsed > self.timeout:
                self.mark_failed(f"Task timed out after {elapsed}")
                return True

        return False

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert task to dictionary.

        Returns:
            Task as dictionary
        """
        return {
            'task_id': self.task_id,
            'goal': self.goal,
            'task_type': self.task_type,
            'priority': self.priority.value,
            'dependencies': self.dependencies,
            'required_tools': self.required_tools,
            'estimated_duration': self.estimated_duration.total_seconds(),
            'risk_level': self.risk_level.value,
            'retry_policy': self.retry_policy.value,
            'approval_required': self.approval_required.value,
            'description': self.description,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'timeout': self.timeout.total_seconds() if self.timeout else None,
            'metadata': self.metadata,
            'status': self.status.value,
            'parent_goal_id': self.parent_goal_id,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration': self.duration.total_seconds() if self.duration else None,
            'has_output': self.output is not None,
            'has_error': self.error is not None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """
        Create task from dictionary.

        Args:
            data: Task as dictionary

        Returns:
            Task instance
        """
        return cls(
            task_id=data.get('task_id'),
            goal=data['goal'],
            task_type=data.get('task_type', 'general'),
            priority=TaskPriority(data.get('priority', 'NORMAL')),
            dependencies=data.get('dependencies'),
            required_tools=data.get('required_tools'),
            estimated_duration=timedelta(seconds=data.get('estimated_duration', 300)),
            risk_level=TaskRiskLevel(data.get('risk_level', 'MEDIUM')),
            retry_policy=RetryPolicy(data.get('retry_policy', 'DEFAULT')),
            approval_required=ApprovalRequired(data.get('approval_required', 'AUTO')),
            description=data.get('description'),
            retry_count=data.get('retry_count', 0),
            max_retries=data.get('max_retries', 3),
            timeout=timedelta(seconds=data.get('timeout')) if data.get('timeout') else None,
            status=TaskStatus(data.get('status', 'CREATED')),
            parent_goal_id=data.get('parent_goal_id')
        )

    def __repr__(self) -> str:
        """String representation."""
        return f"Task({self.task_id[:8]}, {self.status.value}, {self.goal[:50]})"
