"""
Tool Execution Engine - Cancellation System

This module provides safe cancellation for tool executions, ensuring
that running operations can be stopped gracefully.
"""

import threading
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from typing import Any

from .exceptions import CancellationError


class CancellationStatus(Enum):
    """Cancellation status values."""

    NOT_REQUESTED = "not_requested"
    REQUESTED = "requested"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class CancellationToken:
    """Represents a cancellation token for an execution."""

    def __init__(self):
        """Initialize the cancellation token."""
        self._event = threading.Event()
        self._status = CancellationStatus.NOT_REQUESTED
        self._cancel_time: datetime | None = None
        self._cancel_reason: str | None = None
        self._callbacks: list = []
        self._lock = threading.RLock()

    def request_cancellation(self, reason: str = None) -> bool:
        """
        Request cancellation of the execution.

        Args:
            reason: Optional reason for cancellation

        Returns:
            True if cancellation was requested
        """
        with self._lock:
            if self._event.is_set():
                return False  # Already cancelled

            self._event.set()
            self._status = CancellationStatus.REQUESTED
            self._cancel_time = datetime.now()
            self._cancel_reason = reason

            # Notify all callbacks
            for callback in self._callbacks:
                try:
                    callback(reason)
                except Exception:
                    # Log error but don't crash
                    pass

            return True

    def check_cancellation(self) -> bool:
        """
        Check if cancellation has been requested.

        Returns:
            True if cancellation has been requested
        """
        with self._lock:
            return self._event.is_set()

    def set_status(self, status: CancellationStatus) -> None:
        """
        Set the cancellation status.

        Args:
            status: The new status
        """
        with self._lock:
            self._status = status

    def is_cancelled(self) -> bool:
        """
        Check if cancellation has been requested.

        Returns:
            True if cancellation has been requested
        """
        return self.check_cancellation()

    def is_set(self) -> bool:
        """
        Check if cancellation has been requested.

        Returns:
            True if cancellation has been requested
        """
        return self.check_cancellation()

    def wait(self, timeout: float = None) -> bool:
        """
        Wait for cancellation or timeout.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            True if cancellation was requested, False on timeout
        """
        return self._event.wait(timeout)

    def add_callback(self, callback: Callable[[str], None]) -> None:
        """
        Add a callback to be notified when cancellation occurs.

        Args:
            callback: Callback function that receives the cancel reason
        """
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[str], None]) -> None:
        """
        Remove a cancellation callback.

        Args:
            callback: The callback to remove
        """
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def clear(self) -> None:
        """Clear the cancellation event (allow re-cancellation)."""
        with self._lock:
            self._event.clear()
            self._status = CancellationStatus.NOT_REQUESTED
            self._cancel_time = None
            self._cancel_reason = None

    def get_status(self) -> CancellationStatus:
        """Get the current cancellation status."""
        with self._lock:
            return self._status

    def get_cancel_time(self) -> datetime | None:
        """Get the time cancellation was requested."""
        with self._lock:
            return self._cancel_time

    def get_cancel_reason(self) -> str | None:
        """Get the reason for cancellation."""
        with self._lock:
            return self._cancel_reason

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        with self._lock:
            return {
                "is_cancelled": self._event.is_set(),
                "status": self._status.value,
                "cancel_time": (
                    self._cancel_time.isoformat() if self._cancel_time else None
                ),
                "cancel_reason": self._cancel_reason,
                "callback_count": len(self._callbacks),
            }


