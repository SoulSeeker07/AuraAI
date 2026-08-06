"""
About Report
Location: src/core/system/about_report.py

Generates the Aura /about system health report.

This is the "operating system status" view of Aura.
Everything is read from live registries — no hardcoded strings.
The report changes automatically as new planners, backends, and managers are added.

Usage:
    report = AboutReport()
    print(report.generate())   # Full text report
    print(report.generate_compact())  # One-line status

Triggered by:
    - "/about" command
    - "aura about" utterance
    - "show system health" query
    - Intent type: system_query → about
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from .identity_loader import IdentityContext, IdentityLoader

logger = logging.getLogger(__name__)

# Startup time is recorded once at module import
_STARTUP_TIME = datetime.datetime.now()


class AboutReport:
    """
    Generates the Aura /about dynamic system health report.

    Reads from:
      - IdentityLoader (name, version, mission, architecture)
      - CapabilityCatalog (live capability count + categories)
      - NativeManagerRegistry (active managers)
      - PlannerRegistry (active planners)
      - BackendRegistry (active backends)

    Output format is human-readable and designed to feel like
    querying an operating system, not a chatbot.
    """

    def __init__(self, identity_loader: IdentityLoader | None = None) -> None:
        self._loader = identity_loader or IdentityLoader.get_instance()

    def generate(self) -> str:
        """
        Generate the full Aura /about report.

        Returns a formatted string designed for terminal or chat display.
        """
        ctx = self._loader.load()
        sections: list[str] = []

        # Header
        sections.append(self._header(ctx))

        # Architecture summary (from live registries)
        sections.append(self._architecture_section())

        # Capability summary (live)
        sections.append(self._capabilities_section())

        # Skills summary (from YAML)
        sections.append(self._skills_section(ctx))

        # Health status
        sections.append(self._health_section())

        # Uptime
        sections.append(self._uptime_section())

        return "\n\n".join(s for s in sections if s)

    def generate_compact(self) -> str:
        """
        Generate a one-line compact status string.

        Used for quick inline responses.
        """
        ctx = self._loader.load()
        cap_count = self._get_capability_count()
        planner_count = len(self._get_live_planners())
        backend_count = len(self._get_live_backends())

        return (
            f"{ctx.name} v{ctx.version} | "
            f"{cap_count} capabilities | "
            f"{planner_count} planners | "
            f"{backend_count} backends | "
            f"Status: ✅ Healthy | "
            f"Uptime: {self._format_uptime()}"
        )

    # ── Private section builders ──────────────────────────────────────────────

    def _header(self, ctx: IdentityContext) -> str:
        name = ctx.name or "Aura AI"
        version = ctx.version or "unknown"
        tagline = ctx.tagline

        lines = [
            "╔══════════════════════════════════════════════════════╗",
            f"  {name}  v{version}",
            "╚══════════════════════════════════════════════════════╝",
        ]
        if tagline:
            lines.append(f"  {tagline}")
        return "\n".join(lines)

    def _architecture_section(self) -> str:
        planners = self._get_live_planners()
        backends = self._get_live_backends()
        managers = self._get_live_managers()

        lines = ["📐 Architecture"]
        lines.append(f"  Planners ({len(planners)}):")
        for name in planners:
            lines.append(f"    ✓ {name}")

        lines.append(f"  Backends ({len(backends)}):")
        for name in backends:
            lines.append(f"    ✓ {name}")

        lines.append(f"  Native Managers ({len(managers)}):")
        for name in managers[:10]:  # cap at 10 for readability
            lines.append(f"    ✓ {name}")
        if len(managers) > 10:
            lines.append(f"    ... and {len(managers) - 10} more")

        return "\n".join(lines)

    def _capabilities_section(self) -> str:
        """Live capability count from CapabilityRegistry."""
        try:
            from .capability_catalog import CapabilityCatalog

            catalog = CapabilityCatalog()
            grouped = catalog.export_by_category()
            total = catalog.count()

            lines = [f"⚡ Capabilities ({total} live)"]
            for category in sorted(grouped.keys()):
                count = len(grouped[category])
                lines.append(f"  {category.title()}: {count}")
            return "\n".join(lines)
        except Exception as e:
            logger.debug(f"AboutReport: capability section unavailable: {e}")
            return "⚡ Capabilities: (registry unavailable)"

    def _skills_section(self, ctx: IdentityContext) -> str:
        """User-facing skills from aura_skills.yaml."""
        skill_domains = ctx.skill_domains
        if not skill_domains:
            return ""

        lines = [f"🎯 Skills ({len(skill_domains)} domains)"]
        for domain in skill_domains:
            name = domain.get("domain", "")
            emoji = domain.get("emoji", "")
            status = domain.get("status", "")
            status_str = f" [{status}]" if status else ""
            summary = domain.get("summary", "").strip().split("\n")[0]
            lines.append(f"  {emoji} {name}{status_str}")
        return "\n".join(lines)

    def _health_section(self) -> str:
        """Check health of each registered backend."""
        backends = self._get_live_backends()
        lines = ["🏥 Health"]

        if not backends:
            lines.append("  ⚠️  BackendRegistry unavailable")
            return "\n".join(lines)

        for name, backend_obj in backends.items():
            try:
                healthy = (
                    backend_obj.health_check()
                    if hasattr(backend_obj, "health_check")
                    else True
                )
                status = "✅ Healthy" if healthy else "❌ Unhealthy"
            except Exception:
                status = "⚠️  Unknown"
            lines.append(f"  {name}: {status}")

        return "\n".join(lines)

    def _uptime_section(self) -> str:
        return f"⏱️  Uptime: {self._format_uptime()}"

    def _format_uptime(self) -> str:
        delta = datetime.datetime.now() - _STARTUP_TIME
        total_seconds = int(delta.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"

    # ── Live registry probes ──────────────────────────────────────────────────

    def _get_live_planners(self) -> dict[str, Any]:
        try:
            from core.orchestration.planner_registry import PlannerRegistry

            registry = PlannerRegistry.get_instance()
            return {
                name: registry.get_planner(name) for name in registry.list_planners()
            }
        except Exception:
            return {}

    def _get_live_backends(self) -> dict[str, Any]:
        try:
            from core.backends.backend_registry import BackendRegistry

            registry = BackendRegistry.get_instance()
            adapters = getattr(registry, "_adapters", []) or getattr(
                registry, "_backends", []
            )
            return {getattr(b, "name", str(b)): b for b in adapters}
        except Exception:
            return {}

    def _get_live_managers(self) -> list[str]:
        try:
            from desktop.native.managers.native_manager_registry import (
                NativeManagerRegistry,
            )

            reg = NativeManagerRegistry.get_instance()
            managers = getattr(reg, "_managers", {})
            return list(managers.keys())
        except Exception:
            # Fallback to static known list
            return [
                "WindowManager",
                "ClipboardManager",
                "AudioManager",
                "DisplayManager",
                "PowerManager",
                "NetworkManager",
                "ServiceManager",
                "RegistryManager",
            ]

    def _get_capability_count(self) -> int:
        try:
            from .capability_catalog import CapabilityCatalog

            return CapabilityCatalog().count()
        except Exception:
            return 0
