"""
Memory Context Formatter for LLM Prompt Synthesis
Location: src/memory/context_formatter.py

Synthesizes ranked cognitive memories (Preferences, Project Directives, Procedural Workflows)
into token-capped, structured prompt sections for planning and conversation.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from .models import MemoryItem, MemoryType

logger = logging.getLogger(__name__)


class MemoryContextFormatter:
    """Formats recalled cognitive memories into structured, token-bounded prompt context."""

    def __init__(self, max_tokens: int = 400):
        self.max_tokens = max_tokens

    def format_planning_context(
        self,
        recalled_memories: List[MemoryItem],
        active_project: str = "global",
        include_provisional: bool = False,
    ) -> str:
        """
        Format recalled memories into structured <user_preferences>, <project_directives>,
        and <procedural_memory> blocks. Excludes SUPERSEDED and PROVISIONAL (unless explicitly requested).
        """
        if not recalled_memories:
            return ""

        confirmed_preferences: List[str] = []
        project_directives: List[str] = []
        procedural_insights: List[str] = []

        for mem in recalled_memories:
            status = mem.metadata.get("status", "CONFIRMED")
            if status == "SUPERSEDED":
                continue
            if status == "PROVISIONAL" and not include_provisional:
                continue

            if mem.type == MemoryType.PREFERENCE:
                confirmed_preferences.append(f"- {mem.content}")
            elif mem.type in (MemoryType.PROJECT, MemoryType.SEMANTIC) and mem.project_id != "global":
                project_directives.append(f"- [{mem.project_id}] {mem.content}")
            elif mem.type == MemoryType.PROCEDURAL:
                procedural_insights.append(f"- {mem.content}")

        sections = []

        if confirmed_preferences:
            pref_block = "\n".join(confirmed_preferences[:5])
            sections.append(f"<user_preferences>\n{pref_block}\n</user_preferences>")

        if project_directives:
            proj_block = "\n".join(project_directives[:5])
            sections.append(f"<project_context project=\"{active_project}\">\n{proj_block}\n</project_context>")

        if procedural_insights:
            proc_block = "\n".join(procedural_insights[:3])
            sections.append(f"<verified_procedures>\n{proc_block}\n</verified_procedures>")

        if not sections:
            return ""

        full_context = "\n\n".join(sections)
        # Approximate token bounding (4 chars ~= 1 token)
        char_limit = self.max_tokens * 4
        if len(full_context) > char_limit:
            full_context = full_context[:char_limit] + "\n... [Context truncated for length]"

        return full_context
