"""
Tests for M19.2 Autonomy Modes & Policy Engine
Location: tests/test_autonomy_hooks.py
"""

import pytest
from core.orchestration.autonomy_mode import (
    AutonomyLevel,
    ActionRisk,
    classify_action_risk,
    should_require_confirmation,
)
from core.orchestration.execution_policy import ExecutionPolicy, PolicyAction


def test_classify_action_risk():
    assert classify_action_risk("browser", "search") == ActionRisk.LOW
    assert classify_action_risk("engineering", "create_file") == ActionRisk.MEDIUM
    assert classify_action_risk("filesystem", "file.delete") == ActionRisk.HIGH
    assert classify_action_risk("browser", "checkout") == ActionRisk.CRITICAL
    assert classify_action_risk("desktop", "purchase", {"amount": 50}) == ActionRisk.CRITICAL


def test_should_require_confirmation_assisted():
    # ASSISTED (default): Low/Med auto, High/Critical prompt
    assert should_require_confirmation(AutonomyLevel.ASSISTED, ActionRisk.LOW) is False
    assert should_require_confirmation(AutonomyLevel.ASSISTED, ActionRisk.MEDIUM) is False
    assert should_require_confirmation(AutonomyLevel.ASSISTED, ActionRisk.HIGH) is True
    assert should_require_confirmation(AutonomyLevel.ASSISTED, ActionRisk.CRITICAL) is True


def test_should_require_confirmation_ask_and_autonomous():
    # ASK: Always prompt
    assert should_require_confirmation(AutonomyLevel.ASK, ActionRisk.LOW) is True
    assert should_require_confirmation(AutonomyLevel.ASK, ActionRisk.HIGH) is True

    # AUTONOMOUS: Low/Med/High auto, Critical prompt
    assert should_require_confirmation(AutonomyLevel.AUTONOMOUS, ActionRisk.LOW) is False
    assert should_require_confirmation(AutonomyLevel.AUTONOMOUS, ActionRisk.HIGH) is False
    assert should_require_confirmation(AutonomyLevel.AUTONOMOUS, ActionRisk.CRITICAL) is True


def test_execution_policy_autonomy_evaluation():
    policy = ExecutionPolicy()
    policy.set_autonomy_level(AutonomyLevel.ASSISTED)

    # Low risk action -> Approved
    d1 = policy.evaluate_action("browser", "search")
    assert d1.action == PolicyAction.LAUNCH_NEW

    # High risk action -> Blocked for user confirmation
    d2 = policy.evaluate_action("filesystem", "file.delete", {"path": "test.txt"})
    assert d2.action == PolicyAction.ASK_USER
    assert policy.has_pending_confirmation() is True
