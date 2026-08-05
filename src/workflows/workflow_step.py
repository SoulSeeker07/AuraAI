"""
Workflow Step Data Model

Defines the structure of an individual step in a workflow.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Union

from .models import StepType

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

    NOTE ON MODEL SHAPE (read this before touching workflow_graph.py /
    workflow_executor.py again):
      - step_type (StepType, from models.py) controls CONTROL FLOW:
        ACTION, WAIT, CONDITION, LOOP, SET_VARIABLE, GET_VARIABLE,
        PROMPT_USER, DECISION, ECHO, MERGE, MERGE_CONFIG.
      - action_type (ActionType, local to this file) only matters when
        step_type == StepType.ACTION, and controls WHAT KIND of action
        runs: GOAL, TOOL, SCRIPT, PROMPT_USER.
      - action_config is a plain dict holding whatever the action/wait/
        echo/set_variable step needs (e.g. {'action_type': 'tool',
        'tool': 'x', 'parameters': {...}}).
      - condition is a plain dict: {'condition_type': 'attribute_check'
        | 'value_check' | 'custom', 'attribute_name', 'expected_value',
        'operator', 'custom_function'}.
      - decision is a plain dict used for branching:
        {'on_true': [step_id, ...], 'on_false': [step_id, ...]}.
      - loop is a plain dict: {'type': 'for_each' | 'while' | 'for_range',
        'collection'/'items', 'item_variable', 'condition',
        'max_iterations', 'start', 'end', 'step'}.
      - on_error is a plain string: 'stop' | 'continue' | 'skip' |
        'ask_user' | 'retry'. There is no ErrorHandling enum in this
        model — do not import one.
    """

    # Core identification
    step_id: str
    name: str
    description: str | None = None

    # Control-flow type (what kind of step this is)
    step_type: StepType = StepType.ACTION

    # Execution type (only relevant when step_type == StepType.ACTION)
    action_type: ActionType = ActionType.GOAL

    # Action configuration
    action_config: dict[str, Any] | None = None

    # Dependencies (steps this step depends on)
    dependencies: list[str] = field(default_factory=list)

    # Conditions
    condition: dict[str, Any] | None = (
        None  # {condition_type, attribute_name, expected_value, operator, custom_function}
    )

    # Decision (branching)
    decision: dict[str, Any] | None = (
        None  # {on_true: [step_id,...], on_false: [step_id,...]}
    )

    # Loops
    loop: dict[str, Any] | None = (
        None  # {type, items/collection, item_variable, condition, max_iterations, start, end, step}
    )

    # Error handling
    on_error: str = "stop"  # stop, continue, retry, skip, ask_user

    # Variables
    output_variable: str | None = None  # Store result in this variable

    # Execution tracking
    status: StepStatus = StepStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    execution_time: float | None = None

    # Error tracking
    error: str | None = None
    retry_count: int = 0
    last_error: str | None = None

    # Retry configuration
    retry_policy: dict[str, Any] | None = None  # {max_retries, delay, exponential}

    # Metadata
    notes: str | None = None
    order: int = 0

    def export_to_dict(self) -> dict[str, Any]:
        """Export step to dictionary."""
        return {
            "step_id": self.step_id,
            "name": self.name,
            "description": self.description,
            "step_type": self.step_type.value,
            "action_type": self.action_type.value,
            "action_config": self.action_config,
            "dependencies": self.dependencies,
            "condition": self.condition,
            "decision": self.decision,
            "loop": self.loop,
            "on_error": self.on_error,
            "output_variable": self.output_variable,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "execution_time": self.execution_time,
            "error": self.error,
            "retry_count": self.retry_count,
            "last_error": self.last_error,
            "retry_policy": self.retry_policy,
            "notes": self.notes,
            "order": self.order,
        }

    @classmethod
    def import_from_dict(cls, data: dict[str, Any]) -> "WorkflowStep":
        """Import step from dictionary."""
        # Parse datetime
        started_at = (
            datetime.fromisoformat(data["started_at"])
            if data.get("started_at")
            else None
        )
        completed_at = (
            datetime.fromisoformat(data["completed_at"])
            if data.get("completed_at")
            else None
        )

        # NOTE: ActionType is defined locally in this module — no import needed.
        # (Previously this incorrectly imported ActionType from .workflow, which
        # does not define it and would fail or shadow the wrong class.)

        return cls(
            step_id=data["step_id"],
            name=data["name"],
            description=data.get("description"),
            step_type=StepType(data.get("step_type", "action")),
            action_type=ActionType(data.get("action_type", "goal")),
            action_config=data.get("action_config"),
            dependencies=data.get("dependencies", []),
            condition=data.get("condition"),
            decision=data.get("decision"),
            loop=data.get("loop"),
            on_error=data.get("on_error", "stop"),
            output_variable=data.get("output_variable"),
            status=StepStatus(data.get("status", "pending")),
            started_at=started_at,
            completed_at=completed_at,
            execution_time=data.get("execution_time"),
            error=data.get("error"),
            retry_count=data.get("retry_count", 0),
            last_error=data.get("last_error"),
            retry_policy=data.get("retry_policy"),
            notes=data.get("notes"),
            order=data.get("order", 0),
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
        if self.started_at:
            self.execution_time = (self.completed_at - self.started_at).total_seconds()
        else:
            self.execution_time = 0.0
        logger.info(f"Completed step {self.step_id[:8]} in {self.execution_time:.2f}s")

    def mark_failed(self, error: str):
        """Mark step as failed."""
        self.status = StepStatus.FAILED
        self.error = error
        self.last_error = error
        self.completed_at = datetime.now()
        logger.error(f"Step {self.step_id[:8]} failed: {error}")

    def mark_skipped(self, reason: str = ""):
        """Mark step as skipped."""
        self.status = StepStatus.SKIPPED
        self.completed_at = datetime.now()
        if reason:
            self.notes = f"{self.notes + ' | ' if self.notes else ''}Skipped: {reason}"
        logger.info(
            f"Skipped step {self.step_id[:8]}" + (f": {reason}" if reason else "")
        )

    def mark_aborted(self):
        """Mark step as aborted."""
        self.status = StepStatus.ABORTED
        self.completed_at = datetime.now()
        logger.warning(f"Aborted step {self.step_id[:8]}")

    def should_retry(self) -> bool:
        """Check if step should retry."""
        if not self.retry_policy:
            return False

        max_retries = self.retry_policy.get("max_retries", 0)
        return self.retry_count < max_retries

    def should_skip_on_error(self) -> bool:
        """Check if should skip on error."""
        return self.on_error in ["skip", "continue", "ask_user"]

    def should_stop_on_error(self) -> bool:
        """Check if should stop on error."""
        return self.on_error in ["stop", "ask_user"]

    def is_ready_to_execute(
        self, dependencies_satisfied: bool, condition_met: bool = True
    ) -> bool:
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
    output_variable: str | None = None,
    on_error: str = "stop",
    dependencies: list[str] | None = None,
    **kwargs,
) -> WorkflowStep:
    """Create a goal execution step."""
    return WorkflowStep(
        step_id="",
        name=name,
        description=f"Execute goal: {goal_description[:50]}...",
        step_type=StepType.ACTION,
        action_type=ActionType.GOAL,
        action_config={"action_type": "goal", "goal": goal_description, **kwargs},
        output_variable=output_variable,
        on_error=on_error,
        dependencies=dependencies or [],
    )