class CancellationManager:
    """Manages cancellation tokens for multiple executions."""

    def __init__(self):
        self._tokens: dict[str, CancellationToken] = {}
        self._lock = None  # Will be set on initialization

    def create_token(self, token_id: str) -> CancellationToken:
        """Create a new cancellation token."""
        with self._get_lock():
            token = CancellationToken()
            self._tokens[token_id] = token
            return token

    def get_token(self, token_id: str) -> CancellationToken | None:
        """Get a cancellation token."""
        with self._get_lock():
            return self._tokens.get(token_id)

    def remove_token(self, token_id: str) -> CancellationToken | None:
        """Remove a cancellation token."""
        with self._get_lock():
            return self._tokens.pop(token_id, None)

    def request_cancellation(self, token_id: str, reason: str = None) -> bool:
        """
        Request cancellation for a specific token.

        Args:
            token_id: The token ID
            reason: Optional reason for cancellation

        Returns:
            True if cancellation was requested
        """
        token = self.get_token(token_id)
        if token:
            return token.request_cancellation(reason)
        return False

    def check_cancellation(self, token_id: str) -> bool:
        """
        Check if a specific token has been cancelled.

        Args:
            token_id: The token ID

        Returns:
            True if cancellation was requested
        """
        token = self.get_token(token_id)
        if token:
            return token.check_cancellation()
        return False

    def get_all_cancelled_tokens(self) -> list:
        """
        Get all cancelled tokens.

        Returns:
            List of cancelled token IDs
        """
        with self._get_lock():
            return [
                token_id
                for token_id, token in self._tokens.items()
                if token.is_cancelled()
            ]

    def get_active_token_count(self) -> int:
        """Get the number of active tokens."""
        with self._get_lock():
            return len(self._tokens)

    def clear_all(self) -> None:
        """Clear all tokens (for testing)."""
        with self._get_lock():
            self._tokens.clear()

    def _get_lock(self):
        """Get or create the lock."""
        if self._lock is None:
            self._lock = threading.RLock()
        return self._lock


class CancellationHandler:
    """Context manager for safe cancellation handling."""

    def __init__(
        self,
        cancellation_token: CancellationToken,
        on_cancel: Callable = None,
        max_wait_time: float = 5.0,
    ):
        """
        Initialize the cancellation handler.

        Args:
            cancellation_token: The cancellation token
            on_cancel: Optional callback when cancellation occurs
            max_wait_time: Maximum time to wait for graceful shutdown
        """
        self.token = cancellation_token
        self.on_cancel = on_cancel
        self.max_wait_time = max_wait_time
        self._cancelled = False
        self._cleanup_performed = False

    def __enter__(self):
        """Enter context manager."""
        self.token.add_callback(self._handle_cancellation)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        self.token.remove_callback(self._handle_cancellation)

        if self._cancelled:
            # Check if exception is cancellation error
            if isinstance(exc_val, CancellationError):
                pass  # Already handled
            else:
                # Raise a cancellation error if operation was cancelled
                raise CancellationError(
                    "Operation was cancelled", execution_id=self.token.get_status()
                )

        return False  # Don't suppress exceptions

    def _handle_cancellation(self, reason: str = None):
        """Handle cancellation event."""
        self._cancelled = True

        if self.on_cancel:
            try:
                self.on_cancel(reason)
            except Exception:
                # Log error but don't crash
                pass


def check_cancellation(
    cancellation_token: CancellationToken, operation_name: str = None
) -> bool:
    """
    Check for cancellation and raise an error if cancelled.

    Args:
        cancellation_token: The cancellation token
        operation_name: Optional name of the operation being checked

    Returns:
        True if not cancelled

    Raises:
        CancellationError: If cancellation was requested
    """
    if cancellation_token.check_cancellation():
        reason = cancellation_token.get_cancel_reason()
        raise CancellationError(
            f"Operation cancelled: {operation_name or 'unknown'}",
            execution_id=cancellation_token.get_status(),
        )
    return True


def safe_execute_with_cancellation(
    operation: Callable,
    cancellation_token: CancellationToken,
    timeout: float = None,
    operation_name: str = None,
) -> Any:
    """
    Execute an operation with cancellation support.

    Args:
        operation: The operation to execute
        cancellation_token: The cancellation token
        timeout: Optional timeout in seconds
        operation_name: Optional name of the operation

    Returns:
        The result of the operation

    Raises:
        CancellationError: If operation was cancelled
        TimeoutError: If operation timed out
    """

    def _wrapper():
        if timeout:
            return operation(timeout=timeout)
        return operation()

    # Check for cancellation before starting
    check_cancellation(cancellation_token, operation_name)

    # Execute the operation
    try:
        return _wrapper()
    except CancellationError:
        # Re-raise cancellation errors
        raise
    except Exception as e:
        # Convert other exceptions
        raise CancellationError(
            f"Operation failed: {operation_name or 'unknown'}",
            execution_id=cancellation_token.get_status(),
        ) from e
