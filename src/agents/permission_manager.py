"""
Permission Manager - Provides user confirmation and logging for destructive operations.

Ensures that operations like process killing, file deletion, etc. require explicit
user approval, maintaining an audit trail that can be reviewed or undone.

This follows the principle of least privilege and provides accountability.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Callable, Any, Dict

logger = logging.getLogger(__name__)


class PermissionLevel(str, Enum):
    """Permission levels for different types of operations"""
    SAFE = "safe"  # No confirmation needed (read-only, query operations)
    MODERATE = "moderate"  # Confirmation needed (moderate impact)
    DANGEROUS = "dangerous"  # Strong confirmation needed (destructive)


@dataclass
class PermissionRequest:
    """
    Represents a permission request.

    Captures all context needed for a user to make an informed decision about
    whether to approve or deny an operation.
    """
    id: str
    operation: str
    target: str  # PID, filename, URL, etc.
    details: str  # Human-readable description
    level: PermissionLevel
    requester: Optional[str] = None  # Who is requesting the permission
    timestamp: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)  # Additional context
    approved: bool = False
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    reason: Optional[str] = None


class PermissionManager:
    """
    Manages permission requests and approvals for system operations.

    Provides a centralized way to request, approve, and log permissions for
    potentially destructive operations.

    Features:
    - Ask for user confirmation before dangerous operations
    - Maintain an audit log of all approved/denied requests
    - Support for custom confirmation handlers
    - Thread-safe operation
    """

    def __init__(self, default_confirmation_handler: Optional[Callable[[PermissionRequest], bool]] = None):
        """
        Initialize the permission manager.

        Args:
            default_confirmation_handler: Optional callback to use as default confirmation method.
                                         If not provided, uses a simple prompt (good for CLI).
        """
        self._request_log: List[PermissionRequest] = []
        self._lock = threading.RLock()
        self._confirmation_handler = default_confirmation_handler or self._default_confirmation_handler

        logger.info("PermissionManager initialized")

    def _default_confirmation_handler(self, request: PermissionRequest) -> bool:
        """
        Default confirmation handler.

        In a GUI environment, this would show a dialog with all the details.
        In a CLI environment, it would prompt the user.

        Args:
            request: The permission request to confirm

        Returns:
            True if user approved, False if denied
        """
        print("\n" + "=" * 70)
        print(f"PERMISSION REQUEST: {request.operation.upper()}")
        print("=" * 70)
        print(f"Target: {request.target}")
        print(f"Details: {request.details}")
        print(f"Level: {request.level.value.upper()}")
        print(f"Time: {request.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

        if request.requester:
            print(f"Requested by: {request.requester}")

        if request.context:
            print("\nContext:")
            for key, value in request.context.items():
                print(f"  {key}: {value}")

        if request.reason:
            print(f"\nReason: {request.reason}")

        while True:
            response = input("\nDo you want to approve this operation? (yes/no): ").strip().lower()
            if response in ('yes', 'y'):
                return True
            elif response in ('no', 'n'):
                return False
            print("Please enter 'yes' or 'no'.")

    def request_permission(
        self,
        operation: str,
        target: str,
        details: str,
        level: PermissionLevel = PermissionLevel.MODERATE,
        requester: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Request permission for an operation.

        Args:
            operation: Name of the operation (e.g., 'kill_process', 'delete_file')
            target: What is being operated on (e.g., PID 1234, file path)
            details: Human-readable description of what will happen
            level: Permission level required
            requester: Who is requesting the permission
            context: Additional context information

        Returns:
            True if approved, False if denied
        """
        request = PermissionRequest(
            id=str(datetime.now().timestamp()).replace('.', '_'),
            operation=operation,
            target=target,
            details=details,
            level=level,
            requester=requester,
            context=context or {}
        )

        try:
            approved = self._confirmation_handler(request)

            # Update request with approval status
            request.approved = approved
            request.approved_at = datetime.now()
            request.approved_by = "user" if approved else None
            request.reason = None

            # Log the request
            with self._lock:
                self._request_log.append(request)

            if approved:
                logger.info(f"Permission approved: {operation} on {target}")
            else:
                logger.info(f"Permission denied: {operation} on {target}")

            return approved

        except Exception as e:
            logger.error(f"Error requesting permission: {e}")
            # Default to denying on error for safety
            return False

    def request_dangerous_permission(
        self,
        operation: str,
        target: str,
        details: str,
        requester: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Request permission for a dangerous operation.

        Dangerous operations require explicit user approval and provide
        clear warnings about potential consequences.

        Args:
            operation: Name of the operation
            target: What is being operated on
            details: Human-readable description
            requester: Who is requesting the permission
            context: Additional context

        Returns:
            True if approved, False if denied
        """
        return self.request_permission(
            operation=operation,
            target=target,
            details=details,
            level=PermissionLevel.DANGEROUS,
            requester=requester,
            context=context
        )

    def get_request_log(self) -> List[PermissionRequest]:
        """
        Get the audit log of all permission requests.

        Returns:
            List of PermissionRequest objects
        """
        with self._lock:
            return self._request_log.copy()

    def get_approved_requests(self) -> List[PermissionRequest]:
        """
        Get all approved permission requests.

        Returns:
            List of approved PermissionRequest objects
        """
        with self._lock:
            return [r for r in self._request_log if r.approved]

    def get_denied_requests(self) -> List[PermissionRequest]:
        """
        Get all denied permission requests.

        Returns:
            List of denied PermissionRequest objects
        """
        with self._lock:
            return [r for r in self._request_log if not r.approved]

    def get_recent_requests(self, limit: int = 10) -> List[PermissionRequest]:
        """
        Get the most recent permission requests.

        Args:
            limit: Maximum number of recent requests to return

        Returns:
            List of recent PermissionRequest objects
        """
        with self._lock:
            return self._request_log[-limit:] if self._request_log else []

    def clear_log(self) -> None:
        """Clear the permission request log."""
        with self._lock:
            self._request_log.clear()
        logger.info("Permission log cleared")

    def set_confirmation_handler(self, handler: Callable[[PermissionRequest], bool]) -> None:
        """
        Set a custom confirmation handler.

        Args:
            handler: Callback function that takes a PermissionRequest and returns bool
        """
        self._confirmation_handler = handler
        logger.info("Confirmation handler updated")

    def format_request_log(self) -> str:
        """
        Format the permission request log for display.

        Returns:
            Formatted string representation of the log
        """
        with self._lock:
            if not self._request_log:
                return "No permission requests in log."

            lines = ["Permission Request Log:"]
            lines.append(f"{'='*70}")
            lines.append(f"{'TIMESTAMP':<20} {'OPERATION':<25} {'TARGET':<30} {'APPROVED':<10}")
            lines.append(f"{'-'*70}")

            for request in self._request_log:
                approved_str = "✓" if request.approved else "✗"
                timestamp_str = request.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                operation_str = request.operation[:25]
                target_str = request.target[:30]

                lines.append(f"{timestamp_str:<20} {operation_str:<25} {target_str:<30} {approved_str:<10}")

            lines.append(f"{'='*70}")
            lines.append(f"Total: {len(self._request_log)} requests")

            return "\n".join(lines)

    def can_execute_operation(self, operation: str, target: str, level: PermissionLevel = PermissionLevel.MODERATE) -> bool:
        """
        Check if an operation can be executed without asking for permission.

        This is useful for safety-critical operations that should never be
        performed without explicit permission.

        Args:
            operation: Name of the operation
            target: What is being operated on
            level: Permission level required

        Returns:
            True if operation is safe to execute without asking, False otherwise
        """
        # Safe operations don't require confirmation
        safe_operations = {
            'list_processes',
            'get_process_info',
            'search_processes',
            'list_files',
            'read_file',
            'get_process_state',
            'get_all_process_states',
        }

        if operation in safe_operations:
            return True

        # Only dangerous operations with specific targets might be safe
        dangerous_operations = {
            'kill_process',
            'stop_process',
            'delete_file',
            'terminate_service',
            'format_disk',
        }

        if operation in dangerous_operations:
            # Never automatically execute dangerous operations
            return False

        # Default to requiring confirmation
        return False
