"""
Native Windows Layer Manager
Main facade for all Windows operations.
All desktop actions must flow through this layer.
"""
from typing import Optional, List, Dict, Any, Callable
from enum import Enum
import logging

from .native_models import (
    WindowInfo,
    ProcessInfo,
    ClipboardData,
    DisplayInfo,
    AudioDevice,
    NetworkInterface,
    RegistryKey,
    ServiceInfo,
    WindowStyle,
)
from .native_exceptions import (
    NativeError,
    WindowNotFoundError,
    ProcessNotFoundError,
    ClipboardError,
    DisplayNotFoundError,
    PowerError,
    AudioDeviceNotFoundError,
    NetworkInterfaceNotFoundError,
    RegistryKeyNotFoundError,
    RegistryValueNotFoundError,
    ServiceNotFoundError,
    CapabilityNotAvailableError,
    PermissionDeniedError,
)
from .native_events import (
    NativeEventBus,
    EventListener,
    get_event_bus,
    EventType,
    NativeEvent,
)
from .native_utils import (
    get_window_by_title,
    get_window_by_process_id,
    get_active_window,
    get_all_windows,
    activate_window,
    close_window,
    minimize_window,
    maximize_window,
    restore_window,
)

from ..permission_manager import PermissionManager

logger = logging.getLogger(__name__)


class NativeCapability(Enum):
    """Supported native capabilities"""
    # Window management
    LIST_WINDOWS = "list_windows"
    GET_WINDOW = "get_window"
    ACTIVATE_WINDOW = "activate_window"
    CLOSE_WINDOW = "close_window"
    MOVE_WINDOW = "move_window"
    RESIZE_WINDOW = "resize_window"
    MINIMIZE_WINDOW = "minimize_window"
    MAXIMIZE_WINDOW = "maximize_window"
    RESTORE_WINDOW = "restore_window"

    # Clipboard
    READ_CLIPBOARD = "read_clipboard"
    WRITE_CLIPBOARD = "write_clipboard"
    CLEAR_CLIPBOARD = "clear_clipboard"

    # Display
    LIST_DISPLAYS = "list_displays"
    GET_PRIMARY_DISPLAY = "get_primary_display"
    GET_DISPLAY = "get_display"

    # Power
    SHUTDOWN = "shutdown"
    RESTART = "restart"
    SLEEP = "sleep"
    HIBERNATE = "hibernate"
    LOCK = "lock"
    LOGOFF = "logoff"

    # Audio
    LIST_AUDIO_DEVICES = "list_audio_devices"
    GET_AUDIO_DEVICE = "get_audio_device"
    SET_VOLUME = "set_volume"
    TOGGLE_MUTE = "toggle_mute"

    # Network
    LIST_NETWORK_INTERFACES = "list_network_interfaces"
    GET_NETWORK_INTERFACE = "get_network_interface"

    # Registry
    READ_REGISTRY_KEY = "read_registry_key"
    WRITE_REGISTRY_KEY = "write_registry_key"
    DELETE_REGISTRY_KEY = "delete_registry_key"

    # Services
    LIST_SERVICES = "list_services"
    START_SERVICE = "start_service"
    STOP_SERVICE = "stop_service"
    RESTART_SERVICE = "restart_service"


