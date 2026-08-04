"""
Workflow Data Model

Defines the structure of a workflow, including steps, triggers, variables, and conditions.
"""


from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
from enum import Enum, auto
import logging

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Workflow status states."""
    CREATED = "created"
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowType(Enum):
    """Workflow type categorization."""
    SCRIPTED = "scripted"
    AUTOMATED = "automated"
    SCHEDULED = "scheduled"
    EVENT_TRIGGERED = "event_triggered"
    MANUAL = "manual"
    CONTEXTUAL = "contextual"


class TriggerType(Enum):
    """Trigger type enumeration."""
    MANUAL = "manual"
    SCHEDULE = "scheduled"
    EVENT = "event"
    WORKSPACE = "workspace"
    VOICE = "voice"
    PLUGIN = "plugin"
    TIME_WINDOW = "time_window"
    CONDITION = "condition"


@dataclass
class Workflow:
    """
    A workflow represents a reusable automation sequence.

    Workflows can be:
    - Scripted: Manual execution with predefined steps
    - Automated: Runs based on triggers (schedule, event, etc.)
    - Scheduled: Runs at specific times
    - Event Triggered: Runs on specific events
    - Contextual: Runs based on workspace/context
    """

    # Core information
    name: str
    description: str
    workflow_id: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    version: int = 1

    # Workflow metadata
    type: WorkflowType = WorkflowType.SCRIPTED
    status: WorkflowStatus = WorkflowStatus.CREATED
    tags: List[str] = field(default_factory=list)
    category: Optional[str] = None
    author: Optional[str] = None
    icon: Optional[str] = None
    is_public: bool = False

    # Trigger configuration
    trigger_type: TriggerType = TriggerType.MANUAL
    trigger_config: Optional[Dict[str, Any]] = None

    # Variables
    variables: Dict[str, Any] = field(default_factory=dict)
    variable_schema: Optional[Dict[str, Dict[str, Any]]] = None

    # Steps
    steps: List['WorkflowStep'] = field(default_factory=list)

    # Error handling
    on_error: str = "stop"  # stop, continue, retry, ask_user
    max_retries: int = 3
    retry_delay: int = 0  # seconds

    # Metadata
    tags: List[str] = field(default_factory=list)
    notes: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None

    # Execution context
    execution_context: Optional[Dict[str, Any]] = None

    def add_step(self, step: 'WorkflowStep'):
        """Add a step to the workflow."""
        step.step_id = f"step_{len(self.steps)}_{datetime.now().timestamp()}"
        self.steps.append(step)
        self.updated_at = datetime.now()
        logger.info(f"Added step {step.step_id[:8]} to workflow {self.workflow_id[:8]}")

    def remove_step(self, step_id: str) -> bool:
        """Remove a step by ID."""
        for i, step in enumerate(self.steps):
            if step.step_id == step_id:
                self.steps.pop(i)
                self.updated_at = datetime.now()
                logger.info(f"Removed step {step_id[:8]} from workflow {self.workflow_id[:8]}")
                return True
        return False

    def update_step(self, step_id: str, **kwargs):
        """Update a step's properties."""
        for step in self.steps:
            if step.step_id == step_id:
                for key, value in kwargs.items():
                    setattr(step, key, value)
                self.updated_at = datetime.now()
                logger.info(f"Updated step {step_id[:8]} in workflow {self.workflow_id[:8]}")
                return
        logger.warning(f"Step {step_id[:8]} not found in workflow {self.workflow_id[:8]}")

    def get_step(self, step_id: str) -> Optional['WorkflowStep']:
        """Get a step by ID."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def get_next_step_id(self, current_step_id: Optional[str] = None) -> Optional[str]:
        """Get the ID of the next step after the current step."""
        if not self.steps:
            return None

        if current_step_id is None:
            return self.steps[0].step_id

        for i, step in enumerate(self.steps):
            if step.step_id == current_step_id:
                if i + 1 < len(self.steps):
                    return self.steps[i + 1].step_id
                else:
                    return None

        return None

    def get_previous_step_id(self, current_step_id: str) -> Optional[str]:
        """Get the ID of the previous step."""
        for i, step in enumerate(self.steps):
            if step.step_id == current_step_id:
                if i > 0:
                    return self.steps[i - 1].step_id
                else:
                    return None

        return None

    def get_step_dependencies(self, step_id: str) -> List[str]:
        """Get IDs of steps this step depends on."""
        step = self.get_step(step_id)
        if step:
            return step.dependencies
        return []

    def is_step_dependent(self, step_id: str, dependent_on_step_id: str) -> bool:
        """Check if a step depends on another step."""
        dependencies = self.get_step_dependencies(step_id)
        return dependent_on_step_id in dependencies

    def mark_started(self):
        """Mark workflow as started."""
        self.status = WorkflowStatus.ACTIVE

    def mark_completed(self):
        """Mark workflow as completed."""
        self.status = WorkflowStatus.COMPLETED
        self.updated_at = datetime.now()

    def mark_failed(self, error: str):
        """Mark workflow as failed."""
        self.status = WorkflowStatus.FAILED
        self.updated_at = datetime.now()
        logger.error(f"Workflow {self.workflow_id[:8]} failed: {error}")

    def mark_cancelled(self):
        """Mark workflow as cancelled."""
        self.status = WorkflowStatus.CANCELLED
        self.updated_at = datetime.now()

    def suspend(self):
        """Suspend the workflow."""
        if self.status in [WorkflowStatus.ACTIVE, WorkflowStatus.DRAFT]:
            self.status = WorkflowStatus.SUSPENDED
            self.updated_at = datetime.now()
            logger.info(f"Suspended workflow {self.workflow_id[:8]}")

    def resume(self):
        """Resume a suspended workflow."""
        if self.status == WorkflowStatus.SUSPENDED:
            self.status = WorkflowStatus.ACTIVE
            self.updated_at = datetime.now()
            logger.info(f"Resumed workflow {self.workflow_id[:8]}")

    def increment_version(self):
        """Increment workflow version."""
        self.version += 1
        self.updated_at = datetime.now()
        logger.info(f"Incremented workflow {self.workflow_id[:8]} to version {self.version}")

    def export_to_dict(self) -> Dict[str, Any]:
        """Export workflow to dictionary."""
        return {
            'name': self.name,
            'description': self.description,
            'workflow_id': self.workflow_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'version': self.version,
            'type': self.type.value,
            'status': self.status.value,
            'tags': self.tags,
            'category': self.category,
            'author': self.author,
            'icon': self.icon,
            'is_public': self.is_public,
            'trigger_type': self.trigger_type.value,
            'trigger_config': self.trigger_config,
            'variables': self.variables,
            'variable_schema': self.variable_schema,
            'steps': [step.export_to_dict() for step in self.steps],
            'on_error': self.on_error,
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'notes': self.notes,
            'parameters': self.parameters
        }

    @classmethod
    def import_from_dict(cls, data: Dict[str, Any]) -> 'Workflow':
        """Import workflow from dictionary."""
        # Import step class
        from .workflow_step import WorkflowStep

        # Parse steps
        steps = []
        for step_data in data.get('steps', []):
            steps.append(WorkflowStep.import_from_dict(step_data))

        # Parse datetime
        created_at = datetime.fromisoformat(data['created_at']) if 'created_at' in data else datetime.now()
        updated_at = datetime.fromisoformat(data['updated_at']) if 'updated_at' in data else datetime.now()

        return cls(
            name=data['name'],
            description=data['description'],
            workflow_id=data['workflow_id'],
            created_at=created_at,
            updated_at=updated_at,
            version=data.get('version', 1),
            type=WorkflowType(data.get('type', 'scripted')),
            status=WorkflowStatus(data.get('status', 'created')),
            tags=data.get('tags', []),
            category=data.get('category'),
            author=data.get('author'),
            icon=data.get('icon'),
            is_public=data.get('is_public', False),
            trigger_type=TriggerType(data.get('trigger_type', 'manual')),
            trigger_config=data.get('trigger_config'),
            variables=data.get('variables', {}),
            variable_schema=data.get('variable_schema'),
            steps=steps,
            on_error=data.get('on_error', 'stop'),
            max_retries=data.get('max_retries', 3),
            retry_delay=data.get('retry_delay', 0),
            notes=data.get('notes'),
            parameters=data.get('parameters')
        )

    def __repr__(self):
        return f"<Workflow id={self.workflow_id[:8]} name={self.name} status={self.status.value}>"
