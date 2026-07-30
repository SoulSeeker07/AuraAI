"""
Tool Execution Engine - Timeout Management

This module provides timeout handling for tool executions, ensuring
operations don't hang indefinitely.
"""


import threading
import time
from typing import Optional, Callable, Dict, Any
from datetime import datetime
from enum import Enum
from .exceptions import TimeoutError


class TimeoutStatus(Enum):
    """Timeout status values."""
    NOT_STARTED = "not_started"
    RUNNING = "running"
    ELAPSED = "elapsed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TimeoutMonitor:
    """Monitors execution timeouts."""
    
    def __init__(self, timeout_seconds: Optional[float] = None):
        """
        Initialize the timeout monitor.
        
        Args:
            timeout_seconds: Optional timeout in seconds
        """
        self.timeout_seconds = timeout_seconds
        self._start_time: Optional[float] = None
        self._elapsed_time: float = 0.0
        self._status = TimeoutStatus.NOT_STARTED
        self._last_check_time: Optional[float] = None
        self._lock = threading.RLock()
        self._callbacks: list = []
    
    def start(self) -> None:
        """Start timeout monitoring."""
        with self._lock:
            self._start_time = time.time()
            self._elapsed_time = 0.0
            self._status = TimeoutStatus.RUNNING
            self._last_check_time = time.time()
    
    def update(self, check_interval: float = 0.1) -> bool:
        """
        Update the timeout monitor.
        
        Args:
            check_interval: Time interval in seconds since last check
            
        Returns:
            True if timeout has been reached
        """
        with self._lock:
            if self._status != TimeoutStatus.RUNNING:
                return False
            
            self._last_check_time = time.time()
            self._elapsed_time = self._last_check_time - self._start_time
            
            # Check if timeout has been reached
            if self.timeout_seconds and self._elapsed_time >= self.timeout_seconds:
                self._status = TimeoutStatus.ELAPSED
                self._notify_callbacks()
                return True
            
            return False
    
    def check(self) -> bool:
        """
        Check if timeout has been reached.
        
        Returns:
            True if timeout has been reached
        """
        with self._lock:
            if self._status != TimeoutStatus.RUNNING:
                return False
            
            self._elapsed_time = time.time() - self._start_time
            
            if self.timeout_seconds and self._elapsed_time >= self.timeout_seconds:
                self._status = TimeoutStatus.ELAPSED
                self._notify_callbacks()
                return True
            
            return False
    
    def complete(self) -> None:
        """Mark timeout monitoring as completed."""
        with self._lock:
            self._status = TimeoutStatus.COMPLETED
    
    def cancel(self) -> None:
        """Mark timeout monitoring as cancelled."""
        with self._lock:
            self._status = TimeoutStatus.CANCELLED
    
    def elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        with self._lock:
            if self._status == TimeoutStatus.RUNNING:
                return time.time() - self._start_time
            return self._elapsed_time
    
    def remaining_time(self) -> Optional[float]:
        """Get remaining time in seconds, or None if no timeout is set."""
        with self._lock:
            if self.timeout_seconds:
                remaining = self.timeout_seconds - self.elapsed_time()
                return max(0.0, remaining)
            return None
    
    def set_timeout(self, timeout_seconds: float) -> None:
        """
        Set a new timeout.
        
        Args:
            timeout_seconds: Timeout in seconds
        """
        with self._lock:
            self.timeout_seconds = timeout_seconds
    
    def add_callback(self, callback: Callable[[float], None]) -> None:
        """
        Add a callback to be notified when timeout is reached.
        
        Args:
            callback: Callback function that receives remaining time
        """
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[float], None]) -> None:
        """
        Remove a timeout callback.
        
        Args:
            callback: The callback to remove
        """
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)
    
    def _notify_callbacks(self) -> None:
        """Notify all callbacks of timeout."""
        for callback in self._callbacks:
            try:
                callback(self.remaining_time())
            except Exception as e:
                # Log error but don't crash
                pass
    
    def get_status(self) -> TimeoutStatus:
        """Get the current status."""
        with self._lock:
            return self._status
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        with self._lock:
            return {
                "timeout_set": self.timeout_seconds is not None,
                "timeout_seconds": self.timeout_seconds,
                "elapsed_time": self.elapsed_time(),
                "remaining_time": self.remaining_time(),
                "status": self._status.value
            }


class TimeoutManager:
    """Manages timeouts for multiple operations."""
    
    def __init__(self):
        self._monitors: Dict[str, TimeoutMonitor] = {}
        self._lock = None  # Will be set on initialization
    
    def create_monitor(
        self,
        monitor_id: str,
        timeout_seconds: Optional[float] = None
    ) -> TimeoutMonitor:
        """Create a new timeout monitor."""
        with self._get_lock():
            monitor = TimeoutMonitor(timeout_seconds)
            self._monitors[monitor_id] = monitor
            return monitor
    
    def get_monitor(self, monitor_id: str) -> Optional[TimeoutMonitor]:
        """Get a timeout monitor."""
        with self._get_lock():
            return self._monitors.get(monitor_id)
    
    def remove_monitor(self, monitor_id: str) -> Optional[TimeoutMonitor]:
        """Remove a timeout monitor."""
        with self._get_lock():
            return self._monitors.pop(monitor_id, None)
    
    def clear_all(self) -> None:
        """Clear all monitors (for testing)."""
        with self._get_lock():
            self._monitors.clear()
    
    def _get_lock(self):
        """Get or create the lock."""
        if self._lock is None:
            self._lock = threading.RLock()
        return self._lock


def execute_with_timeout(
    operation: Callable,
    timeout_seconds: Optional[float] = None,
    operation_name: str = None
) -> Any:
    """
    Execute an operation with a timeout.
    
    Args:
        operation: The operation to execute
        timeout_seconds: Optional timeout in seconds
        operation_name: Optional name of the operation
        
    Returns:
        The result of the operation
        
    Raises:
        TimeoutError: If operation times out
    """
    def _wrapper():
        return operation()
    
    # Start timeout monitor if timeout is set
    if timeout_seconds:
        monitor = TimeoutMonitor(timeout_seconds)
        monitor.start()
        
        try:
            result = _wrapper()
            
            # Check if timeout was reached during execution
            if monitor.check():
                elapsed = monitor.elapsed_time()
                raise TimeoutError(
                    f"Operation timed out after {elapsed:.2f} seconds: {operation_name or 'unknown'}",
                    timeout_seconds=timeout_seconds,
                    tool_name=operation_name
                )
            
            return result
        finally:
            monitor.complete()
    else:
        return _wrapper()


def execute_with_timeout_and_cancellation(
    operation: Callable,
    timeout_seconds: Optional[float] = None,
    cancellation_token=None,
    operation_name: str = None
) -> Any:
    """
    Execute an operation with both timeout and cancellation support.
    
    Args:
        operation: The operation to execute
        timeout_seconds: Optional timeout in seconds
        cancellation_token: Optional cancellation token
        operation_name: Optional name of the operation
        
    Returns:
        The result of the operation
        
    Raises:
        TimeoutError: If operation times out
        CancellationError: If operation is cancelled
    """
    # Check for cancellation before starting
    if cancellation_token and cancellation_token.check_cancellation():
        raise TimeoutError(
            f"Operation was cancelled: {operation_name or 'unknown'}",
            timeout_seconds=timeout_seconds,
            tool_name=operation_name
        )
    
    # Execute with timeout
    return execute_with_timeout(
        operation,
        timeout_seconds,
        operation_name
    )
