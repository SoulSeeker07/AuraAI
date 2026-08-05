"""
Task Manager - Orchestrates task execution and coordination.

The Task Manager maintains a registry of all tasks, handles task execution
queues, and coordinates task dependencies.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from .task_model import Task, TaskInput, TaskOutput, TaskStatus, TaskType, create_task


class TaskManager:
    """
    Manages the lifecycle of tasks across all agents.

    The Task Manager:
    - Registers and tracks all tasks
    - Executes tasks in priority order
    - Handles task dependencies
    - Manages retries and timeouts
    - Provides task status queries
    """

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._running_tasks: dict[str, Task] = {}
        self._completed_tasks: dict[str, Task] = {}
        self._failed_tasks: dict[str, Task] = {}
        self._pending_tasks: dict[str, Task] = {}
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._lock = threading.Lock()
        self._max_concurrent_tasks: int = 5
        self._task_handlers: dict[TaskType, Callable] = {}
        self._callbacks: dict[str, list[Callable]] = {}
        self._task_counter: int = 0

    def register_task_handler(
        self, task_type: TaskType, handler: Callable[[Task], TaskOutput]
    ) -> None:
        """
        Register a handler for a specific task type.

        Args:
            task_type: Type of task to handle
            handler: Function that executes the task
        """
        self._task_handlers[task_type] = handler

    def unregister_task_handler(self, task_type: TaskType) -> None:
        """Unregister handler for task type."""
        if task_type in self._task_handlers:
            del self._task_handlers[task_type]

    def create_task(
        self, task_type: TaskType, title: str, description: str = "", **kwargs
    ) -> Task:
        """
        Create a new task.

        Args:
            task_type: Type of task
            title: Task title
            description: Task description
            **kwargs: Additional task parameters

        Returns:
            Created task instance
        """
        task = create_task(task_type, title, description, **kwargs)

        with self._lock:
            self._tasks[task.id] = task
            self._pending_tasks[task.id] = task
            self._task_counter += 1

        # Add to queue if not waiting for dependencies
        if not task.subtasks:
            try:
                asyncio.create_task(self._process_task(task))
            except RuntimeError:
                # Event loop not running, keep in pending
                pass

        return task

    def get_task(self, task_id: str) -> Task | None:
        """Get task by ID."""
        return self._tasks.get(task_id)

    def get_tasks_by_status(self, status: TaskStatus, limit: int = 100) -> list[Task]:
        """Get tasks by status."""
        with self._lock:
            return [task for task in self._tasks.values() if task.status == status][
                :limit
            ]

    def get_all_tasks(self) -> list[Task]:
        """Get all tasks."""
        with self._lock:
            return list(self._tasks.values())

    def get_pending_tasks(self) -> list[Task]:
        """Get pending tasks."""
        with self._lock:
            return list(self._pending_tasks.values())

    def get_running_tasks(self) -> list[Task]:
        """Get running tasks."""
        with self._lock:
            return list(self._running_tasks.values())

    def get_completed_tasks(self, limit: int = 100) -> list[Task]:
        """Get completed tasks."""
        with self._lock:
            return list(self._completed_tasks.values())[:limit]

    def get_failed_tasks(self, limit: int = 100) -> list[Task]:
        """Get failed tasks."""
        with self._lock:
            return list(self._failed_tasks.values())[:limit]

    def get_tasks_by_type(self, task_type: TaskType) -> list[Task]:
        """Get tasks by type."""
        return [task for task in self._tasks.values() if task.type == task_type]

    async def _process_task(self, task: Task) -> None:
        """
        Process a single task execution.

        Args:
            task: Task to process
        """
        with self._lock:
            if task.id in self._pending_tasks:
                del self._pending_tasks[task.id]
            self._running_tasks[task.id] = task

        task.mark_running()

        try:
            # Get handler for this task type
            handler = self._task_handlers.get(task.type)

            if handler is None:
                error_msg = f"No handler registered for task type: {task.type.value}"
                task.mark_failed(error_msg)
                self._handle_failed_task(task)
                return

            # Execute the task
            task_output = handler(task)

            # Update task with output
            with self._lock:
                task.output = task_output
                if task_output.success:
                    task.mark_completed()
                    self._completed_tasks[task.id] = task
                else:
                    task.mark_failed(task_output.error)
                    self._failed_tasks[task.id] = task

            # Check for subtasks
            if task_output.data.get("subtasks"):
                self._create_subtasks(task, task_output.data["subtasks"])

            # Notify callbacks
            self._notify_callbacks(task)

        except asyncio.CancelledError:
            task.mark_cancelled()
            with self._lock:
                if task.id in self._running_tasks:
                    del self._running_tasks[task.id]
        except Exception as e:
            error_msg = str(e)
            task.mark_failed(error_msg)
            with self._lock:
                self._failed_tasks[task.id] = task

            # Retry if allowed
            if task.should_retry():
                await asyncio.sleep(task.retry_delay_seconds)
                task.status = TaskStatus.PENDING
                with self._lock:
                    self._pending_tasks[task.id] = task
                    if task.id in self._running_tasks:
                        del self._running_tasks[task.id]
                asyncio.create_task(self._process_task(task))
            else:
                self._handle_failed_task(task)

    def _create_subtasks(self, parent_task: Task, subtask_configs: list[dict]) -> None:
        """
        Create subtasks from task output.

        Args:
            parent_task: Parent task
            subtask_configs: List of subtask configurations
        """
        subtasks_created = []

        for config in subtask_configs:
            subtask_type = config.get("type", TaskType.GENERAL)
            subtask_title = config.get("title", f"Subtask {len(subtasks_created) + 1}")
            subtask_description = config.get("description", "")

            subtask = create_task(
                task_type=subtask_type,
                title=subtask_title,
                description=subtask_description,
                parent_task_id=parent_task.id,
                input=TaskInput(data=config.get("input", {})),
            )

            with self._lock:
                self._tasks[subtask.id] = subtask
                self._pending_tasks[subtask.id] = subtask

            # Add to parent's subtasks list
            parent_task.subtasks.append(subtask.id)

            subtasks_created.append(subtask.id)

        parent_task.subtasks = subtasks_created

    def _handle_failed_task(self, task: Task) -> None:
        """Handle failed task."""
        if task.result_callback:
            try:
                task.result_callback(task)
            except Exception:
                pass

    def register_callback(self, task_id: str, callback: Callable[[Task], None]) -> None:
        """Register callback for task completion."""
        if task_id not in self._callbacks:
            self._callbacks[task_id] = []
        self._callbacks[task_id].append(callback)

    def unregister_callback(
        self, task_id: str, callback: Callable[[Task], None]
    ) -> None:
        """Unregister callback for task."""
        if task_id in self._callbacks and callback in self._callbacks[task_id]:
            self._callbacks[task_id].remove(callback)

    def _notify_callbacks(self, task: Task) -> None:
        """Notify all callbacks for task."""
        if task.id in self._callbacks:
            for callback in self._callbacks[task.id]:
                try:
                    callback(task)
                except Exception:
                    pass

    def get_statistics(self) -> dict[str, Any]:
        """Get task manager statistics."""
        with self._lock:
            # Count tasks by filtering from self._tasks based on status
            completed_count = sum(
                1
                for task in self._tasks.values()
                if task.status == TaskStatus.COMPLETED
            )
            pending_count = sum(
                1 for task in self._tasks.values() if task.status == TaskStatus.PENDING
            )
            running_count = sum(
                1 for task in self._tasks.values() if task.status == TaskStatus.RUNNING
            )
            failed_count = sum(
                1 for task in self._tasks.values() if task.status == TaskStatus.FAILED
            )
            cancelled_count = sum(
                1
                for task in self._tasks.values()
                if task.status == TaskStatus.CANCELLED
            )

            return {
                "total_tasks": len(self._tasks),
                "pending_tasks": pending_count,
                "running_tasks": running_count,
                "completed_tasks": completed_count,
                "failed_tasks": failed_count,
                "cancelled_tasks": cancelled_count,
                "failed": failed_count,  # Legacy key for backward compatibility
                "task_counter": self._task_counter,
                "active_handlers": len(self._task_handlers),
            }

    def clear_completed_tasks(self, older_than: timedelta | None = None) -> int:
        """
        Clear completed tasks older than specified time.

        Args:
            older_than: Remove tasks older than this time

        Returns:
            Number of tasks cleared
        """
        cutoff = datetime.now() - (older_than or timedelta(days=1))

        to_remove = [
            task_id
            for task_id, task in self._completed_tasks.items()
            if task.completed_at and task.completed_at < cutoff
        ]

        for task_id in to_remove:
            if task_id in self._tasks:
                del self._tasks[task_id]
            if task_id in self._completed_tasks:
                del self._completed_tasks[task_id]

        return len(to_remove)

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running task.

        Args:
            task_id: Task ID to cancel

        Returns:
            True if cancelled, False if task not found or not running
        """
        task = self.get_task(task_id)
        if not task or task.status != TaskStatus.RUNNING:
            return False

        task.mark_cancelled()

        with self._lock:
            if task_id in self._running_tasks:
                del self._running_tasks[task_id]

            if task_id in self._pending_tasks:
                del self._pending_tasks[task_id]

        return True

    def get_task_dependencies(self, task_id: str) -> list[str]:
        """
        Get list of task IDs that depend on this task.

        Args:
            task_id: Task ID

        Returns:
            List of dependent task IDs
        """
        return [
            tid for tid, task in self._tasks.items() if task.parent_task_id == task_id
        ]


# Global task manager instance
_task_manager: TaskManager | None = None


def get_task_manager() -> TaskManager:
    """Get or create global task manager instance."""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager
