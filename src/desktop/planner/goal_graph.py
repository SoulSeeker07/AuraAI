"""
Goal Graph
Maps high-level user intent to required capabilities, risk scores, parallelization tags, and estimated duration.
"""

from dataclasses import dataclass, field

from ..native.capability_registry import CapabilityRegistry, RiskLevel
from .desktop_goal import DesktopGoal


@dataclass
class GoalGraphNode:
    """
    Node in a GoalGraph representing a capability requirement.
    """

    capability: str
    risk_level: RiskLevel
    estimated_duration_ms: float
    parallelizable: bool = True
    requires: list[str] = field(default_factory=list)
    verifies: list[str] = field(default_factory=list)
    rollback_capabilities: list[str] = field(default_factory=list)


class GoalGraph:
    """
    Constructs a dependency and execution graph for a DesktopGoal using CapabilityRegistry metadata.
    """

    def __init__(self, registry: CapabilityRegistry | None = None):
        self.registry = registry or CapabilityRegistry()

    def build_graph(
        self, goal: DesktopGoal, target_capability: str
    ) -> list[GoalGraphNode]:
        """
        Build a list of GoalGraphNode instances representing the goal execution graph.

        Args:
            goal: User DesktopGoal
            target_capability: Capability to execute

        Returns:
            List of GoalGraphNode objects in execution order
        """
        nodes = []
        visited = set()

        def _add_node(cap_name: str, is_primary: bool = False):
            if cap_name in visited:
                return
            visited.add(cap_name)

            desc = self.registry.get(cap_name)
            risk = desc.risk_level if desc else RiskLevel.LOW
            duration = desc.timeout_seconds * 100.0 if desc else 500.0
            parallel = (
                not (
                    desc.is_destructive or risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)
                )
                if desc
                else True
            )

            reqs = desc.requires if desc else []
            vers = desc.verifies if desc else []
            rbs = desc.rollback_capabilities if desc else []

            # Add prerequisite nodes first
            for req in reqs:
                _add_node(req)

            node = GoalGraphNode(
                capability=cap_name,
                risk_level=risk,
                estimated_duration_ms=duration,
                parallelizable=parallel,
                requires=reqs,
                verifies=vers,
                rollback_capabilities=rbs,
            )
            nodes.append(node)

            # Add verification nodes after
            for ver in vers:
                _add_node(ver)

        _add_node(target_capability, is_primary=True)
        return nodes
