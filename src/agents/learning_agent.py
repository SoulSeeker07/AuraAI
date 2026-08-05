"""
Learning Agent - Stores and retrieves workflow knowledge.

The Learning Agent can:
- Store workflow successes
- Track workflow failures
- Retrieve and reuse successful workflows
- Learn from user feedback
- Build knowledge about effective patterns
- Suggest optimized workflows
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .task_model import Task, TaskOutput


@dataclass
class WorkflowEntry:
    """Represents a learned workflow."""

    workflow_id: str
    name: str
    description: str
    inputs: dict[str, Any]
    steps: list[dict[str, Any]]
    success_count: int = 0
    failure_count: int = 0
    last_run: datetime = field(default_factory=datetime.now)
    success_rate: float = 0.0
    notes: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class LearningStats:
    """Statistics about learned workflows."""

    total_workflows: int = 0
    total_successes: int = 0
    total_failures: int = 0
    average_success_rate: float = 0.0
    most_used_workflow: str = ""
    most_successful_workflow: str = ""


class LearningAgent:
    """
    Stores and retrieves workflow knowledge.

    Capabilities:
    - Workflow storage
    - Success/failure tracking
    - Workflow retrieval and reuse
    - User feedback collection
    - Knowledge about effective patterns
    - Workflow optimization suggestions
    """

    def __init__(
        self, task_manager, knowledge_manager=None, storage_path: str = "data/learning"
    ):
        """
        Initialize the learning agent.

        Args:
            task_manager: TaskManager instance
            knowledge_manager: Optional knowledge brain manager
            storage_path: Path to store learning data
        """
        self.task_manager = task_manager
        self._knowledge = knowledge_manager
        self._storage_path = Path(storage_path)
        self._workflows: dict[str, WorkflowEntry] = {}

        # Create storage directory
        self._storage_path.mkdir(parents=True, exist_ok=True)

        # Load existing workflows
        self._load_workflows()

    def execute_task(self, task: Task) -> TaskOutput:
        """
        Execute a learning task.

        Args:
            task: Task to execute

        Returns:
            Task execution result
        """
        try:
            method = getattr(self, f"_execute_{task.type.value}", None)

            if not method:
                return TaskOutput(
                    success=False,
                    message=f"No handler for task type: {task.type.value}",
                    error=f"Task type {task.type.value} not supported",
                )

            return method(task)

        except Exception as e:
            return TaskOutput(
                success=False, message="Error executing task", error=str(e)
            )

    # ========================================
    # WORKFLOW STORAGE
    # ========================================

    def _execute_workflow_store(self, task: Task) -> TaskOutput:
        """Store a workflow execution."""
        workflow_name = task.input.get("workflow_name", "unnamed_workflow")
        inputs = task.input.get("inputs", {})
        steps = task.input.get("steps", [])
        outcome = task.input.get("outcome", "success")
        notes = task.input.get("notes", "")

        try:
            # Create workflow entry
            workflow_id = f"wf_{len(self._workflows) + 1}"

            workflow = WorkflowEntry(
                workflow_id=workflow_id,
                name=workflow_name,
                description=f"Workflow: {workflow_name}",
                inputs=inputs,
                steps=steps,
                notes=notes,
            )

            # Update stats
            if outcome == "success":
                workflow.success_count += 1
                workflow.success_rate = workflow.success_count / (
                    workflow.success_count + workflow.failure_count + 1
                )
            else:
                workflow.failure_count += 1
                workflow.success_rate = workflow.success_count / (
                    workflow.success_count + workflow.failure_count + 1
                )

            workflow.last_run = datetime.now()

            # Store in memory and disk
            self._workflows[workflow_id] = workflow
            self._save_workflow(workflow)

            # Add to knowledge brain if available
            if self._knowledge:
                self._add_to_knowledge_brain(workflow)

            return TaskOutput(
                success=True,
                message=f"Workflow stored: {workflow_name}",
                data={
                    "workflow_id": workflow_id,
                    "workflow_name": workflow_name,
                    "success_count": workflow.success_count,
                    "failure_count": workflow.failure_count,
                    "success_rate": workflow.success_rate,
                },
            )

        except Exception as e:
            return TaskOutput(
                success=False, message="Workflow storage failed", error=str(e)
            )

    def _save_workflow(self, workflow: WorkflowEntry):
        """Save workflow to disk."""
        file_path = self._storage_path / f"{workflow.workflow_id}.json"

        data = {
            "workflow_id": workflow.workflow_id,
            "name": workflow.name,
            "description": workflow.description,
            "inputs": workflow.inputs,
            "steps": workflow.steps,
            "success_count": workflow.success_count,
            "failure_count": workflow.failure_count,
            "last_run": workflow.last_run.isoformat(),
            "success_rate": workflow.success_rate,
            "notes": workflow.notes,
            "tags": workflow.tags,
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def _load_workflows(self):
        """Load workflows from disk."""
        if not self._storage_path.exists():
            return

        for json_file in self._storage_path.glob("*.json"):
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)

                workflow = WorkflowEntry(
                    workflow_id=data["workflow_id"],
                    name=data["name"],
                    description=data["description"],
                    inputs=data["inputs"],
                    steps=data["steps"],
                    success_count=data.get("success_count", 0),
                    failure_count=data.get("failure_count", 0),
                    notes=data.get("notes", ""),
                    tags=data.get("tags", []),
                )

                # Parse last_run datetime
                if "last_run" in data:
                    workflow.last_run = datetime.fromisoformat(data["last_run"])

                # Calculate success rate
                total_runs = workflow.success_count + workflow.failure_count
                if total_runs > 0:
                    workflow.success_rate = workflow.success_count / total_runs

                self._workflows[workflow.workflow_id] = workflow

            except Exception:
                continue

    # ========================================
    # WORKFLOW RETRIEVAL
    # ========================================

    def _execute_workflow_retrieve(self, task: Task) -> TaskOutput:
        """Retrieve a workflow by name or ID."""
        workflow_name = task.input.get("workflow_name")
        workflow_id = task.input.get("workflow_id")

        try:
            # Search for workflow
            workflow = None

            if workflow_id:
                workflow = self._workflows.get(workflow_id)
            elif workflow_name:
                for w in self._workflows.values():
                    if workflow_name.lower() in w.name.lower():
                        workflow = w
                        break

            if not workflow:
                return TaskOutput(
                    success=False,
                    message="Workflow not found",
                    error=f"No workflow found with name or ID: {workflow_name or workflow_id}",
                )

            return TaskOutput(
                success=True,
                message=f"Workflow retrieved: {workflow.name}",
                data={
                    "workflow_id": workflow.workflow_id,
                    "name": workflow.name,
                    "description": workflow.description,
                    "inputs": workflow.inputs,
                    "steps": workflow.steps,
                    "success_count": workflow.success_count,
                    "failure_count": workflow.failure_count,
                    "success_rate": workflow.success_rate,
                    "last_run": workflow.last_run.isoformat(),
                },
            )

        except Exception as e:
            return TaskOutput(
                success=False, message="Workflow retrieval failed", error=str(e)
            )

    def _execute_workflow_list(self, task: Task) -> TaskOutput:
        """List all stored workflows."""
        try:
            workflows = list(self._workflows.values())

            # Group by name
            grouped = {}
            for w in workflows:
                name = w.name
                if name not in grouped:
                    grouped[name] = []
                grouped[name].append(w)

            # Get summary
            summary = []
            for name, workflows_list in grouped.items():
                total_runs = sum(
                    w.success_count + w.failure_count for w in workflows_list
                )
                total_success = sum(w.success_count for w in workflows_list)
                success_rate = total_success / total_runs * 100 if total_runs > 0 else 0

                summary.append(
                    {
                        "name": name,
                        "count": len(workflows_list),
                        "total_runs": total_runs,
                        "success_count": total_success,
                        "failure_count": total_runs - total_success,
                        "success_rate": success_rate,
                    }
                )

            return TaskOutput(
                success=True,
                message=f"Found {len(workflows)} workflows",
                data={"workflows": summary, "count": len(workflows)},
            )

        except Exception as e:
            return TaskOutput(
                success=False, message="Workflow listing failed", error=str(e)
            )

    # ========================================
    # FEEDBACK COLLECTION
    # ========================================

    def _execute_workflow_feedback(self, task: Task) -> TaskOutput:
        """Collect feedback on a workflow execution."""
        workflow_id = task.input.get("workflow_id")
        rating = task.input.get("rating", 0)  # 1-5 stars
        comment = task.input.get("comment", "")

        try:
            workflow = self._workflows.get(workflow_id)
            if not workflow:
                return TaskOutput(
                    success=False,
                    message="Workflow not found",
                    error=f"Workflow ID not found: {workflow_id}",
                )

            # Update workflow based on feedback
            if rating >= 4:
                workflow.success_count += 1
            elif rating <= 2:
                workflow.failure_count += 1

            # Update success rate
            total_runs = workflow.success_count + workflow.failure_count
            if total_runs > 0:
                workflow.success_rate = workflow.success_count / total_runs

            workflow.last_run = datetime.now()
            workflow.notes += f"\nUser feedback: Rating {rating}/5. Comment: {comment}"

            # Save updated workflow
            self._save_workflow(workflow)

            return TaskOutput(
                success=True,
                message="Feedback recorded for workflow",
                data={
                    "workflow_id": workflow_id,
                    "rating": rating,
                    "comment": comment,
                    "success_count": workflow.success_count,
                    "failure_count": workflow.failure_count,
                },
            )

        except Exception as e:
            return TaskOutput(
                success=False, message="Feedback collection failed", error=str(e)
            )

    # ========================================
    # STATISTICS
    # ========================================

    def _execute_learning_stats(self, task: Task) -> TaskOutput:
        """Get learning statistics."""
        try:
            total_successes = sum(w.success_count for w in self._workflows.values())
            total_failures = sum(w.failure_count for w in self._workflows.values())
            total_runs = total_successes + total_failures
            avg_success_rate = (
                total_successes / total_runs * 100 if total_runs > 0 else 0
            )

            # Find most used
            most_used = max(
                self._workflows.values(),
                key=lambda w: w.success_count + w.failure_count,
                default=None,
            )

            # Find most successful
            most_successful = max(
                self._workflows.values(),
                key=lambda w: w.success_rate if w.success_rate > 0 else 0,
                default=None,
            )

            stats = LearningStats(
                total_workflows=len(self._workflows),
                total_successes=total_successes,
                total_failures=total_failures,
                average_success_rate=avg_success_rate,
                most_used_workflow=most_used.name if most_used else "None",
                most_successful_workflow=(
                    most_successful.name if most_successful else "None"
                ),
            )

            return TaskOutput(
                success=True,
                message="Learning statistics retrieved",
                data={
                    "workflows_count": stats.total_workflows,
                    "successes": stats.total_successes,
                    "failures": stats.total_failures,
                    "success_rate": f"{stats.average_success_rate:.1f}%",
                    "most_used": stats.most_used_workflow,
                    "most_successful": stats.most_successful_workflow,
                },
            )

        except Exception as e:
            return TaskOutput(
                success=False, message="Statistics retrieval failed", error=str(e)
            )

    # ========================================
    # KNOWLEDGE BRAIN INTEGRATION
    # ========================================

    def _add_to_knowledge_brain(self, workflow: WorkflowEntry):
        """Add workflow knowledge to knowledge brain."""
        if not self._knowledge:
            return

        try:
            # Add as a "fact" about the workflow
            fact_content = {
                "type": "workflow",
                "name": workflow.name,
                "success_rate": f"{workflow.success_rate * 100:.1f}%",
                "successes": workflow.success_count,
                "failures": workflow.failure_count,
                "last_run": workflow.last_run.isoformat(),
            }

            # In production, this would use knowledge brain APIs
            pass

        except Exception:
            pass

    def _execute_workflow_optimize(self, task: Task) -> TaskOutput:
        """Suggest optimizations for a workflow."""
        workflow_name = task.input.get("workflow_name")

        try:
            workflow = self._workflows.get(workflow_name)
            if not workflow:
                return TaskOutput(
                    success=False,
                    message="Workflow not found",
                    error=f"Workflow not found: {workflow_name}",
                )

            suggestions = []

            # Analyze success rate
            if workflow.success_rate < 0.5:
                suggestions.append(
                    {
                        "type": "risk",
                        "message": f"Low success rate ({workflow.success_rate * 100:.1f}%)",
                        "recommendation": "Review workflow steps and add error handling",
                    }
                )

            # Analyze step count
            if len(workflow.steps) > 10:
                suggestions.append(
                    {
                        "type": "complexity",
                        "message": "Complex workflow with many steps",
                        "recommendation": "Consider breaking into sub-workflows",
                    }
                )

            # Analyze recent failures
            if workflow.failure_count > workflow.success_count:
                suggestions.append(
                    {
                        "type": "warning",
                        "message": "More failures than successes",
                        "recommendation": "Review and improve workflow based on failures",
                    }
                )

            if not suggestions:
                suggestions.append(
                    {
                        "type": "success",
                        "message": "Workflow is well-optimized",
                        "recommendation": "Keep current implementation",
                    }
                )

            return TaskOutput(
                success=True,
                message="Workflow optimization suggestions",
                data={
                    "workflow_name": workflow.name,
                    "suggestions": suggestions,
                    "success_rate": workflow.success_rate,
                },
            )

        except Exception as e:
            return TaskOutput(
                success=False, message="Optimization suggestions failed", error=str(e)
            )
