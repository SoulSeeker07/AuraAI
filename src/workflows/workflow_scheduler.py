"""
Workflow Scheduler

Manages scheduled workflow execution (cron-like scheduling).
"""

import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

from croniter import croniter

from .models import WorkflowTriggerType
from .workflow_engine import WorkflowEngine

logger = logging.getLogger(__name__)


class WorkflowScheduler:
    """
    Manages scheduled workflow execution.
    """

    def __init__(
        self,
        engine: WorkflowEngine,
        on_schedule_trigger: Callable[[str, dict[str, Any]], None] | None = None,
        timezone: str = "UTC",
    ):
        """
        Initialize workflow scheduler.

        Args:
            engine: WorkflowEngine instance
            on_schedule_trigger: Callback when schedule triggers
            timezone: Timezone for scheduling
        """
        self.engine = engine
        self.on_schedule_trigger = on_schedule_trigger
        self.timezone = timezone

        # Scheduled workflows: workflow_id -> schedule_info
        self.schedules: dict[str, dict[str, Any]] = {}

        # Thread management
        self.scheduler_running = False
        self.scheduler_thread: threading.Thread | None = None

        # Last run times: workflow_id -> last_run_time
        self.last_run_times: dict[str, datetime] = {}

        logger.info("Workflow Scheduler initialized")

    def add_schedule(
        self, workflow_id: str, schedule: str, timezone: str = "UTC"
    ) -> bool:
        """
        Add schedule for workflow.

        Args:
            workflow_id: Workflow ID
            schedule: Cron-style schedule (e.g., "0 9 * * 1-5")
            timezone: Timezone

        Returns:
            Success
        """
        try:
            # Validate schedule format
            croniter(schedule, datetime.now(timezone))

            # Calculate next run time
            next_run = self._calculate_next_run(schedule, timezone)

            self.schedules[workflow_id] = {
                "schedule": schedule,
                "timezone": timezone,
                "next_run": next_run,
                "created_at": datetime.now(timezone),
                "last_run": None,
            }

            logger.info(f"Added schedule for workflow {workflow_id[:8]}: {schedule}")
            return True

        except Exception as e:
            logger.error(f"Invalid schedule format for workflow {workflow_id[:8]}: {e}")
            return False

    def remove_schedule(self, workflow_id: str) -> bool:
        """
        Remove schedule for workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Success
        """
        if workflow_id in self.schedules:
            del self.schedules[workflow_id]
            if workflow_id in self.last_run_times:
                del self.last_run_times[workflow_id]
            logger.info(f"Removed schedule for workflow {workflow_id[:8]}")
            return True
        return False

    def update_schedule(self, workflow_id: str, schedule: str) -> bool:
        """
        Update schedule for workflow.

        Args:
            workflow_id: Workflow ID
            schedule: New schedule

        Returns:
            Success
        """
        return self.add_schedule(workflow_id, schedule)

    def schedule_now(self, workflow_id: str) -> bool:
        """
        Trigger workflow immediately.

        Args:
            workflow_id: Workflow ID

        Returns:
            Success
        """
        if workflow_id not in self.schedules:
            logger.warning(
                f"Cannot schedule workflow {workflow_id[:8]}: no schedule found"
            )
            return False

        logger.info(f"Triggering workflow {workflow_id[:8]} immediately")
        self._trigger_workflow(workflow_id, WorkflowTriggerType.MANUAL)
        return True

    def start(self):
        """Start the scheduler."""
        if self.scheduler_running:
            logger.warning("Scheduler already running")
            return

        self.scheduler_running = True
        self.scheduler_thread = threading.Thread(
            target=self._scheduler_loop, daemon=True
        )
        self.scheduler_thread.start()

        logger.info("Workflow Scheduler started")

    def stop(self):
        """Stop the scheduler."""
        if not self.scheduler_running:
            return

        self.scheduler_running = False

        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)

        logger.info("Workflow Scheduler stopped")

    def _scheduler_loop(self):
        """
        Main scheduler loop.
        Checks schedules every second and triggers workflows when due.
        """
        while self.scheduler_running:
            try:
                self._check_schedules()
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)

    def _check_schedules(self):
        """Check all schedules and trigger workflows when due."""
        current_time = datetime.now(self.timezone)

        for workflow_id, schedule_info in list(self.schedules.items()):
            next_run = schedule_info.get("next_run")

            # Check if workflow should run now
            if next_run and current_time >= next_run:
                # Trigger workflow
                self._trigger_workflow(workflow_id, WorkflowTriggerType.SCHEDULED)

                # Calculate next run time
                cron = croniter(schedule_info["schedule"], current_time)
                next_run = cron.get_next(datetime)

                # Update schedule info
                self.schedules[workflow_id]["next_run"] = next_run
                self.schedules[workflow_id]["last_run"] = current_time

    def _trigger_workflow(self, workflow_id: str, trigger_type: WorkflowTriggerType):
        """
        Trigger workflow execution.

        Args:
            workflow_id: Workflow ID
            trigger_type: Trigger type
        """
        logger.info(f"Triggering workflow {workflow_id[:8]} via {trigger_type.value}")

        # Trigger callback
        if self.on_schedule_trigger:
            self.on_schedule_trigger(workflow_id, {"trigger_type": trigger_type})

        # Execute workflow
        self.engine.workflow_manager.execute_workflow(workflow_id)

    def _calculate_next_run(self, schedule: str, timezone: str) -> datetime:
        """
        Calculate next run time for schedule.

        Args:
            schedule: Cron schedule
            timezone: Timezone

        Returns:
            Next run datetime
        """
        return croniter(schedule, datetime.now(timezone)).get_next(datetime)

    def get_schedules(self) -> dict[str, dict[str, Any]]:
        """
        Get all scheduled workflows.

        Returns:
            Dictionary of workflow IDs to schedule info
        """
        return self.schedules.copy()

    def get_next_run_time(self, workflow_id: str) -> datetime | None:
        """
        Get next run time for a workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Next run datetime or None
        """
        if workflow_id in self.schedules:
            return self.schedules[workflow_id].get("next_run")
        return None

    def get_schedule(self, workflow_id: str) -> dict[str, Any] | None:
        """
        Get schedule info for a workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Schedule info or None
        """
        return self.schedules.get(workflow_id)

    def get_statistics(self) -> dict[str, Any]:
        """
        Get scheduler statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "total_scheduled": len(self.schedules),
            "schedules": list(self.schedules.keys()),
            "last_run_times": list(self.last_run_times.keys()),
            "scheduler_running": self.scheduler_running,
        }

    def pause_workflow(self, workflow_id: str) -> bool:
        """
        Pause a scheduled workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Success
        """
        if workflow_id in self.schedules:
            logger.info(f"Pausing workflow {workflow_id[:8]}")
            # Note: This is a placeholder. In a real implementation,
            # you might want to mark the workflow as paused in the manager
            return True
        return False

    def resume_workflow(self, workflow_id: str) -> bool:
        """
        Resume a paused workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Success
        """
        if workflow_id in self.schedules:
            logger.info(f"Resuming workflow {workflow_id[:8]}")
            # Note: This is a placeholder. In a real implementation,
            # you might want to update the last run time to force immediate execution
            return True
        return False
