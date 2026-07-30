"""
Tool Execution Engine - Progress Tracking

This module provides standardized progress tracking for tool executions,
ensuring consistent progress updates across all tools.
"""


from typing import Callable, Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import threading


class ProgressStatus(Enum):
    """Progress status values."""
    NOT_STARTED = "not_started"
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ProgressUpdate:
    """Represents a progress update."""
    
    def __init__(
        self,
        progress: float,  # 0.0 to 100.0
        current_step: str = None,
        status: str = ProgressStatus.IN_PROGRESS.value,
        message: str = None,
        details: Dict[str, Any] = None,
        timestamp: datetime = None
    ):
        self.progress = max(0.0, min(100.0, progress))
        self.current_step = current_step
        self.status = status
        self.message = message
        self.details = details or {}
        self.timestamp = timestamp or datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert progress update to dictionary."""
        return {
            "progress": self.progress,
            "current_step": self.current_step,
            "status": self.status,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat()
        }


class ProgressTracker:
    """Tracks and reports progress for tool executions."""
    
    def __init__(
        self,
        update_callback: Optional[Callable[[ProgressUpdate], None]] = None,
        minimum_interval: float = 0.1  # Minimum interval between updates (seconds)
    ):
        """
        Initialize the progress tracker.
        
        Args:
            update_callback: Callback function called on each progress update
            minimum_interval: Minimum time between updates to prevent flooding
        """
        self.update_callback = update_callback
        self.minimum_interval = minimum_interval
        self._progress = 0.0
        self._current_step: Optional[str] = None
        self._status = ProgressStatus.NOT_STARTED
        self._message: Optional[str] = None
        self._start_time: Optional[datetime] = None
        self._last_update_time: Optional[datetime] = None
        self._details: Dict[str, Any] = {}
        self._progress_history: List[ProgressUpdate] = []
        self._lock = threading.RLock()
        self._is_paused = False
    
    def start(self) -> None:
        """Mark progress tracking as started."""
        with self._lock:
            if self._status == ProgressStatus.NOT_STARTED:
                self._status = ProgressStatus.STARTED
                self._start_time = datetime.now()
                self._progress = 0.0
                self._current_step = None
                self._message = None
                self._last_update_time = None
                self._progress_history = []
                self._details = {}
                self._is_paused = False
                self._notify_update(ProgressUpdate(0.0, status=ProgressStatus.STARTED.value))
    
    def update(
        self,
        progress: float,
        current_step: str = None,
        message: str = None,
        details: Dict[str, Any] = None
    ) -> ProgressUpdate:
        """
        Update progress.
        
        Args:
            progress: Progress value (0.0 to 100.0)
            current_step: Current step description
            message: Optional message
            details: Optional additional details
            
        Returns:
            The progress update that was applied
        """
        with self._lock:
            # Check if paused
            if self._is_paused:
                raise RuntimeError("Progress tracker is paused")
            
            # Clamp progress to valid range
            progress = max(0.0, min(100.0, progress))
            
            # Check minimum interval
            now = datetime.now()
            if (self._last_update_time and 
                (now - self._last_update_time).total_seconds() < self.minimum_interval):
                return self._get_current_progress()
            
            # Update state
            self._progress = progress
            self._current_step = current_step
            self._message = message
            self._details = details or {}
            self._last_update_time = now
            
            # Create and store update
            update = ProgressUpdate(
                progress=progress,
                current_step=current_step,
                status=ProgressStatus.IN_PROGRESS.value,
                message=message,
                details=details,
                timestamp=now
            )
            self._progress_history.append(update)
            
            # Notify callback
            self._notify_update(update)
            
            return update
    
    def set_status(self, status: ProgressStatus) -> None:
        """
        Set the progress status.
        
        Args:
            status: The new status
        """
        with self._lock:
            self._status = status
            if status in (ProgressStatus.COMPLETED, ProgressStatus.FAILED, ProgressStatus.CANCELLED):
                update = ProgressUpdate(
                    progress=self._progress,
                    current_step=self._current_step,
                    status=status.value,
                    message=self._message,
                    details=self._details,
                    timestamp=datetime.now()
                )
                self._progress_history.append(update)
                self._notify_update(update)
    
    def pause(self) -> None:
        """Pause progress tracking."""
        with self._lock:
            if self._status in (ProgressStatus.IN_PROGRESS, ProgressStatus.STARTED):
                self._is_paused = True
                self._notify_update(ProgressUpdate(
                    progress=self._progress,
                    status=ProgressStatus.PAUSED.value,
                    timestamp=datetime.now()
                ))
    
    def resume(self) -> None:
        """Resume progress tracking."""
        with self._lock:
            if self._is_paused:
                self._is_paused = False
                self._notify_update(ProgressUpdate(
                    progress=self._progress,
                    status=ProgressStatus.IN_PROGRESS.value,
                    timestamp=datetime.now()
                ))
    
    def complete(self) -> ProgressUpdate:
        """Mark as completed."""
        with self._lock:
            self._status = ProgressStatus.COMPLETED
            update = ProgressUpdate(
                progress=100.0,
                current_step=self._current_step,
                status=ProgressStatus.COMPLETED.value,
                message=self._message,
                details=self._details,
                timestamp=datetime.now()
            )
            self._progress_history.append(update)
            self._notify_update(update)
            return update
    
    def fail(self, error: Exception) -> ProgressUpdate:
        """
        Mark as failed.
        
        Args:
            error: The error that caused failure
        """
        with self._lock:
            self._status = ProgressStatus.FAILED
            update = ProgressUpdate(
                progress=self._progress,
                current_step=self._current_step,
                status=ProgressStatus.FAILED.value,
                message=str(error),
                details=self._details,
                timestamp=datetime.now()
            )
            self._progress_history.append(update)
            self._notify_update(update)
            return update
    
    def cancel(self) -> ProgressUpdate:
        """Mark as cancelled."""
        with self._lock:
            self._status = ProgressStatus.CANCELLED
            update = ProgressUpdate(
                progress=self._progress,
                current_step=self._current_step,
                status=ProgressStatus.CANCELLED.value,
                timestamp=datetime.now()
            )
            self._progress_history.append(update)
            self._notify_update(update)
            return update
    
    def reset(self) -> None:
        """Reset progress tracking to initial state."""
        with self._lock:
            self._progress = 0.0
            self._current_step = None
            self._status = ProgressStatus.NOT_STARTED
            self._message = None
            self._start_time = None
            self._last_update_time = None
            self._details = {}
            self._progress_history = []
            self._is_paused = False
    
    def _notify_update(self, update: ProgressUpdate) -> None:
        """Notify callback of progress update."""
        if self.update_callback:
            try:
                self.update_callback(update)
            except Exception as e:
                # Log error but don't crash
                pass
    
    def get_progress(self) -> float:
        """Get current progress value."""
        with self._lock:
            return self._progress
    
    def get_status(self) -> ProgressStatus:
        """Get current status."""
        with self._lock:
            return self._status
    
    def get_current_step(self) -> Optional[str]:
        """Get current step."""
        with self._lock:
            return self._current_step
    
    def get_message(self) -> Optional[str]:
        """Get message."""
        with self._lock:
            return self._message
    
    def get_history(self) -> List[ProgressUpdate]:
        """Get progress history."""
        with self._lock:
            return list(self._progress_history)
    
    def get_update_count(self) -> int:
        """Get number of progress updates."""
        with self._lock:
            return len(self._progress_history)
    
    def get_elapsed_time(self) -> Optional[float]:
        """Get elapsed time in seconds."""
        with self._lock:
            if self._start_time:
                return (datetime.now() - self._start_time).total_seconds()
            return None
    
    def get_details(self) -> Dict[str, Any]:
        """Get details."""
        with self._lock:
            return dict(self._details)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        with self._lock:
            return {
                "progress": self._progress,
                "status": self._status.value,
                "current_step": self._current_step,
                "message": self._message,
                "elapsed_time": self.get_elapsed_time(),
                "update_count": len(self._progress_history),
                "details": dict(self._details)
            }


class ProgressTrackerManager:
    """Manages multiple progress trackers."""
    
    def __init__(self):
        self._trackers: Dict[str, ProgressTracker] = {}
        self._lock = None  # Will be set on initialization
    
    def create_tracker(
        self,
        tracker_id: str,
        update_callback: Optional[Callable[[ProgressUpdate], None]] = None,
        minimum_interval: float = 0.1
    ) -> ProgressTracker:
        """Create a new progress tracker."""
        with self._get_lock():
            tracker = ProgressTracker(update_callback, minimum_interval)
            self._trackers[tracker_id] = tracker
            return tracker
    
    def get_tracker(self, tracker_id: str) -> Optional[ProgressTracker]:
        """Get a progress tracker."""
        with self._get_lock():
            return self._trackers.get(tracker_id)
    
    def remove_tracker(self, tracker_id: str) -> Optional[ProgressTracker]:
        """Remove a progress tracker."""
        with self._get_lock():
            return self._trackers.pop(tracker_id, None)
    
    def clear_all(self) -> None:
        """Clear all trackers (for testing)."""
        with self._get_lock():
            self._trackers.clear()
    
    def _get_lock(self):
        """Get or create the lock."""
        if self._lock is None:
            self._lock = threading.RLock()
        return self._lock
