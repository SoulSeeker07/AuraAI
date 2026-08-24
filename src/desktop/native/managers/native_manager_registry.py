"""
Native Manager Registry & Auto-Discovery Subsystem

Single source of truth for all native desktop managers in Aura.
Handles dynamic package discovery, manager lifecycle, capability resolution,
dependency checks, and health monitoring.
"""

import builtins
import importlib
import inspect
import logging
import pkgutil
import threading
from typing import Any, Optional

from ..native_exceptions import NativeError
from .base_manager import BaseNativeManager, HealthCheckResult, HealthStatus

logger = logging.getLogger(__name__)


class NativeManagerRegistry:
    """
    Registry and lifecycle manager for all native managers.

    Key responsibilities:
    1. Dynamic Auto-Discovery of BaseNativeManager subclasses in package.
    2. Lifecycle management (Discover -> Instantiate -> Initialize -> Health -> Register -> Shutdown).
    3. Data-driven capability resolution (resolve(capability) -> Manager).
    4. Aggregated Health and Diagnostic monitoring.
    """

    _instance: Optional["NativeManagerRegistry"] = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self):
        """Initialize empty registry."""
        self._managers: dict[str, BaseNativeManager] = {}
        self._capability_map: dict[str, BaseNativeManager] = {}
        self._health_cache: dict[str, HealthCheckResult] = {}
        self._auto_discovered: bool = False

    @classmethod
    def get_instance(cls) -> "NativeManagerRegistry":
        """Get or create singleton instance of NativeManagerRegistry."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (primarily for testing)."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.shutdown_all()
                cls._instance = None

    def discover(self, package_name: str = "src.desktop.native.managers") -> list[str]:
        """
        Scan package directory to auto-discover and register all BaseNativeManager subclasses.

        Lifecycle for discovered managers:
        1. Discover: Import module and find BaseNativeManager subclass.
        2. Instantiate: Instantiate manager.
        3. Initialize: Call manager.initialize().
        4. Health Check: Perform health_check().
        5. Register Capabilities: Map capabilities to manager.
        6. Ready: Add to registry.

        Args:
            package_name: Dot-separated package name to scan.

        Returns:
            List of registered manager names.
        """
        if package_name.startswith("src."):
            package_name = package_name.replace("src.", "", 1)

        logger.info(f"Starting native manager discovery in package: '{package_name}'")
        discovered_classes: list[type[BaseNativeManager]] = []

        try:
            package = importlib.import_module(package_name)
        except ImportError as e:
            logger.warning(
                f"Could not import package '{package_name}' for discovery: {e}"
            )
            return []

        package_path = getattr(package, "__path__", None)
        if not package_path:
            logger.warning(f"Package '{package_name}' has no __path__ attribute")
            return []

        for _, module_name, is_pkg in pkgutil.walk_packages(
            package_path, prefix=f"{package_name}."
        ):
            if is_pkg:
                continue
            try:
                module = importlib.import_module(module_name)
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (
                        issubclass(obj, BaseNativeManager)
                        and obj is not BaseNativeManager
                        and not inspect.isabstract(obj)
                    ):
                        if obj not in discovered_classes:
                            discovered_classes.append(obj)
            except Exception as e:
                logger.error(f"Failed to scan module {module_name}: {e}")

        # Sort classes by PRIORITY attribute (lower = higher priority)
        discovered_classes.sort(key=lambda cls: getattr(cls, "PRIORITY", 100))

        registered_names: list[str] = []
        excluded_managers: list[tuple[str, str]] = []
        for cls in discovered_classes:
            mgr_name = getattr(cls, "NAME", cls.__name__.lower())
            try:
                instance = cls()
                self.register(instance)
                registered_names.append(instance.name)
            except Exception as e:
                excluded_managers.append((mgr_name, str(e)))
                logger.error(
                    f"Manager '{mgr_name}' ({cls.__name__}) failed discovery lifecycle and was EXCLUDED: {e}"
                )

        self._auto_discovered = True
        if excluded_managers:
            logger.warning(
                f"Discovery summary: {len(registered_names)}/{len(discovered_classes)} native managers registered. "
                f"EXCLUDED ({len(excluded_managers)}): {[name for name, _ in excluded_managers]}"
            )
        else:
            logger.info(
                f"Discovery summary: 100% healthy ({len(registered_names)}/{len(discovered_classes)} managers registered): {registered_names}"
            )
        return registered_names

    def register(self, manager: Any) -> None:
        """
        Register a manager instance into the registry following lifecycle.

        Args:
            manager: Subclass instance of BaseNativeManager or compatible manager.
        """
        name = getattr(
            manager,
            "name",
            getattr(manager, "NAME", manager.__class__.__name__.lower()),
        )
        if not name:
            raise NativeError(f"Manager {manager} must have a valid non-empty name.")

        # Lifecycle Stage 3: Initialize
        if hasattr(manager, "initialize") and callable(getattr(manager, "initialize")):
            try:
                manager.initialize()
            except Exception as e:
                raise NativeError(
                    f"Manager '{name}' failed during initialize() and cannot be registered: {e}"
                ) from e

        # Lifecycle Stage 3.5: Register capabilities on manager
        if hasattr(manager, "register_capabilities") and callable(
            getattr(manager, "register_capabilities")
        ):
            try:
                manager_caps = getattr(manager, "capabilities", [])
                if callable(manager_caps):
                    manager_caps = manager_caps()
                if hasattr(manager, "get_capabilities"):
                    already = set(manager.get_capabilities())
                elif hasattr(manager, "_capabilities"):
                    already = set(getattr(manager, "_capabilities", []))
                else:
                    already = set()
                needed = [c for c in manager_caps if c not in already]
                if needed:
                    manager.register_capabilities(needed)
            except Exception as e:
                raise NativeError(
                    f"Manager '{name}' failed during register_capabilities() and cannot be registered: {e}"
                ) from e

        # Lifecycle Stage 4: Health Check
        if hasattr(manager, "health_check") and callable(
            getattr(manager, "health_check")
        ):
            try:
                health_res = manager.health_check()
                self._health_cache[name] = health_res
            except Exception as e:
                logger.warning(f"Manager '{name}' health check failed: {e}")

        # Lifecycle Stage 5: Capability Mapping
        caps = getattr(manager, "capabilities", [])
        if callable(caps):
            caps = caps()

        priority = getattr(manager, "PRIORITY", 100)
        for cap in caps:
            if cap in self._capability_map:
                existing_manager = self._capability_map[cap]
                existing_priority = getattr(existing_manager, "PRIORITY", 100)
                if priority > existing_priority:
                    continue
                logger.warning(
                    f"Capability '{cap}' already mapped to '{existing_manager.name}' (priority {existing_priority}). "
                    f"Overriding with higher priority manager '{name}' (priority {priority})."
                )
            self._capability_map[cap] = manager

        self._managers[name] = manager
        logger.info(
            f"Registered native manager '{name}' with {len(caps)} capabilities."
        )

    def unregister(self, name: str) -> None:
        """Unregister and shutdown a manager by name."""
        if name in self._managers:
            manager = self._managers.pop(name)
            self._health_cache.pop(name, None)

            # Clean capability map
            caps_to_remove = [
                cap for cap, m in self._capability_map.items() if m.name == name
            ]
            for cap in caps_to_remove:
                del self._capability_map[cap]

            try:
                manager.shutdown()
            except Exception as e:
                logger.error(f"Error during manager '{name}' shutdown: {e}")

    def resolve(self, capability: str) -> BaseNativeManager | None:
        """
        Resolve the responsible manager for a given capability name.

        Args:
            capability: Dot-separated or standard capability name.

        Returns:
            The BaseNativeManager instance or None if unmapped.
        """
        if capability in self._capability_map:
            return self._capability_map[capability]

        # Prefix fallback (e.g. "window.activate" -> manager with name "window")
        prefix = (
            capability.split(".")[0] if "." in capability else capability.split("_")[0]
        )
        if prefix in self._managers:
            return self._managers[prefix]

        return None

    def get(self, name: str) -> BaseNativeManager | None:
        """Get manager instance by name."""
        return self._managers.get(name)

    def get_manager(self, name: str) -> BaseNativeManager | None:
        """Alias for get() to support get_manager(name)."""
        return self.get(name)

    def list(self) -> list[dict[str, Any]]:
        """List descriptors of all registered managers."""
        res = []
        for name, m in self._managers.items():
            health_info = self._health_cache.get(name)
            res.append(
                {
                    "name": name,
                    "version": getattr(m, "VERSION", "1.0"),
                    "priority": getattr(m, "PRIORITY", 100),
                    "capabilities_count": len(m.capabilities),
                    "health_status": (
                        health_info.status.value
                        if health_info
                        else HealthStatus.HEALTHY.value
                    ),
                }
            )
        return res

    def health(self) -> dict[str, dict[str, Any]]:
        """Return health summary of all managers."""
        out = {}
        for name, m in self._managers.items():
            h_res = m.health_check()
            self._health_cache[name] = h_res
            out[name] = {
                "status": h_res.status.value,
                "missing_dependencies": h_res.missing_dependencies,
                "available_fallbacks": h_res.available_fallbacks,
                "total_capabilities": h_res.total_capabilities,
                "available_capabilities": h_res.available_capabilities,
                "details": h_res.details,
            }
        return out

    def diagnostics(self) -> dict[str, Any]:
        """Get rich diagnostic status of native manager registry."""
        h_data = self.health()
        healthy_count = sum(
            1 for v in h_data.values() if v["status"] == HealthStatus.HEALTHY.value
        )
        return {
            "total_managers": len(self._managers),
            "healthy_managers": healthy_count,
            "total_mapped_capabilities": len(self._capability_map),
            "auto_discovered": self._auto_discovered,
            "managers": h_data,
        }

    def reload(self) -> builtins.list[str]:
        """Dynamic reload: shutdown all managers and re-discover."""
        self.shutdown_all()
        return self.discover()

    def shutdown_all(self) -> None:
        """Shutdown all registered managers."""
        for name in list(self._managers.keys()):
            self.unregister(name)
        self._managers.clear()
        self._capability_map.clear()
        self._health_cache.clear()
        self._auto_discovered = False

    def get_boot_report(self, simulation_mode: bool = False) -> str:
        """
        Generate a human-readable Aura Desktop Boot Report.

        Args:
            simulation_mode: Whether DesktopExecutionEngine is in simulation mode.

        Returns:
            Formatted multiline boot report string.
        """
        health_data = self.health()
        healthy_count = sum(
            1 for v in health_data.values() if v["status"] == HealthStatus.HEALTHY.value
        )
        degraded_count = sum(
            1
            for v in health_data.values()
            if v["status"] == HealthStatus.DEGRADED.value
        )

        lines = [
            "========================================",
            "          Aura Desktop Boot             ",
            "========================================",
            "Loading managers...",
        ]

        for name, manager in self._managers.items():
            adapter_info = ""
            if hasattr(manager, "adapter"):
                adapter_info = f" ({manager.adapter.name})"
            h_info = health_data.get(name, {})
            st_symbol = (
                "✓" if h_info.get("status") == HealthStatus.HEALTHY.value else "⚠"
            )
            lines.append(f"  {st_symbol} {manager.__class__.__name__}{adapter_info}")

        lines.extend(
            [
                "",
                "Manager Registry",
                f"  Managers Loaded: {len(self._managers)}",
                f"  Capabilities Mapped: {len(self._capability_map)}",
                f"  Healthy: {healthy_count} | Degraded: {degraded_count}",
                "",
                "Simulation Mode",
                f"  {'Enabled' if simulation_mode else 'Disabled'}",
                "",
                "Desktop Ready",
                "========================================",
            ]
        )

        return "\n".join(lines)
