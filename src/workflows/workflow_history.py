"""
Workflow History

Tracks workflow execution history with filtering and statistics.
"""

import logging
from datetime import datetime
from typing import Any

from .models import WorkflowStatus

logger = logging.getLogger(__name__)


class WorkflowHistory:
    """
    Tracks workflow execution history.
    """

    def __init__(self):
        """Initialize workflow history."""
        self.history: list[dict[str, Any]] = []
        logger.info("Workflow History initialized")

    def log_execution(
        self,
        workflow_id: str,
        workflow_name: str,
        status: WorkflowStatus,
        start_time: datetime,
        end_time: datetime | None = None,
        duration: float | None = None,
        error: str | None = None,
        steps_completed: int = 0,
        steps_failed: int = 0,
        trigger_type: str | None = None,
        trigger_data: dict[str, Any] | None = None,
    ):
        """
        Log a workflow execution.

        Args:
            workflow_id: Workflow ID
            workflow_name: Workflow name
            status: Execution status
            start_time: Start time
            end_time: End time
            duration: Duration in seconds
            error: Error message if failed
            steps_completed: Number of steps completed
            steps_failed: Number of steps failed
            trigger_type: Type of trigger
            trigger_data: Trigger data
        """
        entry = {
            "workflow_id": workflow_id,
            "workflow_name": workflow_name,
            "status": status.value,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat() if end_time else None,
            "duration": duration,
            "error": error,
            "steps_completed": steps_completed,
            "steps_failed": steps_failed,
            "trigger_type": trigger_type,
            "trigger_data": trigger_data,
            "logged_at": datetime.now().isoformat(),
        }

        self.history.append(entry)

        logger.info(f"Logged workflow execution {workflow_id[:8]}: {status.value}")

    def log_step_completion(
        self,
        workflow_id: str,
        step_id: str,
        step_name: str,
        success: bool,
        output: Any = None,
        duration: float | None = None,
    ):
        """
        Log step completion.

        Args:
            workflow_id: Workflow ID
            step_id: Step ID
            step_name: Step name
            success: Whether step succeeded
            output: Step output
            duration: Duration in seconds
        """
        entry = {
            "workflow_id": workflow_id,
            "step_id": step_id,
            "step_name": step_name,
            "success": success,
            "output": str(output) if output else None,
            "duration": duration,
            "logged_at": datetime.now().isoformat(),
        }

        self.history.append(entry)

        logger.debug(
            f"Logged step completion {step_id[:8]} in workflow {workflow_id[:8]}"
        )

    def log_step_failure(
        self,
        workflow_id: str,
        step_id: str,
        step_name: str,
        error: str,
        duration: float | None = None,
    ):
        """
        Log step failure.

        Args:
            workflow_id: Workflow ID
            step_id: Step ID
            step_name: Step name
            error: Error message
            duration: Duration in seconds
        """
        entry = {
            "workflow_id": workflow_id,
            "step_id": step_id,
            "step_name": step_name,
            "success": False,
            "error": error,
            "duration": duration,
            "logged_at": datetime.now().isoformat(),
        }

        self.history.append(entry)

        logger.error(
            f"Logged step failure {step_id[:8]} in workflow {workflow_id[:8]}: {error}"
        )

    def filter_history(
        self,
        workflow_id: str | None = None,
        status: str | None = None,
        trigger_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Filter execution history.

        Args:
            workflow_id: Filter by workflow ID
            status: Filter by status
            trigger_type: Filter by trigger type
            start_time: Filter by start time
            end_time: Filter by end time
            limit: Maximum number of results

        Returns:
            List of filtered entries
        """
        filtered = self.history.copy()

        # Filter by workflow ID
        if workflow_id:
            filtered = [
                entry for entry in filtered if entry["workflow_id"] == workflow_id
            ]

        # Filter by status
        if status:
            filtered = [entry for entry in filtered if entry["status"] == status]

        # Filter by trigger type
        if trigger_type:
            filtered = [
                entry for entry in filtered if entry["trigger_type"] == trigger_type
            ]

        # Filter by start time
        if start_time:
            filtered = [
                entry
                for entry in filtered
                if datetime.fromisoformat(entry["start_time"]) >= start_time
            ]

        # Filter by end time
        if end_time:
            filtered = [
                entry
                for entry in filtered
                if datetime.fromisoformat(entry["start_time"]) <= end_time
            ]

        # Sort by start time (newest first)
        filtered.sort(
            key=lambda x: datetime.fromisoformat(x["start_time"]), reverse=True
        )

        # Limit results
        return filtered[:limit]

    def get_statistics(self, workflow_id: str | None = None) -> dict[str, Any]:
        """
        Get execution statistics.

        Args:
            workflow_id: Filter by workflow ID

        Returns:
            Statistics dictionary
        """
        filtered = self.filter_history(workflow_id=workflow_id)

        if not filtered:
            return {
                "total_executions": 0,
                "success_count": 0,
                "failure_count": 0,
                "success_rate": 0.0,
                "avg_duration": 0.0,
            }

        total_executions = len(filtered)
        success_count = sum(1 for entry in filtered if entry["status"] == "completed")
        failure_count = sum(1 for entry in filtered if entry["status"] == "failed")
        success_rate = success_count / total_executions if total_executions > 0 else 0.0

        durations = [
            entry["duration"] for entry in filtered if entry["duration"] is not None
        ]
        avg_duration = sum(durations) / len(durations) if durations else 0.0

        return {
            "total_executions": total_executions,
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": success_rate,
            "avg_duration": avg_duration,
        }

    def get_workflow_summary(self, workflow_id: str) -> dict[str, Any] | None:
        """
        Get summary for a specific workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Summary dictionary
        """
        executions = self.filter_history(workflow_id=workflow_id)

        if not executions:
            return None

        return {
            "workflow_id": workflow_id,
            "total_executions": len(executions),
            "success_count": sum(1 for e in executions if e["status"] == "completed"),
            "failure_count": sum(1 for e in executions if e["status"] == "failed"),
            "avg_duration": sum(e["duration"] for e in executions if e["duration"])
            / len(executions),
            "last_executed": max(e["start_time"] for e in executions),
            "most_recent_trigger": executions[0].get("trigger_type"),
        }

    def export_history(
        self, workflow_id: str | None = None, filepath: str | None = None
    ) -> str:
        """
        Export execution history to file.

        Args:
            workflow_id: Filter by workflow ID
            filepath: Output filepath (auto-generated if not provided)

        Returns:
            Filepath
        """
        filtered = self.filter_history(workflow_id=workflow_id)

        if filepath is None:
            import os
            from datetime import datetime

            data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
            os.makedirs(data_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(data_dir, f"workflow_history_{timestamp}.json")

        import json

        with open(filepath, "w") as f:
            json.dump(filtered, f, indent=2, default=str)

        logger.info(f"Exported {len(filtered)} history entries to {filepath}")
        return filepath

    def clear_history(self):
        """Clear all history."""
        self.history.clear()
        logger.info("Cleared workflow history")

    def get_history_count(self) -> int:
        """
        Get total number of history entries.

        Returns:
            Count
        """
        return len(self.history)

    def get_recent_executions(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get most recent executions.

        Args:
            limit: Maximum number of results

        Returns:
            List of recent executions
        """
        return self.filter_history(limit=limit)
