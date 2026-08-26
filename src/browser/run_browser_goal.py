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
    """Turn a result dict into the standard format for Aura conversation engine."""
    status = result.get("status")
    if status == "SUCCESS":
        lines = [
            "🌐 **Aura Autonomous Browser Engine**\n",
            f"**Goal:** `{goal}`",
            f"**Result:** {result.get('summary')}",
        ]
        if result.get("url"):
            lines.append(f"**Page:** {result.get('url')}")
        if result.get("steps"):
            lines.append("\n### ⚡ Executed Browser Actions:")
            for s in result.get("steps", []):
                tool = s.get("tool", "action")
                args = s.get("args", {})
                lines.append(f"- **{tool}**: `{args}`")
        return "\n".join(lines)

    if status == "REQUIRE_AUTH_TICKET":
        return result.get("summary", "🛑 Action blocked pending confirmation.")

    if status == "ASK_USER":
        return f"⏸️ **Needs Input:**\n\n{result.get('summary')}\n**Page:** {result.get('url', 'N/A')}"

    if status == "HAND_BACK_TO_USER":
        return f"🔒 **Security / CAPTCHA Check:**\n\n{result.get('summary')}"

    if status == "NO_PAUSED_SESSION":
        return result.get("summary", "No paused browser session found.")

    if status == "INVALID_TICKET":
        return f"❌ {result.get('summary', 'Invalid or expired ticket.')}"

    return f"⚠️ Stopped ({status}): {result.get('summary', 'Unknown error')}"
