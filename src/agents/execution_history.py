"""
Execution History

Manages execution history and logging for debugging and analytics.
"""


import logging
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from enum import Enum


logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of execution events."""
    GOAL_CREATED = "goal_created"
    GOAL_STARTED = "goal_started"
    GOAL_COMPLETED = "goal_completed"
    GOAL_FAILED = "goal_failed"
    GOAL_CANCELLED = "goal_cancelled"

    TASK_CREATED = "task_created"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_QUEUED = "task_queued"
    TASK_CANCELLED = "task_cancelled"

    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"

    RECOVERY_APPLIED = "recovery_applied"
    PAUSED = "paused"
    RESUMED = "resumed"

    PROGRESS_UPDATE = "progress_update"
    ERROR = "error"


class ExecutionEvent:
    """Represents an execution event."""

    def __init__(
        self,
        event_type: EventType,
        goal_id: Optional[str] = None,
        task_id: Optional[str] = None,
        detail: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ):
        """
        Initialize execution event.

        Args:
            event_type: Type of event
            goal_id: ID of goal (if applicable)
            task_id: ID of task (if applicable)
            detail: Event detail
            metadata: Additional metadata
            timestamp: Event timestamp
        """
        self.event_type = event_type
        self.goal_id = goal_id
        self.task_id = task_id
        self.detail = detail
        self.metadata = metadata or {}
        self.timestamp = timestamp or datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            'event_type': self.event_type.value,
            'goal_id': self.goal_id,
            'task_id': self.task_id,
            'detail': self.detail,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat()
        }


class ExecutionHistory:
    """
    Manages execution history and logging.

    The Execution History tracks all events during goal execution
    for debugging, analytics, and auditing.
    """

    def __init__(
        self,
        on_event: Optional[Callable[['ExecutionHistory', ExecutionEvent], None]] = None,
        max_events: int = 1000
    ):
        """
        Initialize execution history.

        Args:
            on_event: Callback when event is recorded
            max_events: Maximum number of events to keep
        """
        self.on_event = on_event
        self.max_events = max_events

        # Event storage
        self.events: List[ExecutionEvent] = []

        # Statistics
        self.total_events = 0
        self.by_goal: Dict[str, int] = {}  # goal_id -> count
        self.by_event_type: Dict[str, int] = {}  # event_type -> count
        self.by_task: Dict[str, int] = {}  # task_id -> count

        # Error tracking
        self.errors: List[ExecutionEvent] = []

        logger.debug("Initialized execution history")

    def log_event(
        self,
        event_type: EventType,
        goal_id: Optional[str] = None,
        task_id: Optional[str] = None,
        detail: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log an execution event.

        Args:
            event_type: Type of event
            goal_id: ID of goal (if applicable)
            task_id: ID of task (if applicable)
            detail: Event detail
            metadata: Additional metadata
        """
        event = ExecutionEvent(
            event_type=event_type,
            goal_id=goal_id,
            task_id=task_id,
            detail=detail,
            metadata=metadata,
            timestamp=datetime.now()
        )

        self.events.append(event)
        self.total_events += 1

        # Update statistics
        if goal_id:
            self.by_goal[goal_id] = self.by_goal.get(goal_id, 0) + 1

        self.by_event_type[event_type.value] = self.by_event_type.get(event_type.value, 0) + 1

        if task_id:
            self.by_task[task_id] = self.by_task.get(task_id, 0) + 1

        # Track errors
        if event_type == EventType.ERROR:
            self.errors.append(event)

        # Keep only last max_events
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]

        # Notify callback
        if self.on_event:
            self.on_event(self, event)

        logger.debug(f"Event logged: {event_type.value} - {detail[:50]}")

    def log_goal_created(self, goal_id: str, description: str):
        """Log goal creation event."""
        self.log_event(
            EventType.GOAL_CREATED,
            goal_id=goal_id,
            detail=f"Goal created: {description[:50]}",
            metadata={'description': description}
        )

    def log_goal_started(self, goal_id: str, steps: int):
        """Log goal start event."""
        self.log_event(
            EventType.GOAL_STARTED,
            goal_id=goal_id,
            detail=f"Goal started with {steps} steps",
            metadata={'steps': steps}
        )

    def log_goal_completed(self, goal_id: str, duration: float):
        """Log goal completion event."""
        self.log_event(
            EventType.GOAL_COMPLETED,
            goal_id=goal_id,
            detail="Goal completed successfully",
            metadata={'duration_seconds': duration}
        )

    def log_goal_failed(self, goal_id: str, error: str):
        """Log goal failure event."""
        self.log_event(
            EventType.GOAL_FAILED,
            goal_id=goal_id,
            detail=f"Goal failed: {error[:50]}",
            metadata={'error': error}
        )

    def log_task_created(self, task_id: str, goal_id: str, goal: str):
        """Log task creation event."""
        self.log_event(
            EventType.TASK_CREATED,
            goal_id=goal_id,
            task_id=task_id,
            detail=f"Task created: {goal[:50]}",
            metadata={'task_goal': goal}
        )

    def log_task_started(self, task_id: str, goal_id: str):
        """Log task start event."""
        self.log_event(
            EventType.TASK_STARTED,
            goal_id=goal_id,
            task_id=task_id,
            detail="Task started"
        )

    def log_task_completed(self, task_id: str, goal_id: str, duration: float):
        """Log task completion event."""
        self.log_event(
            EventType.TASK_COMPLETED,
            goal_id=goal_id,
            task_id=task_id,
            detail="Task completed successfully",
            metadata={'duration_seconds': duration}
        )

    def log_task_failed(self, task_id: str, goal_id: str, error: str):
        """Log task failure event."""
        self.log_event(
            EventType.TASK_FAILED,
            goal_id=goal_id,
            task_id=task_id,
            detail=f"Task failed: {error[:50]}",
            metadata={'error': error}
        )

    def log_approval_requested(self, task_id: str, goal_id: str, description: str, risk_level: str):
        """Log approval request event."""
        self.log_event(
            EventType.APPROVAL_REQUESTED,
            goal_id=goal_id,
            task_id=task_id,
            detail=f"Approval requested: {description[:50]}",
            metadata={'risk_level': risk_level, 'description': description}
        )

    def log_recovery_applied(self, task_id: str, goal_id: str, strategy: str):
        """Log recovery action event."""
        self.log_event(
            EventType.RECOVERY_APPLIED,
            goal_id=goal_id,
            task_id=task_id,
            detail=f"Recovery applied: {strategy}",
            metadata={'strategy': strategy}
        )

    def log_progress_update(self, task_id: str, goal_id: str, progress: float, detail: str):
        """Log progress update event."""
        self.log_event(
            EventType.PROGRESS_UPDATE,
            goal_id=goal_id,
            task_id=task_id,
            detail=f"Progress: {progress*100:.1f}% - {detail[:50]}",
            metadata={'progress': progress, 'detail': detail}
        )

    def log_error(self, goal_id: Optional[str] = None, task_id: Optional[str] = None, error: str, context: str = ""):
        """Log error event."""
        self.log_event(
            EventType.ERROR,
            goal_id=goal_id,
            task_id=task_id,
            detail=f"Error: {error[:100]}",
            metadata={'error': error, 'context': context}
        )

    def get_events_by_goal(self, goal_id: str) -> List[ExecutionEvent]:
        """
        Get all events for a specific goal.

        Args:
            goal_id: Goal ID

        Returns:
            List of events
        """
        return [e for e in self.events if e.goal_id == goal_id]

    def get_events_by_task(self, task_id: str) -> List[ExecutionEvent]:
        """
        Get all events for a specific task.

        Args:
            task_id: Task ID

        Returns:
            List of events
        """
        return [e for e in self.events if e.task_id == task_id]

    def get_errors(self) -> List[ExecutionEvent]:
        """Get all error events."""
        return self.errors.copy()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get execution history statistics.

        Returns:
            Statistics dictionary
        """
        return {
            'total_events': self.total_events,
            'unique_goals': len(self.by_goal),
            'unique_tasks': len(self.by_task),
            'events_by_event_type': self.by_event_type,
            'events_by_goal': self.by_goal,
            'total_errors': len(self.errors),
            'recent_errors': self.errors[-10:] if self.errors else []
        }

    def get_summary_by_goal(self) -> List[Dict[str, Any]]:
        """
        Get summary of all goals.

        Returns:
            List of goal summaries
        """
        summaries = []

        for goal_id, count in self.by_goal.items():
            summaries.append({
                'goal_id': goal_id,
                'event_count': count,
                'goal_events': self.get_events_by_goal(goal_id)
            })

        return summaries

    def clear_history(self):
        """Clear execution history."""
        self.events.clear()
        self.errors.clear()
        self.total_events = 0
        self.by_goal.clear()
        self.by_event_type.clear()
        self.by_task.clear()

        logger.debug("Execution history cleared")

    def export_events(self, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Export events as dictionaries.

        Args:
            event_type: Filter by event type (optional)

        Returns:
            List of event dictionaries
        """
        if event_type:
            filtered = [e for e in self.events if e.event_type.value == event_type]
        else:
            filtered = self.events

        return [e.to_dict() for e in filtered]

    def export_history_json(self, filepath: str):
        """
        Export entire history to JSON file.

        Args:
            filepath: Output file path
        """
        data = {
            'total_events': self.total_events,
            'events': [e.to_dict() for e in self.events],
            'statistics': self.get_statistics()
        }

        import json
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Execution history exported to {filepath}")
