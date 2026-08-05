"""
Workflow Engine

Main orchestrator for the Workflow Engine.
Orchestrates workflows, triggers, and execution.
"""

import logging
import threading
from collections.abc import Callable
from typing import Any, Optional

from .models import WorkflowPriority, WorkflowStatus, WorkflowTriggerType
from .trigger_manager import TriggerManager
from .workflow import Workflow
from .workflow_executor import WorkflowExecutor
from .workflow_history import WorkflowHistory
from .workflow_manager import WorkflowManager

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """
    Main orchestrator for the Workflow Engine.

    The Workflow Engine sits above the Agent Runtime, orchestrating it
    for persistent automation scenarios.
    """

    def __init__(
        self,
        on_workflow_start: Callable[["WorkflowEngine", "Workflow"], None] | None = None,
        on_workflow_complete: (
            Callable[["WorkflowEngine", "Workflow", bool], None] | None
        ) = None,
        on_workflow_fail: (
            Callable[["WorkflowEngine", "Workflow", str], None] | None
        ) = None,
        on_trigger_fire: (
            Callable[["WorkflowEngine", "Workflow", dict[str, Any]], None] | None
        ) = None,
        agent_runtime=None,
    ):
        """
        Initialize Workflow Engine.

        Args:
            on_workflow_start: Callback when workflow starts
            on_workflow_complete: Callback when workflow completes
            on_workflow_fail: Callback when workflow fails
            on_trigger_fire: Callback when trigger fires
            agent_runtime: Agent Runtime instance for execution
        """
        # Callbacks
        self.on_workflow_start = on_workflow_start
        self.on_workflow_complete = on_workflow_complete
        self.on_workflow_fail = on_workflow_fail
        self.on_trigger_fire = on_trigger_fire

        # Core components
        self.workflow_manager = WorkflowManager()
        self.trigger_manager = TriggerManager(
            on_trigger_fire=self._on_trigger_fire, agent_runtime=agent_runtime
        )
        self.executor = WorkflowExecutor(
            on_step_start=self._on_step_start,
            on_step_complete=self._on_step_complete,
            on_step_fail=self._on_step_fail,
            on_workflow_start=self.on_workflow_start,
            on_workflow_complete=self.on_workflow_complete,
            on_workflow_fail=self.on_workflow_fail,
        )
        self.history = WorkflowHistory()

        # State
        self.is_running = False
        self.execution_thread: threading.Thread | None = None

        logger.info("Workflow Engine initialized")

    def create_workflow(
        self,
        name: str,
        description: str = "",
        trigger_type: WorkflowTriggerType = WorkflowTriggerType.MANUAL,
        trigger_config: dict[str, Any] | None = None,
        priority: WorkflowPriority = WorkflowPriority.NORMAL,
    ) -> str:
        """
        Create a new workflow.

        Args:
            name: Workflow name
            description: Workflow description
            trigger_type: Trigger type
            trigger_config: Trigger configuration
            priority: Workflow priority

        Returns:
            Workflow ID
        """
        workflow = self.workflow_manager.create_workflow(
            name=name,
            description=description,
            trigger_type=trigger_type,
            trigger_config=trigger_config or {},
            priority=priority,
        )
        return workflow.workflow_id

    def get_workflow(self, workflow_id: str) -> Optional["Workflow"]:
        """
        Get workflow by ID.

        Args:
            workflow_id: Workflow ID

        Returns:
            Workflow or None
        """
        return self.workflow_manager.get_workflow(workflow_id)

    def list_workflows(
        self,
        status: str | None = None,
        trigger_type: WorkflowTriggerType | None = None,
        active_only: bool = False,
    ) -> list["Workflow"]:
        """
        List workflows.

        Args:
            status: Filter by status
            trigger_type: Filter by trigger type
            active_only: Only return active workflows

        Returns:
            List of workflows
        """
        return self.workflow_manager.list_workflows(status, trigger_type, active_only)

    def run_workflow(
        self,
        workflow_id: str,
        context: dict[str, Any] | None = None,
        wait_for_completion: bool = True,
    ) -> bool:
        """
        Run a workflow.

        Args:
            workflow_id: Workflow ID
            context: Additional context
            wait_for_completion: Wait for workflow to complete

        Returns:
            Success
        """
        workflow = self.workflow_manager.get_workflow(workflow_id)
        if not workflow:
            logger.error(f"Workflow {workflow_id[:8]} not found")
            return False

        if workflow.status == WorkflowStatus.RUNNING:
            logger.error(f"Workflow {workflow_id[:8]} is already running")
            return False

        # Set context
        if context:
            workflow.set_context("run_context", context)

        # Execute workflow
        self.executor.execute_workflow(workflow_id, wait_for_completion)

        if wait_for_completion:
            # Wait for completion
            self.executor.wait_for_completion(workflow_id)

        return True

    def pause_workflow(self, workflow_id: str) -> bool:
        """
        Pause a running workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Success
        """
        workflow = self.workflow_manager.get_workflow(workflow_id)
        if not workflow or workflow.status != WorkflowStatus.RUNNING:
            return False

        self.executor.pause_workflow(workflow_id)
        workflow.mark_paused()

        return True

    def resume_workflow(self, workflow_id: str) -> bool:
        """
        Resume a paused workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Success
        """
        workflow = self.workflow_manager.get_workflow(workflow_id)
        if not workflow or workflow.status != WorkflowStatus.PAUSED:
            return False

        workflow.status = WorkflowStatus.RUNNING
        self.executor.resume_workflow(workflow_id)

        return True

    def cancel_workflow(self, workflow_id: str) -> bool:
        """
        Cancel a running workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Success
        """
        workflow = self.workflow_manager.get_workflow(workflow_id)
        if not workflow:
            return False

        self.executor.cancel_workflow(workflow_id)
        workflow.mark_cancelled()

        return True

    def schedule_workflow(
        self,
        workflow_id: str,
        schedule: str,
        timezone: str = "UTC",
        enabled: bool = True,
    ) -> bool:
        """
        Schedule a workflow.

        Args:
            workflow_id: Workflow ID
            schedule: Cron-style schedule
            timezone: Timezone
            enabled: Whether workflow is enabled

        Returns:
            Success
        """
        workflow = self.workflow_manager.get_workflow(workflow_id)
        if not workflow:
            return False

        workflow.trigger_config["schedule"] = schedule
        workflow.trigger_config["timezone"] = timezone
        workflow.trigger_config["enabled"] = enabled

        if enabled:
            workflow.trigger_type = WorkflowTriggerType.SCHEDULED
            self.trigger_manager.add_schedule(workflow_id, schedule, timezone)
            workflow.mark_scheduled()
        else:
            workflow.trigger_type = WorkflowTriggerType.MANUAL

        return True

    def trigger_workflow(
        self, workflow_id: str, trigger_data: dict[str, Any] | None = None
    ) -> bool:
        """
        Manually trigger a workflow.

        Args:
            workflow_id: Workflow ID
            trigger_data: Trigger data

        Returns:
            Success
        """
        workflow = self.workflow_manager.get_workflow(workflow_id)
        if not workflow:
            logger.error(f"Workflow {workflow_id[:8]} not found")
            return False

        # Set trigger data in context
        if trigger_data:
            workflow.set_context("trigger_data", trigger_data)

        # Execute workflow
        return self.run_workflow(workflow_id, wait_for_completion=False)

    def export_workflow(self, workflow_id: str, filepath: str) -> bool:
        """
        Export workflow to file.

        Args:
            workflow_id: Workflow ID
            filepath: Output filepath

        Returns:
            Success
        """
        workflow = self.workflow_manager.get_workflow(workflow_id)
        if not workflow:
            return False

        import json

        with open(filepath, "w") as f:
            json.dump(workflow.to_dict(), f, indent=2, default=str)

        logger.info(f"Exported workflow {workflow_id[:8]} to {filepath}")
        return True

    def import_workflow(self, filepath: str) -> Optional["Workflow"]:
        """
        Import workflow from file.

        Args:
            filepath: Input filepath

        Returns:
            Workflow or None
        """
        import json

        with open(filepath) as f:
            data = json.load(f)

        workflow = Workflow.from_dict(data)
        self.workflow_manager.add_workflow(workflow)

        logger.info(f"Imported workflow {workflow.workflow_id[:8]} from {filepath}")
        return workflow

    def get_history(self, workflow_id: str | None = None) -> list[dict[str, Any]]:
        """
        Get workflow execution history.

        Args:
            workflow_id: Filter by workflow ID

        Returns:
            List of history entries
        """
        return self.history.get_history(workflow_id)

    def get_statistics(self) -> dict[str, Any]:
        """
        Get workflow engine statistics.

        Returns:
            Statistics dictionary
        """
        workflows = self.workflow_manager.list_workflows()

        return {
            "total_workflows": len(workflows),
            "active_workflows": sum(1 for w in workflows if w.is_active),
            "running_workflows": sum(
                1 for w in workflows if w.status == WorkflowStatus.RUNNING
            ),
            "scheduled_workflows": sum(
                1 for w in workflows if w.trigger_type == WorkflowTriggerType.SCHEDULED
            ),
            "total_executions": sum(w.execution_count for w in workflows),
            "total_success": sum(w.success_count for w in workflows),
            "total_failures": sum(w.failure_count for w in workflows),
            "success_rate": (
                sum(w.success_count for w in workflows)
                / sum(w.execution_count for w in workflows)
                if any(w.execution_count for w in workflows)
                else 0
            ),
        }

    # Callback methods
    def _on_trigger_fire(self, workflow_id: str, trigger_data: dict[str, Any]):
        """Called when trigger fires."""
        logger.info(f"Trigger fired for workflow {workflow_id[:8]}")

        if self.on_trigger_fire:
            workflow = self.workflow_manager.get_workflow(workflow_id)
            self.on_trigger_fire(self, workflow, trigger_data)

    def _on_step_start(self, workflow_id: str, step_id: str):
        """Called when step starts."""
        logger.debug(f"Step {step_id[:8]} started in workflow {workflow_id[:8]}")

    def _on_step_complete(
        self, workflow_id: str, step_id: str, success: bool, output: Any
    ):
        """Called when step completes."""
        logger.debug(
            f"Step {step_id[:8]} completed in workflow {workflow_id[:8]}: {'success' if success else 'failed'}"
        )

    def _on_step_fail(self, workflow_id: str, step_id: str, error: str):
        """Called when step fails."""
        logger.error(
            f"Step {step_id[:8]} failed in workflow {workflow_id[:8]}: {error}"
        )
