"""
Capability Registry
Metadata and descriptions for all native capabilities.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


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
    events_triggered: List[str] = field(default_factory=list)

    # GUI information
    supports_visualization: bool = True
    success_message_template: Optional[str] = None

    # Fallbacks
    fallback_capability: Optional[str] = None
    alternative_actions: List[str] = field(default_factory=list)

    # Behavior
    is_destructive: bool = False
    requires_confirmation: bool = False
    timeout_seconds: int = 30

    # Undo/rollback
    supports_undo: bool = False
    rollback_description: Optional[str] = None

    # Platform support
    supported_platforms: List[str] = field(default_factory=lambda: ["windows"])
    requires_elevation: bool = False

    # Additional metadata
    tags: List[str] = field(default_factory=list)
    usage_examples: List[str] = field(default_factory=list)

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
        self._capabilities: Dict[str, CapabilityDescriptor] = {}
        self._by_category: Dict[str, List[str]] = {}
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
        self.register(CapabilityDescriptor(
            name="list_windows",
            description="List all visible windows on the desktop",
            manager="window",
            category="window",
            permission=PermissionRequired.READ,
            permission_label="Read",
            risk_level=RiskLevel.SAFE,
            supports_undo=False,
            usage_examples=["List all open windows", "Find a specific window by title"],
        ))

        self.register(CapabilityDescriptor(
            name="get_window",
            description="Get detailed information about a specific window",
            manager="window",
            category="window",
            permission=PermissionRequired.READ,
            permission_label="Read",
            risk_level=RiskLevel.SAFE,
            supports_undo=False,
        ))

        self.register(CapabilityDescriptor(
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
            usage_examples=["Switch to a specific application", "Bring a minimized window back"],
        ))

        self.register(CapabilityDescriptor(
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
        ))

        self.register(CapabilityDescriptor(
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
        ))

        self.register(CapabilityDescriptor(
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
        ))

        self.register(CapabilityDescriptor(
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
        ))

        self.register(CapabilityDescriptor(
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
        ))

        self.register(CapabilityDescriptor(
            name="restore_window",
            description="Restore a minimized or maximized window",
            manager="window",
            category="window",
            permission=PermissionRequired.CONTROL,
            permission_label="Control",
            risk_level=RiskLevel.SAFE,
            supports_undo=False,
            events_triggered=["window_restored"],
        ))

    def _register_clipboard_capabilities(self) -> None:
        """Register clipboard capabilities"""
        self.register(CapabilityDescriptor(
            name="read_clipboard",
            description="Read text and other data from the clipboard",
            manager="clipboard",
            category="clipboard",
            permission=PermissionRequired.READ,
            permission_label="Read",
            risk_level=RiskLevel.SAFE,
            supports_undo=False,
            usage_examples=["Get clipboard content", "Read copied text"],
        ))

        self.register(CapabilityDescriptor(
            name="write_clipboard",
            description="Write text or other data to the clipboard",
            manager="clipboard",
            category="clipboard",
            permission=PermissionRequired.WRITE,
            permission_label="Write",
            risk_level=RiskLevel.SAFE,
            supports_undo=False,
            events_triggered=["clipboard_changed"],
            usage_examples=["Copy text", "Set clipboard content"],
        ))

        self.register(CapabilityDescriptor(
            name="clear_clipboard",
            description="Clear the clipboard contents",
            manager="clipboard",
            category="clipboard",
            permission=PermissionRequired.WRITE,
            permission_label="Write",
            risk_level=RiskLevel.SAFE,
            supports_undo=False,
            events_triggered=["clipboard_changed"],
            usage_examples=["Clear clipboard", "Remove clipboard content"],
        ))

    def _register_display_capabilities(self) -> None:
        """Register display capabilities"""
        self.register(CapabilityDescriptor(
            name="list_displays",
            description="List all connected display monitors",
            manager="display",
            category="display",
            permission=PermissionRequired.READ,
            permission_label="Read",
            risk_level=RiskLevel.SAFE,
            supports_undo=False,
            usage_examples=["List connected monitors", "Get display information"],
        ))

        self.register(CapabilityDescriptor(
            name="get_primary_display",
            description="Get information about the primary monitor",
            manager="display",
            category="display",
            permission=PermissionRequired.READ,
            permission_label="Read",
            risk_level=RiskLevel.SAFE,
            supports_undo=False,
        ))

        self.register(CapabilityDescriptor(
            name="get_display",
            description="Get information about a specific display",
            manager="display",
            category="display",
            permission=PermissionRequired.READ,
            permission_label="Read",
            risk_level=RiskLevel.SAFE,
            supports_undo=False,
        ))

    def _register_power_capabilities(self) -> None:
        """Register power capabilities"""
        self.register(CapabilityDescriptor(
            name="shutdown",
            description="Shutdown the system",
            manager="power",
            category="power",
            permission=PermissionRequired.CONTROL,
            permission_label="Control",
            risk_level=RiskLevel.CRITICAL,
            requires_confirmation=True,
            is_destructive=True,
            requires_admin=True,
            usage_examples=["Shutdown computer", "Turn off system"],
        ))

        self.register(CapabilityDescriptor(
            name="restart",
            description="Restart the system",
            manager="power",
            category="power",
            permission=PermissionRequired.CONTROL,
            permission_label="Control",
            risk_level=RiskLevel.CRITICAL,
            requires_confirmation=True,
            is_destructive=True,
            requires_admin=True,
            usage_examples=["Restart computer", "Reboot system"],
        ))

        self.register(CapabilityDescriptor(
            name="sleep",
            description="Put system to sleep mode",
            manager="power",
            category="power",
            permission=PermissionRequired.CONTROL,
            permission_label="Control",
            risk_level=RiskLevel.LOW,
            is_destructive=False,
            usage_examples=["Put to sleep", "Hibernate"],
        ))

        self.register(CapabilityDescriptor(
            name="lock",
            description="Lock the screen",
            manager="power",
            category="power",
            permission=PermissionRequired.CONTROL,
            permission_label="Control",
            risk_level=RiskLevel.SAFE,
            is_destructive=False,
            usage_examples=["Lock screen", "Lock workstation"],
        ))

        self.register(CapabilityDescriptor(
            name="logoff",
            description="Log off the current user",
            manager="power",
            category="power",
            permission=PermissionRequired.CONTROL,
            permission_label="Control",
            risk_level=RiskLevel.MODERATE,
            requires_confirmation=True,
            is_destructive=False,
            usage_examples=["Log off user", "Switch user"],
        ))

    def _register_audio_capabilities(self) -> None:
        """Register audio capabilities"""
        self.register(CapabilityDescriptor(
            name="list_audio_devices",
            description="List all audio output and input devices",
            manager="audio",
            category="audio",
            permission=PermissionRequired.READ,
            permission_label="Read",
            risk_level=RiskLevel.SAFE,
            supports_undo=False,
            usage_examples=["List audio devices", "Get speaker and microphone info"],
        ))

        self.register(CapabilityDescriptor(
            name="set_volume",
            description="Set volume level for an audio device",
            manager="audio",
            category="audio",
            permission=PermissionRequired.CONTROL,
            permission_label="Control",
            risk_level=RiskLevel.SAFE,
            supports_undo=True,
            rollback_description="Restore previous volume level",
            events_triggered=["audio_volume_changed"],
        ))

        self.register(CapabilityDescriptor(
            name="toggle_mute",
            description="Mute or unmute an audio device",
            manager="audio",
            category="audio",
            permission=PermissionRequired.CONTROL,
            permission_label="Control",
            risk_level=RiskLevel.SAFE,
            supports_undo=True,
            rollback_description="Restore previous mute state",
            events_triggered=["audio_volume_changed"],
        ))

    def _register_network_capabilities(self) -> None:
        """Register network capabilities"""
        self.register(CapabilityDescriptor(
            name="list_network_interfaces",
            description="List all network interface adapters",
            manager="network",
            category="network",
            permission=PermissionRequired.READ,
            permission_label="Read",
            risk_level=RiskLevel.LOW,
            supports_undo=False,
            usage_examples=["List network adapters", "Get network interface info"],
        ))

    def _register_registry_capabilities(self) -> None:
        """Register registry capabilities"""
        self.register(CapabilityDescriptor(
            name="read_registry_key",
            description="Read Windows registry keys or values",
            manager="registry",
            category="registry",
            permission=PermissionRequired.READ,
            permission_label="Read",
            risk_level=RiskLevel.MODERATE,
            requires_admin=True,
            usage_examples=["Read registry key", "Get registry value"],
        ))

        self.register(CapabilityDescriptor(
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
        ))

        self.register(CapabilityDescriptor(
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
        ))

    def _register_service_capabilities(self) -> None:
        """Register service capabilities"""
        self.register(CapabilityDescriptor(
            name="list_services",
            description="List all Windows services",
            manager="service",
            category="service",
            permission=PermissionRequired.READ,
            permission_label="Read",
            risk_level=RiskLevel.LOW,
            supports_undo=False,
            usage_examples=["List services", "Get all services"],
        ))

        self.register(CapabilityDescriptor(
            name="start_service",
            description="Start a Windows service",
            manager="service",
            category="service",
            permission=PermissionRequired.CONTROL,
            permission_label="Control",
            risk_level=RiskLevel.MODERATE,
            requires_admin=True,
            usage_examples=["Start a service", "Start database service"],
        ))

        self.register(CapabilityDescriptor(
            name="stop_service",
            description="Stop a Windows service",
            manager="service",
            category="service",
            permission=PermissionRequired.CONTROL,
            permission_label="Control",
            risk_level=RiskLevel.MODERATE,
            requires_admin=True,
            usage_examples=["Stop a service", "Stop a network service"],
        ))

        self.register(CapabilityDescriptor(
            name="restart_service",
            description="Restart a Windows service",
            manager="service",
            category="service",
            permission=PermissionRequired.CONTROL,
            permission_label="Control",
            risk_level=RiskLevel.MODERATE,
            requires_admin=True,
            usage_examples=["Restart service", "Restart web server"],
        ))

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

    def get(self, capability_name: str) -> Optional[CapabilityDescriptor]:
        """
        Get capability descriptor by name.

        Args:
            capability_name: Name of capability

        Returns:
            CapabilityDescriptor or None
        """
        return self._capabilities.get(capability_name)

    def get_by_category(self, category: str) -> List[CapabilityDescriptor]:
        """
        Get all capabilities in a category.

        Args:
            category: Category name

        Returns:
            List of CapabilityDescriptor objects
        """
        capability_names = self._by_category.get(category, [])
        return [self._capabilities[name] for name in capability_names if name in self._capabilities]

    def list_all(self) -> List[CapabilityDescriptor]:
        """
        List all registered capabilities.

        Returns:
            List of CapabilityDescriptor objects
        """
        return list(self._capabilities.values())

    def list_by_category(self) -> Dict[str, List[CapabilityDescriptor]]:
        """
        List capabilities organized by category.

        Returns:
            Dictionary mapping category to list of CapabilityDescriptor objects
        """
        result = {}
        for category, capability_names in self._by_category.items():
            result[category] = [self._capabilities[name] for name in capability_names if name in self._capabilities]
        return result

    def list_by_permission(self, permission: PermissionRequired) -> List[CapabilityDescriptor]:
        """
        List capabilities that require a specific permission.

        Args:
            permission: Permission level

        Returns:
            List of CapabilityDescriptor objects
        """
        return [
            cap for cap in self._capabilities.values()
            if cap.permission == permission
        ]

    def list_by_risk(self, risk_level: RiskLevel) -> List[CapabilityDescriptor]:
        """
        List capabilities with a specific risk level.

        Args:
            risk_level: Risk level

        Returns:
            List of CapabilityDescriptor objects
        """
        return [
            cap for cap in self._capabilities.values()
            if cap.risk_level == risk_level
        ]

    def get_permissions_required(self) -> List[PermissionRequired]:
        """Get all permission levels required by capabilities"""
        permissions = set()
        for cap in self._capabilities.values():
            permissions.add(cap.permission)
        return sorted(permissions, key=lambda x: x.value)

    def get_risk_levels(self) -> List[RiskLevel]:
        """Get all risk levels present in the registry"""
        risks = set()
        for cap in self._capabilities.values():
            risks.add(cap.risk_level)
        return sorted(risks, key=lambda x: x.value)


# Global capability registry instance
_registry: Optional[CapabilityRegistry] = None


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
