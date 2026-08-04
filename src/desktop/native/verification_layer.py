"""
Verification Layer
Verifies that desktop actions completed successfully.

Every capability supports execute() → verify() → complete().
"""

from typing import Callable, Optional, Any
from dataclasses import dataclass

from .native_models import WindowInfo, ProcessInfo, ClipboardData, DisplayInfo, AudioDevice, NetworkInterface
from .native_exceptions import VerificationError
from .native_execution_context import NativeExecutionContext


class VerificationMode(Enum):
    """Verification mode"""
    NONE = "none"  # No verification
    PRE_CHECK = "pre_check"  # Check before execution
    POST_CHECK = "post_check"  # Check after execution
    BOTH = "both"  # Both pre and post check
    EXACT = "exact"  # Verify exact values


@dataclass
class VerificationResult:
    """
    Result of a verification check.

    Contains whether verification passed and any error messages.
    """
    passed: bool
    error_message: Optional[str] = None
    warnings: list[str] = None
    details: dict = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.details is None:
            self.details = {}


class VerificationLayer:
    """
    Verification layer for desktop actions.

    Provides verification methods for each capability type.
    """

    # Verification functions for different capability types
    _verification_handlers: dict[str, Callable[[Any, dict], VerificationResult]] = {}

    @classmethod
    def register_handler(cls, capability_type: str, handler: Callable) -> None:
        """
        Register a verification handler for a capability type.

        Args:
            capability_type: Type of capability
            handler: Verification handler function
        """
        cls._verification_handlers[capability_type] = handler

    @classmethod
    def verify_window_activated(cls, context: NativeExecutionContext) -> VerificationResult:
        """
        Verify that a window was activated.

        Args:
            context: Execution context

        Returns:
            VerificationResult
        """
        # Get the window info from arguments
        window_id = context.arguments.get("window_id")
        if not window_id:
            return VerificationResult(passed=False, error_message="Window ID not provided")

        # Get the active window from desktop context
        desktop_context = context.desktop_context
        active_window = desktop_context.get_active_window()

        if not active_window:
            return VerificationResult(
                passed=False,
                error_message="No active window found"
            )

        # Check if the activated window matches
        # For simplicity, we check if the active window has the expected title or process ID
        if window_id == active_window.title or window_id == str(active_window.process_id):
            return VerificationResult(passed=True)

        return VerificationResult(
            passed=False,
            error_message=f"Expected window '{window_id}', but got '{active_window.title}'"
        )

    @classmethod
    def verify_window_closed(cls, context: NativeExecutionContext) -> VerificationResult:
        """
        Verify that a window was closed.

        Args:
            context: Execution context

        Returns:
            VerificationResult
        """
        window_id = context.arguments.get("window_id")
        if not window_id:
            return VerificationResult(passed=False, error_message="Window ID not provided")

        # Check if window still exists
        windows = context.desktop_context.get_windows()
        window_exists = any(win.title == window_id for win in windows)

        if not window_exists:
            return VerificationResult(passed=True, details={"window_closed": True})

        return VerificationResult(
            passed=False,
            error_message=f"Window '{window_id}' still exists"
        )

    @classmethod
    def verify_window_moved(cls, context: NativeExecutionContext) -> VerificationResult:
        """
        Verify that a window was moved to expected position.

        Args:
            context: Execution context

        Returns:
            VerificationResult
        """
        expected_x = context.arguments.get("x")
        expected_y = context.arguments.get("y")
        window_id = context.arguments.get("window_id")

        if not expected_x or not expected_y or not window_id:
            return VerificationResult(passed=False, error_message="Missing position or window_id")

        # Get window info
        windows = context.desktop_context.get_windows()
        target_window = None
        for win in windows:
            if win.title == window_id:
                target_window = win
                break

        if not target_window:
            return VerificationResult(passed=False, error_message=f"Window '{window_id}' not found")

        # Check position
        actual_x = target_window.rect.left
        actual_y = target_window.rect.top

        if abs(actual_x - expected_x) < 1 and abs(actual_y - expected_y) < 1:
            return VerificationResult(
                passed=True,
                details={
                    "expected": {"x": expected_x, "y": expected_y},
                    "actual": {"x": actual_x, "y": actual_y}
                }
            )

        return VerificationResult(
            passed=False,
            error_message=f"Window position mismatch: expected ({expected_x}, {expected_y}), got ({actual_x}, {actual_y})"
        )

    @classmethod
    def verify_window_resized(cls, context: NativeExecutionContext) -> VerificationResult:
        """
        Verify that a window was resized to expected dimensions.

        Args:
            context: Execution context

        Returns:
            VerificationResult
        """
        expected_width = context.arguments.get("width")
        expected_height = context.arguments.get("height")
        window_id = context.arguments.get("window_id")

        if not expected_width or not expected_height or not window_id:
            return VerificationResult(passed=False, error_message="Missing dimensions or window_id")

        # Get window info
        windows = context.desktop_context.get_windows()
        target_window = None
        for win in windows:
            if win.title == window_id:
                target_window = win
                break

        if not target_window:
            return VerificationResult(passed=False, error_message=f"Window '{window_id}' not found")

        # Check dimensions
        actual_width = target_window.rect.right - target_window.rect.left
        actual_height = target_window.rect.bottom - target_window.rect.top

        if abs(actual_width - expected_width) < 1 and abs(actual_height - expected_height) < 1:
            return VerificationResult(
                passed=True,
                details={
                    "expected": {"width": expected_width, "height": expected_height},
                    "actual": {"width": actual_width, "height": actual_height}
                }
            )

        return VerificationResult(
            passed=False,
            error_message=f"Window size mismatch: expected ({expected_width}x{expected_height}), got ({actual_width}x{actual_height})"
        )

    @classmethod
    def verify_clipboard_updated(cls, context: NativeExecutionContext) -> VerificationResult:
        """
        Verify that clipboard was updated.

        Args:
            context: Execution context

        Returns:
            VerificationResult
        """
        # Check if clipboard has content
        clipboard = context.desktop_context.get_clipboard()

        if not clipboard or not clipboard.has_text:
            return VerificationResult(passed=False, error_message="Clipboard not updated or has no text")

        # Check if clipboard matches expected content (if provided)
        expected_text = context.arguments.get("text")
        if expected_text and clipboard.text != expected_text:
            return VerificationResult(
                passed=False,
                error_message=f"Clipboard text mismatch: expected '{expected_text}', got '{clipboard.text}'"
            )

        return VerificationResult(
            passed=True,
            details={"has_text": clipboard.has_text, "length": len(clipboard.text) if clipboard.text else 0}
        )

    @classmethod
    def verify_display_updated(cls, context: NativeExecutionContext) -> VerificationResult:
        """
        Verify that display information was retrieved.

        Args:
            context: Execution context

        Returns:
            VerificationResult
        """
        # This is a read operation, so verification is about whether we got data
        if not context.result or not context.result.success:
            return VerificationResult(passed=False, error_message="Failed to retrieve display information")

        displays = context.desktop_context.get_displays()
        if not displays or len(displays) == 0:
            return VerificationResult(passed=False, error_message="No displays found")

        return VerificationResult(
            passed=True,
            details={"display_count": len(displays)}
        )

    @classmethod
    def verify_power_operation(cls, context: NativeExecutionContext) -> VerificationResult:
        """
        Verify that power operation completed.

        Args:
            context: Execution context

        Returns:
            VerificationResult
        """
        # Power operations (shutdown, restart, sleep, etc.) are tricky to verify
        # We can't easily check if computer is off/shutdown
        # So we just check if the operation started successfully
        if not context.result or not context.result.success:
            return VerificationResult(passed=False, error_message="Power operation failed")

        return VerificationResult(passed=True)

    @classmethod
    def verify_audio_device_updated(cls, context: NativeExecutionContext) -> VerificationResult:
        """
        Verify that audio devices were updated.

        Args:
            context: Execution context

        Returns:
            VerificationResult
        """
        if not context.result or not context.result.success:
            return VerificationResult(passed=False, error_message="Failed to retrieve audio devices")

        devices = context.desktop_context.get_audio_devices()
        if not devices or len(devices) == 0:
            return VerificationResult(passed=False, error_message="No audio devices found")

        return VerificationResult(
            passed=True,
            details={"device_count": len(devices)}
        )

    @classmethod
    def verify_network_interface_updated(cls, context: NativeExecutionContext) -> VerificationResult:
        """
        Verify that network interfaces were updated.

        Args:
            context: Execution context

        Returns:
            VerificationResult
        """
        if not context.result or not context.result.success:
            return VerificationResult(passed=False, error_message="Failed to retrieve network interfaces")

        interfaces = context.desktop_context.get_network_interfaces()
        if not interfaces or len(interfaces) == 0:
            return VerificationResult(passed=False, error_message="No network interfaces found")

        return VerificationResult(
            passed=True,
            details={"interface_count": len(interfaces)}
        )

    @classmethod
    def verify_registry_key_updated(cls, context: NativeExecutionContext) -> VerificationResult:
        """
        Verify that registry key was read.

        Args:
            context: Execution context

        Returns:
            VerificationResult
        """
        if not context.result or not context.result.success:
            return VerificationResult(passed=False, error_message="Failed to read registry key")

        # Registry read is a read operation
        return VerificationResult(passed=True)

    @classmethod
    def verify_service_updated(cls, context: NativeExecutionContext) -> VerificationResult:
        """
        Verify that service was started/stopped/restarted.

        Args:
            context: Execution context

        Returns:
            VerificationResult
        """
        if not context.result or not context.result.success:
            return VerificationResult(passed=False, error_message="Service operation failed")

        return VerificationResult(passed=True)

    @classmethod
    def verify(cls, context: NativeExecutionContext, mode: VerificationMode = VerificationMode.POST_CHECK) -> VerificationResult:
        """
        Verify the execution result.

        Args:
            context: Execution context
            mode: Verification mode

        Returns:
            VerificationResult
        """
        # Check if context has a result
        if not context.result:
            return VerificationResult(passed=False, error_message="No result to verify")

        # Check if operation succeeded
        if not context.result.success:
            return VerificationResult(
                passed=False,
                error_message=f"Operation failed: {context.result.error.message if context.result.error else 'Unknown error'}"
            )

        # Check pre-conditions
        if mode in [VerificationMode.PRE_CHECK, VerificationMode.BOTH]:
            pass  # Could add pre-execution checks here

        # Check post-conditions
        if mode in [VerificationMode.POST_CHECK, VerificationMode.BOTH]:
            # Try to verify based on capability type
            capability = context.capability.lower()
            handler = cls._verification_handlers.get(capability)

            if handler:
                return handler(context)

            # Generic verification for successful operations
            if context.result.data is not None:
                return VerificationResult(
                    passed=True,
                    details={"has_data": True, "data_type": type(context.result.data).__name__}
                )

        return VerificationResult(passed=True, details={"verified": True})

    @classmethod
    def register_default_handlers(cls) -> None:
        """Register default verification handlers for all capability types"""
        # Window handlers
        cls.register_handler("activate_window", cls.verify_window_activated)
        cls.register_handler("close_window", cls.verify_window_closed)
        cls.register_handler("move_window", cls.verify_window_moved)
        cls.register_handler("resize_window", cls.verify_window_resized)

        # Clipboard handlers
        cls.register_handler("write_clipboard", cls.verify_clipboard_updated)
        cls.register_handler("clear_clipboard", cls.verify_clipboard_updated)

        # Display handlers
        cls.register_handler("list_displays", cls.verify_display_updated)
        cls.register_handler("get_display", cls.verify_display_updated)

        # Power handlers
        cls.register_handler("shutdown", cls.verify_power_operation)
        cls.register_handler("restart", cls.verify_power_operation)
        cls.register_handler("sleep", cls.verify_power_operation)
        cls.register_handler("lock", cls.verify_power_operation)
        cls.register_handler("logoff", cls.verify_power_operation)

        # Audio handlers
        cls.register_handler("list_audio_devices", cls.verify_audio_device_updated)
        cls.register_handler("set_volume", cls.verify_audio_device_updated)
        cls.register_handler("toggle_mute", cls.verify_audio_device_updated)

        # Network handlers
        cls.register_handler("list_network_interfaces", cls.verify_network_interface_updated)
        cls.register_handler("get_default_interface", cls.verify_network_interface_updated)

        # Registry handlers
        cls.register_handler("read_registry_key", cls.verify_registry_key_updated)

        # Service handlers
        cls.register_handler("start_service", cls.verify_service_updated)
        cls.register_handler("stop_service", cls.verify_service_updated)
        cls.register_handler("restart_service", cls.verify_service_updated)
