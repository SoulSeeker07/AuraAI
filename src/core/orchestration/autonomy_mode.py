"""
M19.2 Autonomy Mode & Risk Classification
=========================================
Location: src/core/orchestration/autonomy_mode.py

Defines system autonomy levels (ASK, ASSISTED, AUTONOMOUS) and deterministic action risk classification.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any


class AutonomyLevel(str, Enum):
    """System-wide autonomy operating mode."""

    ASK = "ask"                # Confirm all actions before execution
    ASSISTED = "assisted"      # Execute low/medium risk actions; confirm high/critical risk (DEFAULT)
    AUTONOMOUS = "autonomous"  # Execute within granted boundaries; confirm critical risk only


class ActionRisk(str, Enum):
    """Risk severity classification of an execution action."""

    LOW = "low"            # Non-mutating or safe read-only operations
    MEDIUM = "medium"      # Standard creation, edit, or local UI navigation
    HIGH = "high"          # Destructive file actions, bulk edits, messaging, external state changes
    CRITICAL = "critical"  # Purchases, financial checkout, credential submission, key destruction


def classify_action_risk(engine: str, action: str, params: dict[str, Any] | None = None) -> ActionRisk:
    """
    Classify the risk level of an intended engine action deterministically.

    Args:
        engine: Target engine (desktop, browser, engineering, etc.).
        action: Specific action name (e.g., "file.delete", "checkout").
        params: Optional execution parameters.

    Returns:
        ActionRisk enum value.
    """
    action_lower = (action or "").lower()
    engine_lower = (engine or "").lower()
    params = params or {}

    # 1. Critical Risk Operations
    critical_keywords = ["checkout", "purchase", "pay", "buy", "credential", "password", "secret", "private_key"]
    if any(kw in action_lower for kw in critical_keywords) or any(kw in str(params).lower() for kw in critical_keywords):
        return ActionRisk.CRITICAL

    # 2. High Risk Operations
    high_keywords = [
        "delete", "remove", "drop", "truncate", "clear", "kill", "unlink",
        "bulk_delete", "send_message", "send_email", "post", "publish",
        "rmdir", "destroy", "format"
    ]
    if any(kw in action_lower for kw in high_keywords):
        return ActionRisk.HIGH

    # 2b. High-risk phrasing embedded in the execution parameters (intent text,
    #     app targets, or UI labels). Provider/chat-styled steps collapse to a
    #     generic action such as `open_app`, hiding the original intent in the
    #     action name — but the params keep the actual user wording. Phrase-based
    #     matching preserves innocuous chat (e.g. "what is format in excel?",
    #     "explain kill in linux") while blocking destructive imperatives such
    #     as "format drive C" or "kill all running processes".
    params_text = str(params).lower()
    high_risk_phrase_patterns = [
        r"\bformat\b.*\b(?:drive|disk|volume|partition|usb|flash|media)\b",
        r"\b(?:wipe|erase|purge)\b.*\b(?:all|everything|entire|drive|disk)\b",
        r"\bkill\b.*\b(?:all|every|process|processes|task|tasks|service|services)\b",
        r"\b(?:delete|remove|drop|destroy)\b.*\b(?:all|everything|every|entire)\b",
        r"\b(?:shutdown|reboot|halt)\b.*\b(?:all|everything|now|processes|services)\b",
        r"\b(?:logout|sign\s*out|signout)\b.*\b(?:all|every|now|sessions?)\b",
        r"\brm\s+-\s*rf\b",
    ]
    if any(re.search(pat, params_text) for pat in high_risk_phrase_patterns):
        return ActionRisk.HIGH

    # Check file modification risk
    if action_lower in ("file.delete", "file.remove", "directory.delete"):
        return ActionRisk.HIGH

    # 3. Medium Risk Operations
    medium_keywords = ["edit", "update", "modify", "write", "create", "launch", "open_app", "click", "input_text"]
    if any(kw in action_lower for kw in medium_keywords):
        return ActionRisk.MEDIUM

    # 4. Default Low Risk Operations (Reads, Searches, Observations)
    return ActionRisk.LOW


def should_require_confirmation(level: AutonomyLevel | str, risk: ActionRisk | str) -> bool:
    """
    Determine if user confirmation is required based on autonomy level and action risk.

    Args:
        level: Current system AutonomyLevel.
        risk: ActionRisk of the intended operation.

    Returns:
        True if user confirmation prompt is required before execution; False otherwise.
    """
    if isinstance(level, str):
        level = AutonomyLevel(level.lower())
    if isinstance(risk, str):
        risk = ActionRisk(risk.lower())

    if level == AutonomyLevel.ASK:
        return True

    if level == AutonomyLevel.ASSISTED:
        return risk in (ActionRisk.HIGH, ActionRisk.CRITICAL)

    if level == AutonomyLevel.AUTONOMOUS:
        return risk == ActionRisk.CRITICAL

    return True


__all__ = ["AutonomyLevel", "ActionRisk", "classify_action_risk", "should_require_confirmation"]
