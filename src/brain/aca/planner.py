"""
ACA Planner — Consumes DecisionContext, Produces ExecutionMap
==============================================================

This is where Groq should actually work.

Prompt:
    DecisionContext
      ↓
    Produce ONLY ExecutionMap JSON.
      ↓
    Nothing else.
    No chatting. No explanations. No code.
    Only execution maps.
"""

from __future__ import annotations

import logging
from typing import Any

from ..schemas.decision_context import DecisionContext
from ..schemas.execution_map import ExecutionMap, ExecutionStep, FallbackOption

logger = logging.getLogger(__name__)


class ACAPlanner:
    """
    Converts a DecisionContext into a structured ExecutionMap.

    This is the ONLY thing the Planner does.
    """

    def __init__(self, llm_client: Any | None = None):
        self.llm_client = llm_client

    def create_plan(self, decision_context: DecisionContext) -> dict[str, Any]:
        """
        Create an ExecutionMap from a DecisionContext.

        Args:
            decision_context: The fused decision context.

        Returns:
            ExecutionMap as a dict.
        """
        # Use the objective/goal to build the map
        objective = decision_context.objective or decision_context.goal.description
        goal = decision_context.goal.description

        # ── Browser navigation ──────────────────────────────────────────────
        entities = [e.name.lower() for e in decision_context.entities]
        if any(site in objective.lower() for site in ["youtube", "github", "gmail", "google", "twitter", "reddit", "linkedin", "facebook", "instagram", "amazon"]):
            site = next(
                (s for s in ["youtube", "github", "gmail", "google", "twitter", "reddit", "linkedin", "facebook", "instagram", "amazon"] if s in objective.lower()),
                ""
            )
            browser = next(
                (b for b in ["chrome", "edge", "firefox", "opera", "brave"] if b in goal.lower()),
                "chrome"
            )
            from core.orchestration.task_decomposer import TaskDecomposer
            _, target_url, _ = TaskDecomposer()._resolve_browser_target(objective)
            if not target_url:
                target_url = f"https://www.{site}.com"
            return {
                "goal": goal,
                "capabilities": ["browser"],
                "steps": [
                    {"engine": "browser", "action": "navigate", "parameters": {"url": target_url}},
                    {"engine": "browser", "action": "verify", "parameters": {"expect": site}},
                ],
                "verification": [f"Navigation to {site} succeeded"],
                "fallbacks": [
                    {"trigger": "Navigation failed", "action": f"Retry navigating to {site}"},
                ],
                "expected_result": f"Browser displays {site}",
                "confidence": decision_context.confidence.overall,
            }

        # ── App launch ─────────────────────────────────────────────────────
        app = next(
            (e.name.lower() for e in decision_context.entities if e.entity_type in ("application", "unknown") and e.name.lower() in ["notepad", "chrome", "edge", "firefox", "spotify", "calculator", "calc", "vscode", "vs code", "visual studio code", "paint", "mspaint", "word", "excel", "powerpoint"]),
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
                "confidence": decision_context.confidence.overall,
            }

        # ── Chat / general ─────────────────────────────────────────────────
        return {
            "goal": goal,
            "capabilities": ["provider"],
            "steps": [
                {"engine": "provider", "action": "chat", "parameters": {"message": decision_context.raw_input}},
            ],
            "verification": ["Response generated"],
            "fallbacks": [],
            "expected_result": "A natural, helpful response",
            "confidence": decision_context.confidence.overall,
        }

    def set_llm_client(self, client: Any) -> None:
        """Set the LLM client for future Groq-based generation."""
        self.llm_client = client


__all__ = ["ACAPlanner"]