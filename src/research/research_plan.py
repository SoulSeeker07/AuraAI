# Research Planner for Aura AI - Phase 4 of Milestone 14 - Research Intelligence

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class ResearchMode(Enum):
    """Research modes for different query types"""

    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"
    RESEARCH = "research"


class StopCondition(Enum):
    """Conditions that can stop research"""

    CONFIDENCE_THRESHOLD = "confidence_threshold"  # Reached target confidence
    MAX_ITERATIONS = "max_iterations"  # Reached max planning iterations
    MAX_STEPS = "max_steps"  # Reached max research steps
    SUFFICIENT_EVIDENCE = "sufficient_evidence"  # Has enough evidence to answer
    QUERY_MATURED = "query_matured"  # Query stopped evolving


@dataclass
class ResearchStep:
    """
    Represents a single step in the research plan.

    Each step contains:
    - The sub-query to search
    - The provider(s) to use
    - Expected content type
    - Confidence goal for this step
    - Priorities/weights
    """

    step_id: int
    query: str
    query_type: Literal["keyword", "entity", "aspect", "compare", "summary"]
    providers: list[str] = field(default_factory=list)
    expected_content_type: str = "general"
    confidence_goal: float = 0.7
    priority: float = 1.0
    is_primary: bool = False
    sources: list[str] = field(default_factory=list)
    evidence_found: int = 0
    confidence_estimate: float = 0.0
    completed: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "step_id": self.step_id,
            "query": self.query,
            "query_type": self.query_type,
            "providers": self.providers,
            "expected_content_type": self.expected_content_type,
            "confidence_goal": self.confidence_goal,
            "priority": self.priority,
            "is_primary": self.is_primary,
            "sources": self.sources,
            "evidence_found": self.evidence_found,
            "confidence_estimate": self.confidence_estimate,
            "completed": self.completed,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchStep":
        """Create from dictionary"""
        return cls(
            step_id=data["step_id"],
            query=data["query"],
            query_type=data["query_type"],
            providers=data.get("providers", []),
            expected_content_type=data.get("expected_content_type", "general"),
            confidence_goal=data.get("confidence_goal", 0.7),
            priority=data.get("priority", 1.0),
            is_primary=data.get("is_primary", False),
            sources=data.get("sources", []),
            evidence_found=data.get("evidence_found", 0),
            confidence_estimate=data.get("confidence_estimate", 0.0),
            completed=data.get("completed", False),
            timestamp=data.get("timestamp", time.time()),
        )


@dataclass
class StopReason:
    """
    Reason why research stopped.
    """

    condition: StopCondition
    confidence_score: float
    iteration_count: int
    steps_completed: int
    message: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "condition": self.condition.value,
            "confidence_score": self.confidence_score,
            "iteration_count": self.iteration_count,
            "steps_completed": self.steps_completed,
            "message": self.message,
        }


