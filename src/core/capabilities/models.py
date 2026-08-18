"""
M19 Universal Capability Models
===============================
Location: src/core/capabilities/models.py

Defines the canonical, cross-domain Capability dataclass, plan validation results,
and graph error types used by the MasterOrchestrator and all domain adapters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.orchestration.autonomy_mode import ActionRisk


class PlanGraphError(Exception):
    """Raised when task graph dependency validation fails (e.g. cyclic dependencies, missing prerequisites)."""
    pass


@dataclass
class PlanValidationResult:
    """Result of validating a task graph against the capability registry."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    missing_prerequisites: list[tuple[str, str]] = field(default_factory=list)  # (task_id, missing_cap)
    unwired_capabilities: list[str] = field(default_factory=list)


@dataclass
class Capability:
    """
    Standardized, cross-domain metadata contract for an executable capability.

    Bridges Desktop Native, Browser, Coding, Memory, Research, and MCP domains
    with uniform schema introspection, governance, and planning dependency graphs.
    """

    # Core Identity & Domain
    name: str  # e.g. "power.battery", "code.analyze", "browser.navigate"
    domain: str = "custom"  # "desktop", "coding", "browser", "memory", "research", "mcp", "custom"
    description: str = ""
    category: str = "general"
    version: str = "1.0"


    # Typed I/O Contracts (JSONSchema)
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)

    # Governance & Autonomy Risk
    risk_level: ActionRisk = ActionRisk.LOW
    permissions: list[str] = field(default_factory=list)
    is_destructive: bool = False
    requires_confirmation: bool = False
    requires_admin: bool = False

    # Execution Lifecycle
    execution_backend: str = "local"  # "desktop_native", "coding_backend", "browser_playwright", "memory_engine", "research_engine", "mcp"
    timeout_seconds: int = 30
    supports_undo: bool = False
    rollback_description: str | None = None

    # Liveness & Availability Gating
    is_live: bool = True  # True if physically wired to an operational backend; False if scaffolded/contract-only
    availability: str = "online"  # "online", "scaffolded", "offline"

    # Planning Dependency Graph (First-Class Cross-Domain Graph Attributes)
    requires: list[str] = field(default_factory=list)  # Prerequisite capability names
    verifies: list[str] = field(default_factory=list)  # Post-condition verification capability names
    rollback_capabilities: list[str] = field(default_factory=list)  # Capabilities used for undo

    # Metadata & Tags
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def fqn(self) -> str:
        """Fully qualified namespaced identifier e.g. 'desktop:power.battery'."""
        return f"{self.domain}:{self.name}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize capability descriptor to dictionary."""
        return {
            "name": self.name,
            "domain": self.domain,
            "fqn": self.fqn,
            "description": self.description,
            "category": self.category,
            "version": self.version,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "risk_level": self.risk_level.value if isinstance(self.risk_level, ActionRisk) else str(self.risk_level),
            "permissions": self.permissions,
            "is_destructive": self.is_destructive,
            "requires_confirmation": self.requires_confirmation,
            "requires_admin": self.requires_admin,
            "execution_backend": self.execution_backend,
            "timeout_seconds": self.timeout_seconds,
            "supports_undo": self.supports_undo,
            "rollback_description": self.rollback_description,
            "is_live": self.is_live,
            "availability": self.availability,
            "requires": self.requires,
            "verifies": self.verifies,
            "rollback_capabilities": self.rollback_capabilities,
            "tags": self.tags,
            "metadata": self.metadata,
        }