def create_tool_step(
    name: str,
    tool_name: str,
    operation: str,
    parameters: dict[str, Any] | None = None,
    output_variable: str | None = None,
    **kwargs,
) -> WorkflowStep:
    """Create a tool execution step."""
    return WorkflowStep(
        step_id="",
        name=name,
        description=f"Execute tool: {tool_name} ({operation})",
        step_type=StepType.ACTION,
        action_type=ActionType.TOOL,
        action_config={
            "action_type": "tool",
            "tool": tool_name,
            "operation": operation,
            "parameters": parameters or {},
            **kwargs,
        },
        output_variable=output_variable,
    )


def create_wait_step(
    name: str, duration: Union[int, float], description: str | None = None, **kwargs
) -> WorkflowStep:
    """Create a wait/timeout step."""
    return WorkflowStep(
        step_id="",
        name=name,
        description=description or f"Wait for {duration} seconds",
        step_type=StepType.WAIT,
        action_type=ActionType.WAIT,
        action_config={"wait_seconds": duration, "duration": duration},
        **kwargs,
    )


def create_variable_step(
    name: str,
    variable_name: str,
    value: Any,
    step_type: str = "set",
    output_variable: str | None = None,
    **kwargs,
) -> WorkflowStep:
    """Create a variable manipulation step."""
    control_step_type = (
        StepType.SET_VARIABLE if step_type == "set" else StepType.GET_VARIABLE
    )
    action_type = (
        ActionType.SET_VARIABLE if step_type == "set" else ActionType.GET_VARIABLE
    )
    return WorkflowStep(
        step_id="",
        name=name,
        description=f"{'Set' if step_type == 'set' else 'Get'} variable: {variable_name}",
        step_type=control_step_type,
        action_type=action_type,
        action_config={"variable_name": variable_name, "value": value},
        output_variable=output_variable,
        **kwargs,
    )


