"""
Workflow Engine Models

Enums and dataclasses for the Workflow Engine.
"""


from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum, auto
from datetime import datetime, timedelta


class WorkflowStatus(Enum):
    """Workflow status states."""
    CREATED = "created"
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    SCHEDULED = "scheduled"


class WorkflowTriggerType(Enum):
    """Types of workflow triggers."""
    MANUAL = "manual"  # Manual trigger
    SCHEDULED = "scheduled"  # Scheduled trigger
    EVENT = "event"  # Event trigger
    WORKSPACE = "workspace"  # Workspace trigger
    VOICE = "voice"  # Voice trigger
    PLUGIN = "plugin"  # Plugin trigger


class WorkflowPriority(Enum):
    """Workflow priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class StepType(Enum):
    """Type of workflow step."""
    ACTION = "action"  # Execute action
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


class ConditionType(Enum):
    """Types of conditions."""
    ATTRIBUTE_CHECK = "attribute_check"  # Check attribute exists and matches value
    VALUE_CHECK = "value_check"  # Check if value meets criteria
    CUSTOM = "custom"  # Execute custom condition function


class ErrorHandling(Enum):
    """Error handling strategies."""
    CONTINUE = "continue"  # Continue to next step
    STOP = "stop"  # Stop workflow execution
    ASK_USER = "ask_user"  # Ask user for input
    RETRY = "retry"  # Retry the step
    SKIP = "skip"  # Skip the step


class LoopType(Enum):
    """Types of loops."""
    FOR_EACH = "for_each"  # Iterate over collection
    WHILE = "while"  # Loop while condition true
    FOR_RANGE = "for_range"  # Iterate over range


class ActionType(Enum):
    """Type of action to execute."""
    GOAL = "goal"  # Agent Runtime goal
    TOOL = "tool"  # Tool execution
    SCRIPT = "script"  # Python script
    WAIT = "wait"  # Delay/timeout
    SET_VARIABLE = "set_variable"  # Variable assignment
    GET_VARIABLE = "get_variable"  # Variable retrieval
    PROMPT_USER = "prompt_user"  # User input prompt
    ECHO = "echo"  # Log output


class DecisionOutcome(Enum):
    """Possible outcomes of a decision."""
    CONTINUE = "continue"
    SKIP = "skip"
    RETRY = "retry"
    STOP = "stop"
    ASK_USER = "ask_user"
    GO_TO_STEP = "go_to_step"  # Jump to specific step


@dataclass
class TriggerData:
    """Data passed when a trigger fires."""
    trigger_type: WorkflowTriggerType
    workflow_id: str
    trigger_data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class StepResult:
    """Result of executing a step."""
    step_id: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    duration: Optional[float] = None


@dataclass
class WorkflowSummary:
    """Summary of workflow execution."""
    workflow_id: str
    workflow_name: str
    status: WorkflowStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    error: Optional[str] = None
    steps_completed: int = 0
    steps_failed: int = 0
    trigger_type: Optional[WorkflowTriggerType] = None
    trigger_data: Optional[Dict[str, Any]] = None
