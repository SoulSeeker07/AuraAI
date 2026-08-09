"""
Software Engineering Expert System
Location: src/experts/software_expert.py

Provides software analysis, AST code inspection, repository health checks, and refactoring proposals.
Proposes actions to ExecutionCoordinator — NEVER executes directly.
"""

from __future__ import annotations

import logging
from typing import Any

from .base_expert import BaseExpertSystem
from .models import (
    DomainActionProposal,
    DomainFinding,
    DomainType,
    ExpertAnalysisResult,
    SeverityLevel,
)

logger = logging.getLogger(__name__)


class SoftwareEngineeringExpert(BaseExpertSystem):
    """
    Expert System for Software Engineering, Code Analysis, and Refactoring.
    """

    @property
    def domain(self) -> DomainType:
        return DomainType.SOFTWARE_ENGINEERING

    def _perform_analysis(
        self, query: str, context: dict[str, Any]
    ) -> ExpertAnalysisResult:
        query_lower = query.lower()
        findings: list[DomainFinding] = []
        proposals: list[DomainActionProposal] = []

        # Analyze software query intent
        target_path = context.get("target_path") or context.get("file_path") or "src"

        if "refactor" in query_lower or "edit" in query_lower:
            findings.append(
                DomainFinding(
                    category="code_quality",
                    title="Refactoring Opportunity Identified",
                    description=f"Target module '{target_path}' analyzed for refactoring opportunity.",
                    severity=SeverityLevel.LOW,
                    evidence=[f"Query: '{query}'", f"Target Path: {target_path}"],
                )
            )
            proposals.append(
                DomainActionProposal(
                    engine="engineering",
                    action="code.edit",
                    parameters={
                        "target_file": target_path,
                        "instruction": query,
                        "user_authorized": context.get("user_authorized", False),
                    },
                    description=f"Apply AST code edit to {target_path}",
                    risk_level="low",
                )
            )
        else:
            findings.append(
                DomainFinding(
                    category="repository_health",
                    title="Codebase Structure Analysis",
                    description=f"Inspecting code structure and quality at '{target_path}'.",
                    severity=SeverityLevel.INFO,
                    evidence=[f"Target: {target_path}"],
                )
            )
            proposals.append(
                DomainActionProposal(
                    engine="engineering",
                    action="code.analyze",
                    parameters={"target_path": target_path},
                    description=f"Perform static analysis on {target_path}",
                    risk_level="low",
                )
            )

        return ExpertAnalysisResult(
            domain=self.domain,
            success=True,
            summary=f"Software engineering analysis complete for '{query}'",
            findings=findings,
            proposals=proposals,
            data={"target_path": target_path},
        )
