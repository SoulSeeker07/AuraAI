"""
Memory Consolidation Engine
Location: src/memory/consolidation_engine.py

Evaluates Working Memory and Short-Term items post-execution; promotes high-importance,
verified insights into Long-Term, Episodic, or Procedural memory.

Guardrail Rule:
    Failed or unverified execution results are explicitly skipped and NEVER consolidated
    into persistent memory.
"""

import logging
from typing import Any

from .models import MemoryItem, MemoryProvenance, MemoryType, ProvenanceSource

logger = logging.getLogger(__name__)


class ConsolidationEngine:
    """Evaluates and consolidates memories post-execution."""

    def consolidate_session(
        self,
        session_id: str,
        goal: str,
        execution_success: bool,
        observations: list[str],
        data: dict[str, Any],
        project_id: str = "global",
    ) -> list[MemoryItem]:
        """
        Evaluate session outcome and promote verified insights to long-term memory.

        If execution_success is False, no long-term procedural or positive episodic
        memory is generated.
        """
        consolidated: list[MemoryItem] = []

        if not execution_success:
            logger.info(f"[ConsolidationEngine] Session {session_id} failed — skipping persistent memory consolidation.")
            return consolidated

        # 1. Promote session episode
        obs_text = " | ".join(observations[:3]) if observations else "No details"
        ep_content = f"Session {session_id} [{project_id}]: Completed goal '{goal}'. Summary: {obs_text[:200]}"

        episode = MemoryItem(
            type=MemoryType.EPISODIC,
            content=ep_content,
            importance=0.7,
            confidence=0.95,
            project_id=project_id,
            topic="session_history",
            provenance=MemoryProvenance(
                source_type=ProvenanceSource.RUNTIME_SESSION,
                source_id=session_id,
                confidence=0.95,
                verified=True,
            ),
            metadata={
                "session_id": session_id,
                "goal": goal,
                "success": True,
                "observations": observations,
            },
        )
        consolidated.append(episode)

        # 2. Promote procedural memory if a multi-step backend succeeded
        backend_used = data.get("backend")
        modified_files = data.get("modified_files")
        if backend_used and modified_files:
            proc_content = f"Verified procedure for '{goal[:40]}': modified {len(modified_files)} files via {backend_used}"
            proc = MemoryItem(
                type=MemoryType.PROCEDURAL,
                content=proc_content,
                importance=0.8,
                confidence=0.95,
                project_id=project_id,
                topic="successful_procedure",
                provenance=MemoryProvenance(
                    source_type=ProvenanceSource.EXECUTION_RESULT,
                    source_id=session_id,
                    confidence=0.95,
                    verified=True,
                ),
                metadata={
                    "backend": backend_used,
                    "modified_files": modified_files,
                },
            )
            consolidated.append(proc)

        logger.info(f"[ConsolidationEngine] Session {session_id} consolidated {len(consolidated)} verified memory item(s).")
        return consolidated
