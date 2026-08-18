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

        # 3. Promote semantic research knowledge with provenance (G4 Provenance Memory)
        citations = data.get("citations") or []
        claims = data.get("claims") or []
        summary = data.get("summary") or (observations[0] if observations else "")
        topic = data.get("topic") or data.get("query") or goal

        if (citations or claims or backend_used == "research_engine") and summary:
            source_urls = [
                c.get("url") for c in citations if isinstance(c, dict) and c.get("url")
            ]
            cit_keys = [
                c.get("key") for c in citations if isinstance(c, dict) and c.get("key")
            ]
            conf_score = float(data.get("confidence_score", 0.95))

            sem_content = f"Research findings on '{topic}': {summary}"
            sem_item = MemoryItem(
                type=MemoryType.SEMANTIC,
                content=sem_content,
                importance=0.85,
                confidence=conf_score,
                project_id=project_id,
                topic=f"research:{topic[:30]}",
                provenance=MemoryProvenance(
                    source_type=ProvenanceSource.EXECUTION_RESULT,
                    source_id=session_id,
                    confidence=conf_score,
                    verified=True,
                ),
                metadata={
                    "topic": topic,
                    "summary": summary,
                    "citations": citations,
                    "claims": claims,
                    "source_urls": source_urls,
                    "citation_keys": cit_keys,
                    "sources_count": len(citations),
                    "research_event_id": session_id,
                },
            )
            consolidated.append(sem_item)

        # 4. Promote multimodal perception records with provenance (Gate G5)
        vision_captures = data.get("vision_captures") or []
        grounding = data.get("grounding")
        transcripts = data.get("transcripts") or []

        if vision_captures or grounding or backend_used == "vision_engine":
            v_desc = (
                observations[0]
                if observations
                else f"Visual screen observation for: {goal}"
            )
            v_window = ""
            if isinstance(grounding, dict):
                v_window = grounding.get("window_title", "")
            elif vision_captures and isinstance(vision_captures[0], dict):
                v_window = vision_captures[0].get("window_title", "")

            vis_item = MemoryItem(
                type=MemoryType.SEMANTIC,
                content=f"Visual perception on '{goal}': {v_desc}",
                importance=0.80,
                confidence=0.92,
                project_id=project_id,
                topic=f"multimodal:vision:{goal[:25]}",
                provenance=MemoryProvenance(
                    source_type=ProvenanceSource.EXECUTION_RESULT,
                    source_id=session_id,
                    confidence=0.92,
                    verified=True,
                ),
                metadata={
                    "modality": "vision",
                    "device_id": "screen_capture",
                    "goal": goal,
                    "window_title": v_window,
                    "grounding": grounding,
                    "vision_captures": vision_captures,
                    "backend": backend_used,
                    "session_id": session_id,
                },
            )
            consolidated.append(vis_item)

        if transcripts or backend_used == "voice_engine":
            t_text = (
                transcripts[0].get("transcript", "")
                if transcripts and isinstance(transcripts[0], dict)
                else (observations[0] if observations else goal)
            )
            voice_item = MemoryItem(
                type=MemoryType.SEMANTIC,
                content=f"Voice interaction on '{goal}': {t_text}",
                importance=0.80,
                confidence=0.90,
                project_id=project_id,
                topic=f"multimodal:voice:{goal[:25]}",
                provenance=MemoryProvenance(
                    source_type=ProvenanceSource.EXECUTION_RESULT,
                    source_id=session_id,
                    confidence=0.90,
                    verified=True,
                ),
                metadata={
                    "modality": "voice",
                    "device_id": "microphone",
                    "goal": goal,
                    "transcripts": transcripts,
                    "backend": backend_used,
                    "session_id": session_id,
                },
            )
            consolidated.append(voice_item)

        # 5. Promote Daemon & Scheduler Routine to Semantic Memory
        job_id = data.get("job_id")
        run_id = data.get("run_id")
        if job_id or backend_used in ("daemon_engine", "Scheduler Engine"):
            daemon_item = MemoryItem(
                type=MemoryType.SEMANTIC,
                content=f"Daemon automation registered for '{goal}': [Job: {job_id or 'routine'}, Run: {run_id or 'scheduled'}]",
                importance=0.85,
                confidence=0.95,
                project_id=project_id,
                topic=f"daemon:automation:{goal[:25]}",
                provenance=MemoryProvenance(
                    source_type=ProvenanceSource.EXECUTION_RESULT,
                    source_id=session_id,
                    confidence=0.95,
                    verified=True,
                ),
                metadata={
                    "domain": "daemon",
                    "job_id": job_id,
                    "run_id": run_id,
                    "goal": goal,
                    "backend": backend_used,
                    "session_id": session_id,
                },
            )
            consolidated.append(daemon_item)

        logger.info(
            f"[ConsolidationEngine] Session {session_id} consolidated {len(consolidated)} verified memory item(s)."
        )
        return consolidated
