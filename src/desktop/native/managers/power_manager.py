"""
Power Manager for Native Windows Layer

Manages Windows power operations (battery, power plan, lock, sleep, hibernate, shutdown, restart) via PowerAdapter abstraction.
All cross-cutting concerns (permissions, verification, rollback, diagnostics) are
handled by the execution pipeline.

This manager ONLY contains Windows-specific code via PowerAdapters.
"""

import logging
from typing import Any

from ..adapters.power_adapter import PowerAdapter, PowerAdapterFactory
from ..desktop_result import DesktopResult
from .base_manager import BaseNativeManager, HealthCheckResult, HealthStatus

logger = logging.getLogger(__name__)


class PowerManager(BaseNativeManager):
    """
    Manages Windows power operations using PowerAdapter abstraction.

    Capabilities:
    - power.battery: Get battery level and charging status
    - power.ac_status: Get AC power line status
    - power.power_plan: Get active power plan
    - power.sleep_supported: Check if sleep mode is supported
    - power.hibernate_supported: Check if hibernate mode is supported
    - power.lock / lock: Lock workstation screen
    - power.sleep / sleep: Put system to sleep
    - power.hibernate: Put system to hibernate
    - power.shutdown / shutdown: Shutdown computer
    - power.restart / restart: Restart computer
    - power.logoff / logoff: Logoff current user
    """

    NAME = "power"
    VERSION = "1.0"
    PRIORITY = 20
    DEPENDENCIES = ["wmi", "ctypes"]

    def __init__(self, adapter: PowerAdapter | None = None):
        """Initialize power manager with optional injected adapter."""
        super().__init__()
        self._adapter = adapter

    @property
    def adapter(self) -> PowerAdapter:
        """Get or initialize active power adapter."""
        if self._adapter is None:
            self._adapter = PowerAdapterFactory.get_adapter()
        return self._adapter

    @property
    def name(self) -> str:
        """Get manager name."""
        return self.NAME

    @property
    def capabilities(self) -> list[str]:
        """Get list of capabilities supported by PowerManager."""
        return [
            "shutdown",
            "restart",
            "sleep",
            "lock",
            "logoff",
            "power.battery",
            "power.ac_status",
            "power.power_plan",
            "power.sleep_supported",
            "power.hibernate_supported",
            "power.lock",
            "power.sleep",
            "power.hibernate",
            "power.shutdown",
            "power.restart",
            "power.logoff",
        ]

    def health_check(self) -> HealthCheckResult:
        """
        Perform health check on PowerManager and active adapter.

        Returns:
            HealthCheckResult with active adapter status.
        """
        active_adapter = self.adapter
        missing = []
        if active_adapter.name == "dummy":
            missing.append("wmi")
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.HEALTHY

        return HealthCheckResult(
            manager_name=self.name,
            status=status,
            missing_dependencies=missing,
            available_fallbacks=[active_adapter.name],
            total_capabilities=len(self.capabilities),
            available_capabilities=len(self.capabilities),
            details={"active_adapter": active_adapter.name},
        )

    def execute(
        self,
        capability: str,
        goal: str = "",
        arguments: dict[str, Any] | None = None,
        **kwargs,
    ) -> DesktopResult:
        """
        Execute native power operation for the given capability.

        Returns:
            DesktopResult with execution data or failure message.
        """
        arguments = arguments or {}
        arguments.update(kwargs)

        try:
            logger.info(f"PowerManager executing capability: {capability}")
            cap_clean = capability.lower()

            if cap_clean == "power.battery":
                return self._handle_get_battery(goal=goal, capability=capability)

            elif cap_clean == "power.ac_status":
                return self._handle_get_ac_status(goal=goal, capability=capability)

            elif cap_clean == "power.power_plan":
                return self._handle_get_power_plan(goal=goal, capability=capability)

            elif cap_clean == "power.sleep_supported":
                return self._handle_sleep_supported(goal=goal, capability=capability)

            elif cap_clean == "power.hibernate_supported":
                return self._handle_hibernate_supported(
                    goal=goal, capability=capability
                )

            elif cap_clean in ("lock", "power.lock"):
                return self._handle_lock(goal=goal, capability=capability)

            elif cap_clean in ("sleep", "power.sleep"):
                return self._handle_sleep(goal=goal, capability=capability)

            elif cap_clean in ("hibernate", "power.hibernate"):
                return self._handle_hibernate(goal=goal, capability=capability)

            elif cap_clean in ("shutdown", "power.shutdown"):
                return self._handle_shutdown(
                    goal=goal, capability=capability, arguments=arguments
                )

            elif cap_clean in ("restart", "power.restart"):
                return self._handle_restart(
                    goal=goal, capability=capability, arguments=arguments
                )

            elif cap_clean in ("logoff", "power.logoff"):
                return self._handle_logoff(
                    goal=goal, capability=capability, arguments=arguments
                )

            else:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"Capability '{capability}' not supported by PowerManager",
                )

        except Exception as e:
            logger.error(f"PowerManager execution failed: {e}", exc_info=True)
            return DesktopResult.create_failure(
                goal=goal, capability=capability, manager=self.name, error=str(e)
            )

    # ==================== Handler Implementations ====================

    def _handle_get_battery(self, goal: str, capability: str) -> DesktopResult:
        batt_data = self.adapter.get_battery_status()
        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name, data=batt_data
        )

    def _handle_get_ac_status(self, goal: str, capability: str) -> DesktopResult:
        ac_data = self.adapter.get_ac_status()
        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name, data=ac_data
        )

    def _handle_get_power_plan(self, goal: str, capability: str) -> DesktopResult:
        plan_data = self.adapter.get_power_plan()
        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name, data=plan_data
        )

    def _handle_sleep_supported(self, goal: str, capability: str) -> DesktopResult:
        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={"supported": True, "backend": self.adapter.name},
        )

    def _handle_hibernate_supported(self, goal: str, capability: str) -> DesktopResult:
        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={"supported": True, "backend": self.adapter.name},
        )

    def _handle_lock(self, goal: str, capability: str) -> DesktopResult:
        ok = self.adapter.lock_workstation()
        if ok:
            return DesktopResult.create_success(
                goal=goal,
                capability=capability,
                manager=self.name,
                data={"status": "locked", "backend": self.adapter.name},
                events=["workstation_locked"],
            )
        else:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="Failed to lock workstation",
            )

    def _handle_sleep(self, goal: str, capability: str) -> DesktopResult:
        ok = self.adapter.sleep()
        if ok:
            return DesktopResult.create_success(
                goal=goal,
                capability=capability,
                manager=self.name,
                data={"status": "sleep_initiated", "backend": self.adapter.name},
                events=["system_sleep"],
            )
        else:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="Failed to put system to sleep",
            )

    def _handle_hibernate(self, goal: str, capability: str) -> DesktopResult:
        ok = self.adapter.hibernate()
        if ok:
            return DesktopResult.create_success(
                goal=goal,
                capability=capability,
                manager=self.name,
                data={"status": "hibernate_initiated", "backend": self.adapter.name},
                events=["system_hibernate"],
            )
        else:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="Failed to hibernate system",
            )

    def _handle_shutdown(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        force = bool(arguments.get("force", False))
        timeout = int(arguments.get("timeout", 0))

        ok = self.adapter.shutdown(force=force, timeout_sec=timeout)
        if ok:
            return DesktopResult.create_success(
                goal=goal,
                capability=capability,
                manager=self.name,
                data={
                    "status": "shutdown_initiated",
                    "force": force,
                    "timeout": timeout,
                    "backend": self.adapter.name,
                },
                events=["system_shutdown"],
            )
        else:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="Failed to initiate shutdown",
            )

    def _handle_restart(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        force = bool(arguments.get("force", False))
        timeout = int(arguments.get("timeout", 0))

        ok = self.adapter.restart(force=force, timeout_sec=timeout)
        if ok:
            return DesktopResult.create_success(
                goal=goal,
                capability=capability,
                manager=self.name,
                data={
                    "status": "restart_initiated",
                    "force": force,
                    "timeout": timeout,
                    "backend": self.adapter.name,
                },
                events=["system_restart"],
            )
        else:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="Failed to initiate restart",
            )

    def _handle_logoff(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        force = bool(arguments.get("force", False))

        ok = self.adapter.logoff(force=force)
        if ok:
            return DesktopResult.create_success(
                goal=goal,
                capability=capability,
                manager=self.name,
                data={
                    "status": "logoff_initiated",
                    "force": force,
                    "backend": self.adapter.name,
                },
                events=["system_logoff"],
            )
        else:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="Failed to logoff user",
            )
