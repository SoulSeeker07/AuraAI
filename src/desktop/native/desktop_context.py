"""
Desktop Context Synchronization
Centralized state management for desktop operations.

Managers only publish events; DesktopContext owns the state.
Provides a synchronized interface for Aura Brain to query current state.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .native_events import EventType
from .native_models import (
    AudioDevice,
    ClipboardData,
    DisplayInfo,
    NetworkInterface,
    ProcessInfo,
    WindowInfo,
)


class ContextScope(Enum):
    """Scope of context changes"""

    LOCAL = "local"
    GLOBAL = "global"


@dataclass
class DesktopContext:
    """
    Centralized state for desktop operations.

    Maintains the current state of windows, clipboard, displays,
    and other desktop elements. Updated through event subscriptions
    from managers.

    This is the source of truth for the desktop state.
    """

    # Window state
    _windows: dict[str, WindowInfo] = field(default_factory=dict)
    _active_window: str | None = None
    _window_timestamps: dict[str, datetime] = field(default_factory=dict)

    # Process state
    _processes: dict[int, ProcessInfo] = field(default_factory=dict)
    _process_timestamps: dict[int, datetime] = field(default_factory=dict)

    # Clipboard state
    _clipboard: ClipboardData | None = None
    _clipboard_timestamp: datetime | None = None

    # Display state
    _displays: list[DisplayInfo] = field(default_factory=list)
    _display_timestamp: datetime | None = None

    # Audio device state
    _audio_devices: list[AudioDevice] = field(default_factory=list)
    _audio_timestamp: datetime | None = None

    # Network interface state
    _network_interfaces: list[NetworkInterface] = field(default_factory=list)
    _network_timestamp: datetime | None = None

    # Event timestamps for all scopes
    _event_timestamps: dict[str, datetime] = field(default_factory=dict)

    # Event subscription callback
    _event_callback: Callable | None = None

    def set_event_callback(self, callback: Callable) -> None:
        """
        Set callback for context updates.

        Args:
            callback: Function to call when context changes
        """
        self._event_callback = callback

    def _publish_event(self, event_type: EventType, **kwargs) -> None:
        """
        Publish context update event.

        Args:
            event_type: Type of event
            **kwargs: Additional event data
        """
        # Update timestamp
        self._event_timestamps[event_type.value] = datetime.now()

        # Call callback if set
        if self._event_callback:
            try:
                self._event_callback(event_type, **kwargs)
            except Exception:
                # Don't let callback errors break context
                pass

    # ==================== Window Context ====================

    def update_windows(
        self, windows: list[WindowInfo], scope: ContextScope = ContextScope.LOCAL
    ) -> None:
        """
        Update window state.

        Args:
            windows: List of window information
            scope: Scope of the update
        """
        self._windows = {win.title: win for win in windows}
        self._window_timestamps = {title: datetime.now() for title in self._windows}

        if scope == ContextScope.GLOBAL:
            self._publish_event(
                EventType.WINDOWS_UPDATED, count=len(windows), scope=scope.value
            )
        else:
            self._publish_event(EventType.WINDOW_UPDATED, count=len(windows))

    def get_windows(self) -> list[WindowInfo]:
        """Get all windows"""
        return list(self._windows.values())

    def get_window_by_title(self, title: str) -> WindowInfo | None:
        """Get window by title"""
        return self._windows.get(title)

    def get_active_window(self) -> WindowInfo | None:
        """Get currently active window"""
        return self._windows.get(self._active_window)

    def set_active_window(self, title: str) -> None:
        """
        Set active window.

        Args:
            title: Title of the active window
        """
        self._active_window = title

    def get_window_count(self) -> int:
        """Get number of windows"""
        return len(self._windows)

    def get_last_window_update(self) -> datetime | None:
        """Get timestamp of last window update"""
        return self._window_timestamps.get(EventType.WINDOWS_UPDATED.value)

    # ==================== Process Context ====================

    def update_processes(
        self, processes: list[ProcessInfo], scope: ContextScope = ContextScope.LOCAL
    ) -> None:
        """
        Update process state.

        Args:
            processes: List of process information
            scope: Scope of the update
        """
        self._processes = {p.pid: p for p in processes}
        self._process_timestamps = {pid: datetime.now() for pid in self._processes}

        if scope == ContextScope.GLOBAL:
            self._publish_event(
                EventType.PROCESSES_UPDATED, count=len(processes), scope=scope.value
            )
        else:
            self._publish_event(EventType.PROCESS_UPDATED, count=len(processes))

    def get_processes(self) -> list[ProcessInfo]:
        """Get all processes"""
        return list(self._processes.values())

    def get_process(self, pid: int) -> ProcessInfo | None:
        """Get process by PID"""
        return self._processes.get(pid)

    def get_process_count(self) -> int:
        """Get number of processes"""
        return len(self._processes)

    def get_last_process_update(self) -> datetime | None:
        """Get timestamp of last process update"""
        return self._process_timestamps.get(EventType.PROCESSES_UPDATED.value)

    # ==================== Clipboard Context ====================

    def update_clipboard(self, data: ClipboardData) -> None:
        """
        Update clipboard state.

        Args:
            data: Clipboard data
        """
        self._clipboard = data
        self._clipboard_timestamp = datetime.now()
        self._publish_event(
            EventType.CLIPBOARD_UPDATED,
            has_text=data.has_text,
            length=len(data.text) if data.text else 0,
        )

    def get_clipboard(self) -> ClipboardData | None:
        """Get current clipboard data"""
        return self._clipboard

    def get_clipboard_text(self) -> str | None:
        """Get clipboard text"""
        if self._clipboard and self._clipboard.text:
            return self._clipboard.text
        return None

    def has_clipboard_text(self) -> bool:
        """Check if clipboard has text"""
        return self._clipboard is not None and self._clipboard.has_text

    def get_last_clipboard_update(self) -> datetime | None:
        """Get timestamp of last clipboard update"""
        return self._clipboard_timestamp

    # ==================== Display Context ====================

    def update_displays(
        self, displays: list[DisplayInfo], scope: ContextScope = ContextScope.LOCAL
    ) -> None:
        """
        Update display state.

        Args:
            displays: List of display information
            scope: Scope of the update
        """
        self._displays = displays
        self._display_timestamp = datetime.now()

        if scope == ContextScope.GLOBAL:
            self._publish_event(
                EventType.DISPLAYS_UPDATED, count=len(displays), scope=scope.value
            )
        else:
            self._publish_event(EventType.DISPLAY_UPDATED, count=len(displays))

    def get_displays(self) -> list[DisplayInfo]:
        """Get all displays"""
        return self._displays

    def get_primary_display(self) -> DisplayInfo | None:
        """Get primary display"""
        for display in self._displays:
            if display.is_primary:
                return display
        return None

    def get_display_by_name(self, name: str) -> DisplayInfo | None:
        """Get display by name"""
        for display in self._displays:
            if display.name == name:
                return display
        return None

    def get_display_count(self) -> int:
        """Get number of displays"""
        return len(self._displays)

    def get_last_display_update(self) -> datetime | None:
        """Get timestamp of last display update"""
        return self._display_timestamp

    # ==================== Audio Context ====================

    def update_audio_devices(
        self, devices: list[AudioDevice], scope: ContextScope = ContextScope.LOCAL
    ) -> None:
        """
        Update audio device state.

        Args:
            devices: List of audio devices
            scope: Scope of the update
        """
        self._audio_devices = devices
        self._audio_timestamp = datetime.now()

        if scope == ContextScope.GLOBAL:
            self._publish_event(
                EventType.AUDIO_DEVICES_UPDATED, count=len(devices), scope=scope.value
            )
        else:
            self._publish_event(EventType.AUDIO_DEVICE_UPDATED, count=len(devices))

    def get_audio_devices(self) -> list[AudioDevice]:
        """Get all audio devices"""
        return self._audio_devices

    def get_default_output_device(self) -> AudioDevice | None:
        """Get default output device"""
        for device in self._audio_devices:
            if device.is_default_output:
                return device
        return None

    def get_default_input_device(self) -> AudioDevice | None:
        """Get default input device"""
        for device in self._audio_devices:
            if device.is_default_input:
                return device
        return None

    def get_audio_device_count(self) -> int:
        """Get number of audio devices"""
        return len(self._audio_devices)

    def get_last_audio_update(self) -> datetime | None:
        """Get timestamp of last audio update"""
        return self._audio_timestamp

    # ==================== Network Context ====================

    def update_network_interfaces(
        self,
        interfaces: list[NetworkInterface],
        scope: ContextScope = ContextScope.LOCAL,
    ) -> None:
        """
        Update network interface state.

        Args:
            interfaces: List of network interfaces
            scope: Scope of the update
        """
        self._network_interfaces = interfaces
        self._network_timestamp = datetime.now()

        if scope == ContextScope.GLOBAL:
            self._publish_event(
                EventType.NETWORK_INTERFACES_UPDATED,
                count=len(interfaces),
                scope=scope.value,
            )
        else:
            self._publish_event(
                EventType.NETWORK_INTERFACE_UPDATED, count=len(interfaces)
            )

    def get_network_interfaces(self) -> list[NetworkInterface]:
        """Get all network interfaces"""
        return self._network_interfaces

    def get_default_interface(self) -> NetworkInterface | None:
        """Get default network interface"""
        for interface in self._network_interfaces:
            if interface.is_default:
                return interface
        return None

    def get_network_interface_count(self) -> int:
        """Get number of network interfaces"""
        return len(self._network_interfaces)

    def get_last_network_update(self) -> datetime | None:
        """Get timestamp of last network update"""
        return self._network_timestamp

    # ==================== Event Timestamps ====================

    def get_last_update(self, event_type: EventType) -> datetime | None:
        """Get timestamp of last update for an event type"""
        return self._event_timestamps.get(event_type.value)

    def get_all_update_timestamps(self) -> dict[str, datetime]:
        """Get all event timestamps"""
        return self._event_timestamps.copy()

    # ==================== Context Sync ====================

    def get_context_snapshot(self) -> dict[str, Any]:
        """
        Get snapshot of current context state.

        Returns:
            Dictionary with all context data
        """
        return {
            "windows": self.get_windows(),
            "active_window": self.get_active_window(),
            "processes": self.get_processes(),
            "clipboard": self.get_clipboard(),
            "displays": self.get_displays(),
            "audio_devices": self.get_audio_devices(),
            "network_interfaces": self.get_network_interfaces(),
            "last_updates": {
                "windows": self.get_last_window_update(),
                "clipboard": self.get_last_clipboard_update(),
                "displays": self.get_last_display_update(),
                "audio": self.get_last_audio_update(),
                "network": self.get_last_network_update(),
            },
        }

    def clear_context(self) -> None:
        """Clear all context state (useful for testing)"""
        self._windows.clear()
        self._active_window = None
        self._window_timestamps.clear()

        self._processes.clear()
        self._process_timestamps.clear()

        self._clipboard = None
        self._clipboard_timestamp = None

        self._displays.clear()
        self._display_timestamp = None

        self._audio_devices.clear()
        self._audio_timestamp = None

        self._network_interfaces.clear()
        self._network_timestamp = None

        self._event_timestamps.clear()


# Singleton instance
_desktop_context: DesktopContext | None = None


def get_desktop_context() -> DesktopContext:
    """Get or create the global desktop context singleton"""
    global _desktop_context
    if _desktop_context is None:
        _desktop_context = DesktopContext()
    return _desktop_context


def reset_desktop_context() -> None:
    """Reset the global desktop context"""
    global _desktop_context
    _desktop_context = None