def create_condition_step(
    name: str,
    condition: str,
    on_true: list[str] | None = None,
    on_false: list[str] | None = None,
    **kwargs,
) -> WorkflowStep:
    """Create a conditional check step."""
    return WorkflowStep(
        step_id="",
        name=name,
        description=f"Check condition: {condition[:50]}...",
        step_type=StepType.CONDITION,
        action_type=ActionType.CONDITION,
        condition={
            "condition_type": "custom",
            "expression": condition,
        },
        decision={"on_true": on_true or [], "on_false": on_false or []},
        **kwargs,
    )


def create_decision_step(
    name: str, on_true: list[str], on_false: list[str], **kwargs
) -> WorkflowStep:
    """
    Create a decision branching step.

    Args:
        name: Step name
        on_true: Step IDs to run if the condition evaluates true
        on_false: Step IDs to run if the condition evaluates false
    """
    return WorkflowStep(
        step_id="",
        name=name,
        description=f"Decision: {len(on_true)} true branch, {len(on_false)} false branch",
        step_type=StepType.DECISION,
        action_type=ActionType.DECISION,
        decision={"on_true": on_true, "on_false": on_false},
        **kwargs,
    )


def create_loop_step(
    name: str,
    loop_type: LoopType,
    items: list[Any],
    condition: str | None = None,
    output_variable: str | None = None,
    **kwargs,
) -> WorkflowStep:
    """Create a loop step."""
    return WorkflowStep(
        step_id="",
        name=name,
        description=f"{loop_type.value} loop over {len(items)} items",
        step_type=StepType.LOOP,
        action_type=ActionType.LOOP,
        loop={"type": loop_type.value, "items": items, "condition": condition},
        output_variable=output_variable,
        **kwargs,
    )


def create_prompt_step(
    name: str,
    prompt: str,
    input_variable: str,
    validation: dict[str, Any] | None = None,
    **kwargs,
) -> WorkflowStep:
    """Create a user prompt step."""
    return WorkflowStep(
        step_id="",
        name=name,
        description=f"Prompt user: {prompt[:50]}...",
        step_type=StepType.PROMPT_USER,
        action_type=ActionType.PROMPT_USER,
        action_config={
            "prompt": prompt,
            "input_variable": input_variable,
            "validation": validation,
        },
        **kwargs,
    )
