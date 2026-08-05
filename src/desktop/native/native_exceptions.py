"""
Native Windows Layer Exceptions
Shared exception hierarchy for all native operations.
"""
from typing import Optional, Any


class NativeError(Exception):
    """Base exception for all native operations"""
    def __init__(
        self,
        message: str,
        operation: str = "",
        win32_error: Optional[int] = None,
        details: Optional[Any] = None
    ):

        self.message = message
        self.operation = operation
        self.win32_error = win32_error
        self.details = details
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        error_part = f" (Win32 Error: {self.win32_error})" if self.win32_error else ""
        details_part = f" - {self.details}" if self.details else ""
        return f"[Native Error: {self.operation}] {self.message}{error_part}{details_part}"


class WindowError(NativeError):
    """Base exception for window operations"""
    pass


class WindowNotFoundError(WindowError):
    """Raised when a window is not found"""
    pass


class WindowActivationError(WindowError):
    """Raised when window activation fails"""
    pass


class WindowAccessDeniedError(WindowError):
    """Raised when window access is denied"""
    pass


class ProcessError(NativeError):
    """Base exception for process operations"""
    pass


class ProcessNotFoundError(ProcessError):
    """Raised when a process is not found"""
    pass


class ProcessAccessDeniedError(ProcessError):
    """Raised when process access is denied"""
    pass


class ClipboardError(NativeError):
    """Base exception for clipboard operations"""
    pass


class ClipboardAccessDeniedError(ClipboardError):
    """Raised when clipboard access is denied"""
    pass


class ClipboardDataError(ClipboardError):
    """Raised when clipboard data is invalid"""
    pass


class DisplayError(NativeError):
    """Base exception for display operations"""
    pass


class DisplayNotFoundError(DisplayError):
    """Raised when a display is not found"""
    pass


class PowerError(NativeError):
    """Base exception for power operations"""
    pass


class PowerStateError(PowerError):
    """Raised when power state operation fails"""
    pass


class AudioError(NativeError):
    """Base exception for audio operations"""
    pass


class AudioDeviceNotFoundError(AudioError):
    """Raised when an audio device is not found"""
    pass


class NetworkError(NativeError):
    """Base exception for network operations"""
    pass


class NetworkInterfaceNotFoundError(NetworkError):
    """Raised when a network interface is not found"""
    pass


class RegistryError(NativeError):
    """Base exception for registry operations"""
    pass


class RegistryKeyNotFoundError(RegistryError):
    """Raised when a registry key is not found"""
    pass


class RegistryValueNotFoundError(RegistryError):
    """Raised when a registry value is not found"""
    pass


class RegistryAccessDeniedError(RegistryError):
    """Raised when registry access is denied"""
    pass


class ServiceError(NativeError):
    """Base exception for service operations"""
    pass


class ServiceNotFoundError(ServiceError):
    """Raised when a service is not found"""
    pass


class ServiceAccessDeniedError(ServiceError):
    """Raised when service access is denied"""
    pass


class CapabilityNotAvailableError(NativeError):
    """Raised when a capability is not available on this platform"""
    pass


class InvalidCapabilityRequestError(NativeError):
    """Raised when a capability request is invalid"""
    pass

class CapabilityNotFoundError(NativeError):
    """Raised when a requested capability does not exist in the registry"""
    pass


class PermissionDeniedError(NativeError):
    """Raised when a permission check fails"""
    pass


class OperationTimeoutError(NativeError):
    """Raised when an operation exceeds its allotted time"""
    pass


class OperationCancelledError(NativeError):
    """Raised when an operation is cancelled before completion"""
    pass

class VerificationError(NativeError):
    """Raised when post-operation verification fails"""
    pass

class RollbackError(NativeError):
    """Raised when a rollback operation fails"""
    pass

class EventPublishError(NativeError):
    """Raised when event publishing fails"""
    pass
