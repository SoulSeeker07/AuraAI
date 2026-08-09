"""
Procedural Memory Subsystem
Location: src/memory/procedural_memory.py

Stores successful task execution procedures and workflow patterns
("When goal is X, steps [S1, S2, S3] yielded success").

Guardrail Rule:
    Only verified successful workflows can be saved as procedural memory.
"""

from .models import MemoryItem, MemoryProvenance, MemoryType, ProvenanceSource


class ProceduralMemoryStore:
    """Manages procedural workflow memories."""

    def record_procedure(
        self,
        goal_pattern: str,
        steps: list[str],
        successful_backend: str,
        session_id: str = "",
        project_id: str = "global",
        confidence: float = 0.95,
    ) -> MemoryItem:
        """
        Record a verified successful workflow procedure.
        """
        steps_str = " -> ".join(steps)
        content = f"Workflow for '{goal_pattern}': Steps [{steps_str}] via backend '{successful_backend}'"

        return MemoryItem(
            type=MemoryType.PROCEDURAL,
            content=content,
            importance=0.8,
            confidence=confidence,
            project_id=project_id,
            topic=f"workflow_{goal_pattern.lower().replace(' ', '_')[:30]}",
            provenance=MemoryProvenance(
                source_type=ProvenanceSource.EXECUTION_RESULT,
                source_id=session_id,
                confidence=confidence,
                verified=True,
            ),
            metadata={
                "goal_pattern": goal_pattern,
                "steps": steps,
                "successful_backend": successful_backend,
            },
        )
