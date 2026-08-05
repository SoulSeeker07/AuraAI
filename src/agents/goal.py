"""
Goal Model

Represents a high-level objective that the Agent Runtime aims to achieve.
"""

import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from .models import ApprovalRequired, GoalPriority, GoalStatus, RetryPolicy

logger = logging.getLogger(__name__)


class Goal:
    """
    A high-level objective that the Agent Runtime aims to achieve.

    Goals are the highest-level unit of work in the Agent Runtime.
    Each goal represents a user request that needs to be completed.
    """

    def __init__(
        self,
        description: str,
        goal_id: str | None = None,
        priority: GoalPriority = GoalPriority.NORMAL,
        estimated_total_duration: timedelta = timedelta(minutes=30),
        risk_level: str = "MEDIUM",
        approval_required: ApprovalRequired = ApprovalRequired.AUTO,
        retry_policy: RetryPolicy = RetryPolicy.DEFAULT,
        max_retries: int = 1,
        context: dict[str, Any] | None = None,
        parent_goal_id: str | None = None,
        tags: list[str] | None = None,
        estimated_steps: int = 1,
        success_criteria: list[str] | None = None,
    ):
        """
        Initialize a goal.

        Args:
            description: The user's goal description
            goal_id: Unique goal identifier
            priority: Priority level
            estimated_total_duration: Expected total time
            risk_level: Risk level (LOW, MEDIUM, HIGH, CRITICAL)
            approval_required: Whether goal requires approval
            retry_policy: Retry policy for goal execution
            max_retries: Maximum retry attempts
            context: Additional context for the goal
            parent_goal_id: ID of parent goal (for sub-goals)
            tags: List of tags for categorization
            estimated_steps: Estimated number of steps
            success_criteria: List of conditions that must be met
        """
        self.description = description
        self.priority = priority
        self.estimated_total_duration = estimated_total_duration
        self.risk_level = risk_level
        self.approval_required = approval_required
        self.retry_policy = retry_policy
        self.max_retries = max_retries
        self.context = context or {}
        self.goal_id = goal_id or str(uuid.uuid4())
        self.parent_goal_id = parent_goal_id
        self.tags = tags or []
        self.estimated_steps = estimated_steps
        self.success_criteria = success_criteria or []

        # Execution tracking
        self.status = GoalStatus.CREATED
        self.created_at = datetime.now()
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None
        self.duration: timedelta | None = None

        # Tasks
        self.tasks: list[Task] = []

        # Progress
        self.total_progress = 0.0
        self.completed_steps = 0
        self.current_step = ""

        # Callbacks
        self.on_start: Callable[[Goal], None] | None = None
        self.on_progress: Callable[[Goal, float], None] | None = None
        self.on_complete: Callable[[Goal], None] | None = None
        self.on_fail: Callable[[Goal], None] | None = None
        self.on_approval_required: Callable[[Goal], bool] | None = None

        # Sub-goals
        self.sub_goals: list[Goal] = []

        logger.debug(f"Created goal: {self.goal_id[:8]} - {description[:50]}")

    @property
    def is_running(self) -> bool:
        """Check if goal is running."""
        return self.status == GoalStatus.RUNNING

    @property
    def is_complete(self) -> bool:
        """Check if goal is complete."""
        return self.status in [
            GoalStatus.COMPLETED,
            GoalStatus.FAILED,
            GoalStatus.CANCELLED,
        ]

    @property
    def is_active(self) -> bool:
        """Check if goal is active (not finished)."""
        return self.status == GoalStatus.RUNNING

    @property
    def progress(self) -> float:
        """
        Get overall goal progress (0.0 - 1.0).

        Returns:
            Progress as float between 0 and 1
        """
        if not self.tasks:
            return 0.0

        total = len(self.tasks)
        completed = sum(1 for t in self.tasks if t.status == "COMPLETED")
        return completed / total

    def add_task(self, task: "Task"):
        """
        Add a task to this goal.

        Args:
            task: Task to add
        """
        task.parent_goal_id = self.goal_id
        self.tasks.append(task)
        logger.debug(f"Added task {task.task_id[:8]} to goal {self.goal_id[:8]}")

    def add_sub_goal(self, sub_goal: "Goal"):
        """
        Add a sub-goal to this goal.

        Args:
            sub_goal: Sub-goal to add
        """
        sub_goal.parent_goal_id = self.goal_id
        self.sub_goals.append(sub_goal)
        logger.debug(
            f"Added sub-goal {sub_goal.goal_id[:8]} to goal {self.goal_id[:8]}"
        )

    def mark_started(self):
        """Mark goal as started."""
        self.status = GoalStatus.RUNNING
        self.started_at = datetime.now()

        # Mark all tasks as queued
        for task in self.tasks:
            task.status = "QUEUED"

        logger.info(f"Goal {self.goal_id[:8]} started")

        if self.on_start:
            self.on_start(self)

    def mark_completed(self):
        """Mark goal as completed."""
        self.status = GoalStatus.COMPLETED
        self.completed_at = datetime.now()
        self.duration = self.completed_at - self.started_at

        logger.info(f"Goal {self.goal_id[:8]} completed in {self.duration}")

        if self.on_complete:
            self.on_complete(self)

    def mark_failed(self, error: str):
        """
        Mark goal as failed.

        Args:
            error: Error description
        """
        self.status = GoalStatus.FAILED
        self.completed_at = datetime.now()
        self.duration = self.completed_at - self.started_at
        self.error = error

        logger.error(f"Goal {self.goal_id[:8]} failed: {error}")

        if self.on_fail:
            self.on_fail(self)

    def mark_cancelled(self):
        """Mark goal as cancelled."""
        self.status = GoalStatus.CANCELLED
        self.completed_at = datetime.now()
        self.duration = self.completed_at - self.started_at
        self.error = "Goal cancelled by user"

        logger.info(f"Goal {self.goal_id[:8]} cancelled")

    def update_progress(self, task: "Task"):
        """
        Update goal progress based on task status.

        Args:
            task: Task that just changed status
        """
        if task.status == "COMPLETED":
            self.completed_steps += 1
            self.current_step = task.goal[:50]
        elif task.status == "FAILED":
            self.current_step = f"Task failed: {task.goal[:50]}"

        # Calculate overall progress
        if self.tasks:
            total_tasks = len(self.tasks)
            completed_tasks = sum(1 for t in self.tasks if t.status == "COMPLETED")
            self.total_progress = completed_tasks / total_tasks

        logger.debug(
            f"Goal {self.goal_id[:8]} progress: {self.total_progress*100:.1f}% - {self.current_step}"
        )

        if self.on_progress:
            self.on_progress(self, self.total_progress)

    def check_approval(self) -> bool:
        """
        Check if goal requires approval.

        Returns:
            True if approval is required and granted, False otherwise
        """
        if self.approval_required == ApprovalRequired.NO:
            return True

        if self.on_approval_required:
            approved = self.on_approval_required(self)
            return approved

        # Auto-approve if not critical
        if self.risk_level != "CRITICAL":
            return True

        # For critical tasks, always require approval
        return False

    def get_status_summary(self) -> dict[str, Any]:
        """
        Get a summary of goal status.

        Returns:
            Status summary dictionary
        """
        return {
            "goal_id": self.goal_id,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "progress": self.total_progress,
            "completed_steps": self.completed_steps,
            "total_steps": self.estimated_steps,
            "current_step": self.current_step,
            "total_duration": self.duration.total_seconds() if self.duration else None,
            "task_count": len(self.tasks),
            "completed_task_count": sum(
                1 for t in self.tasks if t.status == "COMPLETED"
            ),
            "failed_task_count": sum(1 for t in self.tasks if t.status == "FAILED"),
            "parent_goal_id": self.parent_goal_id,
            "tags": self.tags,
        }

    def to_dict(self) -> dict[str, Any]:
        """
        Convert goal to dictionary.

        Returns:
            Goal as dictionary
        """
        return {
            "goal_id": self.goal_id,
            "description": self.description,
            "priority": self.priority.value,
            "estimated_total_duration": self.estimated_total_duration.total_seconds(),
            "risk_level": self.risk_level,
            "approval_required": self.approval_required.value,
            "retry_policy": self.retry_policy.value,
            "context": self.context,
            "parent_goal_id": self.parent_goal_id,
            "tags": self.tags,
            "estimated_steps": self.estimated_steps,
            "success_criteria": self.success_criteria,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "duration": self.duration.total_seconds() if self.duration else None,
            "total_progress": self.total_progress,
            "completed_steps": self.completed_steps,
            "current_step": self.current_step,
            "task_count": len(self.tasks),
            "sub_goal_count": len(self.sub_goals),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Goal":
        """
        Create goal from dictionary.

        Args:
            data: Goal as dictionary

        Returns:
            Goal instance
        """
        return cls(
            goal_id=data.get("goal_id"),
            description=data["description"],
            priority=GoalPriority(data.get("priority", "NORMAL")),
            estimated_total_duration=timedelta(
                seconds=data.get("estimated_total_duration", 1800)
            ),
            risk_level=data.get("risk_level", "MEDIUM"),
            approval_required=ApprovalRequired(data.get("approval_required", "AUTO")),
            retry_policy=RetryPolicy(data.get("retry_policy", "DEFAULT")),
            max_retries=data.get("max_retries", 1),
            context=data.get("context"),
            parent_goal_id=data.get("parent_goal_id"),
            tags=data.get("tags"),
            estimated_steps=data.get("estimated_steps", 1),
            success_criteria=data.get("success_criteria"),
        )

    def __repr__(self) -> str:
        """String representation."""
        return f"Goal({self.goal_id[:8]}, {self.status.value}, {self.description[:50]})"
