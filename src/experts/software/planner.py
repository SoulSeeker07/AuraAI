"""
Software Engineering Expert Planner (M25 Phase 2)
Location: src/experts/software/planner.py

Specialized domain planner coordinating AST analysis, dependency graphs,
automated bug reproduction, and safe refactoring workflows.

Architectural Invariants:
1. Pure Reasoning: Generates DomainAssessment and PlanDAG data structures.
   Zero direct capability invocation, zero file mutation during planning.
2. Causal Continuity: Preserves event_id, correlation_id, and assessment_id.
3. Strict Governance: All downstream modifications flow through the CapabilityRegistry
   and AutonomyPolicyGate.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from core.capabilities.capability_registry import CapabilityRegistry
from core.capabilities.models import PlanValidationResult
from core.orchestration.autonomy_mode import ActionRisk
from ..base_expert import DomainExpertPlanner
from ..models import DomainAssessment, PlanDAG, PlanNode
from .ast_analyzer import ASTAnalyzer
from .dependency_analyzer import DependencyAnalyzer
from .refactoring_planner import RefactoringPlanner
from .reproduction_planner import ReproductionPlanner

logger = logging.getLogger(__name__)


class SoftwareEngineeringExpertPlanner(DomainExpertPlanner):
    """
    Professional domain planner for software engineering, architecture, and automated repair.
    """

    def __init__(
        self,
        ast_analyzer: ASTAnalyzer | None = None,
        dependency_analyzer: DependencyAnalyzer | None = None,
        reproduction_planner: ReproductionPlanner | None = None,
        refactoring_planner: RefactoringPlanner | None = None,
    ) -> None:
        self.ast_analyzer = ast_analyzer or ASTAnalyzer()
        self.dependency_analyzer = dependency_analyzer or DependencyAnalyzer(self.ast_analyzer)
        self.reproduction_planner = reproduction_planner or ReproductionPlanner()
        self.refactoring_planner = refactoring_planner or RefactoringPlanner()

    @property
    def domain(self) -> str:
        return "software_engineering"

    @property
    def description(self) -> str:
        return "Specialized expert for AST analysis, dependency resolution, bug diagnosis, reproduction testing, and safe refactoring."

    @property
    def supported_intents(self) -> list[str]:
        return [
            "engineering.diagnose",
            "engineering.refactor",
            "engineering.test_reproduce",
            "engineering.syntax_repair",
            "engineering.dependency_audit",
        ]

    def can_handle(
        self,
        goal_text: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[bool, float, str]:
        """
        Evaluates goal text against software engineering semantic patterns.
        """
        g = goal_text.lower().strip()
        ctx = context or {}

        # Check explicit intent from context
        intent = ctx.get("intent", "")
        if intent in self.supported_intents:
            return True, 0.98, f"Direct match with supported intent '{intent}'."

        # High-confidence indicators
        high_indicators = [
            r"\brefactor\b", r"\bpytest\b", r"\bunit test\b", r"\bast\b", r"\bstack trace\b",
            r"\btraceback\b", r"\bassertionerror\b", r"\btypeerror\b", r"\bsyntaxerror\b",
            r"\bcircular import\b", r"\bbug fix\b", r"\bfix test\b", r"\bfailing test\b",
            r"\bcode edit\b", r"\bgit diff\b"
        ]
        matched_high = [ind for ind in high_indicators if re.search(ind, g)]
        if matched_high:
            clean_names = [ind.replace(r"\b", "") for ind in matched_high]
            confidence = min(0.95, 0.80 + (0.05 * len(matched_high)))
            return True, confidence, f"Matched software engineering signals: {', '.join(clean_names)}."

        # Medium-confidence indicators
        med_indicators = [
            r"\bfunction\b", r"\bclass\b", r"\bmodule\b", r"\bdependency\b",
            r"\bcompile\b", r"\blint\b", r"\bexception\b"
        ]
        matched_med = [ind for ind in med_indicators if re.search(ind, g)]
        if matched_med:
            clean_names = [ind.replace(r"\b", "") for ind in matched_med]
            return True, 0.70, f"Matched coding-related terms: {', '.join(clean_names)}."

        return False, 0.10, "Goal does not require specialized software engineering expertise."

    async def assess(
        self,
        goal_text: str,
        context: dict[str, Any] | None = None,
    ) -> DomainAssessment:
        """
        Conducts deep software domain evaluation and synthesizes findings and strategy.
        """
        ctx = context or {}
        causal = ctx.get("causal_context", {})
        findings: list[str] = []
        assumptions: list[str] = []
        required_caps: list[str] = []

        g = goal_text.lower()
        is_bug_or_test = any(w in g for w in ["bug", "fail", "test", "error", "traceback", "assertion"])
        is_refactor = any(w in g for w in ["refactor", "rename", "extract", "clean", "structure"])

        if is_bug_or_test:
            repro_plan = self.reproduction_planner.plan_reproduction(goal_text, context=ctx)
            findings.append(f"Target Error Type: {repro_plan['error_type']}")
            if repro_plan["target_file"]:
                findings.append(f"Failing File: {repro_plan['target_file']}")
            findings.append(f"Reproduction Strategy: {repro_plan['reproduction_strategy']}")
            assumptions.extend([
                "Local workspace test runner is operational.",
                "Reproduction test will fail on current code and pass after patch.",
            ])
            required_caps.extend(["code.analyze", "code.edit", "code.test", "workspace.walk"])
            strategy = f"Reproduce failure ({repro_plan['error_type']}) -> Isolate AST -> Apply minimal patch -> Verify test suite."

        elif is_refactor:
            ref_plan = self.refactoring_planner.plan_refactoring(goal_text, context=ctx)
            findings.append(f"Refactoring Operation: {ref_plan['refactoring_type']}")
            findings.append(f"Rollback Strategy: {ref_plan['rollback_strategy']}")
            assumptions.extend([
                "Codebase has valid syntax prior to refactoring.",
                "Atomic backup will be created before modifying files.",
            ])
            required_caps.extend(ref_plan["required_capabilities"])
            strategy = f"Baseline AST check -> Atomic {ref_plan['refactoring_type']} -> Post-verification test suite."

        else:
            findings.append("General software engineering task.")
            assumptions.append("Workspace files are readable and writable.")
            required_caps.extend(["code.analyze", "workspace.walk", "code.edit", "code.test"])
            strategy = "Inspect workspace AST -> Synthesize code modification -> Verify regression tests."

        return DomainAssessment.create(
            domain=self.domain,
            confidence=0.92,
            findings=findings,
            assumptions=assumptions,
            required_capabilities=list(set(required_caps)),
            recommended_strategy=strategy,
            causal_context=causal,
            metadata={"goal": goal_text},
        )

    async def generate_plan(
        self,
        goal_text: str,
        assessment: DomainAssessment,
        context: dict[str, Any] | None = None,
    ) -> PlanDAG:
        """
        Synthesizes a dependency-ordered PlanDAG for software engineering tasks.
        """
        plan = PlanDAG.create(
            domain=self.domain,
            goal=goal_text,
            assessment_id=assessment.assessment_id,
            causal_context=dict(assessment.causal_context),
        )

        # Stage 1: Workspace & AST Discovery
        plan.add_node(
            PlanNode(
                node_id="sw_discover_01",
                capability="workspace.walk",
                description="Scan workspace structure and locate candidate source files.",
                risk_level=ActionRisk.LOW,
            )
        )
        plan.add_node(
            PlanNode(
                node_id="sw_ast_analyze_02",
                capability="code.analyze",
                dependencies=["sw_discover_01"],
                description="Perform AST analysis and build symbol hierarchy.",
                risk_level=ActionRisk.LOW,
            )
        )

        # Stage 2: Code Modification with Rollback
        plan.add_node(
            PlanNode(
                node_id="sw_code_edit_03",
                capability="code.edit",
                dependencies=["sw_ast_analyze_02"],
                description="Apply code patch with atomic physical backup.",
                risk_level=ActionRisk.HIGH,
            )
        )

        # Stage 3: Verification & Regression Testing
        plan.add_node(
            PlanNode(
                node_id="sw_test_verify_04",
                capability="code.test",
                dependencies=["sw_code_edit_03"],
                description="Execute automated test suite to verify fix and ensure zero regression.",
                risk_level=ActionRisk.MEDIUM,
            )
        )

        plan.compute_execution_stages()
        return plan
