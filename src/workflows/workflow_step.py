"""
Workflow Step Data Model

Defines the structure of an individual step in a workflow.
"""


from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Union, Callable
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Type of action to execute."""
    GOAL = "goal"  # Agent Runtime goal
    TOOL = "tool"  # Tool execution
    SCRIPT = "script"  # Python script
    WAIT = "wait"  # Delay/timeout
    CONDITION = "condition"  # Conditional check
    LOOP = "loop"  # Loop iteration
    SET_VARIABLE = "set_variable"  # Variable assignment
    GET_VARIABLE = "get_variable"  # Variable retrieval
    PROMPT_USER = "prompt_user"  # User input prompt
    DECISION = "decision"  # Conditional branching
    ECHO = "echo"  # Log output
    MERGE = "merge"  # Merge data
    MERGE_CONFIG = "merge_config"  # Merge configuration


class DecisionOutcome(Enum):
    """Possible outcomes of a decision."""
    CONTINUE = "continue"
    SKIP = "skip"
    RETRY = "retry"
    STOP = "stop"
    ASK_USER = "ask_user"
    GO_TO_STEP = "go_to_step"  # Jump to specific step


class LoopType(Enum):
    """Type of loop."""
    FOR_EACH = "for_each"  # Iterate over collection
    WHILE = "while"  # Loop while condition true
    FOR_RANGE = "for_range"  # Iterate over range


class StepStatus(Enum):
    """Step execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ABORTED = "aborted"


@dataclass
class WorkflowStep:
    """
    A single step in a workflow.

    Steps can:
    - Execute goals or tools
    - Have conditions and decisions
    - Support loops and iterations
    - Define error handling strategies
    - Use and set variables
    """

    # Core identification
    step_id: str
    name: str
    description: Optional[str] = None

    # Execution type
    action_type: ActionType = ActionType.GOAL

    # Action configuration
    action_config: Optional[Dict[str, Any]] = None

    # Dependencies (steps this step depends on)
    dependencies: List[str] = field(default_factory=list)

    # Conditions
    condition: Optional[Dict[str, Any]] = None  # {expression, variable_name, value}

    # Decision (branching)
    decision: Optional[Dict[str, Any]] = None  # {on_success, on_failure, on_error}

    # Loops
    loop: Optional[Dict[str, Any]] = None  # {type, items, condition}

    # Error handling
    on_error: str = "stop"  # stop, continue, retry, skip, ask_user

    # Variables
    output_variable: Optional[str] = None  # Store result in this variable

    # Execution tracking
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time: Optional[float] = None

    # Error tracking
    error: Optional[str] = None
    retry_count: int = 0
    last_error: Optional[str] = None

    # Retry configuration
    retry_policy: Optional[Dict[str, Any]] = None  # {max_retries, delay, exponential}

    # Metadata
    notes: Optional[str] = None
    order: int = 0

    def export_to_dict(self) -> Dict[str, Any]:
        """Export step to dictionary."""
        return {
            'step_id': self.step_id,
            'name': self.name,
            'description': self.description,
            'action_type': self.action_type.value,
            'action_config': self.action_config,
            'dependencies': self.dependencies,
            'condition': self.condition,
            'decision': self.decision,
            'loop': self.loop,
            'on_error': self.on_error,
            'output_variable': self.output_variable,
            'status': self.status.value,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'execution_time': self.execution_time,
            'error': self.error,
            'retry_count': self.retry_count,
            'last_error': self.last_error,
            'retry_policy': self.retry_policy,
            'notes': self.notes,
            'order': self.order
        }

    @classmethod
    def import_from_dict(cls, data: Dict[str, Any]) -> 'WorkflowStep':
        """Import step from dictionary."""
        # Parse datetime
        started_at = datetime.fromisoformat(data['started_at']) if 'started_at' in data else None
        completed_at = datetime.fromisoformat(data['completed_at']) if 'completed_at' in data else None

        # Import ActionType
        from .workflow import ActionType

        return cls(
            step_id=data['step_id'],
            name=data['name'],
            description=data.get('description'),
            action_type=ActionType(data.get('action_type', 'goal')),
            action_config=data.get('action_config'),
            dependencies=data.get('dependencies', []),
            condition=data.get('condition'),
            decision=data.get('decision'),
            loop=data.get('loop'),
            on_error=data.get('on_error', 'stop'),
            output_variable=data.get('output_variable'),
            status=StepStatus(data.get('status', 'pending')),
            started_at=started_at,
            completed_at=completed_at,
            execution_time=data.get('execution_time'),
            error=data.get('error'),
            retry_count=data.get('retry_count', 0),
            last_error=data.get('last_error'),
            retry_policy=data.get('retry_policy'),
            notes=data.get('notes'),
            order=data.get('order', 0)
        )

    def mark_started(self):
        """Mark step as started."""
        self.status = StepStatus.RUNNING
        self.started_at = datetime.now()
        logger.info(f"Started step {self.step_id[:8]}")

    def mark_completed(self, result: Any = None):
        """Mark step as completed."""
        self.status = StepStatus.COMPLETED
        self.completed_at = datetime.now()
        self.execution_time = (self.completed_at - self.started_at).total_seconds()
        logger.info(f"Completed step {self.step_id[:8]} in {self.execution_time:.2f}s")

    def mark_failed(self, error: str):
        """Mark step as failed."""
        self.status = StepStatus.FAILED
        self.error = error
        self.last_error = error
        self.completed_at = datetime.now()
        logger.error(f"Step {self.step_id[:8]} failed: {error}")

    def mark_skipped(self):
        """Mark step as skipped."""
        self.status = StepStatus.SKIPPED
        self.completed_at = datetime.now()
        logger.info(f"Skipped step {self.step_id[:8]}")

    def mark_aborted(self):
        """Mark step as aborted."""
        self.status = StepStatus.ABORTED
        self.completed_at = datetime.now()
        logger.warning(f"Aborted step {self.step_id[:8]}")

    def should_retry(self) -> bool:
        """Check if step should retry."""
        if not self.retry_policy:
            return False

        max_retries = self.retry_policy.get('max_retries', 0)
        return self.retry_count < max_retries

    def should_skip_on_error(self) -> bool:
        """Check if should skip on error."""
        return self.on_error in ['skip', 'continue', 'ask_user']

    def should_stop_on_error(self) -> bool:
        """Check if should stop on error."""
        return self.on_error in ['stop', 'ask_user']

    def is_ready_to_execute(self, dependencies_satisfied: bool, condition_met: bool = True) -> bool:
        """
        Check if step is ready to execute.

        Args:
            dependencies_satisfied: All dependencies have been completed
            condition_met: Condition (if any) is met

        Returns:
            True if ready to execute
        """
        if self.status != StepStatus.PENDING:
            return False

        return dependencies_satisfied and condition_met

    def reset_for_retry(self):
        """Reset step for retry."""
        self.retry_count += 1
        self.status = StepStatus.PENDING
        self.started_at = None
        self.completed_at = None
        self.error = None
        self.last_error = None

    def __repr__(self):
        return f"<Step id={self.step_id[:8]} name={self.name} type={self.action_type.value} status={self.status.value}>"


