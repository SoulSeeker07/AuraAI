"""
DomainExpertPlanner Abstract Base Contract (M25 Phase 1)
Location: src/experts/base_expert.py

Defines the universal contract for all specialized domain experts:
Software Engineering, Network Engineering, Cybersecurity, Financial Analysis.

Architectural Invariants:
1. Pure Reasoning: Planners generate DomainAssessment and PlanDAG data structures.
   They NEVER execute capabilities directly or bypass the AutonomyPolicyGate.
2. Context Integration: Planners can query WorldModel, CognitiveMemory, and Research facts.
3. Strict Validation: Every generated plan is dependency-validated and schema-checked.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
from typing import Any

from core.capabilities.capability_registry import CapabilityRegistry
from core.capabilities.models import PlanValidationResult
from .models import DomainAssessment, PlanDAG, PlanNode, DomainType, ExpertAnalysisResult

logger = logging.getLogger(__name__)


class BaseExpertSystem(ABC):
    """
    Abstract contract for Professional Expert Systems.
    """

    @property
    @abstractmethod
    def domain(self) -> DomainType:
        """The domain type handled by this expert system."""
        ...

    @property
    def name(self) -> str:
        """Name identifier of the expert system."""
        return self.domain.value if hasattr(self.domain, "value") else str(self.domain)

    @abstractmethod
    def _perform_analysis(
        self, query: str, context: dict[str, Any]
    ) -> ExpertAnalysisResult:
        """Domain-specific analysis logic implemented by subclasses."""
        ...

    def analyze(
        self, query: str, context: dict[str, Any] | None = None
    ) -> ExpertAnalysisResult:
        """
        Public analysis entry point with error isolation.
        Catches any domain expert exception and wraps it in a failed ExpertAnalysisResult
        so expert failures never crash the Aura runtime.
        """
        ctx = context or {}
        dom_val = self.domain.value if hasattr(self.domain, "value") else str(self.domain)
        logger.info(f"[{self.__class__.__name__}] Analyzing query in domain '{dom_val}': '{query}'")

        try:
            result = self._perform_analysis(query, ctx)
            logger.info(
                f"[{self.__class__.__name__}] Analysis complete: success={result.success}, "
                f"findings={len(result.findings)}, proposals={len(result.proposals)}"
            )
            return result
        except Exception as exc:
            logger.error(f"[{self.__class__.__name__}] Analysis failed with exception: {exc}", exc_info=True)
            return ExpertAnalysisResult(
                domain=self.domain,
                success=False,
                summary=f"Analysis in domain '{dom_val}' failed due to error: {exc}",
                error=f"{type(exc).__name__}: {exc}",
            )


class DomainExpertPlanner(ABC):
    """
    Abstract base class for all Milestone 25 Professional Domain Experts.
    """

    @property
    @abstractmethod
    def domain(self) -> str:
        """Unique domain identifier e.g. 'software_engineering', 'network_engineering', 'cybersecurity', 'finance'."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of domain capabilities."""
        pass

    @property
    def supported_intents(self) -> list[str]:
        """List of intent strings or intent patterns supported by this expert."""
        return []

    @abstractmethod
    def can_handle(
        self,
        goal_text: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[bool, float, str]:
        """
        Evaluates whether this domain expert can handle the given goal.

        Returns:
            (matches: bool, confidence_score: float [0.0..1.0], rationale: str)
        """
        pass

    @abstractmethod
    async def assess(
        self,
        goal_text: str,
        context: dict[str, Any] | None = None,
    ) -> DomainAssessment:
        """
        Conducts deep domain analysis and situational diagnostics before planning.
        Assembles findings, assumptions, and required capability inventory into an immutable DomainAssessment.
        """
        pass

    @abstractmethod
    async def generate_plan(
        self,
        goal_text: str,
        assessment: DomainAssessment,
        context: dict[str, Any] | None = None,
    ) -> PlanDAG:
        """
        Synthesizes a dependency-ordered PlanDAG of capability calls to satisfy the assessed goal.
        Does NOT execute any capabilities.
        """
        pass

    def validate_plan(
        self,
        plan: PlanDAG,
        capability_registry: CapabilityRegistry | None = None,
    ) -> PlanValidationResult:
        """
        Validates the PlanDAG against the CapabilityRegistry:
        1. Checks for absence of cyclic dependencies.
        2. Verifies all referenced capabilities exist and are active.
        3. Validates node dependencies exist within the plan.
        """
        errors: list[str] = []
        warnings: list[str] = []
        missing_prereqs: list[tuple[str, str]] = []
        unwired_caps: list[str] = []

        # 1. Topological cycle validation
        try:
            plan.compute_execution_stages()
        except ValueError as e:
            errors.append(f"Cycle validation error: {e}")

        # 2. Capability registry validation
        cap_reg = capability_registry or CapabilityRegistry.get_instance()

        for nid, node in plan.nodes.items():
            # Check internal dependency references
            for dep in node.dependencies:
                if dep not in plan.nodes:
                    errors.append(f"Node '{nid}' references non-existent dependency '{dep}'.")

            # Check capability existence
            cap = cap_reg.get(node.capability)
            if cap is None:
                errors.append(f"Node '{nid}' requests unknown capability '{node.capability}'.")
                unwired_caps.append(node.capability)
            else:
                if not cap.is_live:
                    warnings.append(f"Capability '{node.capability}' on node '{nid}' is scaffolded/offline.")

        is_valid = len(errors) == 0
        return PlanValidationResult(
            valid=is_valid,
            errors=errors,
            warnings=warnings,
            missing_prerequisites=missing_prereqs,
            unwired_capabilities=unwired_caps,
        )

    def explain_plan(
        self,
        plan: PlanDAG,
        assessment: DomainAssessment,
    ) -> str:
        """Generates structured explanation of the generated domain plan."""
        stages = plan.execution_stages if plan.execution_stages else [list(plan.nodes.keys())]
        lines = [
            f"=== Domain Plan: {self.domain.upper()} (Plan ID: {plan.plan_id}) ===",
            f"Goal: {plan.goal}",
            f"Assessment: {assessment.assessment_id} (Confidence: {assessment.confidence:.2f})",
            f"Strategy: {assessment.recommended_strategy}",
            f"Execution Stages ({len(stages)} total):",
        ]
        for idx, stage in enumerate(stages, 1):
            stage_nodes = [f"{nid} ({plan.nodes[nid].capability})" for nid in stage if nid in plan.nodes]
            lines.append(f"  Stage {idx}: {', '.join(stage_nodes)}")
        return "\n".join(lines)