@dataclass
class ResearchPlan:
    """
    Main research plan that orchestrates the research process.

    A plan contains:
    - Original query and analysis
    - Decomposed sub-queries
    - Provider assignments
    - Execution order
    - Confidence tracking
    - Stop conditions
    """

    plan_id: str
    original_query: str
    query_analysis: dict[str, Any] = field(default_factory=dict)
    research_mode: ResearchMode = ResearchMode.STANDARD

    # Planning constraints
    max_iterations: int = 3
    max_steps: int = 10
    confidence_threshold: float = 0.85
    iteration_count: int = 0

    # Plan structure
    steps: list[ResearchStep] = field(default_factory=list)

    # Execution status
    current_step_index: int = 0
    confidence_estimate: float = 0.0
    is_complete: bool = False
    stop_reason: StopReason | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "plan_id": self.plan_id,
            "original_query": self.original_query,
            "query_analysis": self.query_analysis,
            "research_mode": self.research_mode.value,
            "max_iterations": self.max_iterations,
            "max_steps": self.max_steps,
            "confidence_threshold": self.confidence_threshold,
            "iteration_count": self.iteration_count,
            "steps": [step.to_dict() for step in self.steps],
            "current_step_index": self.current_step_index,
            "confidence_estimate": self.confidence_estimate,
            "is_complete": self.is_complete,
            "stop_reason": self.stop_reason.to_dict() if self.stop_reason else None,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchPlan":
        """Create from dictionary"""
        steps = [ResearchStep.from_dict(s) for s in data.get("steps", [])]
        stop_reason = (
            StopReason.from_dict(data.get("stop_reason"))
            if data.get("stop_reason")
            else None
        )

        return cls(
            plan_id=data["plan_id"],
            original_query=data["original_query"],
            query_analysis=data.get("query_analysis", {}),
            research_mode=ResearchMode(data.get("research_mode", "standard")),
            max_iterations=data.get("max_iterations", 3),
            max_steps=data.get("max_steps", 10),
            confidence_threshold=data.get("confidence_threshold", 0.85),
            iteration_count=data.get("iteration_count", 0),
            steps=steps,
            current_step_index=data.get("current_step_index", 0),
            confidence_estimate=data.get("confidence_estimate", 0.0),
            is_complete=data.get("is_complete", False),
            stop_reason=stop_reason,
        )

    def add_step(self, step: ResearchStep) -> None:
        """Add a research step to the plan"""
        self.steps.append(step)
        self.updated_at = time.time()

    def update_step_confidence(
        self, step_id: int, confidence: float, evidence_count: int = 1
    ) -> None:
        """Update confidence for a specific step"""
        for step in self.steps:
            if step.step_id == step_id:
                step.confidence_estimate = confidence
                step.evidence_found = evidence_count
                step.completed = True
                self.updated_at = time.time()
                break

    def update_confidence_estimate(self) -> None:
        """Update overall confidence estimate based on all steps"""
        if not self.steps:
            self.confidence_estimate = 0.0
            return

        weighted_sum = sum(
            step.confidence_estimate * step.priority for step in self.steps
        )
        total_priority = sum(step.priority for step in self.steps)

        self.confidence_estimate = (
            weighted_sum / total_priority if total_priority > 0 else 0.0
        )
        self.updated_at = time.time()

    def check_stop_conditions(self) -> StopReason | None:
        """
        Check if research should stop.

        Returns StopReason if a stop condition is met, None otherwise.
        """
        # Check iteration limit
        if self.iteration_count >= self.max_iterations:
            return StopReason(
                condition=StopCondition.MAX_ITERATIONS,
                confidence_score=self.confidence_estimate,
                iteration_count=self.iteration_count,
                steps_completed=sum(1 for step in self.steps if step.completed),
                message=f"Maximum iterations ({self.max_iterations}) reached",
            )

        # Check confidence threshold
        if self.confidence_estimate >= self.confidence_threshold:
            return StopReason(
                condition=StopCondition.CONFIDENCE_THRESHOLD,
                confidence_score=self.confidence_estimate,
                iteration_count=self.iteration_count,
                steps_completed=sum(1 for step in self.steps if step.completed),
                message=f"Confidence threshold ({self.confidence_threshold}) reached",
            )

        # Check if we have enough steps
        completed_steps = sum(1 for step in self.steps if step.completed)
        if completed_steps >= self.max_steps:
            return StopReason(
                condition=StopCondition.MAX_STEPS,
                confidence_score=self.confidence_estimate,
                iteration_count=self.iteration_count,
                steps_completed=completed_steps,
                message=f"Maximum steps ({self.max_steps}) reached",
            )

        # Check if query has matured (no significant evidence gain)
        if completed_steps > 0:
            # This is a simple check - in real implementation, we'd track evidence gain
            # for each iteration and detect if research is stagnating
            pass

        return None

    def get_next_step(self) -> ResearchStep | None:
        """Get the next step to execute.

        Returns the next uncompleted step, or None if all steps are done.
        """
        for step in self.steps:
            if not step.completed:
                return step
        return None
