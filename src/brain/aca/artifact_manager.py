"""
Artifact Manager — Everything Aura Creates
==========================================

Responses should not be the primary output. Artifacts should.

    Research → ResearchArtifact → Verification → Response
    Engineering → CodeArtifact → Verification → Response

The Artifact Manager collects artifacts from execution and stores them
in the RuntimeSession.
"""

from __future__ import annotations

import logging
from typing import Any

from ..schemas.artifact import Artifact

logger = logging.getLogger(__name__)


class ArtifactManager:
    """
    Collects and manages artifacts created during execution.

    This is an explicit stage between execution and reflection.
    """

    def __init__(self):
        self._artifacts: dict[str, Artifact] = {}

    def create_artifact(
        self,
        artifact_type: str,
        name: str,
        content: str = "",
        location: str = "",
        creator: str = "",
        session_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Artifact:
        """Create a new artifact."""
        artifact = Artifact(
            artifact_type=artifact_type,
            name=name,
            content=content,
            location=location,
            creator=creator,
            session_id=session_id,
            metadata=metadata or {},
        )
        self._artifacts[artifact.artifact_id] = artifact
        logger.info(
            f"ArtifactManager created [{artifact.artifact_id}]: "
            f"{artifact_type} '{name}' by {creator}"
        )
        return artifact

    def collect_from_execution(
        self, coordination: Any, session_id: str = ""
    ) -> list[Artifact]:
        """
        Collect artifacts from execution results.

        Args:
            coordination: The CoordinationResult from the ExecutionCoordinator.
            session_id: The session this artifact belongs to.

        Returns:
            List of collected artifacts.
        """
        artifacts: list[Artifact] = []

        if coordination is None:
            return artifacts

        # Collect from step results
        step_results = getattr(coordination, "step_results", [])
        for step in step_results:
            data = step.data if isinstance(step.data, dict) else {}
            observations = step.observations or []

            # Create an artifact from each step's output
            artifact = self.create_artifact(
                artifact_type=step.engine,
                name=f"{step.action} result",
                content="\n".join(observations) if observations else str(data),
                creator=step.engine,
                session_id=session_id,
                metadata={"action": step.action, "success": step.success},
            )
            artifacts.append(artifact)

        return artifacts

    def get_artifact(self, artifact_id: str) -> Artifact | None:
        """Get an artifact by ID."""
        return self._artifacts.get(artifact_id)

    def list_artifacts(self, session_id: str | None = None) -> list[Artifact]:
        """List all artifacts, optionally filtered by session."""
        if session_id:
            return [a for a in self._artifacts.values() if a.session_id == session_id]
        return list(self._artifacts.values())

    def get_artifacts_by_type(self, artifact_type: str) -> list[Artifact]:
        """Get artifacts by type."""
        return [a for a in self._artifacts.values() if a.artifact_type == artifact_type]


__all__ = ["ArtifactManager"]