# Factory functions for creating steps

def create_goal_step(
    name: str,
    goal_description: str,
    output_variable: Optional[str] = None,
    on_error: str = "stop",
    dependencies: Optional[List[str]] = None,
    **kwargs
) -> WorkflowStep:
    """Create a goal execution step."""
    return WorkflowStep(
        step_id="",
        name=name,
        description=f"Execute goal: {goal_description[:50]}...",
        action_type=ActionType.GOAL,
        action_config={
            'goal': goal_description,
            **kwargs
        },
        output_variable=output_variable,
        on_error=on_error,
        dependencies=dependencies or []
    )


def create_tool_step(
    name: str,
    tool_name: str,
    operation: str,
    parameters: Optional[Dict[str, Any]] = None,
    output_variable: Optional[str] = None,
    **kwargs
) -> WorkflowStep:
    """Create a tool execution step."""
    return WorkflowStep(
        step_id="",
        name=name,
        description=f"Execute tool: {tool_name} ({operation})",
        action_type=ActionType.TOOL,
        action_config={
            'tool': tool_name,
            'operation': operation,
            'parameters': parameters or {},
            **kwargs
        },
        output_variable=output_variable
    )


def create_wait_step(
    name: str,
    duration: Union[int, float],
    description: Optional[str] = None,
    **kwargs
) -> WorkflowStep:
    """Create a wait/timeout step."""
    return WorkflowStep(
        step_id="",
        name=name,
        description=description or f"Wait for {duration} seconds",
        action_type=ActionType.WAIT,
        action_config={'duration': duration},
        **kwargs
    )


def create_variable_step(
    name: str,
    variable_name: str,
    value: Any,
    step_type: str = "set",
    output_variable: Optional[str] = None,
    **kwargs
) -> WorkflowStep:
    """Create a variable manipulation step."""
    action_type = ActionType.SET_VARIABLE if step_type == "set" else ActionType.GET_VARIABLE
    return WorkflowStep(
        step_id="",
        name=name,
        description=f"{'Set' if step_type == 'set' else 'Get'} variable: {variable_name}",
        action_type=action_type,
        action_config={
            'variable_name': variable_name,
            'value': value
        },
        output_variable=output_variable,
        **kwargs
    )


def create_condition_step(
    name: str,
    condition: str,
    on_true: str = "continue",
    on_false: str = "skip",
    **kwargs
) -> WorkflowStep:
    """Create a conditional check step."""
    return WorkflowStep(
        step_id="",
        name=name,
        description=f"Check condition: {condition[:50]}...",
        action_type=ActionType.CONDITION,
        action_config={
            'condition': condition,
            'on_true': on_true,
            'on_false': on_false
        },
        **kwargs
    )


def create_decision_step(
    name: str,
    decisions: Dict[str, str],
    on_default: str = "continue",
    **kwargs
) -> WorkflowStep:
    """
    Create a decision branching step.

    Args:
        name: Step name
        decisions: Dict of {decision_path: outcome}
        on_default: Outcome when no decision matches
    """
    return WorkflowStep(
        step_id="",
        name=name,
        description=f"Decision: {len(decisions)} branches",
        action_type=ActionType.DECISION,
        action_config={
            'decisions': decisions,
            'on_default': on_default
        },
        **kwargs
    )


def create_loop_step(
    name: str,
    loop_type: LoopType,
    items: List[Any],
    condition: Optional[str] = None,
    output_variable: Optional[str] = None,
    **kwargs
) -> WorkflowStep:
    """Create a loop step."""
    return WorkflowStep(
        step_id="",
        name=name,
        description=f"{loop_type.value} loop over {len(items)} items",
        action_type=ActionType.LOOP,
        action_config={
            'type': loop_type.value,
            'items': items,
            'condition': condition
        },
        output_variable=output_variable,
        **kwargs
    )


def create_prompt_step(
    name: str,
    prompt: str,
    input_variable: str,
    validation: Optional[Dict[str, Any]] = None,
    **kwargs
) -> WorkflowStep:
    """Create a user prompt step."""
    return WorkflowStep(
        step_id="",
        name=name,
        description=f"Prompt user: {prompt[:50]}...",
        action_type=ActionType.PROMPT_USER,
        action_config={
            'prompt': prompt,
            'input_variable': input_variable,
            'validation': validation
        },
        **kwargs
    )
