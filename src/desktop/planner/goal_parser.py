"""
Goal Parser
Parses natural language goal strings into structured intent definitions and parameter dictionaries.
"""

from typing import Any

from .desktop_goal import DesktopGoal, GoalPriority


class GoalParser:
    """
    Parses user natural language goal inputs.
    """

    def parse(self, text: str, parameters: dict[str, Any] | None = None) -> DesktopGoal:
        """
        Parse natural language goal text into a DesktopGoal object.

        Args:
            text: Natural language string
            parameters: Optional initial parameters

        Returns:
            Parsed DesktopGoal
        """
        params = (parameters or {}).copy()
        clean_text = text.strip()

        # Extract explicit capability if formatted like capability:arg
        explicit_cap = None
        if ":" in clean_text and not clean_text.startswith("http"):
            parts = clean_text.split(":", 1)
            candidate_cap = parts[0].strip()
            if (
                candidate_cap.replace(".", "_").replace("-", "_").isidentifier()
                and len(parts) > 1
            ):
                explicit_cap = candidate_cap
                params["target"] = parts[1].strip()

        # Simple priority detection
        priority = GoalPriority.NORMAL
        if "urgent" in clean_text.lower() or "critical" in clean_text.lower():
            priority = GoalPriority.CRITICAL
        elif "high priority" in clean_text.lower():
            priority = GoalPriority.HIGH

        return DesktopGoal(
            goal=clean_text,
            priority=priority,
            explicit_capability=explicit_cap,
            parameters=params,
        )
