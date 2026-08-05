"""
Progress Manager

Manages task progress tracking and reporting.
"""

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from .goal import Goal
from .task import Task

logger = logging.getLogger(__name__)


class ProgressEvent:
    """Represents a progress event."""

    def __init__(
        self,
        event_type: str,
        task_id: str,
        progress: float,
        detail: str = "",
        timestamp: datetime | None = None,
    ):
        """
        Initialize progress event.

        Args:
            event_type: Type of event (START, UPDATE, COMPLETE, FAIL, etc.)
            task_id: ID of task
            progress: Progress value (0.0 - 1.0)
            detail: Detailed information
            timestamp: Event timestamp
        """
        self.event_type = event_type
        self.task_id = task_id
        self.progress = progress
        self.detail = detail
        self.timestamp = timestamp or datetime.now()


class ProgressManager:
    """
    Manages task progress tracking and reporting.

    The Progress Manager provides real-time progress updates
    for both individual tasks and entire goals.
    """

    def __init__(
        self,
        on_progress_update: (
            Callable[["ProgressManager", ProgressEvent], None] | None
        ) = None,
        on_goal_update: Callable[["ProgressManager", Goal, float], None] | None = None,
        on_task_complete: Callable[["ProgressManager", Task], None] | None = None,
        enable_console_logging: bool = True,
    ):
        """
        Initialize progress manager.

        Args:
            on_progress_update: Callback when progress updates
            on_goal_update: Callback when goal progress changes
            on_task_complete: Callback when task completes
            enable_console_logging: Enable console logging of progress
        """
        self.on_progress_update = on_progress_update
        self.on_goal_update = on_goal_update
        self.on_task_complete = on_task_complete
        self.enable_console_logging = enable_console_logging

        # Progress state
        self.tasks_progress: dict[str, dict[str, Any]] = {}  # task_id -> progress info
        self.current_goals_progress: dict[str, float] = {}  # goal_id -> progress
        self.completed_tasks: list[str] = []
        self.total_completed_tasks: int = 0

        # Statistics
        self.total_progress_updates = 0
        self.total_progress_events = 0

        logger.debug("Initialized progress manager")

    def update_task_progress(self, task: Task, progress: float, detail: str = ""):
        """
        Update task progress.

        Args:
            task: Task with updated progress
            progress: New progress value (0.0 - 1.0)
            detail: Progress description
        """
        # Validate progress
        progress = max(0.0, min(1.0, progress))

        # Update task progress info
        if task.task_id not in self.tasks_progress:
            self.tasks_progress[task.task_id] = {
                "task_id": task.task_id,
                "goal": task.goal,
                "started_at": datetime.now(),
                "last_update": datetime.now(),
                "total_updates": 0,
            }

        progress_info = self.tasks_progress[task.task_id]
        progress_info["last_update"] = datetime.now()
        progress_info["total_updates"] += 1

        # Update progress
        progress_info["current_progress"] = progress
        progress_info["last_detail"] = detail

        self.total_progress_updates += 1
        self.total_progress_events += 1

        # Log to console if enabled
        if self.enable_console_logging:
            self._log_progress_update(task, progress, detail)

        # Notify callback
        if self.on_progress_update:
            event = ProgressEvent(
                event_type="UPDATE",
                task_id=task.task_id,
                progress=progress,
                detail=detail,
                timestamp=datetime.now(),
            )
            self.on_progress_update(self, event)

        # Check for completion
        if progress >= 1.0:
            self.task_completed(task)

    def task_completed(self, task: Task):
        """
        Mark task as completed.

        Args:
            task: Completed task
        """
        if task.task_id not in self.completed_tasks:
            self.completed_tasks.append(task.task_id)
            self.total_completed_tasks += 1

            logger.info(f"Task {task.task_id[:8]} completed")

            # Notify callback
            if self.on_task_complete:
                self.on_task_complete(self, task)

    def update_goal_progress(self, goal: Goal):
        """
        Update goal progress based on tasks.

        Args:
            goal: Goal to update
        """
        if goal.goal_id not in self.current_goals_progress:
            self.current_goals_progress[goal.goal_id] = {
                "goal_id": goal.goal_id,
                "description": goal.description,
                "started_at": datetime.now(),
                "tasks_completed": 0,
                "total_tasks": len(goal.tasks),
                "last_update": datetime.now(),
            }

        goal_progress = self.current_goals_progress[goal.goal_id]

        # Update task completion count
        completed = sum(1 for t in goal.tasks if t.status == "COMPLETED")
        goal_progress["tasks_completed"] = completed
        goal_progress["last_update"] = datetime.now()

        # Update overall progress
        total_tasks = len(goal.tasks)
        if total_tasks > 0:
            progress = completed / total_tasks
            self.current_goals_progress[goal.goal_id]["progress"] = progress
        else:
            self.current_goals_progress[goal.goal_id]["progress"] = 0.0

        # Log progress if enabled
        if self.enable_console_logging:
            self._log_goal_update(goal, progress)

        # Notify callback
        if self.on_goal_update:
            self.on_goal_update(self, goal, progress)

    def get_task_progress(self, task_id: str) -> dict[str, Any] | None:
        """
        Get progress for a specific task.

        Args:
            task_id: Task ID

        Returns:
            Progress information or None
        """
        return self.tasks_progress.get(task_id)

    def get_goal_progress(self, goal_id: str) -> dict[str, Any] | None:
        """
        Get progress for a specific goal.

        Args:
            goal_id: Goal ID

        Returns:
            Progress information or None
        """
        return self.current_goals_progress.get(goal_id)

    def get_all_progress(self) -> dict[str, Any]:
        """
        Get all progress information.

        Returns:
            Complete progress information
        """
        return {
            "tasks": list(self.tasks_progress.values()),
            "goals": list(self.current_goals_progress.values()),
            "completed_tasks": self.completed_tasks,
            "total_completed_tasks": self.total_completed_tasks,
            "total_progress_updates": self.total_progress_updates,
            "total_progress_events": self.total_progress_events,
        }

    def get_progress_summary(self, task_id: str) -> dict[str, Any]:
        """
        Get formatted progress summary for a task.

        Args:
            task_id: Task ID

        Returns:
            Progress summary dictionary
        """
        progress_info = self.tasks_progress.get(task_id)
        if not progress_info:
            return {"task_id": task_id, "progress": 0.0, "status": "not_started"}

        return {
            "task_id": task_id,
            "goal": progress_info.get("goal", ""),
            "progress": progress_info.get("current_progress", 0.0),
            "total_updates": progress_info.get("total_updates", 0),
            "last_update": progress_info.get("last_update", None),
            "last_detail": progress_info.get("last_detail", ""),
            "status": (
                "completed"
                if progress_info.get("current_progress", 0.0) >= 1.0
                else "in_progress"
            ),
        }

    def get_progress_bar(self, task_id: str, width: int = 30) -> str:
        """
        Get progress bar for a task.

        Args:
            task_id: Task ID
            width: Width of progress bar in characters

        Returns:
            Formatted progress bar string
        """
        progress_info = self.get_progress_summary(task_id)

        if progress_info["status"] == "completed":
            return f"[{'=' * width}] 100%"

        filled = int(width * progress_info["progress"])
        bar = "[" + "=" * filled + " " * (width - filled) + "]"
        percent = f"{progress_info['progress'] * 100:.1f}%"

        return f"{bar} {percent}"

    def get_progress_summary_for_goals(self, width: int = 30) -> list[dict[str, Any]]:
        """
        Get progress summaries for all goals.

        Args:
            width: Width of progress bars

        Returns:
            List of progress summaries
        """
        summaries = []

        for goal_id, goal_info in self.current_goals_progress.items():
            progress = goal_info.get("progress", 0.0)

            if progress >= 1.0:
                status = "completed"
                bar = "=" * width
            else:
                status = "in_progress"
                filled = int(width * progress)
                bar = "=" * filled + " " * (width - filled)

            summaries.append(
                {
                    "goal_id": goal_id,
                    "description": goal_info.get("description", ""),
                    "progress": progress,
                    "completed_tasks": goal_info.get("tasks_completed", 0),
                    "total_tasks": goal_info.get("total_tasks", 0),
                    "status": status,
                    "bar": bar,
                    "percent": f"{progress * 100:.1f}%",
                }
            )

        return summaries

    def _log_progress_update(self, task: Task, progress: float, detail: str):
        """Log progress update to console."""
        percent = progress * 100
        bar = self.get_progress_bar(task.task_id)

        logger.info(f"{bar} {percent:.1f}% - {detail[:50]}")

    def _log_goal_update(self, goal: Goal, progress: float):
        """Log goal update to console."""
        bar = self.get_progress_bar(goal.goal_id)

        logger.info(f"{bar} {progress * 100:.1f}% - {goal.current_step[:50]}")

    def get_statistics(self) -> dict[str, Any]:
        """
        Get progress manager statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "total_progress_updates": self.total_progress_updates,
            "total_progress_events": self.total_progress_events,
            "total_completed_tasks": self.total_completed_tasks,
            "active_tasks": len(
                [
                    t
                    for t in self.tasks_progress.values()
                    if t.get("current_progress", 0) < 1.0
                ]
            ),
            "completed_tasks": len(self.completed_tasks),
        }

    def reset_for_new_goal(self, goal: Goal):
        """
        Reset progress manager for a new goal.

        Args:
            goal: New goal to start tracking
        """
        self.tasks_progress.clear()
        self.current_goals_progress.clear()
        self.completed_tasks.clear()
        self.total_completed_tasks = 0
        self.total_progress_updates = 0
        self.total_progress_events = 0

        # Initialize for new goal
        for task in goal.tasks:
            self.tasks_progress[task.task_id] = {
                "task_id": task.task_id,
                "goal": task.goal,
                "started_at": datetime.now(),
                "last_update": datetime.now(),
                "total_updates": 0,
                "current_progress": 0.0,
                "last_detail": "",
            }

        self.current_goals_progress[goal.goal_id] = {
            "goal_id": goal.goal_id,
            "description": goal.description,
            "started_at": datetime.now(),
            "tasks_completed": 0,
            "total_tasks": len(goal.tasks),
            "last_update": datetime.now(),
            "progress": 0.0,
        }

        logger.info(f"Reset progress manager for goal {goal.goal_id[:8]}")
