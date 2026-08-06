"""
Desktop Execution Engine
Main orchestrator for desktop operations.

Mirrors ResearchEngine exactly:

    ResearchEngine:
        Query → Planner → Search → Reasoner → Report

    DesktopExecutionEngine:
        Goal → Discovery → Registry → Pipeline → Verification → Diagnostics → DesktopResult

Everything in the desktop layer goes through this engine.
Nothing executes outside it.

    engine.execute(goal="Activate VS Code")

is exactly like:

    research_engine.research(query="What is quantum computing?")
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .capability_registry import (
    CapabilityDescriptor,
    CapabilityRegistry,
    PermissionRequired,
    RiskLevel,
)
from .desktop_context import get_desktop_context
from .desktop_result import DesktopResult
from .managers.native_manager_registry import NativeManagerRegistry
from .metrics import MetricsLevel, get_metrics_recorder
from .mock_manager import MockManager
from .native_diagnostics import DiagnosticsStage, NativeDiagnostics
from .native_events import EventType, NativeEvent, get_event_bus

logger = logging.getLogger(__name__)


class ExecutionStage(Enum):
    """Stages of the desktop execution pipeline."""

    GOAL_RECEIVED = "goal_received"
    CAPABILITY_DISCOVERY = "capability_discovery"
    REGISTRY_LOOKUP = "registry_lookup"
    PERMISSION_CHECK = "permission_check"
    PIPELINE_EXECUTE = "pipeline_execute"
    VERIFICATION = "verification"
    CONTEXT_UPDATE = "context_update"
    DIAGNOSTICS = "diagnostics"
    COMPLETE = "complete"


@dataclass
class ExecutionConfig:
    """Configuration for the DesktopExecutionEngine."""

    enabled: bool = True
    default_timeout: float = 30.0
    require_confirmation_for_high_risk: bool = True
    auto_rollback_on_failure: bool = False
    metrics_level: MetricsLevel = MetricsLevel.STANDARD
    enable_diagnostics: bool = True
    enable_verification: bool = True
    enable_context_updates: bool = True
    simulation_mode: bool = False


class DesktopExecutionEngine:
    """
    Main orchestrator for desktop operations.

    This is the ONLY entry point for desktop operations in Aura.
    All desktop actions flow through this engine.

    Mirrors ResearchEngine:
        ResearchEngine.research(query) → ResearchReport
        DesktopExecutionEngine.execute(goal) → DesktopResult
    """

    def __init__(
        self,
        manager: Any | None = None,
        manager_registry: NativeManagerRegistry | None = None,
        registry: CapabilityRegistry | None = None,
        config: ExecutionConfig | None = None,
    ):
        self.manager_registry = manager_registry or NativeManagerRegistry.get_instance()
        if not self.manager_registry.list():
            self.manager_registry.discover("desktop.native.managers")
            if not self.manager_registry.list():
                self.manager_registry.discover("src.desktop.native.managers")

        self.manager = manager or MockManager()
        self.manager_registry.register(self.manager)

        self.registry = registry or CapabilityRegistry()
        self.config = config or ExecutionConfig()
        self.event_bus = get_event_bus()
        self.desktop_context = get_desktop_context()
        self.metrics_recorder = get_metrics_recorder()
        self.diagnostics = NativeDiagnostics()
        self._execution_history: list[DesktopResult] = []

        logger.info(
            f"DesktopExecutionEngine initialized "
            f"(manager={self.manager.name}, "
            f"capabilities={len(self.registry.list_all())})"
        )

    def execute(
        self,
        goal: str,
        capability: str | None = None,
        arguments: dict[str, Any] | None = None,
        **kwargs,
    ) -> DesktopResult:
        """
        Execute a desktop operation.

        This is the ONLY method that should be called to perform desktop operations.
        Exactly like ResearchEngine.research(query).

        Args:
            goal: The user's goal in natural language (e.g., "Activate VS Code")
            capability: Optional explicit capability name (skips discovery)
            arguments: Optional arguments for the capability
            **kwargs: Additional arguments

        Returns:
            DesktopResult with all execution metadata
        """
        if not self.config.enabled:
            fallback_name = self.manager.name if self.manager else "unknown"
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability or "unknown",
                manager=fallback_name,
                error="Engine is disabled",
            )

        arguments = arguments or {}
        arguments.update(kwargs)
        start_time = time.perf_counter()

        logger.info(f"\n{'='*60}")
        logger.info("Desktop Execution Engine")
        logger.info(f"{'='*60}")
        logger.info(f"Goal: {goal}")

        self.diagnostics.start_operation()

        try:
            # Stage 1: Capability Discovery
            if capability is None:
                logger.info("\n--- Stage: Capability Discovery ---")
                capability = self._discover_capability(goal)
                if capability is None:
                    return self._fail(
                        goal,
                        "unknown",
                        start_time,
                        f"No capability found for goal: {goal}",
                    )
                logger.info(f"Discovered: {capability}")

            # Stage 2: Registry Lookup
            logger.info("\n--- Stage: Registry Lookup ---")
            descriptor = self.registry.get(capability)
            if descriptor is None:
                return self._fail(
                    goal,
                    capability,
                    start_time,
                    f"Capability not in registry: {capability}",
                )

            logger.info(f"  Manager: {descriptor.manager}")
            logger.info(f"  Permission: {descriptor.permission.value}")
            logger.info(f"  Risk: {descriptor.risk_level.value}")

            self.diagnostics.start_stage(DiagnosticsStage.PERMISSION)
            self.diagnostics.complete_stage(DiagnosticsStage.PERMISSION)

            # Stage 3: Permission Check
            logger.info("\n--- Stage: Permission Check ---")
            if not self._check_permission(descriptor):
                return self._fail(
                    goal,
                    capability,
                    start_time,
                    f"Permission denied: {descriptor.permission.value}",
                )
            logger.info("  Permission: GRANTED")

            # Stage 4: Pipeline Execute
            logger.info("\n--- Stage: Pipeline Execute ---")
            self.diagnostics.start_stage(DiagnosticsStage.EXECUTION)

            from core.orchestration.world_snapshot import WorldSnapshotProvider

            before_snap = WorldSnapshotProvider().snapshot()

            target_manager = (
                self.manager_registry.resolve(capability)
                or self.manager
                or MockManager()
            )

            if self.config.simulation_mode and (
                descriptor.is_destructive
                or descriptor.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
                or descriptor.permission
                in (PermissionRequired.CONTROL, PermissionRequired.WRITE)
            ):

                logger.info(
                    f"SIMULATION MODE ACTIVE: Bypassing physical execution of '{capability}'"
                )
                result = DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=descriptor.manager,
                    data={
                        "simulated": True,
                        "status": "simulated_execution",
                        "capability": capability,
                    },
                    events=descriptor.events_triggered,
                )
            else:
                result = target_manager.execute(
                    capability=capability,
                    goal=goal,
                    arguments=arguments,
                )

            self.diagnostics.complete_stage(DiagnosticsStage.EXECUTION)

            after_snap = WorldSnapshotProvider().snapshot()

            result.goal = goal
            result.capability = capability
            result.manager = descriptor.manager

            # Stage 5: Real OS Verification
            logger.info("\n--- Stage: Verification ---")
            self.diagnostics.start_stage(DiagnosticsStage.VERIFICATION)

            if self.config.enable_verification:
                from .verification import ActionVerifier

                result.verification = ActionVerifier.verify_action(
                    capability=capability,
                    goal=goal,
                    before_snap=before_snap,
                    after_snap=after_snap,
                    result=result,
                )
                result.success = result.success and result.verification.get(
                    "passed", False
                )
            else:
                result.verification = {
                    "passed": result.success,
                    "skipped": True,
                }

            logger.info(f"  Passed: {result.verification.get('passed', False)}")
            self.diagnostics.complete_stage(DiagnosticsStage.VERIFICATION)

            # Stage 6: Context Update
            logger.info("\n--- Stage: Context Update ---")
            self.diagnostics.start_stage(DiagnosticsStage.CONTEXT)

            if self.config.enable_context_updates and result.success:
                self._update_context(result)
                logger.info(f"  Changes: {len(result.context_changes)}")

            self.diagnostics.complete_stage(DiagnosticsStage.CONTEXT)

            # Stage 7: Events
            logger.info("\n--- Stage: Events ---")
            self.diagnostics.start_stage(DiagnosticsStage.EVENTS)

            for event_type in result.events:
                self._publish_event(event_type, result)
                logger.info(f"  Published: {event_type}")

            self.diagnostics.complete_stage(DiagnosticsStage.EVENTS)

            # Stage 8: Diagnostics
            self.diagnostics.start_stage(DiagnosticsStage.COMPLETE)
            self.diagnostics.complete_stage(DiagnosticsStage.COMPLETE)
            self.diagnostics.complete_operation()

            result.metrics["diagnostics"] = self.diagnostics.to_dict()
            result.metrics["total_duration_ms"] = (
                time.perf_counter() - start_time
            ) * 1000

            self.metrics_recorder.record(
                capability=capability,
                manager=descriptor.manager,
                action=capability,
                category=descriptor.category,
                permission=descriptor.permission,
                events_triggered=result.events,
                success=result.success,
            )

            result.completed_at = time.time()
            self._log_summary(result, start_time)
            self._execution_history.append(result)
            return result

        except Exception as e:
            logger.error(f"Desktop execution failed: {e}", exc_info=True)
            return self._fail(goal, capability or "unknown", start_time, str(e))

    # ==================== Pipeline Stages ====================

    def _discover_capability(self, goal: str) -> str | None:
        """Discover the best capability for a goal using keyword matching."""
        goal_lower = goal.lower()

        capability_keywords = {
            "activate_window": [
                "activate",
                "focus",
                "bring to front",
                "switch to",
                "open window",
                "focus window",
            ],
            "close_window": ["close", "exit", "quit", "end"],
            "list_windows": [
                "list windows",
                "show windows",
                "what windows",
                "open windows",
                "show all open windows",
            ],
            "minimize_window": ["minimize", "hide window", "minimize window"],
            "maximize_window": [
                "maximize",
                "fullscreen",
                "full screen",
                "maximize window",
            ],
            "restore_window": [
                "restore",
                "unminimize",
                "restore window",
                "restore active window",
            ],
            "clipboard.read_text": [
                "read clipboard",
                "get clipboard",
                "paste clipboard",
                "read copied text",
                "read text",
            ],
            "clipboard.write_text": [
                "write clipboard",
                "set clipboard",
                "copy to clipboard",
                "copy text",
            ],
            "clipboard.clear": [
                "clear clipboard",
                "empty clipboard",
                "clear desktop clipboard",
            ],
            "clipboard.read_image": [
                "read clipboard image",
                "get clipboard image",
                "read screenshot",
            ],
            "clipboard.write_image": [
                "write clipboard image",
                "copy image to clipboard",
            ],
            "clipboard.read_files": ["read clipboard files", "get copied files"],
            "clipboard.write_files": [
                "write clipboard files",
                "copy files to clipboard",
            ],
            "clipboard.read_html": ["read clipboard html", "get clipboard html"],
            "clipboard.write_html": ["write clipboard html", "copy html to clipboard"],
            "clipboard.get_formats": [
                "clipboard formats",
                "what is in clipboard",
                "list clipboard formats",
            ],
            "clipboard.has_text": ["clipboard has text", "does clipboard have text"],
            "clipboard.has_image": ["clipboard has image", "does clipboard have image"],
            "clipboard.has_files": ["clipboard has files", "does clipboard have files"],
            "list_displays": [
                "list displays",
                "show displays",
                "monitors",
                "connected monitors",
            ],
            "get_primary_display": ["primary display", "main monitor", "main display"],
            "get_volume": [
                "get volume",
                "read volume",
                "master volume",
                "current volume",
                "check volume",
            ],
            "set_volume": [
                "set volume",
                "change volume",
                "turn up",
                "turn down",
                "adjust volume",
                "lower volume",
                "increase volume",
            ],
            "toggle_mute": ["mute", "unmute", "toggle mute", "mute system sound"],
            "is_muted": ["is muted", "are speakers muted", "check if muted", "muted"],
            "list_microphones": [
                "microphones",
                "list microphones",
                "connected microphones",
            ],
            "list_audio_devices": ["list audio", "audio devices", "sound devices"],
            "list_network_interfaces": [
                "list network",
                "network interfaces",
                "show network adapters",
            ],
            "network.interfaces": ["get network interfaces", "all network adapters"],
            "network.default_interface": [
                "default interface",
                "active adapter",
                "main network",
            ],
            "network.public_ip": [
                "public ip",
                "external ip",
                "my public ip",
                "what is my ip",
                "public ip address",
            ],
            "network.local_ip": [
                "local ip",
                "internal ip",
                "ip address",
                "my ip",
                "internal ip address",
            ],
            "network.gateway": ["default gateway", "gateway address", "router ip"],
            "network.dns": ["dns servers", "dns configuration", "what is my dns"],
            "network.mac": ["mac address", "physical address", "hardware address"],
            "network.hostname": ["hostname", "computer name"],
            "network.connection_type": ["connection type", "am i on wifi"],
            "network.wifi_name": ["wifi name", "ssid", "connected wifi"],
            "network.signal_strength": ["signal strength", "wifi strength"],
            "network.ping": ["ping", "ping google", "ping host"],
            "network.traceroute": ["traceroute", "tracert", "trace route"],
            "network.lookup": ["dns lookup", "nslookup", "domain lookup"],
            "network.port_check": ["port check", "check port", "is port open"],
            "network.internet": [
                "internet connection",
                "check internet",
                "is internet working",
                "internet is slow",
            ],
            "network.speed": ["speed test", "test speed", "internet speed"],
            "network.latency": ["measure latency", "check latency", "ping latency"],
            "network.packet_loss": ["packet loss", "check loss"],
            "network.enable_adapter": ["enable adapter", "enable wifi"],
            "network.disable_adapter": ["disable adapter", "disable wifi"],
            "network.release_ip": ["release ip", "release dhcp"],
            "network.renew_ip": ["renew ip", "renew dhcp"],
            "network.flush_dns": ["flush dns", "clear dns cache"],
            "network.disconnect_wifi": ["disconnect wifi", "disconnect wireless"],
            "network.connect_wifi": ["connect wifi", "connect to wifi"],
            "power.battery": [
                "battery",
                "battery level",
                "battery status",
                "get battery",
                "charge level",
            ],
            "power.ac_status": [
                "ac status",
                "ac power",
                "plugged in",
                "charger status",
            ],
            "power.power_plan": ["power plan", "power scheme", "active power plan"],
            "shutdown": ["shutdown", "turn off", "power off"],
            "restart": ["restart", "reboot"],
            "sleep": ["sleep", "hibernate", "standby"],
            "lock": ["lock", "lock screen", "lock computer"],
            "list_services": ["list services", "show services", "windows services"],
            "start_service": ["start service"],
            "stop_service": ["stop service", "kill service"],
        }

        best_match = None
        best_score = 0

        for cap_name, keywords in capability_keywords.items():
            for keyword in keywords:
                if keyword in goal_lower:
                    score = len(keyword)
                    if score > best_score:
                        best_score = score
                        best_match = cap_name

        if best_match is None:
            for descriptor in self.registry.list_all():
                if descriptor.name in goal_lower:
                    best_match = descriptor.name
                    break

        return best_match

    def _check_permission(self, descriptor: CapabilityDescriptor) -> bool:
        """Check if permission is granted for a capability."""
        if descriptor.risk_level == RiskLevel.CRITICAL:
            logger.warning(f"High-risk operation: {descriptor.name}")
        return True

    def _verify_result(
        self,
        result: DesktopResult,
        descriptor: CapabilityDescriptor,
    ) -> dict[str, Any]:
        """Verify that the execution result is valid."""
        verification = {"passed": True, "method": "generic", "checks": []}

        if result.data is not None:
            verification["checks"].append({"name": "has_data", "passed": True})
        else:
            verification["checks"].append({"name": "has_data", "passed": False})
            verification["passed"] = False

        if descriptor.supports_undo:
            if result.rollback_available:
                verification["checks"].append(
                    {"name": "rollback_available", "passed": True}
                )
            else:
                verification["checks"].append(
                    {
                        "name": "rollback_available",
                        "passed": False,
                        "message": "Capability supports undo but no rollback provided",
                    }
                )
                verification["passed"] = False

        return verification

    def _update_context(self, result: DesktopResult) -> None:
        """Update desktop context with execution results."""
        for key, value in result.context_changes.items():
            if key == "active_window":
                self.desktop_context.set_active_window(value)

    def _publish_event(self, event_type: str, result: DesktopResult) -> None:
        """Publish an event to the event bus."""
        try:
            event_enum = None
            for et in EventType:
                if et.value == event_type:
                    event_enum = et
                    break

            if event_enum:
                event = NativeEvent(
                    event_type=event_enum,
                    source="desktop_execution_engine",
                    data={
                        "capability": result.capability,
                        "goal": result.goal,
                        "success": result.success,
                    },
                )
                self.event_bus.publish(event)
        except Exception as e:
            logger.warning(f"Failed to publish event {event_type}: {e}")

    # ==================== Helpers ====================

    def _fail(
        self, goal: str, capability: str, start_time: float, error: str
    ) -> DesktopResult:
        """Create a failure result."""
        result = DesktopResult.create_failure(
            goal=goal,
            capability=capability,
            manager=self.manager.name,
            error=error,
            metrics={"total_duration_ms": (time.perf_counter() - start_time) * 1000},
        )
        result.completed_at = time.time()
        self._execution_history.append(result)
        return result

    def _log_summary(self, result: DesktopResult, start_time: float) -> None:
        """Log execution summary."""
        duration = (time.perf_counter() - start_time) * 1000
        status = "✓ SUCCESS" if result.success else "✗ FAILURE"

        logger.info(f"\n{'='*60}")
        logger.info("Desktop Execution Complete")
        logger.info(f"{'='*60}")
        logger.info(f"Status: {status}")
        logger.info(f"Goal: {result.goal}")
        logger.info(f"Capability: {result.capability}")
        logger.info(f"Manager: {result.manager}")
        logger.info(f"Duration: {duration:.2f}ms")
        logger.info(f"Events: {result.events}")
        logger.info(f"Verification: {result.verification.get('passed', 'N/A')}")
        logger.info(f"Rollback available: {result.rollback_available}")
        logger.info(f"Context changes: {len(result.context_changes)}")
        if result.warnings:
            logger.info(f"Warnings: {result.warnings}")
        if result.error:
            logger.info(f"Error: {result.error}")
        logger.info(f"{'='*60}\n")

    # ==================== Introspection ====================

    def get_execution_history(self) -> list[DesktopResult]:
        return self._execution_history.copy()

    def get_last_result(self) -> DesktopResult | None:
        if not self._execution_history:
            return None
        return self._execution_history[-1]

    def get_execution_count(self) -> int:
        return len(self._execution_history)

    def get_success_rate(self) -> float:
        if not self._execution_history:
            return 0.0
        successes = sum(1 for r in self._execution_history if r.success)
        return successes / len(self._execution_history)

    def get_diagnostics_report(self) -> str:
        return self.diagnostics.to_detailed_report()

    def get_boot_report(self) -> str:
        """Get human-readable boot report for Aura Desktop."""
        return self.manager_registry.get_boot_report(
            simulation_mode=self.config.simulation_mode
        )

    def reset(self) -> None:

        self._execution_history.clear()
        self.diagnostics = NativeDiagnostics()
        if hasattr(self.manager, "reset"):
            self.manager.reset()


# ==================== Singleton ====================

_engine: DesktopExecutionEngine | None = None


def get_desktop_execution_engine(
    manager: Any | None = None,
    registry: CapabilityRegistry | None = None,
    config: ExecutionConfig | None = None,
    engine_instance: DesktopExecutionEngine | None = None,
) -> DesktopExecutionEngine:
    """Get or create the global DesktopExecutionEngine singleton."""
    global _engine
    if _engine is None:
        _engine = engine_instance or DesktopExecutionEngine(
            manager=manager, registry=registry, config=config
        )
    return _engine


def reset_desktop_execution_engine() -> None:
    """Reset the global DesktopExecutionEngine."""
    global _engine
    _engine = None
