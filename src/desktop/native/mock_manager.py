"""
Mock Manager
A mock native manager for testing the execution pipeline without Win32.

This manager implements the same interface as future native managers
(WindowManager, ClipboardManager, etc.) but returns mock data.

Purpose:
- Prove the architecture works end-to-end
- Test the full pipeline: Discovery → Registry → Pipeline → Verification → Context
- Validate that all middleware, events, metrics, and rollback work correctly

When Phase 2B begins, real managers (WindowManager, etc.) will replace
this mock with actual Win32 API calls — but the pipeline stays the same.
"""

from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
import time
import logging

from .desktop_result import DesktopResult, DesktopStatus

logger = logging.getLogger(__name__)


@dataclass
class MockWindowState:
    """Mock window state for testing."""
    title: str
    hwnd: int = 0
    process_id: int = 0
    is_active: bool = False
    is_minimized: bool = False
    is_maximized: bool = False


class MockManager:
    """
    Mock native manager for testing the execution pipeline.

    Implements the same execute() interface that real managers will use.
    Returns DesktopResult objects with mock data.

    This is the ONLY thing that changes between Phase 2A.6 (mock)
    and Phase 2B (real Win32 managers). The pipeline, middleware,
    verification, rollback, metrics, and context all stay the same.
    """

    def __init__(self):
        """Initialize the mock manager."""
        self.name = "mock"
        self._call_log: List[Dict[str, Any]] = []
        self._mock_windows: Dict[str, MockWindowState] = {}
        self._clipboard_text: str = ""
        self._volume: float = 0.5
        self._muted: bool = False

        # Initialize some mock windows
        self._mock_windows["Calculator"] = MockWindowState(
            title="Calculator", hwnd=1001, process_id=2001, is_active=True
        )
        self._mock_windows["VS Code"] = MockWindowState(
            title="VS Code", hwnd=1002, process_id=2002
        )
        self._mock_windows["Chrome"] = MockWindowState(
            title="Chrome", hwnd=1003, process_id=2003
        )

        logger.info("MockManager initialized with 3 mock windows")

    # ==================== Capability Execution ====================

    def execute(
        self,
        capability: str,
        goal: str,
        arguments: Dict[str, Any],
    ) -> DesktopResult:
        """
        Execute a capability and return a DesktopResult.

        This is the method that the DesktopExecutionEngine calls.
        Real managers will implement actual Win32 calls here.

        Args:
            capability: Name of the capability to execute
            goal: Original user goal
            arguments: Arguments for the capability

        Returns:
            DesktopResult with mock data
        """
        start_time = time.time()

        # Log the call
        self._call_log.append({
            "capability": capability,
            "goal": goal,
            "arguments": arguments,
            "timestamp": start_time,
        })

        logger.info(f"[MockManager] Executing capability: {capability}")
        logger.info(f"[MockManager] Goal: {goal}")
        logger.info(f"[MockManager] Arguments: {arguments}")

        # Route to specific mock handler
        handler = self._get_handler(capability)
        if handler is None:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Unknown capability: {capability}",
                metrics={"duration_ms": (time.time() - start_time) * 1000},
            )

        # Execute the handler
        try:
            result = handler(goal, arguments)
            result.metrics["duration_ms"] = (time.time() - start_time) * 1000
            result.completed_at = time.time()
            return result
        except Exception as e:
            logger.error(f"[MockManager] Error executing {capability}: {e}")
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=str(e),
                metrics={"duration_ms": (time.time() - start_time) * 1000},
            )

    def _get_handler(self, capability: str) -> Optional[Callable]:
        """Get the handler function for a capability."""
        handlers = {
            "activate_window": self._handle_activate_window,
            "close_window": self._handle_close_window,
            "list_windows": self._handle_list_windows,
            "minimize_window": self._handle_minimize_window,
            "maximize_window": self._handle_maximize_window,
            "restore_window": self._handle_restore_window,
            "read_clipboard": self._handle_read_clipboard,
            "write_clipboard": self._handle_write_clipboard,
            "clear_clipboard": self._handle_clear_clipboard,
            "list_displays": self._handle_list_displays,
            "get_primary_display": self._handle_get_primary_display,
            "set_volume": self._handle_set_volume,
            "toggle_mute": self._handle_toggle_mute,
            "list_audio_devices": self._handle_list_audio_devices,
            "list_network_interfaces": self._handle_list_network_interfaces,
            "shutdown": self._handle_shutdown,
            "restart": self._handle_restart,
            "sleep": self._handle_sleep,
            "lock": self._handle_lock,
            "list_services": self._handle_list_services,
            "start_service": self._handle_start_service,
            "stop_service": self._handle_stop_service,
        }
        return handlers.get(capability)

    # ==================== Window Handlers ====================

    def _handle_activate_window(self, goal: str, args: Dict) -> DesktopResult:
        """Handle activate_window capability."""
        window_title = args.get("window_title") or args.get("title") or ""

        # Find the window
        window = self._mock_windows.get(window_title)
        if not window:
            # Try partial match
            for title, win in self._mock_windows.items():
                if window_title.lower() in title.lower():
                    window = win
                    break

        if not window:
            return DesktopResult.create_failure(
                goal=goal,
                capability="activate_window",
                manager=self.name,
                error=f"Window not found: {window_title}",
            )

        # Deactivate all other windows
        for w in self._mock_windows.values():
            w.is_active = False

        # Activate the target window
        window.is_active = True

        # Create rollback function
        def rollback() -> bool:
            window.is_active = False
            # Reactivate the first window
            first = list(self._mock_windows.values())[0]
            first.is_active = True
            logger.info(f"[MockManager] Rollback: deactivated {window_title}")
            return True

        return DesktopResult.create_success(
            goal=goal,
            capability="activate_window",
            manager=self.name,
            data={"window": window_title, "hwnd": window.hwnd, "activated": True},
            events=["window_activated"],
            rollback=rollback,
            verification={"passed": True, "method": "active_window_check"},
            context_changes={"active_window": window_title},
        )

    def _handle_close_window(self, goal: str, args: Dict) -> DesktopResult:
        """Handle close_window capability."""
        window_title = args.get("window_title") or args.get("title") or ""

        window = self._mock_windows.get(window_title)
        if not window:
            for title, win in self._mock_windows.items():
                if window_title.lower() in title.lower():
                    window = win
                    window_title = title
                    break

        if not window:
            return DesktopResult.create_failure(
                goal=goal,
                capability="close_window",
                manager=self.name,
                error=f"Window not found: {window_title}",
            )

        # Store for rollback
        closed_window = MockWindowState(
            title=window_title,
            hwnd=window.hwnd,
            process_id=window.process_id,
        )

        # Remove the window
        del self._mock_windows[window_title]

        def rollback() -> bool:
            self._mock_windows[window_title] = closed_window
            logger.info(f"[MockManager] Rollback: re-opened {window_title}")
            return True

        return DesktopResult.create_success(
            goal=goal,
            capability="close_window",
            manager=self.name,
            data={"window": window_title, "closed": True},
            events=["window_closed"],
            rollback=rollback,
            verification={"passed": True, "method": "window_removed_check"},
            context_changes={"windows_count": len(self._mock_windows)},
        )

    def _handle_list_windows(self, goal: str, args: Dict) -> DesktopResult:
        """Handle list_windows capability."""
        windows = [
            {
                "title": w.title,
                "hwnd": w.hwnd,
                "process_id": w.process_id,
                "is_active": w.is_active,
                "is_minimized": w.is_minimized,
                "is_maximized": w.is_maximized,
            }
            for w in self._mock_windows.values()
        ]

        return DesktopResult.create_success(
            goal=goal,
            capability="list_windows",
            manager=self.name,
            data=windows,
            events=["windows_listed"],
            verification={"passed": True, "method": "data_present_check"},
            context_changes={"windows_count": len(windows)},
        )

    def _handle_minimize_window(self, goal: str, args: Dict) -> DesktopResult:
        """Handle minimize_window capability."""
        window_title = args.get("window_title") or args.get("title") or ""
        window = self._mock_windows.get(window_title)
        if not window:
            return DesktopResult.create_failure(
                goal=goal, capability="minimize_window", manager=self.name,
                error=f"Window not found: {window_title}",
            )

        previous_state = window.is_minimized
        window.is_minimized = True
        window.is_maximized = False

        def rollback() -> bool:
            window.is_minimized = previous_state
            return True

        return DesktopResult.create_success(
            goal=goal, capability="minimize_window", manager=self.name,
            data={"window": window_title, "minimized": True},
            events=["window_minimized"],
            rollback=rollback,
            verification={"passed": True},
            context_changes={f"window_{window_title}_minimized": True},
        )

    def _handle_maximize_window(self, goal: str, args: Dict) -> DesktopResult:
        """Handle maximize_window capability."""
        window_title = args.get("window_title") or args.get("title") or ""
        window = self._mock_windows.get(window_title)
        if not window:
            return DesktopResult.create_failure(
                goal=goal, capability="maximize_window", manager=self.name,
                error=f"Window not found: {window_title}",
            )

        previous_max = window.is_maximized
        previous_min = window.is_minimized
        window.is_maximized = True
        window.is_minimized = False

        def rollback() -> bool:
            window.is_maximized = previous_max
            window.is_minimized = previous_min
            return True

        return DesktopResult.create_success(
            goal=goal, capability="maximize_window", manager=self.name,
            data={"window": window_title, "maximized": True},
            events=["window_maximized"],
            rollback=rollback,
            verification={"passed": True},
            context_changes={f"window_{window_title}_maximized": True},
        )

    def _handle_restore_window(self, goal: str, args: Dict) -> DesktopResult:
        """Handle restore_window capability."""
        window_title = args.get("window_title") or args.get("title") or ""
        window = self._mock_windows.get(window_title)
        if not window:
            return DesktopResult.create_failure(
                goal=goal, capability="restore_window", manager=self.name,
                error=f"Window not found: {window_title}",
            )

        window.is_minimized = False
        window.is_maximized = False

        return DesktopResult.create_success(
            goal=goal, capability="restore_window", manager=self.name,
            data={"window": window_title, "restored": True},
            events=["window_restored"],
            verification={"passed": True},
            context_changes={f"window_{window_title}_restored": True},
        )

    # ==================== Clipboard Handlers ====================

    def _handle_read_clipboard(self, goal: str, args: Dict) -> DesktopResult:
        """Handle read_clipboard capability."""
        return DesktopResult.create_success(
            goal=goal, capability="read_clipboard", manager=self.name,
            data={"text": self._clipboard_text, "length": len(self._clipboard_text)},
            events=["clipboard_read"],
            verification={"passed": True},
        )

    def _handle_write_clipboard(self, goal: str, args: Dict) -> DesktopResult:
        """Handle write_clipboard capability."""
        text = args.get("text", "")
        previous_text = self._clipboard_text
        self._clipboard_text = text

        def rollback() -> bool:
            self._clipboard_text = previous_text
            return True

        return DesktopResult.create_success(
            goal=goal, capability="write_clipboard", manager=self.name,
            data={"text": text, "length": len(text)},
            events=["clipboard_changed"],
            rollback=rollback,
            verification={"passed": True, "method": "content_match_check"},
            context_changes={"clipboard_text": text},
        )

    def _handle_clear_clipboard(self, goal: str, args: Dict) -> DesktopResult:
        """Handle clear_clipboard capability."""
        previous_text = self._clipboard_text
        self._clipboard_text = ""

        def rollback() -> bool:
            self._clipboard_text = previous_text
            return True

        return DesktopResult.create_success(
            goal=goal, capability="clear_clipboard", manager=self.name,
            data={"cleared": True},
            events=["clipboard_changed"],
            rollback=rollback,
            verification={"passed": True},
            context_changes={"clipboard_text": ""},
        )

    # ==================== Display Handlers ====================

    def _handle_list_displays(self, goal: str, args: Dict) -> DesktopResult:
        """Handle list_displays capability."""
        displays = [
            {"index": 0, "name": "Main Display", "width": 1920, "height": 1080, "primary": True},
            {"index": 1, "name": "Secondary", "width": 1280, "height": 720, "primary": False},
        ]

        return DesktopResult.create_success(
            goal=goal, capability="list_displays", manager=self.name,
            data=displays,
            events=["displays_listed"],
            verification={"passed": True},
            context_changes={"displays_count": len(displays)},
        )

    def _handle_get_primary_display(self, goal: str, args: Dict) -> DesktopResult:
        """Handle get_primary_display capability."""
        return DesktopResult.create_success(
            goal=goal, capability="get_primary_display", manager=self.name,
            data={"index": 0, "name": "Main Display", "width": 1920, "height": 1080, "primary": True},
            events=["primary_display_retrieved"],
            verification={"passed": True},
        )

    # ==================== Audio Handlers ====================

    def _handle_set_volume(self, goal: str, args: Dict) -> DesktopResult:
        """Handle set_volume capability."""
        new_volume = args.get("volume", 0.5)
        previous_volume = self._volume
        self._volume = new_volume

        def rollback() -> bool:
            self._volume = previous_volume
            return True

        return DesktopResult.create_success(
            goal=goal, capability="set_volume", manager=self.name,
            data={"volume": new_volume, "previous_volume": previous_volume},
            events=["audio_volume_changed"],
            rollback=rollback,
            verification={"passed": True},
            context_changes={"volume": new_volume},
        )

    def _handle_toggle_mute(self, goal: str, args: Dict) -> DesktopResult:
        """Handle toggle_mute capability."""
        previous_muted = self._muted
        self._muted = not self._muted

        def rollback() -> bool:
            self._muted = previous_muted
            return True

        return DesktopResult.create_success(
            goal=goal, capability="toggle_mute", manager=self.name,
            data={"muted": self._muted, "previous_muted": previous_muted},
            events=["audio_volume_changed"],
            rollback=rollback,
            verification={"passed": True},
            context_changes={"muted": self._muted},
        )

    def _handle_list_audio_devices(self, goal: str, args: Dict) -> DesktopResult:
        """Handle list_audio_devices capability."""
        devices = [
            {"index": 0, "name": "Speakers", "type": "output", "volume": self._volume, "muted": self._muted, "is_default": True},
            {"index": 1, "name": "Microphone", "type": "input", "volume": 0.8, "muted": False, "is_default": True},
        ]

        return DesktopResult.create_success(
            goal=goal, capability="list_audio_devices", manager=self.name,
            data=devices,
            events=["audio_devices_listed"],
            verification={"passed": True},
            context_changes={"audio_devices_count": len(devices)},
        )

    # ==================== Network Handlers ====================

    def _handle_list_network_interfaces(self, goal: str, args: Dict) -> DesktopResult:
        """Handle list_network_interfaces capability."""
        interfaces = [
            {"name": "Ethernet", "is_up": True, "ip_address": "192.168.1.100", "mac_address": "AA:BB:CC:DD:EE:FF"},
            {"name": "Wi-Fi", "is_up": False, "ip_address": None, "mac_address": "11:22:33:44:55:66"},
        ]

        return DesktopResult.create_success(
            goal=goal, capability="list_network_interfaces", manager=self.name,
            data=interfaces,
            events=["network_interfaces_listed"],
            verification={"passed": True},
            context_changes={"network_interfaces_count": len(interfaces)},
        )

    # ==================== Power Handlers ====================

    def _handle_shutdown(self, goal: str, args: Dict) -> DesktopResult:
        """Handle shutdown capability."""
        return DesktopResult.create_success(
            goal=goal, capability="shutdown", manager=self.name,
            data={"action": "shutdown", "initiated": True},
            events=["system_shutdown"],
            verification={"passed": True},
            warnings=["This is a mock - no actual shutdown occurred"],
        )

    def _handle_restart(self, goal: str, args: Dict) -> DesktopResult:
        """Handle restart capability."""
        return DesktopResult.create_success(
            goal=goal, capability="restart", manager=self.name,
            data={"action": "restart", "initiated": True},
            events=["system_restart"],
            verification={"passed": True},
            warnings=["This is a mock - no actual restart occurred"],
        )

    def _handle_sleep(self, goal: str, args: Dict) -> DesktopResult:
        """Handle sleep capability."""
        return DesktopResult.create_success(
            goal=goal, capability="sleep", manager=self.name,
            data={"action": "sleep", "initiated": True},
            events=["system_sleep"],
            verification={"passed": True},
            warnings=["This is a mock - no actual sleep occurred"],
        )

    def _handle_lock(self, goal: str, args: Dict) -> DesktopResult:
        """Handle lock capability."""
        return DesktopResult.create_success(
            goal=goal, capability="lock", manager=self.name,
            data={"action": "lock", "initiated": True},
            events=["system_lock"],
            verification={"passed": True},
            warnings=["This is a mock - no actual lock occurred"],
        )

    # ==================== Service Handlers ====================

    def _handle_list_services(self, goal: str, args: Dict) -> DesktopResult:
        """Handle list_services capability."""
        services = [
            {"service_name": "AuraService", "display_name": "Aura AI Service", "status": "running", "start_type": "auto"},
            {"service_name": "WindowsUpdate", "display_name": "Windows Update", "status": "stopped", "start_type": "manual"},
        ]

        return DesktopResult.create_success(
            goal=goal, capability="list_services", manager=self.name,
            data=services,
            events=["services_listed"],
            verification={"passed": True},
            context_changes={"services_count": len(services)},
        )

    def _handle_start_service(self, goal: str, args: Dict) -> DesktopResult:
        """Handle start_service capability."""
        service_name = args.get("service_name", "")
        return DesktopResult.create_success(
            goal=goal, capability="start_service", manager=self.name,
            data={"service": service_name, "action": "start", "status": "running"},
            events=["service_started"],
            verification={"passed": True},
        )

    def _handle_stop_service(self, goal: str, args: Dict) -> DesktopResult:
        """Handle stop_service capability."""
        service_name = args.get("service_name", "")
        return DesktopResult.create_success(
            goal=goal, capability="stop_service", manager=self.name,
            data={"service": service_name, "action": "stop", "status": "stopped"},
            events=["service_stopped"],
            verification={"passed": True},
        )

    # ==================== Introspection ====================

    def get_call_log(self) -> List[Dict[str, Any]]:
        """Get the log of all calls made to this manager."""
        return self._call_log.copy()

    def get_call_count(self) -> int:
        """Get the number of calls made to this manager."""
        return len(self._call_log)

    def was_called(self, capability: str) -> bool:
        """Check if a specific capability was called."""
        return any(call["capability"] == capability for call in self._call_log)

    def reset(self) -> None:
        """Reset the mock manager state."""
        self._call_log.clear()
        self._mock_windows.clear()
        self._clipboard_text = ""
        self._volume = 0.5
        self._muted = False

        # Re-initialize mock windows
        self._mock_windows["Calculator"] = MockWindowState(
            title="Calculator", hwnd=1001, process_id=2001, is_active=True
        )
        self._mock_windows["VS Code"] = MockWindowState(
            title="VS Code", hwnd=1002, process_id=2002
        )
        self._mock_windows["Chrome"] = MockWindowState(
            title="Chrome", hwnd=1003, process_id=2003
        )