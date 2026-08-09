"""
M19.2 Autonomy Mode & Risk Classification
=========================================
Location: src/core/orchestration/autonomy_mode.py

Defines system autonomy levels (ASK, ASSISTED, AUTONOMOUS) and deterministic action risk classification.
"""

from __future__ import annotations

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
