"""
Engineering Planner

Plans engineering tasks using the full engineering lifecycle.

This module enables Aura to:
- Understand before implementing
- Design before coding
- Estimate before working
- Plan before executing
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import json

logger = logging.getLogger(__name__)


class PlanningPhase(Enum):
    """Phases of the engineering lifecycle."""
    UNDERSTAND = "understand"
    ANALYZE = "analyze"
    DESIGN = "design"
    ESTIMATE = "estimate"
    PLAN = "plan"
    IMPLEMENT = "implement"
    REVIEW = "review"
    TEST = "test"
    DOCUMENT = "document"
    COMMIT = "commit"


@dataclass
class PlanningStep:
    """A single step in the planning process."""
    phase: PlanningPhase
    description: str
    details: Dict[str, Any] = field(default_factory=dict)
    estimated_time: str = "unknown"
    dependencies: List[str] = field(default_factory=list)
    estimated_cost: str = "unknown"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "phase": self.phase.value,
            "description": self.description,
            "details": self.details,
            "estimated_time": self.estimated_time,
            "dependencies": self.dependencies,
            "estimated_cost": self.estimated_cost
        }


@dataclass
class RefactoringPlan:
    """Plan for a refactoring operation."""
    operation: str  # e.g., "rename", "extract", "move"
    old_name: str
    new_name: str
    affected_files: List[str]
    steps: List[PlanningStep]
    estimated_time: str
    risk_level: str  # "low", "medium", "high"
    validation_required: bool = True
    requires_review: bool = True
    dependencies: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "operation": self.operation,
            "old_name": self.old_name,
            "new_name": self.new_name,
            "affected_files": self.affected_files,
            "steps": [s.to_dict() for s in self.steps],
            "estimated_time": self.estimated_time,
            "risk_level": self.risk_level,
            "validation_required": self.validation_required,
            "requires_review": self.requires_review
        }


@dataclass
class FeaturePlan:
    """Plan for a new feature."""
    feature_name: str
    description: str
    phases: List[PlanningStep]
    estimated_effort: str
    dependencies: List[str] = field(default_factory=list)
    acceptance_criteria: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "feature_name": self.feature_name,
            "description": self.description,
            "phases": [p.to_dict() for p in self.phases],
            "estimated_effort": self.estimated_effort,
            "dependencies": self.dependencies,
            "acceptance_criteria": self.acceptance_criteria
        }


class EngineeringPlanner:
    """
    Plans engineering tasks using the full engineering lifecycle.
    
    Usage:
        planner = EngineeringPlanner(repository_path="/path/to/repo")
        
        # Plan a refactoring
        plan = planner.plan_refactoring(
            old_name="MyClass",
            new_name="NewClass",
            operation="rename"
        )
        
        # Plan a feature
        feature_plan = planner.plan_feature(
            feature_name="Authentication",
            description="Add OAuth authentication"
        )
        
        # Plan a bug fix
        bug_plan = planner.plan_bug_fix(
            bug_description="Login button doesn't work",
            test_file="tests/test_auth.py"
        )
    """
    
    def __init__(
        self,
        repository_path: Path,
        use_memory: bool = True
    ):
        """
        Initialize the Engineering Planner.
        
        Args:
            repository_path: Path to the repository
            use_memory: Whether to use engineering memory
        """
        self.repository_path = Path(repository_path).resolve()
        self.use_memory = use_memory
    
    def plan_refactoring(
        self,
        old_name: str,
        new_name: str,
        operation: str = "rename",
        context: Optional[Dict[str, Any]] = None
    ) -> RefactoringPlan:
        """
        Plan a refactoring operation.
        
        Args:
            old_name: Current name
            new_name: New name
            operation: Type of refactoring
            context: Additional context
            
        Returns:
            RefactoringPlan
        """
        logger.info(f"Planning refactoring: {operation} {old_name} -> {new_name}")
        
        steps = self._generate_refactoring_steps(
            operation=operation,
            old_name=old_name,
            new_name=new_name,
            context=context or {}
        )
        
        affected_files = self._get_affected_files(old_name, new_name, operation)
        
        return RefactoringPlan(
            operation=operation,
            old_name=old_name,
            new_name=new_name,
            affected_files=affected_files,
            steps=steps,
            estimated_time=self._estimate_time(len(steps), operation),
            risk_level=self._assess_risk(operation, old_name, new_name),
            validation_required=True,
            requires_review=True
        )
    
    def _generate_refactoring_steps(
        self,
        operation: str,
        old_name: str,
        new_name: str,
        context: Dict[str, Any]
    ) -> List[PlanningStep]:
        """Generate steps for a refactoring operation."""
        steps = []
        
        # Understand phase
        steps.append(PlanningStep(
            phase=PlanningPhase.UNDERSTAND,
            description=f"Understand {operation} operation for {old_name}",
            details={
                "operation": operation,
                "old_name": old_name,
                "new_name": new_name
            },
            estimated_time="5-10 minutes",
            dependencies=[]
        ))
        
        # Analyze phase
        steps.append(PlanningStep(
            phase=PlanningPhase.ANALYZE,
            description=f"Analyze impact of {operation} on {old_name}",
            details={
                "affected_files": context.get("affected_files", []),
                "references_count": context.get("references_count", 0)
            },
            estimated_time="5-15 minutes",
            dependencies=["Understand"]
        ))
        
        # Design phase
        steps.append(PlanningStep(
            phase=PlanningPhase.DESIGN,
            description=f"Design {operation} strategy for {old_name}",
            details={
                "strategy": "atomic_commit",
                "validation": "tests"
            },
            estimated_time="10-20 minutes",
            dependencies=["Analyze"]
        ))
        
        # Plan phase
        steps.append(PlanningStep(
            phase=PlanningPhase.PLAN,
            description=f"Create detailed plan for {operation}",
            details={
                "preparation": "create_backup",
                "validation": "dry_run"
            },
            estimated_time="10-15 minutes",
            dependencies=["Design"]
        ))
        
        # Implement phase
        steps.append(PlanningStep(
            phase=PlanningPhase.IMPLEMENT,
            description=f"Execute {operation} of {old_name}",
            details={
                "operation": operation,
                "old_name": old_name,
                "new_name": new_name
            },
            estimated_time="15-30 minutes",
            dependencies=["Plan"]
        ))
        
        # Review phase
        steps.append(PlanningStep(
            phase=PlanningPhase.REVIEW,
            description=f"Review {operation} changes",
            details={
                "checks": ["code_style", "tests", "documentation"]
            },
            estimated_time="10-20 minutes",
            dependencies=["Implement"]
        ))
        
        # Test phase
        steps.append(PlanningStep(
            phase=PlanningPhase.TEST,
            description=f"Test {operation} changes",
            details={
                "tests": context.get("tests", []),
                "coverage": "target 90%"
            },
            estimated_time="15-30 minutes",
            dependencies=["Review"]
        ))
        
        # Document phase
        steps.append(PlanningStep(
            phase=PlanningPhase.DOCUMENT,
            description=f"Document {operation} changes",
            details={
                "changelog": True,
                "comments": True
            },
            estimated_time="10 minutes",
            dependencies=["Test"]
        ))
        
        # Commit phase
        steps.append(PlanningStep(
            phase=PlanningPhase.COMMIT,
            description=f"Commit {operation} changes",
            details={
                "message": f"Refactor {operation}: {old_name} -> {new_name}",
                "branch": context.get("branch", "feature/refactor")
            },
            estimated_time="5 minutes",
            dependencies=["Document"]
        ))
        
        return steps
    
    def _get_affected_files(
        self,
        old_name: str,
        new_name: str,
        operation: str
    ) -> List[str]:
        """Get files affected by the refactoring."""
        # In a real implementation, this would query the symbol graph
        return [f"{old_name}.py", f"{old_name}_test.py"]
    
    def _estimate_time(self, step_count: int, operation: str) -> str:
        """Estimate time for a refactoring operation."""
        base_time = 5 * step_count
        
        if operation == "rename":
            base_time *= 1.5
        elif operation == "extract":
            base_time *= 2
        elif operation == "move":
            base_time *= 3
        
        return f"{base_time}-{base_time * 2} minutes"
    
    def _assess_risk(self, operation: str, old_name: str, new_name: str) -> str:
        """Assess risk level of a refactoring."""
        if operation in ["rename", "extract"]:
            return "low"
        elif operation in ["move", "merge"]:
            return "medium"
        else:
            return "high"
    
    def plan_feature(
        self,
        feature_name: str,
        description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> FeaturePlan:
        """
        Plan a new feature.
        
        Args:
            feature_name: Name of the feature
            description: Feature description
            context: Additional context
            
        Returns:
            FeaturePlan
        """
        logger.info(f"Planning feature: {feature_name}")
        
        phases = [
            PlanningStep(
                phase=PlanningPhase.UNDERSTAND,
                description=f"Understand requirements for {feature_name}",
                details={"requirements": description}
            ),
            PlanningStep(
                phase=PlanningPhase.ANALYZE,
                description=f"Analyze current architecture for {feature_name}"
            ),
            PlanningStep(
                phase=PlanningPhase.DESIGN,
                description=f"Design solution for {feature_name}"
            ),
            PlanningStep(
                phase=PlanningPhase.PLAN,
                description=f"Plan implementation for {feature_name}"
            ),
            PlanningStep(
                phase=PlanningPhase.IMPLEMENT,
                description=f"Implement {feature_name}"
            ),
            PlanningStep(
                phase=PlanningPhase.TEST,
                description=f"Test {feature_name}"
            ),
            PlanningStep(
                phase=PlanningPhase.REVIEW,
                description=f"Review {feature_name}"
            ),
            PlanningStep(
                phase=PlanningPhase.DOCUMENT,
                description=f"Document {feature_name}"
            ),
            PlanningStep(
                phase=PlanningPhase.COMMIT,
                description=f"Commit {feature_name}"
            )
        ]
        
        return FeaturePlan(
            feature_name=feature_name,
            description=description,
            phases=phases,
            estimated_effort=f"{len(phases)} hours",
            dependencies=context.get("dependencies", []) if context else []
        )
    
    def plan_bug_fix(
        self,
        bug_description: str,
        test_file: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> RefactoringPlan:
        """
        Plan a bug fix.
        
        Args:
            bug_description: Description of the bug
            test_file: Path to test file
            context: Additional context
            
        Returns:
            RefactoringPlan
        """
        logger.info(f"Planning bug fix: {bug_description}")
        
        steps = []
        
        # Understand bug
        steps.append(PlanningStep(
            phase=PlanningPhase.UNDERSTAND,
            description=f"Understand bug: {bug_description}"
        ))
        
        # Reproduce
        steps.append(PlanningStep(
            phase=PlanningPhase.UNDERSTAND,
            description=f"Reproduce the bug"
        ))
        
        # Analyze
        steps.append(PlanningStep(
            phase=PlanningPhase.ANALYZE,
            description=f"Analyze root cause"
        ))
        
        # Fix
        steps.append(PlanningStep(
            phase=PlanningPhase.IMPLEMENT,
            description=f"Implement fix"
        ))
        
        # Test
        steps.append(PlanningStep(
            phase=PlanningPhase.TEST,
            description=f"Test fix",
            details={"test_file": test_file}
        ))
        
        # Review
        steps.append(PlanningStep(
            phase=PlanningPhase.REVIEW,
            description=f"Review fix"
        ))
        
        # Commit
        steps.append(PlanningStep(
            phase=PlanningPhase.COMMIT,
            description=f"Commit fix"
        ))
        
        return RefactoringPlan(
            operation="fix_bug",
            old_name="unknown",
            new_name="unknown",
            affected_files=[],
            steps=steps,
            estimated_time="1-3 hours",
            risk_level="low"
        )
    
    def get_planning_summary(self, plan: Union[RefactoringPlan, FeaturePlan]) -> Dict[str, Any]:
        """
        Get a summary of a plan.
        
        Args:
            plan: RefactoringPlan or FeaturePlan
            
        Returns:
            Summary dictionary
        """
        if isinstance(plan, RefactoringPlan):
            return {
                "type": "refactoring",
                "operation": plan.operation,
                "old_name": plan.old_name,
                "new_name": plan.new_name,
                "affected_files": plan.affected_files,
                "steps": len(plan.steps),
                "estimated_time": plan.estimated_time,
                "risk_level": plan.risk_level
            }
        else:
            return {
                "type": "feature",
                "name": plan.feature_name,
                "description": plan.description,
                "phases": len(plan.phases),
                "estimated_effort": plan.estimated_effort
            }
    
    def to_json(self, plan: Union[RefactoringPlan, FeaturePlan]) -> str:
        """Convert plan to JSON."""
        return json.dumps(plan.to_dict(), indent=2)
