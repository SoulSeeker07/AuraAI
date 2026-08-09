"""
Project Memory Isolation Subsystem
Location: src/memory/project_isolation.py

Manages project-scoped memory spaces (e.g., 'global', 'AuraAI', 'NetworkEngine').
Prevents cross-project memory contamination during recall while allowing fallback to global memories.
"""

from .models import MemoryItem


class ProjectMemoryFilter:
    """Filters memories based on project_id scoping rules."""

    def filter_for_project(
        self,
        memories: list[MemoryItem],
        active_project: str = "global",
        include_global: bool = True,
    ) -> list[MemoryItem]:
        """
        Filter memories for active project scope.

        If active_project is 'AuraAI' and include_global is True:
            Returns memories where project_id == 'AuraAI' OR project_id == 'global'.
        """
        if active_project == "global":
            return memories

        filtered = []
        for mem in memories:
            if mem.project_id == active_project:
                filtered.append(mem)
            elif include_global and mem.project_id == "global":
                filtered.append(mem)

        return filtered
