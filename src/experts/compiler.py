"""
PlanDAG to TaskGraph Compiler (Milestone 25)
Location: src/experts/compiler.py

Translates structured Domain Expert PlanDAG reasoning graphs into
executable MasterOrchestrator TaskGraph dependency trees with:
1. Universal CapabilityRegistry domain -> PlannerRole resolution
2. Deterministic 1:1 artifact dependency wiring
3. Causal context and risk classification propagation
4. Strict fail-loud validation against cycles, unknown capabilities, and dangling dependencies.
"""

from __future__ import annotations

import logging
from typing import Any

from core.capabilities.capability_registry import CapabilityRegistry
from core.orchestration.task_decomposer import PlannerRole, SubTask, TaskGraph
from .models import PlanDAG, PlanNode

logger = logging.getLogger(__name__)

# Domain to PlannerRole mapping table
DOMAIN_ROLE_MAP: dict[str, PlannerRole] = {
    "coding": PlannerRole.CODING,
    "browser": PlannerRole.BROWSER,
    "research": PlannerRole.RESEARCH,
    "memory": PlannerRole.MEMORY,
    "desktop": PlannerRole.DESKTOP,
    "daemon": PlannerRole.DESKTOP,
    "multimodal": PlannerRole.DESKTOP,
}


class PlanDAGCompiler:
    """
    Automated compiler bridging pure domain expert reasoning (PlanDAG)
    with the Cognitive Orchestration Layer (TaskGraph).
    """

    def __init__(self, capability_registry: CapabilityRegistry | None = None) -> None:
        self.capability_registry = capability_registry or CapabilityRegistry.get_instance()

    def compile(self, plan: PlanDAG) -> TaskGraph:
        """
        Compiles a PlanDAG into an executable TaskGraph.

        Raises:
            ValueError: If the PlanDAG contains unknown capabilities, cyclic
                        dependencies, or references non-existent dependencies.
        """
        if not isinstance(plan, PlanDAG):
            raise TypeError(f"PlanDAGCompiler expects a PlanDAG instance, got {type(plan).__name__}")

        if not plan.nodes:
            raise ValueError(f"Cannot compile empty PlanDAG '{plan.plan_id}' with zero nodes.")

        # 1. Validate internal dependency existence
        for node_id, node in plan.nodes.items():
            for dep in node.dependencies:
                if dep not in plan.nodes:
                    raise ValueError(
                        f"PlanDAG compilation failed: Node '{node_id}' references non-existent dependency '{dep}'."
                    )

        # 2. Topological Sorting & Cycle Validation
        try:
            stages = plan.compute_execution_stages()
        except ValueError as exc:
            raise ValueError(f"PlanDAG compilation failed for '{plan.plan_id}': {exc}") from exc

        graph = TaskGraph(goal=plan.goal)

        # 3. Translate PlanNodes into SubTasks
        for node_id, node in plan.nodes.items():

            # Resolve capability & role
            cap = self.capability_registry.get(node.capability)
            if cap is None:
                raise ValueError(
                    f"PlanDAG compilation failed: Node '{node_id}' requests unknown capability '{node.capability}' "
                    f"not found in CapabilityRegistry."
                )

            cap_domain = (cap.domain or "desktop").lower()
            role = DOMAIN_ROLE_MAP.get(cap_domain)
            if role is None:
                raise ValueError(
                    f"PlanDAG compilation failed: Capability '{node.capability}' has unsupported domain '{cap_domain}'."
                )

            # Assemble canonical parameters with single-source metadata
            params = dict(node.parameters or {})
            params["risk_level"] = node.risk_level.value if hasattr(node.risk_level, "value") else str(node.risk_level)
            params["timeout_seconds"] = node.timeout_seconds
            params["expected_output_type"] = node.expected_output_type
            params["assessment_id"] = plan.assessment_id
            params["plan_id"] = plan.plan_id
            params["domain"] = plan.domain
            if plan.causal_context:
                params["causal_context"] = dict(plan.causal_context)

            # Deterministic Artifact Wiring
            # Producer: produces art_{node_id}
            output_art = params.get("output_artifact") or f"art_{node_id}"
            output_artifacts = [output_art]

            # Consumer: consumes art_{dep} for all dependencies
            input_artifacts = [f"art_{dep}" for dep in node.dependencies]

            title = node.description or f"Execute {node.capability}"

            subtask = SubTask(
                task_id=node.node_id,
                title=title,
                required_role=role,
                capability=node.capability,
                description=node.description or f"[{plan.domain}] {node.capability}",
                dependencies=list(node.dependencies),
                parameters=params,
                input_artifacts=input_artifacts,
                output_artifacts=output_artifacts,
                status="pending",
            )
            graph.add_task(subtask)

        # 3. Assign Execution Order
        graph.execution_order = [list(stage) for stage in stages]

        logger.info(
            f"[PlanDAGCompiler] Compiled PlanDAG '{plan.plan_id}' ({plan.domain}) -> "
            f"TaskGraph with {len(graph.subtasks)} subtasks across {len(graph.execution_order)} parallel stages."
        )
        return graph
