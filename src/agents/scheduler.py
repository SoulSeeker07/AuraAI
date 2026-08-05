"""
Scheduler

Handles task scheduling and parallel execution based on dependencies.
"""

import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from queue import Queue
from typing import Any

from .execution_graph import ExecutionGraph
from .models import TaskPriority, TaskStatus
from .task import Task

logger = logging.getLogger(__name__)


class ExecutionStrategy(Enum):
    """Execution strategies for task scheduling."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    BALANCED = "balanced"


class Scheduler:
    """
    Manages task scheduling and parallel execution.

    The Scheduler takes tasks from the Execution Graph and executes them
    based on dependencies and configured execution strategy.
    """

    def __init__(
        self,
        execution_strategy: ExecutionStrategy = ExecutionStrategy.BALANCED,
        max_workers: int = 4,
        max_parallel_groups: int = 2,
        on_task_complete: Callable[[Task], None] | None = None,
        on_task_fail: Callable[[Task], None] | None = None,
        on_task_progress: Callable[[Task, float], None] | None = None,
    ):
        """
        Initialize scheduler.

        Args:
            execution_strategy: How to execute tasks (sequential, parallel, balanced)
            max_workers: Maximum number of concurrent workers
            max_parallel_groups: Maximum number of parallel task groups
            on_task_complete: Callback when task completes
            on_task_fail: Callback when task fails
            on_task_progress: Callback for task progress updates
        """
        self.execution_strategy = execution_strategy
        self.max_workers = max_workers
        self.max_parallel_groups = max_parallel_groups

        # Callbacks
        self.on_task_complete = on_task_complete
        self.on_task_fail = on_task_fail
        self.on_task_progress = on_task_progress

        # Execution state
        self.running = False
        self.execution_graph: ExecutionGraph | None = None
        self.completed_tasks: list[Task] = []
        self.failed_tasks: list[Task] = []

        # Thread pool
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        # Task queue
        self.task_queue = Queue()

        logger.debug(
            f"Initialized scheduler with {execution_strategy.value} strategy, {max_workers} workers"
        )

    def schedule_graph(self, graph: ExecutionGraph):
        """
        Schedule all tasks in the execution graph.

        Args:
            graph: Execution graph to schedule
        """
        if not graph:
            logger.warning("No execution graph provided")
            return

        self.execution_graph = graph
        self.running = True
        self.completed_tasks = []
        self.failed_tasks = []

        logger.info(
            f"Scheduling {len(graph.tasks)} tasks for goal {graph.goal.goal_id[:8]}"
        )

        # Build task queue
        ready_tasks = graph.get_ready_tasks()
        for task in ready_tasks:
            self.task_queue.put(task)

        # Start execution
        self._start_execution()

    def _start_execution(self):
        """Start the execution thread."""
        thread = threading.Thread(target=self._execution_loop, daemon=True)
        thread.start()
        logger.debug("Scheduler execution thread started")

    def _execution_loop(self):
        """Main execution loop."""
        logger.info("Scheduler execution loop started")

        while self.running:
            try:
                task = self.task_queue.get(timeout=0.1)

                if task is None:
                    # Sentinel to stop execution
                    break

                # Execute task
                self._execute_task(task)

            except Exception as e:
                logger.error(f"Error in execution loop: {e}")

        logger.info("Scheduler execution loop stopped")

    def _execute_task(self, task: Task):
        """
        Execute a single task.

        Args:
            task: Task to execute
        """
        logger.info(f"Executing task {task.task_id[:8]}: {task.goal[:50]}")

        task.mark_started()

        # Set progress callback
        task.on_progress = self._on_task_progress

        try:
            # Execute task
            result = self._run_task(task)

            # Task completed successfully
            task.mark_completed(output=result)

            if self.on_task_complete:
                self.on_task_complete(task)

            self.completed_tasks.append(task)

            # Process dependent tasks
            self._process_dependents(task)

        except Exception as e:
            # Task failed
            task.mark_failed(str(e))
            self.failed_tasks.append(task)

            if self.on_task_fail:
                self.on_task_fail(task)

            # Check if task should be retried
            if task.should_retry:
                logger.info(
                    f"Retrying task {task.task_id[:8]} (attempt {task.retry_count + 1}/{task.max_retries})"
                )
                task.retry_count += 1
                self.task_queue.put(task)
            else:
                logger.error(f"Task {task.task_id[:8]} failed permanently")

    def _run_task(self, task: Task) -> Any:
        """
        Run a task (placeholder - actual execution via Tool Engine).

        Args:
            task: Task to execute

        Returns:
            Task result
        """
        # This is a placeholder - actual execution should be done
        # through the Tool Execution Engine
        logger.debug(f"Task {task.task_id[:8]} execution placeholder")

        # Simulate task execution
        import time

        time.sleep(0.1)

        return f"Result for {task.goal}"

    def _process_dependents(self, completed_task: Task):
        """
        Process dependent tasks after a task completes.

        Args:
            completed_task: Task that just completed
        """
        graph = self.execution_graph
        if not graph:
            return

        # Find all tasks that depend on this task
        for task_id, task in graph.tasks.items():
            if task.task_id in graph.adjacency.get(completed_task.task_id, set()):
                # Check if dependencies are met
                if task.is_ready:
                    self.task_queue.put(task)

        # Check if all tasks are done
        if not graph.get_ready_tasks() and not self.task_queue.empty():
            self.running = False

    def _on_task_progress(self, task: Task, progress: float):
        """
        Handle task progress update.

        Args:
            task: Task with updated progress
            progress: New progress value (0.0 - 1.0)
        """
        logger.debug(f"Task {task.task_id[:8]} progress: {progress*100:.1f}%")

        if self.on_task_progress:
            self.on_task_progress(task, progress)

    def get_execution_stats(self) -> dict[str, Any]:
        """
        Get scheduler execution statistics.

        Returns:
            Statistics dictionary
        """
        graph = self.execution_graph
        if not graph:
            return {
                "status": "idle",
                "total_tasks": 0,
                "completed_tasks": 0,
                "failed_tasks": 0,
                "running_tasks": 0,
            }

        return {
            "status": "running" if self.running else "stopped",
            "execution_strategy": self.execution_strategy.value,
            "max_workers": self.max_workers,
            "total_tasks": len(graph.tasks),
            "completed_tasks": len(self.completed_tasks),
            "failed_tasks": len(self.failed_tasks),
            "running_tasks": sum(
                1 for t in graph.tasks.values() if t.status == TaskStatus.RUNNING
            ),
            "ready_tasks": len(graph.get_ready_tasks()),
        }

    def cancel_all(self):
        """Cancel all pending tasks."""
        self.running = False
        logger.info("Cancelled all pending tasks")

    def wait_for_completion(self, timeout: float | None = None) -> bool:
        """
        Wait for all tasks to complete.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if all tasks completed, False if timeout
        """
        import time

        start_time = time.time()
        while self.running:
            elapsed = time.time() - start_time
            if timeout and elapsed >= timeout:
                return False
            time.sleep(0.1)

        return True

    def shutdown(self):
        """Shutdown the scheduler."""
        self.running = False
        self.executor.shutdown(wait=True)
        logger.debug("Scheduler shutdown complete")

    def get_failed_tasks(self) -> list[Task]:
        """
        Get all failed tasks.

        Returns:
            List of failed tasks
        """
        return self.failed_tasks.copy()

    def get_completed_tasks(self) -> list[Task]:
        """
        Get all completed tasks.

        Returns:
            List of completed tasks
        """
        return self.completed_tasks.copy()

    def get_statistics_by_priority(self) -> dict[str, int]:
        """
        Get statistics by task priority.

        Returns:
            Dictionary mapping priority to count
        """
        if not self.execution_graph:
            return {}

        stats = {priority.value: 0 for priority in TaskPriority}

        for task in self.execution_graph.tasks.values():
            if task.status == TaskStatus.COMPLETED:
                stats[task.priority.value] += 1

        return stats
