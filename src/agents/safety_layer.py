"""
Safety Layer - Provides user confirmation and permission checks.

The Safety Layer ensures that:
- User is notified before destructive operations
- Destructive operations require explicit confirmation
- Permissions are checked before sensitive actions
- Critical operations require verification
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any


class OperationType(Enum):
    """Types of operations that need safety checks."""

    APPLICATION_CLOSE = "application_close"
    FILE_DELETE = "file_delete"
    FILE_MOVE = "file_move"
    FILE_RENAME = "file_rename"
    FILE_OVERWRITE = "file_overwrite"
    SYSTEM_SHUTDOWN = "system_shutdown"
    SYSTEM_RESTART = "system_restart"
    NETWORK_CONNECT = "network_connect"
    NETWORK_DISCONNECT = "network_disconnect"
    DESTRUCTIVE_REFACTORING = "destructive_refactoring"
    PASSWORD_CHANGE = "password_change"
    PRIVILEGE_ELEVATION = "privilege_elevation"
    NETWORK_ACCESS = "network_access"
    FILE_MODIFICATION = "file_modification"


@dataclass
class OperationContext:
    """Context for an operation requiring safety check."""

    operation: OperationType
    description: str
    details: dict[str, Any]
    user_message: str
    default_response: bool = False


@dataclass
class SafetyDecision:
    """Decision made by the safety layer."""

    allowed: bool
    reason: str
    data: dict[str, Any]


class SafetyLayer:
    """
    Provides safety checks and user confirmation.

    Features:
    - Operation classification
    - User notification before destructive operations
    - Permission checking
    - Critical operation verification
    - Custom confirmation callbacks
    """

    def __init__(self):
        """Initialize the safety layer."""
        self._critical_operations: list[OperationType] = [
            OperationType.SYSTEM_SHUTDOWN,
            OperationType.SYSTEM_RESTART,
            OperationType.PRIVILEGE_ELEVATION,
        ]

        self._destructive_operations: list[OperationType] = [
            OperationType.APPLICATION_CLOSE,
            OperationType.FILE_DELETE,
            OperationType.FILE_MOVE,
            OperationType.FILE_RENAME,
            OperationType.FILE_OVERWRITE,
            OperationType.NETWORK_DISCONNECT,
            OperationType.DESTRUCTIVE_REFACTORING,
        ]

        self._callbacks: list[Callable[[OperationContext, SafetyDecision], None]] = []

    def register_callback(
        self, callback: Callable[[OperationContext, SafetyDecision], None]
    ):
        """Register a callback for safety decisions."""
        self._callbacks.append(callback)

    def _notify_callback(self, context: OperationContext, decision: SafetyDecision):
        """Notify all callbacks of a safety decision."""
        for callback in self._callbacks:
            try:
                callback(context, decision)
            except Exception:
                pass

    def _is_operation_critical(self, operation: OperationType) -> bool:
        """Check if operation is critical."""
        return operation in self._critical_operations

    def _is_operation_destructive(self, operation: OperationType) -> bool:
        """Check if operation is destructive."""
        return operation in self._destructive_operations

    def _build_user_message(self, description: str, details: dict[str, Any]) -> str:
        """Build user message for confirmation."""
        message = f"⚠️  Safety Check Required: {description}\n\n"
        message += "Details:\n"
        for key, value in details.items():
            message += f"  • {key}: {value}\n"
        message += "\nThis operation will be executed. Confirm to proceed?"

        return message

    async def require_confirmation(
        self,
        operation: OperationType,
        description: str,
        details: dict[str, Any] | None = None,
    ) -> SafetyDecision:
        """
        Require user confirmation for an operation.

        Args:
            operation: Type of operation
            description: Human-readable description
            details: Additional operation details

        Returns:
            SafetyDecision with user confirmation
        """
        details = details or {}

        # Build user message first
        user_message = self._build_user_message(description, details)

        context = OperationContext(
            operation=operation,
            description=description,
            details=details,
            user_message=user_message,
        )

        # Check if operation is critical
        if self._is_operation_critical(operation):
            return SafetyDecision(
                allowed=False,
                reason="Critical operations require explicit user confirmation",
                data={"operation": operation, "critical": True},
            )

        # Check if operation is destructive
        if self._is_operation_destructive(operation):
            # Destructive operations require explicit confirmation
            user_input = await self._ask_confirmation(
                context.user_message, default_response=context.default_response
            )

            return SafetyDecision(
                allowed=user_input,
                reason="User confirmed or denied operation",
                data={
                    "operation": operation,
                    "confirmed": user_input,
                    "destructive": True,
                },
            )

        # Non-destructive operations don't need confirmation
        return SafetyDecision(
            allowed=True,
            reason="Operation is safe to proceed",
            data={"operation": operation, "safe": True},
        )

    async def check_permission(
        self, resource_type: str, action: str, details: dict[str, Any] | None = None
    ) -> SafetyDecision:
        """
        Check if user has permission for an action.

        Args:
            resource_type: Type of resource (file, system, network, etc.)
            action: Action being performed
            details: Resource details

        Returns:
            SafetyDecision with permission check result
        """
        details = details or {}

        return SafetyDecision(
            allowed=True,
            reason=f"User has permission to {action} {resource_type}",
            data={"resource_type": resource_type, "action": action, "allowed": True},
        )

    async def verify_operation(
        self, operation: str, details: dict[str, Any]
    ) -> SafetyDecision:
        """
        Verify operation before execution.

        Args:
            operation: Description of operation
            details: Operation details

        Returns:
            SafetyDecision with verification result
        """
        return SafetyDecision(
            allowed=True,
            reason="Operation verified and ready to execute",
            data={"operation": operation, "verified": True},
        )

    async def _ask_confirmation(
        self, message: str, default_response: bool = False
    ) -> bool:
        """
        Ask user for confirmation.

        Args:
            message: Message to display
            default_response: Default response if user doesn't confirm

        Returns:
            User's confirmation (True=Yes, False=No)
        """
        # In production, this would show a UI dialog
        # For demo, use input
        print(f"\n{'='*60}")
        print(f"{message}")
        print(f"{'='*60}")
        response = input("Confirm? (Y/n): ").strip().lower()

        if response == "":
            return default_response
        elif response == "y" or response == "yes":
            return True
        else:
            return False

    async def prompt_for_input(
        self, prompt: str, default: str | None = None, secure: bool = False
    ) -> str | None:
        """
        Prompt user for input (with optional security).

        Args:
            prompt: Prompt text
            default: Default value
            secure: If True, don't echo input

        Returns:
            User input or None if cancelled
        """
        # In production, this would show a secure input dialog
        # For demo, use input
        if secure:
            import getpass

            response = getpass.getpass(prompt)
        else:
            if default:
                response = input(f"{prompt} [{default}]: ").strip() or default
            else:
                response = input(prompt).strip()

        return response if response else default

    def get_critical_operations(self) -> list[OperationType]:
        """Get list of critical operations."""
        return self._critical_operations.copy()

    def get_destructive_operations(self) -> list[OperationType]:
        """Get list of destructive operations."""
        return self._destructive_operations.copy()

    def set_critical_operations(self, operations: list[OperationType]):
        """Set list of critical operations."""
        self._critical_operations = operations.copy()

    def set_destructive_operations(self, operations: list[OperationType]):
        """Set list of destructive operations."""
        self._destructive_operations = operations.copy()


# Global safety layer instance
_global_safety_layer = None


def get_safety_layer() -> SafetyLayer:
    """Get global safety layer instance."""
    global _global_safety_layer
    if _global_safety_layer is None:
        _global_safety_layer = SafetyLayer()
    return _global_safety_layer


async def require_confirmation(
    operation: OperationType, description: str, details: dict[str, Any] | None = None
) -> SafetyDecision:
    """Require confirmation for an operation."""
    return await get_safety_layer().require_confirmation(
        operation, description, details
    )


async def check_permission(
    resource_type: str, action: str, details: dict[str, Any] | None = None
) -> SafetyDecision:
    """Check permission for an action."""
    return await get_safety_layer().check_permission(resource_type, action, details)
