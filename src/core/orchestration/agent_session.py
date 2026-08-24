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

try:
    from research.models import MIN_SYNTHESIS_CONFIDENCE_THRESHOLD
except (ImportError, ValueError):
    MIN_SYNTHESIS_CONFIDENCE_THRESHOLD = 0.40

from ..planning.execution_trace import ExecutionTrace
from .artifact import Artifact
from .observation import Observation
from .pipeline_error import ArtifactLowConfidence, ArtifactPayloadMissing

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

    def get_artifact(self, artifact_id: str) -> Artifact | None:
        """Retrieve an artifact by its logical ID.

        Searches in reverse order so the most recently added artifact
        with a given ID wins (allows overwriting).
        """
        for art in reversed(self.artifacts):
            if art.artifact_id == artifact_id:
                return art
        return None

    def require_artifact(
        self, artifact_id: str, for_task: str, min_confidence: float | None = None
    ) -> Artifact:
        """Retrieve an artifact or raise ``ArtifactPayloadMissing`` / ``ArtifactLowConfidence``.

        This is the fail-loud contract: if an upstream stage did not produce
        the expected artifact with a non-empty payload, or if the artifact's
        confidence is below the applicable threshold, the pipeline halts immediately.
        """
        art = self.get_artifact(artifact_id)
        if art is None or not art.has_payload:
            raise ArtifactPayloadMissing(for_task, artifact_id)

        # Scoped threshold: If min_confidence is not explicitly provided,
        # apply MIN_SYNTHESIS_CONFIDENCE_THRESHOLD only for research artifacts.
        threshold = min_confidence
        if threshold is None and getattr(art, "artifact_type", None) == "research":
            threshold = MIN_SYNTHESIS_CONFIDENCE_THRESHOLD

        if threshold is not None:
            # Check confidence if present on artifact, metadata, or verification report
            art_conf = getattr(art, "confidence", None)
            if art_conf is None and art.verification_report is not None:
                art_conf = getattr(art.verification_report, "confidence", None)
            if art_conf is None and "confidence_score" in art.metadata:
                art_conf = art.metadata["confidence_score"]
            if art_conf is None and "confidence" in art.metadata:
                art_conf = art.metadata["confidence"]

            if art_conf is not None and isinstance(art_conf, (int, float)) and art_conf < threshold:
                raise ArtifactLowConfidence(for_task, artifact_id, float(art_conf), threshold)

        return art

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
