"""
Desktop Permission Manager

Permission gatekeeper for NativeManager. Every operation exposed by
NativeManager routes through check_permission() before touching Win32.

Risk model:
- SAFE       -> auto-approved (read-only operations, e.g. list_windows)
- MODERATE   -> auto-approved by default, but a confirmation_handler can be
                supplied to prompt the user (e.g. activate_window, set_volume)
- DANGEROUS  -> denied by default unless a confirmation_handler explicitly
                approves it (e.g. shutdown, delete_registry_key)

This mirrors the pattern already used in src/execution/permission_manager.py
and src/agents/permission_manager.py, adapted to NativeCapability instead of
PermissionAction, and to the (operation_name, capability=...) call signature
that NativeManager already uses.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk level for a native capability."""
    SAFE = "safe"
    MODERATE = "moderate"
    DANGEROUS = "dangerous"


# Default risk classification, keyed by NativeCapability.value (a plain string).
# Anything not listed here falls back to MODERATE.
DEFAULT_CAPABILITY_RISK: Dict[str, RiskLevel] = {
    # Window management - read-only
    "list_windows": RiskLevel.SAFE,
    "get_window": RiskLevel.SAFE,
    # Window management - reversible
    "activate_window": RiskLevel.MODERATE,
    "close_window": RiskLevel.MODERATE,
    "move_window": RiskLevel.MODERATE,
    "resize_window": RiskLevel.MODERATE,
    "minimize_window": RiskLevel.MODERATE,
    "maximize_window": RiskLevel.MODERATE,
    "restore_window": RiskLevel.MODERATE,
    # Clipboard
    "read_clipboard": RiskLevel.SAFE,
    "write_clipboard": RiskLevel.MODERATE,
    "clear_clipboard": RiskLevel.MODERATE,
    # Display
    "list_displays": RiskLevel.SAFE,
    "get_primary_display": RiskLevel.SAFE,
    "get_display": RiskLevel.SAFE,
    # Power
    "shutdown": RiskLevel.DANGEROUS,
    "restart": RiskLevel.DANGEROUS,
    "sleep": RiskLevel.MODERATE,
    "hibernate": RiskLevel.MODERATE,
    "lock": RiskLevel.SAFE,
    "logoff": RiskLevel.DANGEROUS,
    # Audio
    "list_audio_devices": RiskLevel.SAFE,
    "get_audio_device": RiskLevel.SAFE,
    "set_volume": RiskLevel.MODERATE,
    "toggle_mute": RiskLevel.MODERATE,
    # Network
    "list_network_interfaces": RiskLevel.SAFE,
    "get_network_interface": RiskLevel.SAFE,
    # Registry
    "read_registry_key": RiskLevel.MODERATE,
    "write_registry_key": RiskLevel.DANGEROUS,
    "delete_registry_key": RiskLevel.DANGEROUS,
    # Services
    "list_services": RiskLevel.SAFE,
    "start_service": RiskLevel.DANGEROUS,
    "stop_service": RiskLevel.DANGEROUS,
    "restart_service": RiskLevel.DANGEROUS,
}


class PermissionManager:
    """
    Permission gatekeeper used by NativeManager.

    Usage (matches native_manager.py exactly):
        pm = PermissionManager()
        pm.subscribe(some_listener)
        pm.check_permission("desktop.activate_window", capability=NativeCapability.ACTIVATE_WINDOW)
    """

    def __init__(
        self,
        allow_all: bool = False,
        confirmation_handler: Optional[Callable[[str, Any, RiskLevel], bool]] = None,
    ) -> None:
        """
        Args:
            allow_all: If True, every check passes automatically. Intended for
                       tests, mocks, or explicitly trusted environments.
            confirmation_handler: Optional callback invoked for MODERATE/
                       DANGEROUS operations to request explicit approval.
                       Signature: (operation_name, capability, risk_level) -> bool.
                       If omitted, MODERATE operations auto-approve and
                       DANGEROUS operations are denied by default (safe default).
        """
        self.allow_all = allow_all
        self._confirmation_handler = confirmation_handler
        self._listeners: List[Callable[[Any], None]] = []

        logger.info("Desktop PermissionManager initialized (allow_all=%s)", allow_all)

    # -- Subscription -----------------------------------------------------

    def subscribe(self, listener: Callable[[Any], None]) -> None:
        """Register a listener to be notified of permission-check events."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[[Any], None]) -> None:
        """Remove a previously registered listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify(self, event: Dict[str, Any]) -> None:
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("Error in permission listener: %s", exc)

    # -- Permission checking ------------------------------------------------

    def _risk_for(self, capability: Any) -> RiskLevel:
        cap_name = getattr(capability, "value", capability)
        return DEFAULT_CAPABILITY_RISK.get(cap_name, RiskLevel.MODERATE)

    def check_permission(
        self,
        operation: str,
        capability: Any = None,
        resource: Optional[str] = None,
    ) -> bool:
        """
        Check whether an operation is permitted to proceed.

        Args:
            operation: Dotted operation name, e.g. "desktop.activate_window".
            capability: The NativeCapability (or its string value) being checked.
            resource: Optional resource identifier (hwnd, registry path, etc.)

        Returns:
            True if the operation may proceed, False otherwise.
            (NativeManager treats False as grounds to raise PermissionDeniedError.)
        """
        if self.allow_all:
            granted = True
        else:
            risk = self._risk_for(capability)
            if risk == RiskLevel.SAFE:
                granted = True
            elif risk == RiskLevel.MODERATE:
                granted = (
                    self._confirmation_handler(operation, capability, risk)
                    if self._confirmation_handler
                    else True
                )
            else:  # DANGEROUS
                granted = (
                    self._confirmation_handler(operation, capability, risk)
                    if self._confirmation_handler
                    else False
                )

        self._notify({
            "operation": operation,
            "capability": capability,
            "resource": resource,
            "granted": granted,
        })

        if not granted:
            logger.info("Permission denied: %s", operation)

        return granted

    def set_confirmation_handler(
        self, handler: Callable[[str, Any, RiskLevel], bool]
    ) -> None:
        """Set or replace the handler used to confirm MODERATE/DANGEROUS operations."""
        self._confirmation_handler = handler