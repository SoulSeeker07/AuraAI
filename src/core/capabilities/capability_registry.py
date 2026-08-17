"""
M19 Universal Capability Registry
=================================
Location: src/core/capabilities/capability_registry.py

Single-source aggregator over domain capability providers (Desktop, Coding, Browser,
Memory, Research, MCP) providing unified schema introspection, governance, and graph validation.
"""

from __future__ import annotations

import logging
import threading

from core.capabilities.models import Capability, PlanGraphError, PlanValidationResult
from core.capabilities.provider import ICapabilityProvider
from core.capabilities.providers.browser_provider import BrowserCapabilityProvider
from core.capabilities.providers.coding_provider import CodingCapabilityProvider
from core.capabilities.providers.desktop_provider import DesktopCapabilityProvider
from core.capabilities.providers.memory_provider import MemoryCapabilityProvider
from core.capabilities.providers.research_provider import ResearchCapabilityProvider
from core.orchestration.autonomy_mode import ActionRisk

logger = logging.getLogger(__name__)


class CapabilityRegistry:
    """
    Singleton universal registry aggregating capabilities across all Aura subsystems.
    """

    _instance: CapabilityRegistry | None = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self, register_defaults: bool = True) -> None:
        self._providers: dict[str, ICapabilityProvider] = {}
        self._direct_capabilities: dict[str, Capability] = {}
        self._registry_lock = threading.RLock()

        if register_defaults:
            self._register_default_providers()

    @classmethod
    def get_instance(cls) -> CapabilityRegistry:
        """Get or initialize the thread-safe singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(register_defaults=True)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (used in test teardown)."""
        with cls._lock:
            cls._instance = None

    def _register_default_providers(self) -> None:
        """Register core domain capability providers."""
        self.register_provider(DesktopCapabilityProvider())
        self.register_provider(CodingCapabilityProvider())
        self.register_provider(BrowserCapabilityProvider())
        self.register_provider(MemoryCapabilityProvider())
        self.register_provider(ResearchCapabilityProvider())

    def register_provider(self, provider: ICapabilityProvider) -> None:
        """Register a domain capability provider."""
        with self._registry_lock:
            self._providers[provider.domain] = provider
            logger.info(f"Registered capability provider for domain '{provider.domain}'")

    def unregister_provider(self, domain: str) -> None:
        """Unregister a domain provider by name."""
        with self._registry_lock:
            if domain in self._providers:
                del self._providers[domain]
                logger.info(f"Unregistered capability provider for domain '{domain}'")

    def register(self, cap: Capability) -> None:
        """Directly register a standalone capability."""
        with self._registry_lock:
            self._direct_capabilities[cap.name] = cap
            logger.info(f"Direct capability registered: {cap.name} [{cap.domain}]")

    def get(self, name: str, require_live: bool = False) -> Capability | None:
        """
        Retrieve a capability by canonical name (e.g. 'power.battery') or alias (e.g. 'desktop:power.battery').
        """
        with self._registry_lock:
            domain_filter = None
            cap_name = name
            if ":" in name:
                domain_filter, cap_name = name.split(":", 1)

            # Check direct registrations first
            if not domain_filter and cap_name in self._direct_capabilities:
                cap = self._direct_capabilities[cap_name]
                if require_live and not cap.is_live:
                    return None
                return cap

            # Search targeted domain provider
            if domain_filter and domain_filter in self._providers:
                cap = self._providers[domain_filter].get_capability(cap_name)
                if cap is not None:
                    if require_live and not cap.is_live:
                        return None
                    return cap

            # Search all registered domain providers
            for provider in self._providers.values():
                if domain_filter and provider.domain != domain_filter:
                    continue
                cap = provider.get_capability(cap_name)
                if cap is not None:
                    if require_live and not cap.is_live:
                        return None
                    return cap

            return None

    def resolve_domain(self, name: str) -> str | None:
        """
        Resolve the owning execution domain for a capability string.
        Returns 'desktop', 'coding', 'browser', 'memory', 'research', 'mcp', or None.
        """
        cap = self.get(name)
        return cap.domain if cap else None

    def list(
        self,
        domain: str | None = None,
        category: str | None = None,
        risk_level: ActionRisk | None = None,
        require_live: bool = False,
    ) -> list[Capability]:
        """List all capabilities matching criteria across providers and direct entries."""
        with self._registry_lock:
            results: list[Capability] = []

            # Direct entries
            for cap in self._direct_capabilities.values():
                if domain and cap.domain != domain:
                    continue
                if category and cap.category != category:
                    continue
                if risk_level and cap.risk_level != risk_level:
                    continue
                if require_live and not cap.is_live:
                    continue
                results.append(cap)

            # Provider entries
            for p_domain, provider in self._providers.items():
                if domain and p_domain != domain:
                    continue
                for cap in provider.list_capabilities():
                    if category and cap.category != category:
                        continue
                    if risk_level and cap.risk_level != risk_level:
                        continue
                    if require_live and not cap.is_live:
                        continue
                    results.append(cap)

            return results

    def discover(self) -> list[Capability]:
        """Discover and return all currently active capabilities across all domains."""
        return self.list()

    def validate_plan_graph(
        self,
        capabilities: list[str] | list[Capability],
        require_live: bool = True,
        require_prerequisites: bool = False,
        strict_fail_closed: bool = False,
    ) -> PlanValidationResult:
        """
        Validate a proposed sequence or graph of capabilities:
        1. Verifies liveness of primary capabilities, requires, and verifies.
        2. Detects cyclic dependencies via topological DFS.
        3. Validates that required prerequisites are satisfied.
        """
        with self._registry_lock:
            # Normalize to Capability objects
            resolved_caps: list[Capability] = []
            errors: list[str] = []
            warnings: list[str] = []
            unwired: list[str] = []
            missing_prereqs: list[tuple[str, str]] = []

            for item in capabilities:
                if isinstance(item, Capability):
                    resolved_caps.append(item)
                else:
                    cap = self.get(str(item))
                    if cap is None:
                        errors.append(f"Unknown capability in plan: '{item}'")
                    else:
                        resolved_caps.append(cap)

            # Check liveness
            if require_live:
                for cap in resolved_caps:
                    if not cap.is_live:
                        err_msg = f"Capability '{cap.name}' is scaffolded (is_live=False) and cannot be executed autonomously."
                        errors.append(err_msg)
                        unwired.append(cap.name)

                    # Also check prerequisite and verification liveness
                    for req in cap.requires:
                        req_cap = self.get(req)
                        if req_cap and not req_cap.is_live:
                            err_msg = f"Prerequisite '{req}' for '{cap.name}' is scaffolded (is_live=False)."
                            errors.append(err_msg)
                            unwired.append(req)

            # Cycle Detection across capability dependencies (including transitive prerequisites)
            graph: dict[str, list[str]] = {}
            to_explore = list(resolved_caps)
            explored_names: set[str] = set()

            while to_explore:
                curr = to_explore.pop()
                if curr.name in explored_names:
                    continue
                explored_names.add(curr.name)
                graph[curr.name] = list(curr.requires)
                for req_name in curr.requires:
                    if req_name not in explored_names:
                        req_obj = self.get(req_name)
                        if req_obj:
                            to_explore.append(req_obj)

            visited: dict[str, int] = {}  # 0: unvisited, 1: visiting, 2: visited

            def dfs(node: str, path: list[str]) -> bool:
                visited[node] = 1
                for neighbor in graph.get(node, []):
                    if neighbor not in graph:
                        continue
                    if visited.get(neighbor, 0) == 1:
                        cycle_path = " -> ".join(path + [neighbor])
                        cycle_err = f"Cyclic capability dependency detected: {cycle_path}"
                        errors.append(cycle_err)
                        if strict_fail_closed:
                            raise PlanGraphError(cycle_err)
                        return False
                    if visited.get(neighbor, 0) == 0:
                        if not dfs(neighbor, path + [neighbor]):
                            return False
                visited[node] = 2
                return True

            for cap in resolved_caps:
                if visited.get(cap.name, 0) == 0:
                    dfs(cap.name, [cap.name])

            # Prerequisite ordering validation
            seen_caps: set[str] = set()
            for cap in resolved_caps:
                for req in cap.requires:
                    if req not in seen_caps:
                        # Prerequisite was not scheduled before this step in the graph
                        missing_prereqs.append((cap.name, req))
                        msg = f"Prerequisite '{req}' for '{cap.name}' should precede it in the plan graph."
                        if require_prerequisites or strict_fail_closed:
                            errors.append(msg)
                        else:
                            warnings.append(msg)
                seen_caps.add(cap.name)


            is_valid = len(errors) == 0
            if strict_fail_closed and not is_valid:
                raise PlanGraphError("; ".join(errors))

            return PlanValidationResult(
                valid=is_valid,
                errors=errors,
                warnings=warnings,
                missing_prerequisites=missing_prereqs,
                unwired_capabilities=unwired,
            )
