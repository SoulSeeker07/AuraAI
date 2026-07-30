"""
Workflow Manager

Manages workflow lifecycle: create, edit, delete, version, export, import.
"""


import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid

from .workflow import Workflow
from .models import WorkflowStatus, WorkflowTriggerType, WorkflowPriority


logger = logging.getLogger(__name__)


class WorkflowManager:
    """
    Manages all workflows in the system.
    """

    def __init__(self):
        """Initialize workflow manager."""
        self.workflows: Dict[str, Workflow] = {}
        self.version_history: Dict[str, List[Workflow]] = {}  # workflow_id -> list of versions
        logger.info("Workflow Manager initialized")

    def create_workflow(
        self,
        name: str,
        description: str = "",
        trigger_type: WorkflowTriggerType = WorkflowTriggerType.MANUAL,
        trigger_config: Optional[Dict[str, Any]] = None,
        priority: WorkflowPriority = WorkflowPriority.NORMAL
    ) -> Workflow:
        """
        Create a new workflow.

        Args:
            name: Workflow name
            description: Workflow description
            trigger_type: Trigger type
            trigger_config: Trigger configuration
            priority: Workflow priority

        Returns:
            Workflow instance
        """
        workflow = Workflow(
            name=name,
            description=description,
            trigger_type=trigger_type,
            trigger_config=trigger_config or {},
            priority=priority
        )

        workflow.status = WorkflowStatus.DRAFT
        self.workflows[workflow.workflow_id] = workflow

        logger.info(f"Created workflow {workflow.workflow_id[:8]}: {name}")

        return workflow

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """
        Get workflow by ID.

        Args:
            workflow_id: Workflow ID

        Returns:
            Workflow or None
        """
        return self.workflows.get(workflow_id)

    def list_workflows(
        self,
        status: Optional[str] = None,
        trigger_type: Optional[WorkflowTriggerType] = None,
        active_only: bool = False
    ) -> List[Workflow]:
        """
        List workflows with optional filters.

        Args:
            status: Filter by status
            trigger_type: Filter by trigger type
            active_only: Only return active workflows

        Returns:
            List of workflows
        """
        workflows = list(self.workflows.values())

        if status:
            workflows = [w for w in workflows if w.status.value == status]

        if trigger_type:
            workflows = [w for w in workflows if w.trigger_type == trigger_type]

        if active_only:
            workflows = [w for w in workflows if w.is_active]

        return workflows

    def add_workflow(self, workflow: Workflow) -> 'WorkflowManager':
        """
        Add or update workflow.

        Args:
            workflow: Workflow to add

        Returns:
            Self for chaining
        """
        # Save current version to history
        if workflow.workflow_id in self.workflows:
            self._save_version(workflow.workflow_id)

        self.workflows[workflow.workflow_id] = workflow
        workflow.last_modified = datetime.now()

        if workflow.is_active:
            workflow.status = WorkflowStatus.DRAFT

        logger.info(f"Added/updated workflow {workflow.workflow_id[:8]}")

        return self

    def update_workflow(
        self,
        workflow_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        trigger_type: Optional[WorkflowTriggerType] = None,
        is_active: Optional[bool] = None
    ) -> Optional[Workflow]:
        """
        Update workflow properties.

        Args:
            workflow_id: Workflow ID
            name: New name
            description: New description
            trigger_type: New trigger type
            is_active: New active status

        Returns:
            Updated workflow or None
        """
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            logger.error(f"Workflow {workflow_id[:8]} not found")
            return None

        # Save version before modifying
        self._save_version(workflow_id)

        if name is not None:
            workflow.name = name

        if description is not None:
            workflow.description = description

        if trigger_type is not None:
            workflow.trigger_type = trigger_type

        if is_active is not None:
            workflow.is_active = is_active
            workflow.last_modified = datetime.now()

        logger.info(f"Updated workflow {workflow_id[:8]}")
        return workflow

    def delete_workflow(self, workflow_id: str) -> bool:
        """
        Delete workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Success
        """
        if workflow_id not in self.workflows:
            logger.error(f"Workflow {workflow_id[:8]} not found")
            return False

        workflow = self.workflows[workflow_id]
        logger.info(f"Deleted workflow {workflow_id[:8]}: {workflow.name}")

        del self.workflows[workflow_id]

        # Remove from version history
        if workflow_id in self.version_history:
            del self.version_history[workflow_id]

        return True

    def duplicate_workflow(self, workflow_id: str, new_name: Optional[str] = None) -> Optional[Workflow]:
        """
        Duplicate workflow.

        Args:
            workflow_id: Source workflow ID
            new_name: New name (optional)

        Returns:
            New workflow or None
        """
        original = self.workflows.get(workflow_id)
        if not original:
            logger.error(f"Workflow {workflow_id[:8]} not found")
            return None

        # Duplicate workflow
        new_workflow = Workflow(
            name=new_name or f"{original.name} (Copy)",
            description=f"Copy of {original.name}",
            trigger_type=original.trigger_type,
            trigger_config=original.trigger_config.copy(),
            priority=original.priority,
            is_active=True
        )

        # Copy steps
        for step in original.graph.steps.values():
            new_workflow.add_step(step)

        # Copy variables
        for var_name, var_data in original.variables.items():
            new_workflow.variables[var_name] = var_data.copy()

        # Copy context
        for key, value in original.context.items():
            new_workflow.context[key] = value

        self.add_workflow(new_workflow)

        logger.info(f"Duplicated workflow {workflow_id[:8]} to {new_workflow.workflow_id[:8]}")
        return new_workflow

    def get_versions(self, workflow_id: str) -> List[Workflow]:
        """
        Get workflow version history.

        Args:
            workflow_id: Workflow ID

        Returns:
            List of workflow versions
        """
        return self.version_history.get(workflow_id, [])

    def restore_version(self, workflow_id: str, version: Workflow) -> bool:
        """
        Restore workflow from a previous version.

        Args:
            workflow_id: Workflow ID
            version: Version to restore

        Returns:
            Success
        """
        if workflow_id not in self.workflows:
            logger.error(f"Workflow {workflow_id[:8]} not found")
            return False

        # Save current version to history
        self._save_version(workflow_id)

        # Restore the version
        self.workflows[workflow_id] = version
        version.last_modified = datetime.now()
        version.status = WorkflowStatus.DRAFT

        logger.info(f"Restored version of workflow {workflow_id[:8]}")
        return True

    def export_workflows(self, filepath: str) -> bool:
        """
        Export all workflows to file.

        Args:
            filepath: Output filepath

        Returns:
            Success
        """
        import json
        data = {
            'workflows': [w.to_dict() for w in self.workflows.values()],
            'exported_at': datetime.now().isoformat()
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(f"Exported {len(self.workflows)} workflows to {filepath}")
        return True

    def import_workflows(self, filepath: str) -> int:
        """
        Import workflows from file.

        Args:
            filepath: Input filepath

        Returns:
            Number of imported workflows
        """
        import json
        with open(filepath, 'r') as f:
            data = json.load(f)

        count = 0
        for workflow_data in data.get('workflows', []):
            workflow = Workflow.from_dict(workflow_data)
            self.add_workflow(workflow)
            count += 1

        logger.info(f"Imported {count} workflows from {filepath}")
        return count

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get workflow manager statistics.

        Returns:
            Statistics dictionary
        """
        workflows = list(self.workflows.values())

        return {
            'total_workflows': len(workflows),
            'active_workflows': sum(1 for w in workflows if w.is_active),
            'running_workflows': sum(1 for w in workflows if w.status.value == 'running'),
            'draft_workflows': sum(1 for w in workflows if w.status.value == 'draft'),
            'completed_workflows': sum(1 for w in workflows if w.status.value == 'completed'),
            'failed_workflows': sum(1 for w in workflows if w.status.value == 'failed'),
            'scheduled_workflows': sum(1 for w in workflows if w.trigger_type.value == 'scheduled'),
            'trigger_types': {
                'manual': sum(1 for w in workflows if w.trigger_type.value == 'manual'),
                'scheduled': sum(1 for w in workflows if w.trigger_type.value == 'scheduled'),
                'event': sum(1 for w in workflows if w.trigger_type.value == 'event'),
                'workspace': sum(1 for w in workflows if w.trigger_type.value == 'workspace'),
                'voice': sum(1 for w in workflows if w.trigger_type.value == 'voice'),
                'plugin': sum(1 for w in workflows if w.trigger_type.value == 'plugin')
            },
            'total_executions': sum(w.execution_count for w in workflows),
            'total_success': sum(w.success_count for w in workflows),
            'total_failures': sum(w.failure_count for w in workflows)
        }

    def _save_version(self, workflow_id: str):
        """Save current workflow version to history."""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return

        if workflow_id not in self.version_history:
            self.version_history[workflow_id] = []

        # Keep last 10 versions
        self.version_history[workflow_id].append(workflow)
        if len(self.version_history[workflow_id]) > 10:
            self.version_history[workflow_id].pop(0)
