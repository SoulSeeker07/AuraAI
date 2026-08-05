"""
Browser Goal Data Model
Location: src/browser/planner/browser_goal.py

Represents a high-level page goal rather than low-level UI clicks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BrowserGoal:
    """
    Structured representation of a page goal.
    
    Expresses intent and parameters without specifying exact DOM clicks/selectors.
    """
    site: str
    intent: str  # e.g., "profile", "search", "navigate", "feed", "check_auth"
    target_url: str = ""
    auth_required: bool = False
    parameters: dict[str, Any] = field(default_factory=dict)
    fallback_prompt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "site": self.site,
            "intent": self.intent,
            "target_url": self.target_url,
            "auth_required": self.auth_required,
            "parameters": self.parameters,
            "fallback_prompt": self.fallback_prompt,
        }
