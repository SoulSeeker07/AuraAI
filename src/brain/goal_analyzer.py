"""
Layer 2: Goal Analyzer
======================

This is where most assistants stop. Aura shouldn't.

The Goal Analyzer decomposes a user request into goals and sub-goals.

Example:
    User: "Open YouTube in Chrome"

    Goal Analyzer:
        Goal: Open YouTube
        Sub Goals:
            - Ensure Chrome exists
            - Focus browser
            - Navigate
            - Verify page

Notice: No mention of Browser Intent. Only goals.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Goal:
    """A single goal derived from user input."""

    description: str
    sub_goals: list[str] = field(default_factory=list)
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "sub_goals": self.sub_goals,
            "priority": self.priority,
            "metadata": self.metadata,
        }


@dataclass
class GoalAnalysis:
    """The result of analyzing a user request into goals."""

    primary_goal: str
    goals: list[Goal] = field(default_factory=list)
    modifiers: dict[str, Any] = field(default_factory=dict)
    original_input: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_goal": self.primary_goal,
            "goals": [g.to_dict() for g in self.goals],
            "modifiers": self.modifiers,
            "original_input": self.original_input,
        }


class GoalAnalyzer:
    """
    Decomposes user requests into goals and sub-goals.

    This is NOT intent classification. It's goal understanding.
    """

    def analyze(
        self, user_input: str, context: dict[str, Any] | None = None
    ) -> GoalAnalysis:
        """
        Analyze a user request into structured goals.

        Args:
            user_input: The user's raw text request.
            context: Optional context (world state, memory, etc.)

        Returns:
            GoalAnalysis with primary goal and sub-goals.
        """
        context = context or {}
        text = user_input.strip()
        text_lower = text.lower()

        # ── Browser navigation: "Open YouTube in Chrome" ────────────────────
        if any(
            site in text_lower
            for site in [
                "youtube",
                "github",
                "gmail",
                "google",
                "twitter",
                "reddit",
                "linkedin",
                "facebook",
                "instagram",
                "amazon",
                "stackoverflow",
                "netflix",
            ]
        ) and any(
            w in text_lower
            for w in [
                "open",
                "go to",
                "navigate",
                "browse",
                "visit",
                "take me to",
                "load",
            ]
        ):
            return self._analyze_browser_navigation(text, text_lower)

        # ── App launch: "Open Notepad" / "Open another Notepad" ─────────────
        if any(
            app in text_lower
            for app in [
                "notepad",
                "chrome",
                "edge",
                "firefox",
                "spotify",
                "calculator",
                "calc",
                "vscode",
                "vs code",
                "visual studio code",
                "paint",
                "mspaint",
                "word",
                "excel",
                "powerpoint",
            ]
        ):
            return self._analyze_app_launch(text, text_lower)

        # ── Research: "Research X" / "Search for X" ─────────────────────────
        if any(
            ind in text_lower
            for ind in [
                "research",
                "search for",
                "look up",
                "find information",
                "find out",
            ]
        ):
            return self._analyze_research(text, text_lower)

        # ── Engineering: "Implement X" / "Fix bug" ──────────────────────────
        if any(
            ind in text_lower
            for ind in [
                "implement",
                "refactor",
                "fix bug",
                "unit test",
                "debug",
                "write script",
                "build feature",
                "create function",
            ]
        ):
            return self._analyze_engineering(text, text_lower)

        # ── Session summary ─────────────────────────────────────────────────
        if any(
            w in text_lower
            for w in [
                "summarize today's session",
                "summarize session",
                "session summary",
            ]
        ):
            return self._analyze_session_summary(text, text_lower)

        # ── Memory operations ───────────────────────────────────────────────
        if any(
            w in text_lower
            for w in [
                "remember",
                "what do you know",
                "my facts",
                "preferences",
                "profile",
            ]
        ):
            return self._analyze_memory(text, text_lower)

        # ── Chat / general conversation ─────────────────────────────────────
        return self._analyze_chat(text, text_lower)

    # ── Specific Analyzers ──────────────────────────────────────────────────

    def _analyze_browser_navigation(self, text: str, text_lower: str) -> GoalAnalysis:
        """Analyze browser navigation requests."""
        site = ""
        for s in [
            "youtube",
            "github",
            "gmail",
            "google",
            "twitter",
            "reddit",
            "linkedin",
            "facebook",
            "instagram",
            "amazon",
            "stackoverflow",
            "netflix",
        ]:
            if s in text_lower:
                site = s
                break

        # Detect browser preference
        browser = "chrome"
        for b in ["chrome", "edge", "firefox", "opera", "brave"]:
            if b in text_lower:
                browser = b
                break

        goals = [
            Goal(
                description=f"Open {site}",
                sub_goals=[
                    f"Ensure {browser} exists",
                    f"Focus {browser}",
                    f"Navigate to {site}",
                    "Verify page loaded",
                ],
                priority=1,
                metadata={"site": site, "browser": browser},
            )
        ]

        return GoalAnalysis(
            primary_goal=f"Open {site} in {browser}",
            goals=goals,
            modifiers={
                "site": site,
                "browser": browser,
                "url": f"https://www.{site}.com",
            },
            original_input=text,
        )

    def _analyze_app_launch(self, text: str, text_lower: str) -> GoalAnalysis:
        """Analyze application launch requests."""
        app = ""
        for a in [
            "notepad",
            "chrome",
            "edge",
            "firefox",
            "spotify",
            "calculator",
            "calc",
            "vscode",
            "vs code",
            "visual studio code",
            "paint",
            "mspaint",
            "word",
            "excel",
            "powerpoint",
        ]:
            if a in text_lower:
                app = a
                break

        new_instance = "another" in text_lower or "new instance" in text_lower

        goals = [
            Goal(
                description=f"Launch {app}",
                sub_goals=[
                    f"Check if {app} is running",
                    f"Launch {app}" + (" (new instance)" if new_instance else ""),
                    f"Verify {app} window exists",
                ],
                priority=1,
                metadata={"app": app, "new_instance": new_instance},
            )
        ]

        return GoalAnalysis(
            primary_goal=f"Launch {app}",
            goals=goals,
            modifiers={"app": app, "new_instance": new_instance},
            original_input=text,
        )

    def _analyze_research(self, text: str, text_lower: str) -> GoalAnalysis:
        """Analyze research requests."""
        topic = text
        for ind in [
            "research",
            "search for",
            "look up",
            "find information",
            "find out",
        ]:
            if ind in text_lower:
                topic = text_lower.split(ind, 1)[1].strip()
                break

        goals = [
            Goal(
                description=f"Research: {topic}",
                sub_goals=[
                    "Search for relevant information",
                    "Synthesize findings",
                    "Verify results are relevant",
                ],
                priority=1,
                metadata={"topic": topic},
            )
        ]

        return GoalAnalysis(
            primary_goal=f"Research: {topic}",
            goals=goals,
            modifiers={"research_topic": topic},
            original_input=text,
        )

    def _analyze_engineering(self, text: str, text_lower: str) -> GoalAnalysis:
        """Analyze engineering/coding requests."""
        goals = [
            Goal(
                description=f"Engineering: {text}",
                sub_goals=[
                    "Inspect workspace structure",
                    "Execute engineering task",
                    "Verify result",
                ],
                priority=1,
                metadata={"task": text},
            )
        ]

        return GoalAnalysis(
            primary_goal=f"Engineering: {text}",
            goals=goals,
            modifiers={"engineering": True, "task": text},
            original_input=text,
        )

    def _analyze_session_summary(self, text: str, text_lower: str) -> GoalAnalysis:
        """Analyze session summary requests."""
        goals = [
            Goal(
                description="Summarize today's session",
                sub_goals=[
                    "Read session history",
                    "Generate session summary",
                ],
                priority=1,
            )
        ]

        return GoalAnalysis(
            primary_goal="Summarize today's session",
            goals=goals,
            modifiers={"session_summary": True},
            original_input=text,
        )

    def _analyze_memory(self, text: str, text_lower: str) -> GoalAnalysis:
        """Analyze memory operations."""
        is_recall = any(
            w in text_lower
            for w in ["what do you know", "my facts", "preferences", "profile"]
        )
        is_write = text_lower.startswith("remember")

        op = "recall" if is_recall else ("write" if is_write else "recall")

        goals = [
            Goal(
                description=f"Memory {op}: {text}",
                sub_goals=[f"{'Search' if op == 'recall' else 'Store'} memory"],
                priority=1,
                metadata={"operation": op},
            )
        ]

        return GoalAnalysis(
            primary_goal=f"Memory {op}",
            goals=goals,
            modifiers={"memory_op": op},
            original_input=text,
        )

    def _analyze_chat(self, text: str, text_lower: str) -> GoalAnalysis:
        """Analyze general conversation."""
        goals = [
            Goal(
                description=f"Respond to: {text}",
                sub_goals=["Generate conversational response"],
                priority=1,
            )
        ]

        return GoalAnalysis(
            primary_goal=f"Respond to: {text}",
            goals=goals,
            modifiers={"chat": True},
            original_input=text,
        )


__all__ = ["GoalAnalyzer", "GoalAnalysis", "Goal"]
