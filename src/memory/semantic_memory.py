"""
Semantic Memory Subsystem
Location: src/memory/semantic_memory.py

Stores conceptual knowledge and relationships as subject-relation-object triplets
(e.g., "AuraAI" -> "uses" -> "Python", "MasterOrchestrator" -> "part_of" -> "AuraAI").
"""

from .models import MemoryItem, MemoryProvenance, MemoryType, ProvenanceSource


class SemanticMemoryStore:
    """Manages conceptual knowledge and entity relationships."""

    def create_relation_memory(
        self,
        subject: str,
        relation: str,
        obj: str,
        project_id: str = "global",
        confidence: float = 0.9,
    ) -> MemoryItem:
        """Create a semantic relationship memory item."""
        content = f"{subject} {relation} {obj}"
        topic = f"relation_{subject.lower().replace(' ', '_')}"

        return MemoryItem(
            type=MemoryType.SEMANTIC,
            content=content,
            importance=0.7,
            confidence=confidence,
            project_id=project_id,
            topic=topic,
            provenance=MemoryProvenance(
                source_type=ProvenanceSource.USER_EXPLICIT,
                confidence=confidence,
                verified=True,
            ),
            metadata={
                "subject": subject,
                "relation": relation,
                "object": obj,
            },
        )
