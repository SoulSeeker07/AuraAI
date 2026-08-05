"""
Capability Router
Intermediary between Planner and NativeManager.

Routes capability requests to appropriate managers and provides
unified interface for Aura Brain.
"""

from enum import Enum
from typing import Any

from .capability_registry import CapabilityRegistry, PermissionRequired
from .desktop_context import ContextScope, get_desktop_context
from .native_exceptions import CapabilityNotFoundError
from .native_manager import NativeCapability, NativeManager
from .native_models import (
    ClipboardData,
)


class RoutingStrategy(Enum):
    """Strategy for routing capability requests"""

    DIRECT = "direct"  # Direct routing to manager
    FALLBACK = "fallback"  # Try primary, fall back to alternatives
    RISK_BASED = "risk_based"  # Choose based on risk level
    PREFER_CACHE = "prefer_cache"  # Prefer cached state


class CapabilityRouter:
    """
    Router for native capability requests.

    Acts as intermediary between:
    - Planner (Aura Brain) → CapabilityRouter → NativeManager → Managers

    Provides:
    - Unified routing interface
    - Permission checking and validation
    - Fallback strategies
    - Context queries
    """

    def __init__(
        self,
        native_manager: NativeManager | None = None,
        registry: CapabilityRegistry | None = None,
        router_strategy: RoutingStrategy = RoutingStrategy.DIRECT,
    ):
        """
        Initialize capability router.

        Args:
            native_manager: NativeManager instance (defaults to singleton)
            registry: CapabilityRegistry instance (defaults to singleton)
            router_strategy: Strategy for routing capability requests
        """
        self.native_manager = native_manager or get_native_manager()
        self.registry = registry or get_capability_registry()
        self.router_strategy = router_strategy

    def route_capability(self, capability: NativeCapability, **kwargs) -> Any:
        """
        Route a capability request to the appropriate manager.

        Args:
            capability: NativeCapability to execute
            **kwargs: Additional arguments for the capability

        Returns:
            Result of the capability execution

        Raises:
            CapabilityNotFoundError: If capability not found in registry
        """
        # Validate capability exists in registry
        descriptor = self.registry.get(capability.value)
        if not descriptor:
            raise CapabilityNotFoundError(
                f"Capability '{capability.value}' not found in registry"
            )

        # Route based on strategy
        if self.router_strategy == RoutingStrategy.DIRECT:
            return self._route_direct(capability, descriptor, **kwargs)
        elif self.router_strategy == RoutingStrategy.FALLBACK:
            return self._route_fallback(capability, descriptor, **kwargs)
        elif self.router_strategy == RoutingStrategy.RISK_BASED:
            return self._route_risk_based(capability, descriptor, **kwargs)
        elif self.router_strategy == RoutingStrategy.PREFER_CACHE:
            return self._route_cache_preferred(capability, descriptor, **kwargs)

        # Default to direct routing
        return self._route_direct(capability, descriptor, **kwargs)

    def _route_direct(
        self, capability: NativeCapability, descriptor: Any, **kwargs
    ) -> Any:
        """
        Direct routing strategy.

        Args:
            capability: NativeCapability to execute
            descriptor: Capability descriptor
            **kwargs: Additional arguments

        Returns:
            Result from native manager
        """
        # Delegate to NativeManager
        manager_method = getattr(self.native_manager, capability.value)
        return manager_method(**kwargs)

    def _route_fallback(
        self, capability: NativeCapability, descriptor: Any, **kwargs
    ) -> Any:
        """
        Fallback routing strategy.

        Tries primary capability first, then alternatives.

        Args:
            capability: NativeCapability to execute
            descriptor: Capability descriptor
            **kwargs: Additional arguments

        Returns:
            Result from native manager or fallback
        """
        # Try primary capability
        try:
            return self._route_direct(capability, descriptor, **kwargs)
        except Exception:
            # Try fallback capability if defined
            if descriptor.fallback_capability:
                try:
                    fallback_cap = NativeCapability(descriptor.fallback_capability)
                    fallback_descriptor = self.registry.get(
                        descriptor.fallback_capability
                    )
                    if fallback_descriptor:
                        return self._route_direct(
                            fallback_cap, fallback_descriptor, **kwargs
                        )
                except Exception:
                    pass

            # Try alternative actions
            for alternative in descriptor.alternative_actions:
                try:
                    alt_cap = NativeCapability(alternative)
                    alt_descriptor = self.registry.get(alternative)
                    if alt_descriptor:
                        return self._route_direct(alt_cap, alt_descriptor, **kwargs)
                except Exception:
                    pass

            # Re-raise original exception
            raise

    def _route_risk_based(
        self, capability: NativeCapability, descriptor: Any, **kwargs
    ) -> Any:
        """
        Risk-based routing strategy.

        May adjust behavior based on risk level and confirmation requirements.

        Args:
            capability: NativeCapability to execute
            descriptor: Capability descriptor
            **kwargs: Additional arguments

        Returns:
            Result from native manager
        """
        # Check risk level and apply strategy
        if descriptor.risk_level.value in ["critical", "high"]:
            # For high risk, log and potentially notify
            # In real implementation, this would trigger UI notifications
            pass

        # Check destructive and requires_confirmation
        if descriptor.is_destructive and descriptor.requires_confirmation:
            # Check if user has confirmed (in real implementation)
            # For now, just proceed
            pass

        # Route directly
        return self._route_direct(capability, descriptor, **kwargs)

    def _route_cache_preferred(
        self, capability: NativeCapability, descriptor: Any, **kwargs
    ) -> Any:
        """
        Cache-preferred routing strategy.

        Tries to use cached state first before calling native manager.

        Args:
            capability: NativeCapability to execute
            descriptor: Capability descriptor
            **kwargs: Additional arguments

        Returns:
            Result from native manager or cache
        """
        # For read operations, prefer cache
        if descriptor.permission == PermissionRequired.READ:
            return self._get_from_cache(capability, **kwargs)
        else:
            # For write/modify operations, call native manager
            return self._route_direct(capability, descriptor, **kwargs)

    def _get_from_cache(self, capability: NativeCapability, **kwargs) -> Any:
        """
        Get data from cache.

        Args:
            capability: NativeCapability to get from cache
            **kwargs: Additional arguments

        Returns:
            Cached data or None
        """
        desktop_context = get_desktop_context()

        if capability == NativeCapability.LIST_WINDOWS:
            return desktop_context.get_windows()
        elif capability == NativeCapability.GET_WINDOW:
            window_id = kwargs.get("window_id")
            if window_id:
                # Try title-based lookup
                windows = desktop_context.get_windows()
                for win in windows:
                    if win.title == window_id:
                        return win
            return None
        elif capability == NativeCapability.GET_ACTIVE_WINDOW:
            return desktop_context.get_active_window()
        elif capability == NativeCapability.LIST_DISPLAYS:
            return desktop_context.get_displays()
        elif capability == NativeCapability.GET_PRIMARY_DISPLAY:
            return desktop_context.get_primary_display()
        elif capability == NativeCapability.LIST_AUDIO_DEVICES:
            return desktop_context.get_audio_devices()
        elif capability == NativeCapability.LIST_NETWORK_INTERFACES:
            return desktop_context.get_network_interfaces()

        # Not a cacheable operation
        return None

    def get_capability_metadata(
        self, capability: NativeCapability
    ) -> dict[str, Any] | None:
        """
        Get metadata for a capability.

        Args:
            capability: NativeCapability to get metadata for

        Returns:
            Dictionary with metadata or None
        """
        descriptor = self.registry.get(capability.value)
        if descriptor:
            return {
                "name": descriptor.name,
                "description": descriptor.description,
                "manager": descriptor.manager,
                "category": descriptor.category,
                "permission": descriptor.permission.value,
                "permission_label": descriptor.permission_label,
                "risk_level": descriptor.risk_level.value,
                "supports_undo": descriptor.supports_undo,
                "is_destructive": descriptor.is_destructive,
                "requires_confirmation": descriptor.requires_confirmation,
                "events_triggered": descriptor.events_triggered,
                "timeout_seconds": descriptor.timeout_seconds,
                "supported_platforms": descriptor.supported_platforms,
            }
        return None

    def get_all_capabilities(self) -> list[dict[str, Any]]:
        """
        Get metadata for all capabilities.

        Returns:
            List of capability metadata dictionaries
        """
        return [
            self.get_capability_metadata(NativeCapability(cap_name))
            for cap_name in self.registry.list_all()
        ]

    def get_capabilities_by_category(self, category: str) -> list[dict[str, Any]]:
        """
        Get all capabilities in a category.

        Args:
            category: Category name

        Returns:
            List of capability metadata dictionaries
        """
        descriptors = self.registry.get_by_category(category)
        return [
            self.get_capability_metadata(NativeCapability(desc.name))
            for desc in descriptors
        ]

    def get_capabilities_by_permission(
        self, permission: PermissionRequired
    ) -> list[dict[str, Any]]:
        """
        Get all capabilities requiring a specific permission.

        Args:
            permission: Permission level

        Returns:
            List of capability metadata dictionaries
        """
        descriptors = self.registry.list_by_permission(permission)
        return [
            self.get_capability_metadata(NativeCapability(desc.name))
            for desc in descriptors
        ]

    def get_capabilities_by_risk(self, risk_level: str) -> list[dict[str, Any]]:
        """
        Get all capabilities with a specific risk level.

        Args:
            risk_level: Risk level value (safe, low, moderate, high, critical)

        Returns:
            List of capability metadata dictionaries
        """
        from .capability_registry import RiskLevel

        try:
            risk_enum = RiskLevel(risk_level)
            descriptors = self.registry.list_by_risk(risk_enum)
            return [
                self.get_capability_metadata(NativeCapability(desc.name))
                for desc in descriptors
            ]
        except ValueError:
            return []

    def list_by_category(self) -> dict[str, list[dict[str, Any]]]:
        """
        List all capabilities organized by category.

        Returns:
            Dictionary mapping category to list of capability metadata
        """
        result = {}
        for category in self.registry.list_by_category():
            result[category] = self.get_capabilities_by_category(category)
        return result

    def query_context(self, context_type: str) -> Any:
        """
        Query current desktop context.

        Args:
            context_type: Type of context to query

        Returns:
            Context data or None

        Context types:
            - windows: List of windows
            - processes: List of processes
            - clipboard: Clipboard data
            - displays: List of displays
            - audio: List of audio devices
            - network: List of network interfaces
        """
        desktop_context = get_desktop_context()

        context_type = context_type.lower()

        if context_type == "windows":
            return desktop_context.get_windows()
        elif context_type == "processes":
            return desktop_context.get_processes()
        elif context_type == "clipboard":
            return desktop_context.get_clipboard()
        elif context_type == "displays":
            return desktop_context.get_displays()
        elif context_type == "audio":
            return desktop_context.get_audio_devices()
        elif context_type == "network":
            return desktop_context.get_network_interfaces()

        return None

    def update_context(
        self, context_type: str, data: Any, scope: ContextScope = ContextScope.LOCAL
    ) -> None:
        """
        Update desktop context.

        Args:
            context_type: Type of context to update
            data: New context data
            scope: Scope of the update (LOCAL or GLOBAL)

        Context types:
            - windows: List of WindowInfo
            - processes: List of ProcessInfo
            - clipboard: ClipboardData
            - displays: List of DisplayInfo
            - audio: List of AudioDevice
            - network: List of NetworkInterface
        """
        desktop_context = get_desktop_context()

        context_type = context_type.lower()

        if context_type == "windows" and isinstance(data, list):
            desktop_context.update_windows(data, scope=scope)
        elif context_type == "processes" and isinstance(data, list):
            desktop_context.update_processes(data, scope=scope)
        elif context_type == "clipboard" and isinstance(data, ClipboardData):
            desktop_context.update_clipboard(data)
        elif context_type == "displays" and isinstance(data, list):
            desktop_context.update_displays(data, scope=scope)
        elif context_type == "audio" and isinstance(data, list):
            desktop_context.update_audio_devices(data, scope=scope)
        elif context_type == "network" and isinstance(data, list):
            desktop_context.update_network_interfaces(data, scope=scope)

    def sync_context(self, scope: ContextScope = ContextScope.GLOBAL) -> None:
        """
        Synchronize context with current desktop state.

        Calls native manager to get current state and updates context.

        Args:
            scope: Scope of synchronization
        """
        # Get current state from native manager
        windows = self.native_manager.list_windows()
        processes = self.native_manager.list_processes()
        clipboard = self.native_manager.read_clipboard()
        displays = self.native_manager.list_displays()
        audio_devices = self.native_manager.list_audio_devices()
        network_interfaces = self.native_manager.list_network_interfaces()

        # Update context
        self.update_context("windows", windows, scope=scope)
        self.update_context("processes", processes, scope=scope)
        self.update_context("clipboard", clipboard)
        self.update_context("displays", displays, scope=scope)
        self.update_context("audio", audio_devices, scope=scope)
        self.update_context("network", network_interfaces, scope=scope)


# Singleton instance
_router: CapabilityRouter | None = None


def get_capability_router(
    native_manager: NativeManager | None = None,
    registry: CapabilityRegistry | None = None,
    router_strategy: RoutingStrategy = RoutingStrategy.DIRECT,
) -> CapabilityRouter:
    """
    Get or create the global capability router singleton.

    Args:
        native_manager: Optional NativeManager instance
        registry: Optional CapabilityRegistry instance
        router_strategy: Optional routing strategy

    Returns:
        CapabilityRouter instance
    """
    global _router
    if _router is None:
        _router = CapabilityRouter(
            native_manager=native_manager,
            registry=registry,
            router_strategy=router_strategy,
        )
    return _router


def reset_capability_router() -> None:
    """Reset the global capability router"""
    global _router
    _router = None


def get_native_manager() -> NativeManager:
    """Get NativeManager singleton (for internal use)"""
    from .native_manager import NativeManager

    return NativeManager()


def get_capability_registry() -> CapabilityRegistry:
    """Get CapabilityRegistry singleton (for internal use)"""
    from .capability_registry import CapabilityRegistry

    return CapabilityRegistry()
