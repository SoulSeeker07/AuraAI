"""
Episodic Memory Subsystem
Location: src/memory/episodic_memory.py

Records event narratives ("what happened when, why, result, entities, project, outcome")
from verified RuntimeSessions.

Guardrail Rule:
    Failed or unverified executions are NEVER recorded as positive episodic knowledge.
"""

import datetime as dt

from .models import MemoryItem, MemoryProvenance, MemoryType, ProvenanceSource


class EpisodicMemoryRecorder:
    """Records timestamped event episodes from verified execution sessions."""

    def record_episode(
        self,
        session_id: str,
        goal: str,
        outcome: str,
        success: bool,
        actions_taken: list[str],
        project_id: str = "global",
        topic: str = "general",
        importance: float = 0.6,
    ) -> MemoryItem | None:
        """
        Record a timestamped episode.

        If success=False, the episode is stored with low importance and marked as
        failed so it is not recalled as a positive procedure.
        """
        now = dt.datetime.now().isoformat(timespec="seconds")
        status_label = "successfully completed" if success else "failed"
        content = (
            f"Episode on {now} [{project_id}]: User requested '{goal}'. "
            f"Aura {status_label} the task. Actions: {', '.join(actions_taken)}. "
            f"Outcome summary: {outcome[:200]}."
        )

        provenance = MemoryProvenance(
            source_type=ProvenanceSource.RUNTIME_SESSION,
            source_id=session_id,
            confidence=0.95 if success else 0.40,
            verified=success,
        )

        return MemoryItem(
            type=MemoryType.EPISODIC,
            content=content,
            importance=importance if success else 0.2,
            confidence=0.95 if success else 0.40,
            project_id=project_id,
            topic=topic,
            provenance=provenance,
            metadata={
                "session_id": session_id,
                "goal": goal,
                "success": success,
                "actions_taken": actions_taken,
                "outcome_summary": outcome[:500],
            },
        )
