"""
Command Catalog
Location: src/core/system/command_catalog.py

Exports the live command surface from NativeManagerRegistry.

This provides a human-readable summary of what actions each manager
exposes, so Aura can answer "what can you do?" with real data.

Usage:
    catalog = CommandCatalog()
    text = catalog.export_as_text()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ManagerSummary:
    """Summary of a single NativeManager's capabilities."""

    name: str
    description: str = ""
    actions: list[str] = field(default_factory=list)

    def to_text_block(self) -> str:
        """Text representation for LLM context."""
        lines = [f"{self.name}:"]
        for action in self.actions[:12]:  # cap at 12 for brevity
            lines.append(f"  • {action}")
        if len(self.actions) > 12:
            lines.append(f"  ... and {len(self.actions) - 12} more")
        return "\n".join(lines)


class CommandCatalog:
    """
    Exports available commands from NativeManagerRegistry.

    Reads the actual manager registry at runtime so newly added managers
    (e.g. BluetoothManager, TouchpadManager) automatically appear.

    Fallback: if NativeManagerRegistry is unavailable, uses a static
    minimal summary derived from known managers.
    """

    # Static fallback listing known managers if registry unavailable
    _STATIC_FALLBACK: dict[str, list[str]] = {
        "WindowManager": [
            "list_windows",
            "get_window",
            "activate_window",
            "close_window",
            "minimize_window",
            "maximize_window",
            "restore_window",
            "resize_window",
            "move_window",
            "launch_app",
            "kill_process",
        ],
        "ClipboardManager": [
            "get_clipboard",
            "set_clipboard",
            "clear_clipboard",
            "get_clipboard_history",
            "monitor_clipboard",
        ],
        "AudioManager": [
            "get_volume",
            "set_volume",
            "volume_up",
            "volume_down",
            "mute",
            "unmute",
            "list_audio_devices",
        ],
        "DisplayManager": [
            "get_display_info",
            "set_brightness",
            "list_monitors",
            "set_resolution",
        ],
        "PowerManager": [
            "get_battery_status",
            "lock",
            "sleep",
            "restart",
            "shutdown",
            "get_power_plan",
        ],
        "NetworkManager": [
            "get_network_status",
            "get_ip_address",
            "enable_wifi",
            "disable_wifi",
            "list_adapters",
            "ping",
            "dns_lookup",
            "get_firewall_status",
        ],
        "ServiceManager": [
            "list_services",
            "start_service",
            "stop_service",
            "get_service_status",
        ],
        "RegistryManager": [
            "read_registry_key",
            "write_registry_key",
            "list_registry_keys",
        ],
    }

    def __init__(self) -> None:
        self._registry: Any | None = None
        self._registry_loaded = False

    def _get_registry(self) -> Any | None:
        """Lazy-load NativeManagerRegistry."""
        if not self._registry_loaded:
            try:
                from desktop.native.managers.native_manager_registry import (
                    NativeManagerRegistry,
                )

                self._registry = NativeManagerRegistry.get_instance()
                self._registry_loaded = True
                logger.debug(
                    "CommandCatalog: NativeManagerRegistry loaded successfully."
                )
            except ImportError as e:
                logger.warning(
                    f"CommandCatalog: NativeManagerRegistry not available: {e}"
                )
                self._registry_loaded = True
            except Exception as e:
                logger.error(
                    f"CommandCatalog: error loading NativeManagerRegistry: {e}"
                )
                self._registry_loaded = True
        return self._registry

    def export_managers(self) -> list[ManagerSummary]:
        """
        Export a summary of each registered NativeManager.

        Falls back to _STATIC_FALLBACK if registry unavailable.
        """
        registry = self._get_registry()

        if registry is None:
            # Use static fallback
            return [
                ManagerSummary(name=name, actions=actions)
                for name, actions in self._STATIC_FALLBACK.items()
            ]

        summaries: list[ManagerSummary] = []
        try:
            # NativeManagerRegistry stores managers in _managers dict
            managers_dict: dict[str, Any] = getattr(registry, "_managers", {})
            for manager_name, manager_obj in managers_dict.items():
                # Extract public method names as "actions"
                actions = [
                    m
                    for m in dir(manager_obj)
                    if not m.startswith("_")
                    and callable(getattr(manager_obj, m, None))
                    and m not in ("register", "unregister", "health_check", "describe")
                ]
                description = getattr(manager_obj, "__doc__", "") or ""
                # Take first line of docstring
                description = description.strip().split("\n")[0] if description else ""
                summaries.append(
                    ManagerSummary(
                        name=manager_name,
                        description=description,
                        actions=actions,
                    )
                )

            if not summaries:
                # Registry exists but is empty — use static fallback
                return [
                    ManagerSummary(name=name, actions=actions)
                    for name, actions in self._STATIC_FALLBACK.items()
                ]

        except Exception as e:
            logger.error(f"CommandCatalog: error iterating managers: {e}")
            return [
                ManagerSummary(name=name, actions=actions)
                for name, actions in self._STATIC_FALLBACK.items()
            ]

        logger.debug(
            f"CommandCatalog.export_managers(): {len(summaries)} managers exported."
        )
        return summaries

    def export_as_text(self) -> str:
        """
        Export all manager commands as a concise LLM-ready text block.

        Format:
            === NATIVE MANAGER COMMAND SURFACE ===
            WindowManager:
              • list_windows
              • activate_window
              ...
        """
        summaries = self.export_managers()
        if not summaries:
            return "(NativeManagerRegistry unavailable — no manager commands exported)"

        lines: list[str] = ["=== NATIVE MANAGER COMMAND SURFACE ==="]
        for summary in summaries:
            lines.append("")
            lines.append(summary.to_text_block())

        total_actions = sum(len(s.actions) for s in summaries)
        lines.append(
            f"\nTotal: {len(summaries)} managers, ~{total_actions} native actions available."
        )
        return "\n".join(lines)

    def list_manager_names(self) -> list[str]:
        """Return list of all registered manager names."""
        return [s.name for s in self.export_managers()]
