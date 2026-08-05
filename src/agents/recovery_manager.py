"""
Recovery Manager

Handles failure recovery strategies and retry logic.
"""

import logging
import random
from collections.abc import Callable
from datetime import datetime
from typing import Any

from .models import RetryPolicy
from .task import Task

logger = logging.getLogger(__name__)


class RecoveryManager:
    """
    Manages failure recovery strategies.

    The Recovery Manager determines appropriate recovery actions when tasks fail,
    including retry, pause, notify, and continue strategies.
    """

    def __init__(
        self,
        on_recover: Callable[["RecoveryManager", Task, str], None] | None = None,
        on_fail_permanently: Callable[["RecoveryManager", Task], None] | None = None,
        on_pause: Callable[["RecoveryManager", Task], None] | None = None,
        max_retries_per_task: int = 3,
        retry_backoff: int = 2,  # Exponential backoff multiplier
    ):
        """
        Initialize recovery manager.

        Args:
            on_recover: Callback when recovery is applied
            on_fail_permanently: Callback when task fails permanently
            on_pause: Callback when task is paused for recovery
            max_retries_per_task: Maximum retries per task
            retry_backoff: Exponential backoff multiplier
        """
        self.on_recover = on_recover
        self.on_fail_permanently = on_fail_permanently
        self.on_pause = on_pause
        self.max_retries_per_task = max_retries_per_task
        self.retry_backoff = retry_backoff

        # Recovery statistics
        self.total_failures = 0
        self.total_recovered = 0
        self.total_permanently_failed = 0
        self.total_paused = 0
        self.recovery_actions: list[dict[str, Any]] = []

        logger.debug("Initialized recovery manager")

    def handle_task_failure(self, task: Task) -> str | None:
        """
        Handle task failure and determine recovery action.

        Args:
            task: Task that failed

        Returns:
            Recovery action ('retry', 'pause', 'notify', 'continue')
        """
        self.total_failures += 1
        recovery_action = None

        logger.error(f"Task {task.task_id[:8]} failed: {task.error}")

        # Check if task should be retried
        if task.should_retry:
            recovery_action = self._determine_recovery_action(task)
        else:
            recovery_action = "continue"
            self.total_permanently_failed += 1
            logger.error(f"Task {task.task_id[:8]} failed permanently")

        # Execute recovery action
        if recovery_action:
            self._execute_recovery(task, recovery_action)

        return recovery_action

    def _determine_recovery_action(self, task: Task) -> str:
        """
        Determine appropriate recovery action.

        Args:
            task: Failed task

        Returns:
            Recovery action
        """
        # Get retry count
        retry_count = task.retry_count

        # Check if out of retries
        if retry_count >= task.max_retries:
            return "continue"

        # Check retry policy
        if task.retry_policy == RetryPolicy.NO_RETRY:
            return "continue"

        # For network errors, retry more aggressively
        if "network" in task.error.lower() or "connection" in task.error.lower():
            return "retry"

        # For temporary errors, retry
        if "timeout" in task.error.lower() or "temporary" in task.error.lower():
            return "retry"

        # For file errors, pause and notify
        if "file" in task.error.lower() or "permission" in task.error.lower():
            return "pause"

        # For database errors, pause and notify
        if "database" in task.error.lower() or "sql" in task.error.lower():
            return "pause"

        # Default: retry with backoff
        return "retry"

    def _execute_recovery(self, task: Task, action: str):
        """
        Execute recovery action.

        Args:
            task: Task to recover
            action: Recovery action to execute
        """
        recovery_log = {
            "task_id": task.task_id,
            "action": action,
            "retry_count": task.retry_count,
            "max_retries": task.max_retries,
            "error": task.error,
            "recovered_at": datetime.now().isoformat(),
            "strategy": self._get_recovery_strategy(task),
        }

        if action == "retry":
            self._execute_retry(task)
            recovery_log["strategy"] = "retry_with_backoff"
            self.total_recovered += 1
            logger.info(f"Task {task.task_id[:8]} will be retried")

        elif action == "pause":
            self._execute_pause(task)
            recovery_log["strategy"] = "pause_for_user_action"
            self.total_paused += 1
            logger.info(f"Task {task.task_id[:8]} paused for user action")

        elif action == "notify":
            self._execute_notify(task)
            recovery_log["strategy"] = "notify_and_continue"
            logger.info(f"Task {task.task_id[:8]} notified and will continue")

        elif action == "continue":
            self._execute_continue(task)
            recovery_log["strategy"] = "continue_without_recovery"
            logger.info(f"Task {task.task_id[:8]} will continue without recovery")

        self.recovery_actions.append(recovery_log)

        if self.on_recover:
            self.on_recover(self, task, action)

    def _execute_retry(self, task: Task):
        """
        Execute retry strategy.

        Args:
            task: Task to retry
        """
        # Increment retry count
        task.retry_count += 1

        # Apply exponential backoff
        delay = self._calculate_retry_delay(task)

        logger.info(
            f"Retrying task {task.task_id[:8]} "
            f"(attempt {task.retry_count}/{task.max_retries}) "
            f"in {delay} seconds"
        )

        # Reset task status and allow retry
        task.status = "QUEUED"

    def _calculate_retry_delay(self, task: Task) -> int:
        """
        Calculate retry delay with exponential backoff.

        Args:
            task: Task to retry

        Returns:
            Delay in seconds
        """
        # Exponential backoff: base * (backoff ^ retry_count)
        delay = min(300, 2**task.retry_count)  # Max 5 minutes

        # Add jitter to prevent thundering herd
        jitter = random.uniform(0, 1) * delay * 0.1
        delay += jitter

        return int(delay)

    def _execute_pause(self, task: Task):
        """
        Execute pause strategy.

        Args:
            task: Task to pause
        """
        logger.warning(f"Pausing task {task.task_id[:8]} for recovery")

        if self.on_pause:
            self.on_pause(self, task)

        # Task is paused - will resume when user intervenes

    def _execute_notify(self, task: Task):
        """
        Execute notify strategy.

        Args:
            task: Task that failed
        """
        logger.info(f"Notifying about task {task.task_id[:8]} failure: {task.error}")

        # Task will continue but with the error recorded

    def _execute_continue(self, task: Task):
        """
        Execute continue strategy (no recovery).

        Args:
            task: Task to continue
        """
        logger.info(f"Continuing with task {task.task_id[:8]} despite failure")

        # Task will continue to next step in execution

    def _get_recovery_strategy(self, task: Task) -> str:
        """
        Get descriptive recovery strategy.

        Args:
            task: Task that failed

        Returns:
            Strategy description
        """
        if task.retry_count >= task.max_retries:
            return f"no_retry_{task.max_retries}"
        elif task.retry_policy == RetryPolicy.NO_RETRY:
            return "no_retry_policy"
        elif "network" in task.error.lower():
            return "network_retry"
        elif "timeout" in task.error.lower():
            return "timeout_retry"
        elif "file" in task.error.lower():
            return "file_pause"
        elif "database" in task.error.lower():
            return "database_pause"
        else:
            return "default_retry"

    def get_recovered_tasks(self) -> list[Task]:
        """
        Get all tasks that were recovered.

        Returns:
            List of recovered tasks
        """
        recovered = []

        for action in self.recovery_actions:
            if action["action"] == "retry":
                task_id = action["task_id"]
                # In a real implementation, we'd look up the task from the graph
                # This is a placeholder

        return recovered

    def get_statistics(self) -> dict[str, Any]:
        """
        Get recovery manager statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "total_failures": self.total_failures,
            "total_recovered": self.total_recovered,
            "total_permanently_failed": self.total_permanently_failed,
            "total_paused": self.total_paused,
            "success_rate": (
                (self.total_recovered / self.total_failures * 100)
                if self.total_failures > 0
                else 0.0
            ),
            "recovery_actions": self.recovery_actions[-10:],  # Last 10 actions
        }

    def get_failure_summary(self) -> dict[str, Any]:
        """
        Get summary of failures by recovery type.

        Returns:
            Summary dictionary
        """
        summary = {"by_action": {}, "by_strategy": {}}

        for action in self.recovery_actions:
            action_type = action["action"]
            strategy = action["strategy"]

            summary["by_action"][action_type] = (
                summary["by_action"].get(action_type, 0) + 1
            )
            summary["by_strategy"][strategy] = (
                summary["by_strategy"].get(strategy, 0) + 1
            )

        return summary

    def clear_history(self):
        """Clear recovery history."""
        self.recovery_actions.clear()
        logger.debug("Recovery history cleared")
