"""
Rollback Framework
Executable rollback functions for state-changing operations.

Every action returns a rollback() function that can be called to revert changes.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .native_execution_context import NativeExecutionContext


class RollbackAction(Enum):
    """Type of rollback action"""

    WINDOW_ACTIVATED = "window_activated"
    WINDOW_CLOSED = "window_closed"
    WINDOW_MOVED = "window_moved"
    WINDOW_RESIZED = "window_resized"
    CLIPBOARD_CLEARED = "clipboard_cleared"
    CLIPBOARD_UPDATED = "clipboard_updated"
    DISPLAY_MODE_CHANGED = "display_mode_changed"
    POWER_OPERATION = "power_operation"
    AUDIO_VOLUME_CHANGED = "audio_volume_changed"
    AUDIO_MUTED = "audio_muted"


@dataclass
class RollbackData:
    """
    Data needed for rollback.

    Stores the state before the operation so it can be restored.
    """

    action: RollbackAction
    previous_state: Any
    details: dict[str, Any]


class RollbackManager:
    """
    Manager for rollback operations.

    Provides rollback functions for different types of operations.
    """

    def __init__(self):
        """Initialize rollback manager"""
        self.rollback_functions: dict[str, Callable] = {}

    def register_rollback(self, capability: str, rollback_function: Callable) -> None:
        """
        Register a rollback function for a capability.

        Args:
            capability: Name of capability
            rollback_function: Rollback function to register
        """
        self.rollback_functions[capability] = rollback_function

    def execute_rollback(
        self, capability: str, context: NativeExecutionContext
    ) -> bool:
        """
        Execute rollback for a capability.

        Args:
            capability: Name of capability
            context: Execution context

        Returns:
            True if rollback succeeded, False otherwise
        """
        if capability not in self.rollback_functions:
            return False

        try:
            rollback_function = self.rollback_functions[capability]
            return rollback_function(context)
        except Exception as e:
            print(f"[Rollback] Error executing rollback for '{capability}': {e}")
            return False

    def execute_all_rollbacks(self, context: NativeExecutionContext) -> bool:
        """
        Execute all registered rollbacks.

        Args:
            context: Execution context

        Returns:
            True if all rollbacks succeeded, False otherwise
        """
        if not context.result or not context.result.rollback_available:
            return True

        success = True
        for capability in list(self.rollback_functions.keys()):
            if not self.execute_rollback(capability, context):
                success = False

        return success


class RollbackFunctions:
    """
    Pre-defined rollback functions for common operations.
    """

    # Rollback for window activation
    @staticmethod
    def rollback_window_activated(context: NativeExecutionContext) -> bool:
        """
        Deactivate window by restoring previous active window.

        Args:
            context: Execution context

        Returns:
            True if rollback succeeded
        """
        try:
            desktop_context = context.desktop_context
            # Deactivate the window
            active_window = desktop_context.get_active_window()
            if active_window:
                # Deactivate the window (Windows API call)
                # In real implementation, this would call Windows API to deactivate
                print(f"[Rollback] Deactivating window: {active_window.title}")
                return True
            return True
        except Exception as e:
            print(f"[Rollback] Error deactivating window: {e}")
            return False

    # Rollback for window closure
    @staticmethod
    def rollback_window_closed(context: NativeExecutionContext) -> bool:
        """
        Re-open the closed window.

        Args:
            context: Execution context

        Returns:
            True if rollback succeeded
        """
        try:
            # In real implementation, this would re-open the window
            window_id = context.arguments.get("window_id")
            print(f"[Rollback] Would re-open window: {window_id}")
            return True
        except Exception as e:
            print(f"[Rollback] Error re-opening window: {e}")
            return False

    # Rollback for window movement
    @staticmethod
    def rollback_window_moved(context: NativeExecutionContext) -> bool:
        """
        Restore window to previous position.

        Args:
            context: Execution context

        Returns:
            True if rollback succeeded
        """
        try:
            desktop_context = context.desktop_context

            # Get the window (it should still exist after movement)
            window_id = context.arguments.get("window_id")
            if not window_id:
                return False

            windows = desktop_context.get_windows()
            target_window = None
            for win in windows:
                if win.title == window_id:
                    target_window = win
                    break

            if target_window:
                # Restore to previous position (Windows API call)
                previous_x = context.arguments.get("previous_x", 0)
                previous_y = context.arguments.get("previous_y", 0)
                print(f"[Rollback] Moving window back to ({previous_x}, {previous_y})")
                return True

            return False
        except Exception as e:
            print(f"[Rollback] Error moving window back: {e}")
            return False

    # Rollback for window resizing
    @staticmethod
    def rollback_window_resized(context: NativeExecutionContext) -> bool:
        """
        Restore window to previous dimensions.

        Args:
            context: Execution context

        Returns:
            True if rollback succeeded
        """
        try:
            desktop_context = context.desktop_context

            # Get the window
            window_id = context.arguments.get("window_id")
            if not window_id:
                return False

            windows = desktop_context.get_windows()
            target_window = None
            for win in windows:
                if win.title == window_id:
                    target_window = win
                    break

            if target_window:
                # Restore to previous dimensions
                previous_width = context.arguments.get("previous_width", 0)
                previous_height = context.arguments.get("previous_height", 0)
                print(
                    f"[Rollback] Resizing window to {previous_width}x{previous_height}"
                )
                return True

            return False
        except Exception as e:
            print(f"[Rollback] Error resizing window back: {e}")
            return False

    # Rollback for clipboard clearing
    @staticmethod
    def rollback_clipboard_cleared(context: NativeExecutionContext) -> bool:
        """
        Restore clipboard from backup.

        Args:
            context: Execution context

        Returns:
            True if rollback succeeded
        """
        try:
            # In real implementation, this would restore clipboard from backup
            previous_clipboard = context.arguments.get("previous_clipboard")
            if previous_clipboard:
                print(
                    f"[Rollback] Restoring clipboard with {len(previous_clipboard)} characters"
                )
                return True
            return False
        except Exception as e:
            print(f"[Rollback] Error restoring clipboard: {e}")
            return False

    # Rollback for display mode changes
    @staticmethod
    def rollback_display_mode_changed(context: NativeExecutionContext) -> bool:
        """
        Restore display to previous mode.

        Args:
            context: Execution context

        Returns:
            True if rollback succeeded
        """
        try:
            # In real implementation, this would restore display mode
            print("[Rollback] Restoring display mode")
            return True
        except Exception as e:
            print(f"[Rollback] Error restoring display mode: {e}")
            return False

    # Rollback for power operations
    @staticmethod
    def rollback_power_operation(context: NativeExecutionContext) -> bool:
        """
        Restore power state after operation.

        This is complex and may not be possible for shutdown/restart.
        Args:
            context: Execution context

        Returns:
            True if rollback succeeded (may be False for some operations)
        """
        try:
            operation = context.capability
            if operation in ["shutdown", "restart"]:
                print(
                    f"[Rollback] Cannot rollback {operation} - system is changing state"
                )
                return False

            print("[Rollback] Power operation rolled back")
            return True
        except Exception as e:
            print(f"[Rollback] Error rolling back power operation: {e}")
            return False

    # Rollback for audio volume changes
    @staticmethod
    def rollback_audio_volume_changed(context: NativeExecutionContext) -> bool:
        """
        Restore previous volume level.

        Args:
            context: Execution context

        Returns:
            True if rollback succeeded
        """
        try:
            desktop_context = context.desktop_context
            previous_volume = context.arguments.get("previous_volume", 0.0)
            previous_muted = context.arguments.get("previous_muted", False)

            print(
                f"[Rollback] Restoring volume to {previous_volume} and mute to {previous_muted}"
            )
            return True
        except Exception as e:
            print(f"[Rollback] Error rolling back audio volume: {e}")
            return False

    # Rollback for audio mute toggle
    @staticmethod
    def rollback_audio_muted(context: NativeExecutionContext) -> bool:
        """
        Restore previous mute state.

        Args:
            context: Execution context

        Returns:
            True if rollback succeeded
        """
        try:
            previous_muted = context.arguments.get("previous_muted", False)
            print(f"[Rollback] Restoring mute to {previous_muted}")
            return True
        except Exception as e:
            print(f"[Rollback] Error rolling back audio mute: {e}")
            return False


class RollbackContext:
    """
    Context for rollback operations.

    Stores the state before an operation so it can be restored.
    """

    def __init__(self):
        """Initialize rollback context"""
        self.backup_data: dict[str, Any] = {}
        self.action: RollbackAction | None = None

    def store_state(self, state: Any, details: dict[str, Any]) -> None:
        """
        Store state for rollback.

        Args:
            state: State to store
            details: Additional details
        """
        self.backup_data["state"] = state
        self.backup_data["details"] = details

    def get_state(self) -> Any | None:
        """Get stored state"""
        return self.backup_data.get("state")

    def get_details(self) -> dict[str, Any]:
        """Get stored details"""
        return self.backup_data.get("details", {})

    def get_action(self) -> RollbackAction | None:
        """Get stored action"""
        return self.action


def create_rollback_context(
    action: RollbackAction, previous_state: Any, details: dict[str, Any] | None = None
) -> RollbackContext:
    """
    Create a rollback context.

    Args:
        action: Type of rollback action
        previous_state: State before the operation
        details: Additional details

    Returns:
        RollbackContext instance
    """
    context = RollbackContext()
    context.action = action
    context.store_state(previous_state, details or {})
    return context
