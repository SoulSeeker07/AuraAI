"""
Agent Session & Execution Budget
Location: src/core/orchestration/agent_session.py

Represents Aura's "Operating System Process" (AgentSession) holding execution context,
budget limits, observations, artifacts, and traces across the multi-agent lifecycle.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ..planning.execution_trace import ExecutionTrace
from .artifact import Artifact
from .observation import Observation

if TYPE_CHECKING:
    from .confirmation import ActionPlanConfirmation


@dataclass
class ExecutionBudget:
    """
    Carries time, cost, concurrency, and policy constraints for an execution session.
    """

    max_time_seconds: float = 30.0
    max_cost_usd: float = 0.10
    max_backends: int = 5
    allow_parallel: bool = True
    local_only: bool = False
    offline_mode: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_time_seconds": self.max_time_seconds,
            "max_cost_usd": self.max_cost_usd,
            "max_backends": self.max_backends,
            "allow_parallel": self.allow_parallel,
            "local_only": self.local_only,
            "offline_mode": self.offline_mode,
        }


@dataclass
class AgentSession:
    """
    Aura Operating System Process context passed through all orchestration stages.
    """

    session_id: str = field(default_factory=lambda: f"sess_{uuid.uuid4().hex[:10]}")
    goal: str = ""
    budget: ExecutionBudget = field(default_factory=ExecutionBudget)
    memory_context: dict[str, Any] = field(default_factory=dict)
    observations: list[Observation] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    execution_trace: ExecutionTrace | None = None
    decision_trace: Any | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    # Session-scoped pending confirmation — replaces AuraCore-level yes/no intercept
    pending_confirmation: "ActionPlanConfirmation | None" = field(
        default=None, repr=False
    )

    def add_observation(self, observation: Observation) -> None:
        """Add an observation to the session."""
        self.observations.append(observation)

    def add_artifact(self, artifact: Artifact) -> None:
        """Add an artifact to the session."""
        self.artifacts.append(artifact)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "goal": self.goal,
            "budget": self.budget.to_dict(),
            "memory_context": self.memory_context,
            "observations": [obs.to_dict() for obs in self.observations],
            "artifacts": [art.to_dict() for art in self.artifacts],
            "execution_trace": (
                self.execution_trace.to_dict() if self.execution_trace else None
            ),
            "decision_trace": (
                self.decision_trace.to_dict()
                if self.decision_trace and hasattr(self.decision_trace, "to_dict")
                else self.decision_trace
            ),
            "metrics": self.metrics,
            "created_at": self.created_at,
        }
