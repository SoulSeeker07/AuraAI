"""
Strategy Engine — Chooses the Best Strategy
===========================================

Formerly "ACAPlanner". A Planner implies A → B → C.
But Aura needs to choose strategies.

Example:
    User: "Summarize this PDF"

    Strategy 1: OCR → LLM
    Strategy 2: PDF Parser → LLM
    Strategy 3: Vision → OCR → LLM

The Strategy Engine decides which strategy to use.
"""

from __future__ import annotations

import logging
from typing import Any

from ..schemas.thought import Thought

logger = logging.getLogger(__name__)


class StrategyEngine:
    """
    Chooses the best strategy and produces an ExecutionMap.

    This is the ONLY thing that consumes a Thought.
    """

    def __init__(self, llm_client: Any | None = None):
        self.llm_client = llm_client

    def create_plan(self, thought: Thought) -> dict[str, Any]:
        """
        Choose a strategy and produce an ExecutionMap.

        Args:
            thought: Aura's internal reasoning state.

        Returns:
            ExecutionMap as a dict.
        """
        objective = thought.objective or thought.goal.description
        goal = thought.goal.description

        # ── Browser navigation strategy ─────────────────────────────────────
        if any(site in objective.lower() for site in ["youtube", "github", "gmail", "google", "twitter", "reddit", "linkedin", "facebook", "instagram", "amazon"]):
            site = next(
                (s for s in ["youtube", "github", "gmail", "google", "twitter", "reddit", "linkedin", "facebook", "instagram", "amazon"] if s in objective.lower()),
                ""
            )
            browser = next(
                (b for b in ["chrome", "edge", "firefox", "opera", "brave"] if b in goal.lower()),
                "chrome"
            )
            return {
                "goal": goal,
                "capabilities": ["desktop", "browser"],
                "steps": [
                    {"engine": "desktop", "action": "check_running", "parameters": {"application": browser}},
                    {"engine": "desktop", "action": "launch_application", "parameters": {"application": browser}},
                    {"engine": "browser", "action": "navigate", "parameters": {"url": f"https://www.{site}.com"}},
                    {"engine": "browser", "action": "verify", "parameters": {"expect": site}},
                ],
                "verification": [f"{browser} window exists", f"Navigation to {site} succeeded"],
                "fallbacks": [
                    {"trigger": f"{browser} not found", "action": f"Try launching {browser} via alternate path"},
                    {"trigger": "Navigation failed", "action": f"Retry navigating to {site}"},
                ],
                "expected_result": f"{browser} displays the {site} homepage",
                "confidence": thought.confidence.overall,
            }

        # ── App launch strategy ─────────────────────────────────────────────
        app = next(
            (e.name.lower() for e in thought.entities if e.name.lower() in ["notepad", "chrome", "edge", "firefox", "spotify", "calculator", "calc", "vscode", "vs code", "visual studio code", "paint", "mspaint", "word", "excel", "powerpoint"]),
            ""
        )
        if app:
            return {
                "goal": goal,
                "capabilities": ["desktop"],
                "steps": [
                    {"engine": "desktop", "action": "check_running", "parameters": {"application": app}},
                    {"engine": "desktop", "action": "launch_application", "parameters": {"application": app}},
                    {"engine": "desktop", "action": "verify_window", "parameters": {"application": app}},
                ],
                "verification": [f"{app} window exists"],
                "fallbacks": [
                    {"trigger": f"{app} not found", "action": "Search for alternate executable path"},
                ],
                "expected_result": f"{app} window is visible",
                "confidence": thought.confidence.overall,
            }

        # ── Chat / general strategy ─────────────────────────────────────────
        return {
            "goal": goal,
            "capabilities": ["provider"],
            "steps": [
                {"engine": "provider", "action": "chat", "parameters": {"message": thought.raw_input}},
            ],
            "verification": ["Response generated"],
            "fallbacks": [],
            "expected_result": "A natural, helpful response",
            "confidence": thought.confidence.overall,
        }

    def set_llm_client(self, client: Any) -> None:
        """Set the LLM client for future Groq-based strategy selection."""
        self.llm_client = client


# Backward-compatible alias
ACAPlanner = StrategyEngine

__all__ = ["StrategyEngine", "ACAPlanner"]