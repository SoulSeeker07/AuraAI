"""
Layer 0: Context Manager
========================

Runs BEFORE Groq. Collects everything Aura already knows
so Groq doesn't have to guess.

Context includes:
    * Conversation history
    * Pending questions
    * Developer mode state
    * Runtime session
    * Current project
    * Current folder
    * Current apps
    * Browser tabs
    * Focused window
    * Current selection
    * Memory facts
    * Learned behaviors

Think of it as Aura's RAM.
Without it, Groq reasons with incomplete information.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ContextSnapshot:
    """A snapshot of everything Aura knows at a point in time."""

    conversation: list[dict[str, Any]] = field(default_factory=list)
    pending_question: dict[str, Any] | None = None
    developer_mode: bool = False
    runtime_session: dict[str, Any] = field(default_factory=dict)
    current_project: str = ""
    current_folder: str = ""
    current_apps: list[str] = field(default_factory=list)
    browser_tabs: list[dict[str, Any]] = field(default_factory=list)
    focused_window: str = ""
    current_selection: str = ""
    memory_facts: list[dict[str, Any]] = field(default_factory=list)
    learned_behaviors: list[dict[str, Any]] = field(default_factory=list)
    workspace_info: dict[str, Any] = field(default_factory=dict)
    llm_enabled: bool = False
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation": self.conversation,
            "pending_question": self.pending_question,
            "developer_mode": self.developer_mode,
            "runtime_session": self.runtime_session,
            "current_project": self.current_project,
            "current_folder": self.current_folder,
            "current_apps": self.current_apps,
            "browser_tabs": self.browser_tabs,
            "focused_window": self.focused_window,
            "current_selection": self.current_selection,
            "memory_facts": self.memory_facts,
            "learned_behaviors": self.learned_behaviors,
            "workspace_info": self.workspace_info,
            "llm_enabled": self.llm_enabled,
            "timestamp": self.timestamp,
        }

    def summarize(self) -> str:
        """Build a compact text summary for the LLM."""
        parts: list[str] = []

        if self.current_project:
            parts.append(f"Project: {self.current_project}")
        if self.current_folder:
            parts.append(f"Folder: {self.current_folder}")
        if self.focused_window:
            parts.append(f"Focused Window: {self.focused_window}")
        if self.current_apps:
            parts.append(f"Running Apps: {', '.join(self.current_apps[:5])}")
        if self.browser_tabs:
            tabs = [t.get("title", t.get("url", "tab")) for t in self.browser_tabs[:5]]
            parts.append(f"Browser Tabs: {', '.join(tabs)}")
        if self.memory_facts:
            facts = [f.get("value", "") for f in self.memory_facts[:5]]
            parts.append(f"Memory: {', '.join(facts)}")
        if self.learned_behaviors:
            behaviors = [b.get("trigger", "") for b in self.learned_behaviors[:3]]
            parts.append(f"Learned Behaviors: {', '.join(behaviors)}")
        if self.pending_question:
            parts.append(
                f"Pending Question: {self.pending_question.get('question', '')}"
            )
        if self.developer_mode:
            parts.append("Developer Mode: ON")

        return "\n".join(parts) if parts else "No context available."


class ContextManager:
    """
    Collects everything Aura already knows before Groq reasons.

    This is Aura's RAM — it runs before the DMM so Groq
    doesn't have to guess about the current state.
    """

    def __init__(
        self,
        memory: Any | None = None,
        workspace: Any | None = None,
        conversation_engine: Any | None = None,
    ):
        self.memory = memory
        self.workspace = workspace
        self.conversation_engine = conversation_engine

    def collect(
        self, user_input: str, extra: dict[str, Any] | None = None
    ) -> ContextSnapshot:
        """
        Collect all available context into a snapshot.

        Args:
            user_input: The user's current request.
            extra: Additional context from the caller.

        Returns:
            ContextSnapshot with everything Aura knows.
        """
        extra = extra or {}
        snapshot = ContextSnapshot()

        # ── Conversation history ────────────────────────────────────────────
        if self.conversation_engine is not None:
            try:
                history = self.conversation_engine.get_recent_history(limit=10)
                snapshot.conversation = history
            except Exception as e:
                logger.debug(f"Conversation history unavailable: {e}")

        # ── Pending question ────────────────────────────────────────────────
        if self.memory is not None:
            try:
                pending = self.memory.get_pending_question()
                if pending:
                    snapshot.pending_question = {
                        "slot": pending.get("slot", ""),
                        "type": pending.get("type", ""),
                        "expected": pending.get("expected", ""),
                    }
            except Exception as e:
                logger.debug(f"Pending question unavailable: {e}")

        # ── Memory facts ────────────────────────────────────────────────────
        if self.memory is not None:
            try:
                facts = self.memory.search(user_input)
                snapshot.memory_facts = [
                    {"category": f.category, "key": f.key, "value": f.value}
                    for f in facts[:10]
                ]
            except Exception as e:
                logger.debug(f"Memory facts unavailable: {e}")

        # ─ Workspace info ───────────────────────────────────────────────────
        if self.workspace is not None:
            try:
                if hasattr(self.workspace, "get_workspace_info"):
                    snapshot.workspace_info = self.workspace.get_workspace_info()
                elif isinstance(self.workspace, dict):
                    snapshot.workspace_info = self.workspace
                snapshot.current_project = snapshot.workspace_info.get(
                    "project", ""
                ) or str(
                    self.workspace.get("path", "")
                    if isinstance(self.workspace, dict)
                    else ""
                )
                snapshot.current_folder = snapshot.workspace_info.get("path", "")
            except Exception as e:
                logger.debug(f"Workspace info unavailable: {e}")

        # ── Extra context from caller ────────────────────────────────────────
        for key, value in extra.items():
            if hasattr(snapshot, key):
                setattr(snapshot, key, value)

        # ── Timestamp ───────────────────────────────────────────────────────
        from datetime import datetime

        snapshot.timestamp = datetime.now().isoformat()

        logger.info(
            f"ContextManager collected: project={snapshot.current_project}, "
            f"facts={len(snapshot.memory_facts)}, "
            f"behaviors={len(snapshot.learned_behaviors)}, "
            f"apps={len(snapshot.current_apps)}"
        )

        return snapshot


__all__ = ["ContextManager", "ContextSnapshot"]
