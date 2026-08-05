"""
Capability Registry
Metadata and descriptions for all native capabilities.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RiskLevel(Enum):
    """Risk level of an action"""

    SAFE = "safe"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class PermissionRequired(Enum):
    """Permission level required"""

    NONE = "none"
    READ = "read"
    WRITE = "write"
    CONTROL = "control"
    ADMIN = "admin"


@dataclass
class CapabilityDescriptor:
    """
    Metadata descriptor for a capability.

    This provides all the information the Planner needs to understand
    and call a capability safely.
    """

    # Core information
    name: str
    description: str
    manager: str
    category: str

    # Permissions
    permission: PermissionRequired = PermissionRequired.READ
    permission_label: str = "Read"

    # Risk assessment
    risk_level: RiskLevel = RiskLevel.LOW
    requires_admin: bool = False

    # Events triggered
    events_triggered: list[str] = field(default_factory=list)

    # GUI information
    supports_visualization: bool = True
    success_message_template: str | None = None

    # Fallbacks
    fallback_capability: str | None = None
    alternative_actions: list[str] = field(default_factory=list)

    # Behavior
    is_destructive: bool = False
    requires_confirmation: bool = False
    timeout_seconds: int = 30

    # Undo/rollback
    supports_undo: bool = False
    rollback_description: str | None = None

    # Hardware / Platform requirements
    backend_required: str | None = None
    minimum_windows_version: str | None = "10"

    # Additional metadata
    tags: list[str] = field(default_factory=list)
    usage_examples: list[str] = field(default_factory=list)

    # Capability Graph Relationships (Planner Intelligence)
    requires: list[str] = field(default_factory=list)
    verifies: list[str] = field(default_factory=list)
    rollback_capabilities: list[str] = field(default_factory=list)

    def get_permission_label(self) -> str:
        """Get human-readable permission label"""
        return self.permission_label or self.permission.value.title()

    def get_risk_label(self) -> str:
        """Get human-readable risk label"""
        return self.risk_level.value.title()


class CapabilityRegistry:
    """
    Registry of all native capabilities with their metadata.

    Provides metadata for:
    - Planner capability selection
    - Permission checking
    - Risk assessment
    - GUI rendering
    - Fallback strategies
    """

    def __init__(self):
        """Initialize the capability registry"""
        self._capabilities: dict[str, CapabilityDescriptor] = {}
        self._by_category: dict[str, list[str]] = {}
        self._build_registry()

    def _build_registry(self) -> None:
        """Build the capability registry with all capabilities"""
        # Window management capabilities
        self._register_window_capabilities()

        # Clipboard capabilities
        self._register_clipboard_capabilities()

        # Display capabilities
        self._register_display_capabilities()

        # Power capabilities
        self._register_power_capabilities()

        # Audio capabilities
        self._register_audio_capabilities()

        # Network capabilities
        self._register_network_capabilities()

        # Registry capabilities
        self._register_registry_capabilities()

        # Service capabilities
        self._register_service_capabilities()

    def _register_window_capabilities(self) -> None:
        """Register window management capabilities"""
        self.register(
            CapabilityDescriptor(
                name="list_windows",
                description="List all visible windows on the desktop",
                manager="window",
                category="window",
                permission=PermissionRequired.READ,
                permission_label="Read",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
                usage_examples=[
                    "List all open windows",
                    "Find a specific window by title",
                ],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="get_window",
                description="Get detailed information about a specific window",
                manager="window",
                category="window",
                permission=PermissionRequired.READ,
                permission_label="Read",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
            )
        )
        self.register(
            CapabilityDescriptor(
                name="app_open",
                description="Launch or activate an application",
                manager="window",
                category="window",
                permission=PermissionRequired.CONTROL,
                permission_label="Control",
                risk_level=RiskLevel.LOW,
                events_triggered=["app_opened"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="app_close",
                description="Close an application",
                manager="window",
                category="window",
                permission=PermissionRequired.CONTROL,
                permission_label="Control",
                risk_level=RiskLevel.MODERATE,
                events_triggered=["app_closed"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="window.minimize",
                description="Minimize a window to taskbar",
                manager="window",
                category="window",
                permission=PermissionRequired.CONTROL,
                permission_label="Control",
                risk_level=RiskLevel.LOW,
                events_triggered=["window_minimized"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="window.activate",
                description="Activate and bring window to front",
                manager="window",
                category="window",
                permission=PermissionRequired.CONTROL,
                permission_label="Control",
                risk_level=RiskLevel.LOW,
                events_triggered=["window_activated"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="activate_window",
                description="Activate and bring a window to the foreground",
                manager="window",
                category="window",
                permission=PermissionRequired.CONTROL,
                permission_label="Control",
                risk_level=RiskLevel.LOW,
                requires_confirmation=False,
                supports_undo=True,
                rollback_description="Deactivate the window and restore previous foreground window",
                events_triggered=["window_activated"],
                usage_examples=[
                    "Switch to a specific application",
                    "Bring a minimized window back",
                ],
                requires=["list_windows"],
                verifies=["get_window"],
                rollback_capabilities=["activate_window"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="close_window",
                description="Close a window",
                manager="window",
                category="window",
                permission=PermissionRequired.CONTROL,
                permission_label="Control",
                risk_level=RiskLevel.MODERATE,
                requires_confirmation=True,
                is_destructive=True,
                supports_undo=False,
                usage_examples=["Close a specific window", "Close multiple windows"],
                requires=["list_windows"],
                verifies=["list_windows"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="move_window",
                description="Move a window to specific coordinates",
                manager="window",
                category="window",
                permission=PermissionRequired.CONTROL,
                permission_label="Control",
                risk_level=RiskLevel.LOW,
                supports_undo=True,
                rollback_description="Restore window to previous position",
                events_triggered=["window_moved"],
                requires=["list_windows"],
                verifies=["get_window"],
                rollback_capabilities=["move_window"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="resize_window",
                description="Resize a window to specific dimensions",
                manager="window",
                category="window",
                permission=PermissionRequired.CONTROL,
                permission_label="Control",
                risk_level=RiskLevel.LOW,
                supports_undo=True,
                rollback_description="Restore window to previous size",
                events_triggered=["window_resized"],
                requires=["list_windows"],
                verifies=["get_window"],
                rollback_capabilities=["resize_window"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="minimize_window",
                description="Minimize a window to the taskbar",
                manager="window",
                category="window",
                permission=PermissionRequired.CONTROL,
                permission_label="Control",
                risk_level=RiskLevel.SAFE,
                supports_undo=True,
                rollback_description="Restore window from minimized state",
                events_triggered=["window_minimized"],
                requires=["list_windows"],
                verifies=["get_window"],
                rollback_capabilities=["restore_window"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="maximize_window",
                description="Maximize a window to full screen",
                manager="window",
                category="window",
                permission=PermissionRequired.CONTROL,
                permission_label="Control",
                risk_level=RiskLevel.MODERATE,
                supports_undo=True,
                rollback_description="Restore window from maximized state",
                events_triggered=["window_maximized"],
                requires=["list_windows"],
                verifies=["get_window"],
                rollback_capabilities=["restore_window"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="restore_window",
                description="Restore a minimized or maximized window",
                manager="window",
                category="window",
                permission=PermissionRequired.CONTROL,
                permission_label="Control",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
                events_triggered=["window_restored"],
                requires=["list_windows"],
                verifies=["get_window"],
            )
        )

    def _register_clipboard_capabilities(self) -> None:
        """Register clipboard capabilities - full clipboard surface"""
        # Text operations
        self.register(
            CapabilityDescriptor(
                name="clipboard.read_text",
                description="Read plain text from the clipboard",
                manager="clipboard",
                category="clipboard",
                permission=PermissionRequired.READ,
                permission_label="Read",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
                usage_examples=[
                    "Get clipboard text",
                    "Read copied text",
                    "Paste clipboard",
                ],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="clipboard.write_text",
                description="Write plain text to the clipboard",
                manager="clipboard",
                category="clipboard",
                permission=PermissionRequired.WRITE,
                permission_label="Write",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
                events_triggered=["clipboard_changed"],
                usage_examples=["Copy text to clipboard", "Set clipboard content"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="clipboard.clear",
                description="Clear the clipboard contents",
                manager="clipboard",
                category="clipboard",
                permission=PermissionRequired.WRITE,
                permission_label="Write",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
                events_triggered=["clipboard_changed"],
                usage_examples=["Clear clipboard", "Empty clipboard"],
            )
        )

        # Image operations
        self.register(
            CapabilityDescriptor(
                name="clipboard.read_image",
                description="Read image from the clipboard - Windows bitmap",
                manager="clipboard",
                category="clipboard",
                permission=PermissionRequired.READ,
                permission_label="Read",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
                usage_examples=["Get clipboard image", "Read screenshot"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="clipboard.write_image",
                description="Write image to the clipboard - Windows bitmap",
                manager="clipboard",
                category="clipboard",
                permission=PermissionRequired.WRITE,
                permission_label="Write",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
                events_triggered=["clipboard_changed"],
                usage_examples=["Copy image to clipboard", "Set clipboard image"],
            )
        )

        # File operations
        self.register(
            CapabilityDescriptor(
                name="clipboard.read_files",
                description="Read file paths from the clipboard",
                manager="clipboard",
                category="clipboard",
                permission=PermissionRequired.READ,
                permission_label="Read",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
                usage_examples=["Get copied files", "Read file paths from clipboard"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="clipboard.write_files",
                description="Write file paths to the clipboard",
                manager="clipboard",
                category="clipboard",
                permission=PermissionRequired.WRITE,
                permission_label="Write",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
                events_triggered=["clipboard_changed"],
                usage_examples=["Copy files to clipboard", "Set clipboard files"],
            )
        )

        # HTML operations
        self.register(
            CapabilityDescriptor(
                name="clipboard.read_html",
                description="Read HTML content from the clipboard",
                manager="clipboard",
                category="clipboard",
                permission=PermissionRequired.READ,
                permission_label="Read",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
                usage_examples=["Get clipboard HTML", "Read formatted content"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="clipboard.write_html",
                description="Write HTML content to the clipboard",
                manager="clipboard",
                category="clipboard",
                permission=PermissionRequired.WRITE,
                permission_label="Write",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
                events_triggered=["clipboard_changed"],
                usage_examples=["Copy HTML to clipboard", "Set clipboard HTML"],
            )
        )

        # Format queries
        self.register(
            CapabilityDescriptor(
                name="clipboard.get_formats",
                description="Get list of available clipboard formats",
                manager="clipboard",
                category="clipboard",
                permission=PermissionRequired.READ,
                permission_label="Read",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
                usage_examples=["List clipboard formats", "What is in the clipboard"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="clipboard.has_text",
                description="Check if clipboard contains text",
                manager="clipboard",
                category="clipboard",
                permission=PermissionRequired.READ,
                permission_label="Read",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
                usage_examples=["Does clipboard have text", "Check clipboard content"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="clipboard.has_image",
                description="Check if clipboard contains an image",
                manager="clipboard",
                category="clipboard",
                permission=PermissionRequired.READ,
                permission_label="Read",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
                usage_examples=[
                    "Does clipboard have an image",
                    "Check clipboard for image",
                ],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="clipboard.has_files",
                description="Check if clipboard contains files",
                manager="clipboard",
                category="clipboard",
                permission=PermissionRequired.READ,
                permission_label="Read",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
                usage_examples=[
                    "Does clipboard have files",
                    "Check clipboard for files",
                ],
            )
        )

    def _register_display_capabilities(self) -> None:
        """Register display capabilities"""
        self.register(
            CapabilityDescriptor(
                name="list_displays",
                description="List all connected display monitors",
                manager="display",
                category="display",
                permission=PermissionRequired.READ,
                permission_label="Read",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
                usage_examples=["List connected monitors", "Get display information"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="display.list",
                description="List all connected display monitors",
                manager="display",
                category="display",
                permission=PermissionRequired.READ,
                permission_label="Read",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
            )
        )

        self.register(
            CapabilityDescriptor(
                name="get_primary_display",
                description="Get information about the primary monitor",
                manager="display",
                category="display",
                permission=PermissionRequired.READ,
                permission_label="Read",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
            )
        )

        self.register(
            CapabilityDescriptor(
                name="display.primary",
                description="Get information about the primary monitor",
                manager="display",
                category="display",
                permission=PermissionRequired.READ,
                permission_label="Read",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
            )
        )

        self.register(
            CapabilityDescriptor(
                name="get_display_info",
                description="Get information about a specific display",
                manager="display",
                category="display",
                permission=PermissionRequired.READ,
                permission_label="Read",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
            )
        )

        self.register(
            CapabilityDescriptor(
                name="display.info",
                description="Get information about a specific display",
                manager="display",
                category="display",
                permission=PermissionRequired.READ,
                permission_label="Read",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
            )
        )

        self.register(
            CapabilityDescriptor(
                name="get_display_layout",
                description="Get virtual desktop layout geometry",
                manager="display",
                category="display",
                permission=PermissionRequired.READ,
                permission_label="Read",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
            )
        )

        self.register(
            CapabilityDescriptor(
                name="display.layout",
                description="Get virtual desktop layout geometry",
                manager="display",
                category="display",
                permission=PermissionRequired.READ,
                permission_label="Read",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
            )
        )

        self.register(
            CapabilityDescriptor(
                name="get_dpi",
                description="Get monitor DPI awareness and scale factor",
                manager="display",
                category="display",
                permission=PermissionRequired.READ,
                permission_label="Read",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
            )
        )

        self.register(
            CapabilityDescriptor(
                name="display.dpi",
                description="Get monitor DPI awareness and scale factor",
                manager="display",
                category="display",
                permission=PermissionRequired.READ,
                permission_label="Read",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
            )
        )

        self.register(
            CapabilityDescriptor(
                name="get_brightness",
                description="Get display brightness level",
                manager="display",
                category="display",
                permission=PermissionRequired.READ,
                permission_label="Read",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
            )
        )

        self.register(
            CapabilityDescriptor(
                name="display.brightness",
                description="Get display brightness level",
                manager="display",
                category="display",
                permission=PermissionRequired.READ,
                permission_label="Read",
                risk_level=RiskLevel.SAFE,
                supports_undo=False,
            )
        )

        self.register(
            CapabilityDescriptor(
                name="set_brightness",
                description="Set display brightness level",
                manager="display",
                category="display",
                permission=PermissionRequired.WRITE,
                permission_label="Write",
                risk_level=RiskLevel.LOW,
                supports_undo=True,
                events_triggered=["brightness_changed"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="display.set_brightness",
                description="Set display brightness level",
                manager="display",
                category="display",
                permission=PermissionRequired.WRITE,
                permission_label="Write",
                risk_level=RiskLevel.LOW,
                supports_undo=True,
                events_triggered=["brightness_changed"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="set_resolution",
                description="Set display resolution",
                manager="display",
                category="display",
                permission=PermissionRequired.WRITE,
                permission_label="Write",
                risk_level=RiskLevel.MODERATE,
                supports_undo=True,
                events_triggered=["resolution_changed"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="display.set_resolution",
                description="Set display resolution",
                manager="display",
                category="display",
                permission=PermissionRequired.WRITE,
                permission_label="Write",
                risk_level=RiskLevel.MODERATE,
                supports_undo=True,
                events_triggered=["resolution_changed"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="set_orientation",
                description="Set display orientation",
                manager="display",
                category="display",
                permission=PermissionRequired.WRITE,
                permission_label="Write",
                risk_level=RiskLevel.MODERATE,
                supports_undo=True,
                events_triggered=["orientation_changed"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="display.set_orientation",
                description="Set display orientation",
                manager="display",
                category="display",
                permission=PermissionRequired.WRITE,
                permission_label="Write",
                risk_level=RiskLevel.MODERATE,
                supports_undo=True,
                events_triggered=["orientation_changed"],
            )
        )

    def _register_power_capabilities(self) -> None:
        """Register power capabilities - full power surface"""
        # Read-only Stage 1
        read_caps = [
            ("power.battery", "Get battery level and charging status"),
            ("power.ac_status", "Get AC power line status"),
            ("power.power_plan", "Get active power plan scheme"),
            ("power.sleep_supported", "Check if sleep mode is supported"),
            ("power.hibernate_supported", "Check if hibernate mode is supported"),
        ]
        for name, desc in read_caps:
            self.register(
                CapabilityDescriptor(
                    name=name,
                    description=desc,
                    manager="power",
                    category="power",
                    permission=PermissionRequired.READ,
                    permission_label="Read",
                    risk_level=RiskLevel.SAFE,
                    supports_undo=False,
                    backend_required="wmi",
                )
            )

        # Safe Actions Stage 2
        safe_caps = [
            ("lock", "Lock workstation screen", "power.lock"),
            ("power.lock", "Lock workstation screen", None),
            ("sleep", "Put system to sleep mode", "power.sleep"),
            ("power.sleep", "Put system to sleep mode", None),
        ]
        for name, desc, fallback in safe_caps:
            self.register(
                CapabilityDescriptor(
                    name=name,
                    description=desc,
                    manager="power",
                    category="power",
                    permission=PermissionRequired.CONTROL,
                    permission_label="Control",
                    risk_level=RiskLevel.LOW,
                    supports_undo=False,
                    fallback_capability=fallback,
                    events_triggered=(
                        ["workstation_locked"] if "lock" in name else ["system_sleep"]
                    ),
                    backend_required="wmi",
                )
            )

        # Destructive Actions Stage 3
        dest_caps = [
            (
                "shutdown",
                "Shutdown the system",
                "power.shutdown",
                RiskLevel.CRITICAL,
                True,
            ),
            ("power.shutdown", "Shutdown the system", None, RiskLevel.CRITICAL, True),
            (
                "restart",
                "Restart the system",
                "power.restart",
                RiskLevel.CRITICAL,
                True,
            ),
            ("power.restart", "Restart the system", None, RiskLevel.CRITICAL, True),
            (
                "power.hibernate",
                "Put system to hibernate mode",
                None,
                RiskLevel.MODERATE,
                False,
            ),
            (
                "logoff",
                "Log off the current user",
                "power.logoff",
                RiskLevel.MODERATE,
                True,
            ),
            (
                "power.logoff",
                "Log off the current user",
                None,
                RiskLevel.MODERATE,
                True,
            ),
        ]
        for name, desc, fallback, risk, confirm in dest_caps:
            self.register(
                CapabilityDescriptor(
                    name=name,
                    description=desc,
                    manager="power",
                    category="power",
                    permission=PermissionRequired.CONTROL,
                    permission_label="Control",
                    risk_level=risk,
                    requires_confirmation=confirm,
                    is_destructive=True,
                    fallback_capability=fallback,
                    backend_required="wmi",
                    events_triggered=(
                        ["system_shutdown"]
                        if "shutdown" in name
                        else (["system_restart"] if "restart" in name else [])
                    ),
                )
            )

    def _register_audio_capabilities(self) -> None:
        """Register audio capabilities - full audio surface"""
        audio_caps = [
            (
                "list_audio_devices",
                "List all audio output and input devices",
                "READ",
                PermissionRequired.READ,
                RiskLevel.SAFE,
                False,
            ),
            (
                "audio.list_devices",
                "List all audio output and input devices",
                "READ",
                PermissionRequired.READ,
                RiskLevel.SAFE,
                False,
            ),
            (
                "get_default_audio_device",
                "Get default output audio device",
                "READ",
                PermissionRequired.READ,
                RiskLevel.SAFE,
                False,
            ),
            (
                "audio.default_device",
                "Get default output audio device",
                "READ",
                PermissionRequired.READ,
                RiskLevel.SAFE,
                False,
            ),
            (
                "get_volume",
                "Get master volume level and mute status",
                "READ",
                PermissionRequired.READ,
                RiskLevel.SAFE,
                False,
            ),
            (
                "audio.volume",
                "Get master volume level and mute status",
                "READ",
                PermissionRequired.READ,
                RiskLevel.SAFE,
                False,
            ),
            (
                "is_muted",
                "Check if audio is muted",
                "READ",
                PermissionRequired.READ,
                RiskLevel.SAFE,
                False,
            ),
            (
                "audio.is_muted",
                "Check if audio is muted",
                "READ",
                PermissionRequired.READ,
                RiskLevel.SAFE,
                False,
            ),
            (
                "list_microphones",
                "List input microphone devices",
                "READ",
                PermissionRequired.READ,
                RiskLevel.SAFE,
                False,
            ),
            (
                "audio.microphones",
                "List input microphone devices",
                "READ",
                PermissionRequired.READ,
                RiskLevel.SAFE,
                False,
            ),
            (
                "set_volume",
                "Set volume level for an audio device (0-100)",
                "CONTROL",
                PermissionRequired.CONTROL,
                RiskLevel.SAFE,
                True,
            ),
            (
                "audio.set_volume",
                "Set volume level for an audio device (0-100)",
                "CONTROL",
                PermissionRequired.CONTROL,
                RiskLevel.SAFE,
                True,
            ),
            (
                "toggle_mute",
                "Mute or unmute an audio device",
                "CONTROL",
                PermissionRequired.CONTROL,
                RiskLevel.SAFE,
                True,
            ),
            (
                "audio.toggle_mute",
                "Mute or unmute an audio device",
                "CONTROL",
                PermissionRequired.CONTROL,
                RiskLevel.SAFE,
                True,
            ),
            (
                "set_default_output",
                "Set default audio output endpoint",
                "CONTROL",
                PermissionRequired.CONTROL,
                RiskLevel.LOW,
                False,
            ),
            (
                "audio.set_default_output",
                "Set default audio output endpoint",
                "CONTROL",
                PermissionRequired.CONTROL,
                RiskLevel.LOW,
                False,
            ),
        ]

        for name, desc, perm_lbl, perm_req, risk, undo in audio_caps:
            self.register(
                CapabilityDescriptor(
                    name=name,
                    description=desc,
                    manager="audio",
                    category="audio",
                    permission=perm_req,
                    permission_label=perm_lbl,
                    risk_level=risk,
                    supports_undo=undo,
                    backend_required="pycaw",
                    minimum_windows_version="10",
                    events_triggered=(
                        ["volume_changed"]
                        if "volume" in name
                        else (["mute_toggled"] if "mute" in name else [])
                    ),
                )
            )

    def _register_network_capabilities(self) -> None:
        """Register network capabilities - full network surface"""
        # Information Capabilities (Read-only, Risk: SAFE or LOW)
        info_caps = [
            ("list_network_interfaces", "List all network interface adapters"),
            ("network.interfaces", "List all network interface adapters"),
            ("network.default_interface", "Get active default network interface"),
            ("network.public_ip", "Get external public IP address"),
            ("network.local_ip", "Get host local IP address"),
            ("network.gateway", "Get default network gateway address"),
            ("network.dns", "Get configured DNS servers"),
            ("network.mac", "Get MAC address of default interface"),
            ("network.hostname", "Get host machine name"),
            ("network.connection_type", "Get connection type (Wi-Fi/Ethernet)"),
            ("network.wifi_name", "Get connected Wi-Fi SSID"),
            ("network.signal_strength", "Get Wi-Fi signal strength percentage"),
        ]
        for name, desc in info_caps:
            self.register(
                CapabilityDescriptor(
                    name=name,
                    description=desc,
                    manager="network",
                    category="network",
                    permission=PermissionRequired.READ,
                    permission_label="Read",
                    risk_level=(
                        RiskLevel.SAFE
                        if "name" in name or "type" in name or "hostname" in name
                        else RiskLevel.LOW
                    ),
                    supports_undo=False,
                    backend_required="netsh",
                )
            )

        # Diagnostic Capabilities (Read-only, Risk: SAFE or LOW)
        diag_caps = [
            ("network.ping", "Ping target host or IP"),
            ("network.traceroute", "Perform traceroute to target host"),
            ("network.lookup", "Perform DNS lookup for domain"),
            ("network.port_check", "Check if specific port is open"),
            ("network.internet", "Check internet connection status"),
            ("network.speed", "Check network throughput speed"),
            ("network.latency", "Measure latency to target host"),
            ("network.packet_loss", "Measure packet loss percentage"),
        ]
        for name, desc in diag_caps:
            self.register(
                CapabilityDescriptor(
                    name=name,
                    description=desc,
                    manager="network",
                    category="network",
                    permission=PermissionRequired.READ,
                    permission_label="Read",
                    risk_level=RiskLevel.LOW,
                    supports_undo=False,
                    backend_required="netsh",
                )
            )

        # Control Capabilities (Mutable, Risk: HIGH or CRITICAL)
        ctrl_caps = [
            (
                "network.enable_adapter",
                "Enable a network adapter interface",
                RiskLevel.HIGH,
                False,
                False,
                ["list_network_interfaces"],
                ["network.default_interface"],
                ["network.disable_adapter"],
            ),
            (
                "network.disable_adapter",
                "Disable a network adapter interface",
                RiskLevel.CRITICAL,
                True,
                True,
                ["list_network_interfaces"],
                ["network.interfaces"],
                ["network.enable_adapter"],
            ),
            (
                "network.release_ip",
                "Release DHCP IP lease for adapter",
                RiskLevel.HIGH,
                False,
                False,
                ["list_network_interfaces"],
                ["network.local_ip"],
                [],
            ),
            (
                "network.renew_ip",
                "Renew DHCP IP lease for adapter",
                RiskLevel.HIGH,
                False,
                False,
                ["list_network_interfaces"],
                ["network.local_ip"],
                [],
            ),
            (
                "network.flush_dns",
                "Flush DNS resolver cache",
                RiskLevel.MODERATE,
                False,
                False,
                ["network.dns"],
                ["network.lookup"],
                [],
            ),
            (
                "network.disconnect_wifi",
                "Disconnect from Wi-Fi network",
                RiskLevel.HIGH,
                False,
                False,
                ["network.wifi_name"],
                ["network.wifi_name"],
                [],
            ),
            (
                "network.connect_wifi",
                "Connect to specified Wi-Fi network",
                RiskLevel.HIGH,
                False,
                False,
                ["list_network_interfaces"],
                ["network.wifi_name"],
                ["network.disconnect_wifi"],
            ),
        ]
        for name, desc, risk, confirm, dest, reqs, vers, rbs in ctrl_caps:
            self.register(
                CapabilityDescriptor(
                    name=name,
                    description=desc,
                    manager="network",
                    category="network",
                    permission=PermissionRequired.CONTROL,
                    permission_label="Control",
                    risk_level=risk,
                    requires_confirmation=confirm,
                    is_destructive=dest,
                    supports_undo=bool(rbs),
                    backend_required="netsh",
                    requires=reqs,
                    verifies=vers,
                    rollback_capabilities=rbs,
                )
            )

    def _register_registry_capabilities(self) -> None:
        """Register registry capabilities"""
        self.register(
            CapabilityDescriptor(
                name="read_registry_key",
                description="Read Windows registry keys or values",
                manager="registry",
                category="registry",
                permission=PermissionRequired.READ,
                permission_label="Read",
                risk_level=RiskLevel.MODERATE,
                requires_admin=True,
                usage_examples=["Read registry key", "Get registry value"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="write_registry_key",
                description="Write to Windows registry",
                manager="registry",
                category="registry",
                permission=PermissionRequired.WRITE,
                permission_label="Write",
                risk_level=RiskLevel.HIGH,
                requires_confirmation=True,
                is_destructive=True,
                requires_admin=True,
                usage_examples=["Set registry value", "Modify registry key"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="delete_registry_key",
                description="Delete registry key and subkeys",
                manager="registry",
                category="registry",
                permission=PermissionRequired.WRITE,
                permission_label="Write",
                risk_level=RiskLevel.HIGH,
                requires_confirmation=True,
                is_destructive=True,
                requires_admin=True,
                usage_examples=["Delete registry key", "Remove registry value"],
            )
        )

    def _register_service_capabilities(self) -> None:
        """Register service capabilities"""
        self.register(
            CapabilityDescriptor(
                name="list_services",
                description="List all Windows services",
                manager="service",
                category="service",
                permission=PermissionRequired.READ,
                permission_label="Read",
                risk_level=RiskLevel.LOW,
                supports_undo=False,
                usage_examples=["List services", "Get all services"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="start_service",
                description="Start a Windows service",
                manager="service",
                category="service",
                permission=PermissionRequired.CONTROL,
                permission_label="Control",
                risk_level=RiskLevel.MODERATE,
                requires_admin=True,
                usage_examples=["Start a service", "Start database service"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="stop_service",
                description="Stop a Windows service",
                manager="service",
                category="service",
                permission=PermissionRequired.CONTROL,
                permission_label="Control",
                risk_level=RiskLevel.MODERATE,
                requires_admin=True,
                usage_examples=["Stop a service", "Stop a network service"],
            )
        )

        self.register(
            CapabilityDescriptor(
                name="restart_service",
                description="Restart a Windows service",
                manager="service",
                category="service",
                permission=PermissionRequired.CONTROL,
                permission_label="Control",
                risk_level=RiskLevel.MODERATE,
                requires_admin=True,
                usage_examples=["Restart service", "Restart web server"],
            )
        )

    def register(self, descriptor: CapabilityDescriptor) -> None:
        """
        Register a capability descriptor.

        Args:
            descriptor: CapabilityDescriptor instance
        """
        self._capabilities[descriptor.name] = descriptor

        # Add to category index
        if descriptor.category not in self._by_category:
            self._by_category[descriptor.category] = []
        self._by_category[descriptor.category].append(descriptor.name)

    def get(self, capability_name: str) -> CapabilityDescriptor | None:
        """
        Get capability descriptor by name.

        Args:
            capability_name: Name of capability

        Returns:
            CapabilityDescriptor or None
        """
        return self._capabilities.get(capability_name)

    def get_by_category(self, category: str) -> list[CapabilityDescriptor]:
        """
        Get all capabilities in a category.

        Args:
            category: Category name

        Returns:
            List of CapabilityDescriptor objects
        """
        capability_names = self._by_category.get(category, [])
        return [
            self._capabilities[name]
            for name in capability_names
            if name in self._capabilities
        ]

    def list_all(self) -> list[CapabilityDescriptor]:
        """
        List all registered capabilities.

        Returns:
            List of CapabilityDescriptor objects
        """
        return list(self._capabilities.values())

    def list_by_category(self) -> dict[str, list[CapabilityDescriptor]]:
        """
        List capabilities organized by category.

        Returns:
            Dictionary mapping category to list of CapabilityDescriptor objects
        """
        result = {}
        for category, capability_names in self._by_category.items():
            result[category] = [
                self._capabilities[name]
                for name in capability_names
                if name in self._capabilities
            ]
        return result

    def list_by_permission(
        self, permission: PermissionRequired
    ) -> list[CapabilityDescriptor]:
        """
        List capabilities that require a specific permission.

        Args:
            permission: Permission level

        Returns:
            List of CapabilityDescriptor objects
        """
        return [
            cap for cap in self._capabilities.values() if cap.permission == permission
        ]

    def list_by_risk(self, risk_level: RiskLevel) -> list[CapabilityDescriptor]:
        """
        List capabilities with a specific risk level.

        Args:
            risk_level: Risk level

        Returns:
            List of CapabilityDescriptor objects
        """
        return [
            cap for cap in self._capabilities.values() if cap.risk_level == risk_level
        ]

    def get_permissions_required(self) -> list[PermissionRequired]:
        """Get all permission levels required by capabilities"""
        permissions = set()
        for cap in self._capabilities.values():
            permissions.add(cap.permission)
        return sorted(permissions, key=lambda x: x.value)

    def get_risk_levels(self) -> list[RiskLevel]:
        """Get all risk levels present in the registry"""
        risk_levels = set()
        for cap in self._capabilities.values():
            risk_levels.add(cap.risk_level)
        return sorted(risk_levels, key=lambda x: x.value)

    def get_capability_graph(self, capability: str) -> dict[str, Any]:
        """
        Get capability graph relationship links (requires, verifies, rollback).

        Args:
            capability: Dot-separated or standard capability name.

        Returns:
            Dictionary containing requirement, verification, and rollback capability links.
        """
        desc = self.get(capability)
        if not desc:
            return {
                "capability": capability,
                "requires": [],
                "verifies": [],
                "rollback_capabilities": [],
            }
        return {
            "capability": desc.name,
            "requires": list(desc.requires),
            "verifies": list(desc.verifies),
            "rollback_capabilities": list(desc.rollback_capabilities),
        }


# Global capability registry instance
_registry: CapabilityRegistry | None = None


def get_capability_registry() -> CapabilityRegistry:
    """
    Get the global capability registry instance.

    Returns:
        CapabilityRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = CapabilityRegistry()
    return _registry
