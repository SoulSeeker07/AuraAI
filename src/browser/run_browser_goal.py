"""
run_browser_goal.py

The single public entry point for browser goals in Aura.
Checks Tier 1 shortcuts first, then dispatches to the tool-calling agent loop.
"""

from __future__ import annotations

from typing import Any, Dict

from browser.agent_loop import run_goal
from browser.tier1_shortcuts import try_shortcut


def run_browser_goal(goal: str, max_steps: int = 20) -> Dict[str, Any]:
    shortcut_result = try_shortcut(goal)
    if shortcut_result:
        return shortcut_result

    return run_goal(goal=goal, max_steps=max_steps)


def format_for_chat(result: Dict[str, Any], goal: str) -> str:
    """Turn a result dict into a clean, concise response for Aura conversation engine."""
    status = result.get("status")
    summary = result.get("summary") or f"Completed request: {goal}"
    screenshot_path = result.get("screenshot_path")
    screenshot_suffix = f"\n\n📸 **Verification Screenshot**: `{screenshot_path}`" if screenshot_path else ""

    if status == "SUCCESS":
        return f"{summary}{screenshot_suffix}"

    if status == "REQUIRE_AUTH_TICKET":
        return summary or "Action blocked pending confirmation."

    if status == "ASK_USER":
        return f"Needs Input: {summary}{screenshot_suffix}"

    if status == "HAND_BACK_TO_USER":
        return f"Security Check: {summary}{screenshot_suffix}"

    if status == "NO_PAUSED_SESSION":
        return summary or "No paused browser session found."

    if status == "INVALID_TICKET":
        return summary or "Invalid or expired ticket."

    return f"{summary or f'Stopped ({status})'}{screenshot_suffix}"