class NativeManager:
    """
    Main facade for all native Windows operations.

    This is the ONLY entry point for desktop operations in Aura.
    All managers import from here, not each other.
    """

    def __init__(self, permission_manager: PermissionManager):
        """
        Initialize the native manager.

        Args:
            permission_manager: PermissionManager instance for authorization checks
        """
        self.permission_manager = permission_manager
        self._window_manager = None
        self._clipboard_manager = None
        self._display_manager = None
        self._power_manager = None
        self._audio_manager = None
        self._network_manager = None
        self._registry_manager = None
        self._service_manager = None

        # Event bus
        self.event_bus = get_event_bus()

        # Subscribe to permission events
        permission_manager.subscribe(self._on_permission_response)

        logger.info("NativeManager initialized")

    def _on_permission_response(self, event: Any) -> None:
        """Handle permission responses"""
        # Can be overridden by subclasses
        pass

    # Window management
    def list_windows(self, **kwargs) -> List[WindowInfo]:
        """List all visible windows"""
        if not self.permission_manager.check_permission(
            "desktop.list_windows",
            capability=NativeCapability.LIST_WINDOWS
        ):
            raise PermissionDeniedError("Permission denied: list_windows")

        # Trigger event
        self.event_bus.publish(NativeEvent(
            event_type=EventType.DESKTOP_CONTEXT_UPDATED,
            data={"action": "list_windows"}
        ))

        return self._window_manager.list_windows(**kwargs)

    def get_window(self, hwnd: int) -> Optional[WindowInfo]:
        """Get information about a specific window"""
        if not self.permission_manager.check_permission(
            "desktop.get_window",
            capability=NativeCapability.GET_WINDOW
        ):
            raise PermissionDeniedError("Permission denied: get_window")

        return self._window_manager.get_window(hwnd)

    def activate_window(self, hwnd: int) -> bool:
        """Activate a specific window"""
        if not self.permission_manager.check_permission(
            "desktop.activate_window",
            capability=NativeCapability.ACTIVATE_WINDOW
        ):
            raise PermissionDeniedError("Permission denied: activate_window")

        result = self._window_manager.activate_window(hwnd)

        # Trigger event
        if result:
            self.event_bus.publish(NativeEvent(
                event_type=EventType.WINDOW_ACTIVATED,
                data={"hwnd": hwnd}
            ))

        return result

    def close_window(self, hwnd: int) -> bool:
        """Close a specific window"""
        if not self.permission_manager.check_permission(
            "desktop.close_window",
            capability=NativeCapability.CLOSE_WINDOW
        ):
            raise PermissionDeniedError("Permission denied: close_window")

        result = self._window_manager.close_window(hwnd)

        # Trigger event
        if result:
            self.event_bus.publish(NativeEvent(
                event_type=EventType.WINDOW_CLOSED,
                data={"hwnd": hwnd}
            ))

        return result

    # Clipboard management
    def read_clipboard(self) -> ClipboardData:
        """Read clipboard data"""
        if not self.permission_manager.check_permission(
            "desktop.read_clipboard",
            capability=NativeCapability.READ_CLIPBOARD
        ):
            raise PermissionDeniedError("Permission denied: read_clipboard")

        return self._clipboard_manager.read()

    def write_clipboard(self, text: str, html: Optional[str] = None) -> bool:
        """Write to clipboard"""
        if not self.permission_manager.check_permission(
            "desktop.write_clipboard",
            capability=NativeCapability.WRITE_CLIPBOARD
        ):
            raise PermissionDeniedError("Permission denied: write_clipboard")

        result = self._clipboard_manager.write(text, html)

        # Trigger event
        if result:
            self.event_bus.publish(NativeEvent(
                event_type=EventType.CLIPBOARD_CHANGED,
                data={"text": text[:100]}  # Truncate for event
            ))

        return result

    def clear_clipboard(self) -> bool:
        """Clear clipboard"""
        if not self.permission_manager.check_permission(
            "desktop.clear_clipboard",
            capability=NativeCapability.CLEAR_CLIPBOARD
        ):
            raise PermissionDeniedError("Permission denied: clear_clipboard")

        result = self._clipboard_manager.clear()

        # Trigger event
        if result:
            self.event_bus.publish(NativeEvent(
                event_type=EventType.CLIPBOARD_CHANGED,
                data={"text": ""}
            ))

        return result

    # Display management
    def list_displays(self) -> List[DisplayInfo]:
        """List all displays"""
        if not self.permission_manager.check_permission(
            "desktop.list_displays",
            capability=NativeCapability.LIST_DISPLAYS
        ):
            raise PermissionDeniedError("Permission denied: list_displays")

        return self._display_manager.list_displays()

    def get_primary_display(self) -> DisplayInfo:
        """Get primary display information"""
        if not self.permission_manager.check_permission(
            "desktop.get_primary_display",
            capability=NativeCapability.GET_PRIMARY_DISPLAY
        ):
            raise PermissionDeniedError("Permission denied: get_primary_display")

        return self._display_manager.get_primary_display()

    def get_display(self, index: int) -> DisplayInfo:
        """Get specific display information"""
        if not self.permission_manager.check_permission(
            "desktop.get_display",
            capability=NativeCapability.GET_DISPLAY
        ):
            raise PermissionDeniedError("Permission denied: get_display")

        return self._display_manager.get_display(index)

    # Power management
    def shutdown(self) -> bool:
        """Shutdown the system"""
        if not self.permission_manager.check_permission(
            "desktop.shutdown",
            capability=NativeCapability.SHUTDOWN
        ):
            raise PermissionDeniedError("Permission denied: shutdown")

        result = self._power_manager.shutdown()

        # Trigger event
        if result:
            self.event_bus.publish(NativeEvent(
                event_type=EventType.SYSTEM_SHUTDOWN,
                data={}
            ))

        return result

    def restart(self) -> bool:
        """Restart the system"""
        if not self.permission_manager.check_permission(
            "desktop.restart",
            capability=NativeCapability.RESTART
        ):
            raise PermissionDeniedError("Permission denied: restart")

        result = self._power_manager.restart()

        # Trigger event
        if result:
            self.event_bus.publish(NativeEvent(
                event_type=EventType.SYSTEM_RESTART,
                data={}
            ))

        return result

    def sleep(self) -> bool:
        """Sleep the system"""
        if not self.permission_manager.check_permission(
            "desktop.sleep",
            capability=NativeCapability.SLEEP
        ):
            raise PermissionDeniedError("Permission denied: sleep")

        result = self._power_manager.sleep()

        # Trigger event
        if result:
            self.event_bus.publish(NativeEvent(
                event_type=EventType.SYSTEM_SLEEP,
                data={}
            ))

        return result

    def lock(self) -> bool:
        """Lock the system"""
        if not self.permission_manager.check_permission(
            "desktop.lock",
            capability=NativeCapability.LOCK
        ):
            raise PermissionDeniedError("Permission denied: lock")

        result = self._power_manager.lock()

        # Trigger event
        if result:
            self.event_bus.publish(NativeEvent(
                event_type=EventType.SYSTEM_LOCK,
                data={}
            ))

        return result

    # Audio management
    def list_audio_devices(self) -> List[AudioDevice]:
        """List all audio devices"""
        if not self.permission_manager.check_permission(
            "desktop.list_audio_devices",
            capability=NativeCapability.LIST_AUDIO_DEVICES
        ):
            raise PermissionDeniedError("Permission denied: list_audio_devices")

        return self._audio_manager.list_devices()

    # Network management
    def list_network_interfaces(self) -> List[NetworkInterface]:
        """List all network interfaces"""
        if not self.permission_manager.check_permission(
            "desktop.list_network_interfaces",
            capability=NativeCapability.LIST_NETWORK_INTERFACES
        ):
            raise PermissionDeniedError("Permission denied: list_network_interfaces")

        return self._network_manager.list_interfaces()

    # Registry management
    def read_registry_key(self, key_path: str, key_name: Optional[str] = None) -> List[RegistryKey]:
        """Read registry key or value"""
        if not self.permission_manager.check_permission(
            "desktop.read_registry_key",
            capability=NativeCapability.READ_REGISTRY_KEY
        ):
            raise PermissionDeniedError("Permission denied: read_registry_key")

        return self._registry_manager.read_key(key_path, key_name)

    # Service management
    def list_services(self) -> List[ServiceInfo]:
        """List all services"""
        if not self.permission_manager.check_permission(
            "desktop.list_services",
            capability=NativeCapability.LIST_SERVICES
        ):
            raise PermissionDeniedError("Permission denied: list_services")

        return self._service_manager.list_services()

    # Property accessors for managers
    @property
    def window_manager(self):
        """Get window manager"""
        if self._window_manager is None:
            from .window_manager import WindowManager
            self._window_manager = WindowManager(self)
        return self._window_manager

    @property
    def clipboard_manager(self):
        """Get clipboard manager"""
        if self._clipboard_manager is None:
            from .clipboard_manager import ClipboardManager
            self._clipboard_manager = ClipboardManager(self)
        return self._clipboard_manager

    @property
    def display_manager(self):
        """Get display manager"""
        if self._display_manager is None:
            from .display_manager import DisplayManager
            self._display_manager = DisplayManager(self)
        return self._display_manager

    @property
    def power_manager(self):
        """Get power manager"""
        if self._power_manager is None:
            from .power_manager import PowerManager
            self._power_manager = PowerManager(self)
        return self._power_manager

    @property
    def audio_manager(self):
        """Get audio manager"""
        if self._audio_manager is None:
            from .audio_manager import AudioManager
            self._audio_manager = AudioManager(self)
        return self._audio_manager

    @property
    def network_manager(self):
        """Get network manager"""
        if self._network_manager is None:
            from .network_manager import NetworkManager
            self._network_manager = NetworkManager(self)
        return self._network_manager

    @property
    def registry_manager(self):
        """Get registry manager"""
        if self._registry_manager is None:
            from .registry_manager import RegistryManager
            self._registry_manager = RegistryManager(self)
        return self._registry_manager

    @property
    def service_manager(self):
        """Get service manager"""
        if self._service_manager is None:
            from .service_manager import ServiceManager
            self._service_manager = ServiceManager(self)
        return self._service_manager