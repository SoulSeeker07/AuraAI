"""
Layer 3: Capability Selector
============================

Converts goals into capabilities.

Example:
    Goal: Open YouTube in Chrome

    Capability Selector:
        Desktop: Launch Chrome
        Browser: Navigate
        Verification: Confirm page

Now Groq knows exactly what tools exist.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .goal_analyzer import GoalAnalysis

logger = logging.getLogger(__name__)


@dataclass
class CapabilityRequirement:
    """A capability required to accomplish a goal."""

    capability: str  # 'desktop', 'browser', 'research', 'engineering', 'memory', 'voice', 'provider'
    action: str
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "action": self.action,
            "description": self.description,
            "parameters": self.parameters,
        }


@dataclass
class CapabilitySelection:
    """The result of selecting capabilities for a goal."""

    capabilities: list[CapabilityRequirement] = field(default_factory=list)
    required_engines: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "capabilities": [c.to_dict() for c in self.capabilities],
            "required_engines": self.required_engines,
        }


class CapabilitySelector:
    """
    Converts goals into concrete capability requirements.

    This tells Groq exactly what tools exist for the task.
    """

    def select(self, goal_analysis: GoalAnalysis) -> CapabilitySelection:
        """
        Select capabilities required to accomplish the analyzed goals.

        Args:
            goal_analysis: The GoalAnalysis from the Goal Analyzer.

        Returns:
            CapabilitySelection with concrete capability requirements.
        """
        selection = CapabilitySelection()
        modifiers = goal_analysis.modifiers

        # ── Browser navigation ──────────────────────────────────────────────
        if modifiers.get("site") and modifiers.get("browser"):
            selection.capabilities.extend(
                [
                    CapabilityRequirement(
                        capability="desktop",
                        action="launch_application",
                        description=f"Launch {modifiers['browser']}",
                        parameters={"application": modifiers["browser"]},
                    ),
                    CapabilityRequirement(
                        capability="browser",
                        action="navigate",
                        description=f"Navigate to {modifiers['site']}",
                        parameters={"url": modifiers.get("url", "")},
                    ),
                    CapabilityRequirement(
                        capability="browser",
                        action="verify",
                        description=f"Verify {modifiers['site']} loaded",
                        parameters={"expect": modifiers["site"]},
                    ),
                ]
            )
            selection.required_engines = ["desktop", "browser"]

        # ── App launch ──────────────────────────────────────────────────────
        elif modifiers.get("app"):
            selection.capabilities.extend(
                [
                    CapabilityRequirement(
                        capability="desktop",
                        action="check_running",
                        description=f"Check if {modifiers['app']} is running",
                        parameters={"application": modifiers["app"]},
                    ),
                    CapabilityRequirement(
                        capability="desktop",
                        action="launch_application",
                        description=f"Launch {modifiers['app']}",
                        parameters={
                            "application": modifiers["app"],
                            "new_instance": modifiers.get("new_instance", False),
                        },
                    ),
                    CapabilityRequirement(
                        capability="desktop",
                        action="verify_window",
                        description=f"Verify {modifiers['app']} window exists",
                        parameters={"application": modifiers["app"]},
                    ),
                ]
            )
            selection.required_engines = ["desktop"]

        # ── Research ────────────────────────────────────────────────────────
        elif modifiers.get("research_topic"):
            selection.capabilities.extend(
                [
                    CapabilityRequirement(
                        capability="research",
                        action="search",
                        description=f"Search for {modifiers['research_topic']}",
                        parameters={"query": modifiers["research_topic"]},
                    ),
                    CapabilityRequirement(
                        capability="provider",
                        action="synthesize",
                        description="Synthesize research findings",
                        parameters={"task": "synthesize"},
                    ),
                ]
            )
            selection.required_engines = ["research", "provider"]

        # ── Engineering ─────────────────────────────────────────────────────
        elif modifiers.get("engineering"):
            selection.capabilities.extend(
                [
                    CapabilityRequirement(
                        capability="filesystem",
                        action="inspect_workspace",
                        description="Inspect workspace structure",
                    ),
                    CapabilityRequirement(
                        capability="engineering",
                        action="execute",
                        description=f"Execute: {modifiers.get('task', '')}",
                        parameters={"task": modifiers.get("task", "")},
                    ),
                    CapabilityRequirement(
                        capability="engineering",
                        action="verify",
                        description="Verify engineering result",
                    ),
                ]
            )
            selection.required_engines = ["engineering", "filesystem"]

        # ── Session summary ─────────────────────────────────────────────────
        elif modifiers.get("session_summary"):
            selection.capabilities.extend(
                [
                    CapabilityRequirement(
                        capability="memory",
                        action="read_session_history",
                        description="Read session history",
                    ),
                    CapabilityRequirement(
                        capability="provider",
                        action="summarize",
                        description="Generate session summary",
                    ),
                ]
            )
            selection.required_engines = ["memory", "provider"]

        # ── Memory operations ───────────────────────────────────────────────
        elif modifiers.get("memory_op"):
            op = modifiers["memory_op"]
            selection.capabilities.append(
                CapabilityRequirement(
                    capability="memory",
                    action="search" if op == "recall" else "remember",
                    description=f"{'Search' if op == 'recall' else 'Store'} memory",
                    parameters={"query": goal_analysis.original_input},
                )
            )
            selection.required_engines = ["memory"]

        # ── Chat / general ──────────────────────────────────────────────────
        else:
            selection.capabilities.append(
                CapabilityRequirement(
                    capability="provider",
                    action="chat",
                    description="Generate conversational response",
                    parameters={"message": goal_analysis.original_input},
                )
            )
            selection.required_engines = ["provider"]

        logger.info(
            f"CapabilitySelector selected: {selection.required_engines} "
            f"({len(selection.capabilities)} requirements)"
        )

        return selection


__all__ = ["CapabilitySelector", "CapabilitySelection", "CapabilityRequirement"]