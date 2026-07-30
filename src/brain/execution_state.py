"""
Execution State Tracking

Tracks current execution state across AuraBrain.
Everything uses the same state for consistency.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum
from datetime import datetime


class StreamingStatus(str, Enum):
    """Streaming execution status."""
    IDLE = "idle"
    STREAMING = "streaming"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Represents a task being executed."""
    task_id: str
    task_type: str
    title: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    progress: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionState:
    """
    Tracks current execution state across AuraBrain.
    
    This ensures everything uses the same state for consistency.
    """
    
    # Current execution
    current_task: Optional[Task] = None
    current_provider: Optional[str] = None
    running_plugins: list[str] = field(default_factory=list)
    
    # Streaming state
    streaming_status: StreamingStatus = StreamingStatus.IDLE
    streaming_position: int = 0
    total_tokens: int = 0
    
    # Cancellation
    cancellation_token: Optional[asyncio.Event] = None
    is_cancelled: bool = False
    
    # Timing
    execution_start_time: datetime = field(default_factory=datetime.now)
    execution_elapsed: float = 0.0
    
    # Conversation tracking
    conversation_id: str = ""
    
    # Progress tracking
    progress_steps: list[str] = field(default_factory=list)
    current_progress_step: Optional[int] = None
    
    # Tool execution tracking
    tools_executed: list[str] = field(default_factory=list)
    tools_failed: list[str] = field(default_factory=list)
    
    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize execution state."""
        if not self.conversation_id:
            import uuid
            self.conversation_id = str(uuid.uuid4())
    
    def start_task(self, task_type: str, title: str, metadata: Optional[dict[str, Any]] = None):
        """
        Start a new task.
        
        Args:
            task_type: Type of task
            title: Task title
            metadata: Additional metadata
        """
        self.current_task = Task(
            task_id=str(uuid.uuid4()),
            task_type=task_type,
            title=title,
            metadata=metadata or {}
        )
        self.current_task.status = TaskStatus.RUNNING
        self.current_task.started_at = datetime.now()
        self.stream('idle', 'started_task', {'task_id': self.current_task.task_id, 'task_type': task_type, 'title': title})
    
    def update_task_status(self, status: TaskStatus, error: Optional[str] = None):
        """
        Update current task status.
        
        Args:
            status: New status
            error: Error message if failed
        """
        if self.current_task:
            self.current_task.status = status
            self.current_task.completed_at = datetime.now()
            if error:
                self.current_task.error = error
            if status == TaskStatus.COMPLETED:
                self.streaming_status = StreamingStatus.COMPLETED
    
    def start_streaming(self):
        """Start streaming execution."""
        self.streaming_status = StreamingStatus.STREAMING
        self.progress_steps = []
        self.current_progress_step = 0
        self.stream('idle', 'start_streaming', {'conversation_id': self.conversation_id})
    
    def update_streaming(self, chunk: str, is_token: bool = False):
        """
        Update streaming progress.
        
        Args:
            chunk: Streaming chunk
            is_token: Whether this is a token
        """
        self.streaming_position += len(chunk)
        if is_token:
            self.total_tokens += 1
        self.stream('idle', 'streaming_update', {'position': self.streaming_position, 'tokens': self.total_tokens})
    
    def complete_streaming(self, chunks: int = 0):
        """Complete streaming execution."""
        self.streaming_status = StreamingStatus.COMPLETED
        self.stream('idle', 'complete_streaming', {'chunks': chunks, 'tokens': self.total_tokens})
    
    def cancel_streaming(self):
        """Cancel streaming execution."""
        self.streaming_status = StreamingStatus.CANCELLED
        if self.cancellation_token:
            self.cancellation_token.set()
        self.is_cancelled = True
        self.stream('idle', 'cancel_streaming', {'conversation_id': self.conversation_id})
    
    def add_plugin(self, plugin_name: str):
        """Add running plugin to tracking."""
        if plugin_name not in self.running_plugins:
            self.running_plugins.append(plugin_name)
            self.stream('idle', 'plugin_started', {'plugin': plugin_name})
    
    def remove_plugin(self, plugin_name: str):
        """Remove plugin from tracking."""
        if plugin_name in self.running_plugins:
            self.running_plugins.remove(plugin_name)
            self.stream('idle', 'plugin_stopped', {'plugin': plugin_name})
    
    def record_tool_result(self, tool_name: str, success: bool, error: Optional[str] = None):
        """
        Record tool execution result.
        
        Args:
            tool_name: Name of tool executed
            success: Whether tool succeeded
            error: Error message if failed
        """
        self.tools_executed.append(tool_name)
        if not success:
            self.tools_failed.append(tool_name)
            self.stream('idle', 'tool_failed', {'tool': tool_name, 'error': error})
        else:
            self.stream('idle', 'tool_success', {'tool': tool_name})
    
    def add_progress_step(self, step: str):
        """Add a progress step."""
        if step not in self.progress_steps:
            self.progress_steps.append(step)
            self.current_progress_step = len(self.progress_steps)
            self.stream('idle', 'progress_step', {'step': step, 'progress': self.current_progress_step})
    
    def set_execution_time(self, elapsed: float):
        """Set execution elapsed time."""
        self.execution_elapsed = elapsed
    
    def update_provider(self, provider: str):
        """Update current provider."""
        self.current_provider = provider
        self.stream('idle', 'provider_changed', {'provider': provider})
    
    def stream(self, event_type: str, event_data: dict[str, Any]):
        """
        Stream execution state events.
        
        Args:
            event_type: Type of event
            event_data: Event data
        """
        # This would normally send events to a logging/monitoring system
        # For now, we just print for debugging
        if self.metadata.get('enable_events', True):
            print(f"[AuraBrain Event] {event_type}: {event_data}")
    
    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary."""
        return {
            'current_task': {
                'task_id': self.current_task.task_id if self.current_task else None,
                'task_type': self.current_task.task_type if self.current_task else None,
                'title': self.current_task.title if self.current_task else None,
                'status': self.current_task.status.value if self.current_task else None,
                'progress': self.current_task.progress if self.current_task else 0.0,
                'error': self.current_task.error,
            } if self.current_task else None,
            'current_provider': self.current_provider,
            'running_plugins': self.running_plugins,
            'streaming_status': self.streaming_status.value,
            'streaming_position': self.streaming_position,
            'total_tokens': self.total_tokens,
            'execution_time': self.execution_elapsed,
            'conversation_id': self.conconversation_id,
            'progress_steps': self.progress_steps,
            'current_progress_step': self.current_progress_step,
            'tools_executed': self.tools_executed,
            'tools_failed': self.tools_failed,
            'conversation_id': self.conversation_id,
            'metadata': self.metadata,
        }
    
    def reset(self):
        """Reset execution state."""
        self.current_task = None
        self.current_provider = None
        self.running_plugins.clear()
        self.streaming_status = StreamingStatus.IDLE
        self.streaming_position = 0
        self.total_tokens = 0
        self.progress_steps.clear()
        self.current_progress_step = None
        self.tools_executed.clear()
        self.tools_failed.clear()
        self.execution_start_time = datetime.now()


import uuid
