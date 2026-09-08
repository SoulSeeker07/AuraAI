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
    policy.set_autonomy_level(AutonomyLevel.ASSISTED)  # safe: leaks to current default ASSISTED — revisit if default changes

    # Low risk action -> Approved
    d1 = policy.evaluate_action("browser", "search")
    assert d1.action == PolicyAction.LAUNCH_NEW

    # High risk action -> Blocked for user confirmation
    d2 = policy.evaluate_action("filesystem", "file.delete", {"path": "test.txt"})
    assert d2.action == PolicyAction.ASK_USER
    assert policy.has_pending_confirmation() is True


def test_browser_critical_and_high_risk_capabilities_are_gated():
    """Verify that newly declared CRITICAL and HIGH risk browser/shopping capabilities are gated."""
    policy = ExecutionPolicy()

    # 1. Default ASSISTED mode:
    token_assisted = policy.set_autonomy_level(AutonomyLevel.ASSISTED)
    try:
        # Low risk -> Approved
        d_nav = policy.evaluate_action("browser", "browser.navigate", {"url": "https://example.com"})
        assert d_nav.action == PolicyAction.LAUNCH_NEW

        # Medium risk shopping cart add -> Approved without prompting under ASSISTED mode
        d_cart = policy.evaluate_action("browser", "shopping.cart.add", {"item_id": "item_456"})
        assert d_cart.action == PolicyAction.LAUNCH_NEW

        # High risk form submit -> Blocked (ASK_USER)
        d_submit = policy.evaluate_action("browser", "form.submit", {"selector": "#login"})
        assert d_submit.action == PolicyAction.ASK_USER

        # Critical risk checkout -> Blocked (ASK_USER)
        d_checkout = policy.evaluate_action("browser", "shopping.checkout", {"cart_id": "cart_123"})
        assert d_checkout.action == PolicyAction.ASK_USER

        # 2. AUTONOMOUS mode — token captured; reset in finally to prevent ContextVar leak
        token_autonomous = policy.set_autonomy_level(AutonomyLevel.AUTONOMOUS)
        try:
            # High risk -> Auto-approved in autonomous mode
            d_submit_auto = policy.evaluate_action("browser", "form.submit", {"selector": "#login"})
            assert d_submit_auto.action == PolicyAction.LAUNCH_NEW

            # Critical risk checkout -> STILL BLOCKED (ASK_USER) even in full AUTONOMOUS mode
            d_checkout_auto = policy.evaluate_action("browser", "shopping.checkout", {"cart_id": "cart_123"})
            assert d_checkout_auto.action == PolicyAction.ASK_USER
        finally:
            policy.reset_autonomy_level(token_autonomous)
    finally:
        policy.reset_autonomy_level(token_assisted)


@pytest.mark.asyncio
async def test_create_file_artifact_autonomy_override_contract(monkeypatch):
    """
    Assert the contract of the Day-1 provisional safety override:
    1. TaskDecomposer canonical risk for codeact.synthesize is ActionRisk.MEDIUM.
    2. AURA_PROVISIONAL_ARTIFACT_CONFIRM='1' forces ActionRisk.HIGH in UnifiedToolDispatcher.dispatch.
    3. AURA_PROVISIONAL_ARTIFACT_CONFIRM='0' restores canonical ActionRisk.MEDIUM parity.
    """
    from core.tools.unified_tool_dispatcher import UnifiedToolDispatcher
    from core.orchestration.task_decomposer import TaskDecomposer

    args = {"goal": "generate shopping list excel for me", "output_filename": "shopping.xlsx"}

    # 1. Verify TaskDecomposer canonical baseline is ActionRisk.MEDIUM
    combined_goal = f"{args['goal']} {args['output_filename']}"
    subtask = TaskDecomposer()._detect_artifact_synthesis(combined_goal.lower(), combined_goal)
    assert subtask is not None
    assert subtask.capability == "codeact.synthesize"
    canonical_risk = classify_action_risk("codeact", subtask.capability, subtask.parameters)
    assert canonical_risk == ActionRisk.MEDIUM

    # 2. Verify UnifiedToolDispatcher mapping matches canonical baseline
    domain, action_verb, risk_params = UnifiedToolDispatcher._map_tool_to_risk("create_file_artifact", args)
    assert domain == "codeact"
    assert action_verb == "codeact.synthesize"
    assert classify_action_risk(domain, action_verb, risk_params) == ActionRisk.MEDIUM

    # 3. Day-1 guard: AURA_PROVISIONAL_ARTIFACT_CONFIRM=1 forces HIGH (requires ticket)
    monkeypatch.setenv("AURA_PROVISIONAL_ARTIFACT_CONFIRM", "1")
    with ExecutionPolicy.autonomy_scope(AutonomyLevel.ASSISTED):
        res_forced = await UnifiedToolDispatcher.dispatch("create_file_artifact", args)
        assert res_forced.get("status") == "confirmation_required"
        assert res_forced.get("ticket_id", "").startswith("tkt_")

    # 4. Retired/relaxed mode: AURA_PROVISIONAL_ARTIFACT_CONFIRM=0 restores canonical MEDIUM
    #    and executes end-to-end through dispatch() without gating.
    monkeypatch.setenv("AURA_PROVISIONAL_ARTIFACT_CONFIRM", "0")
    from pathlib import Path
    test_args = {
        "goal": "generate shopping list excel for me",
        "output_filename": "test_contract_shopping.xlsx",
        "destination": "cwd",
    }
    with ExecutionPolicy.autonomy_scope(AutonomyLevel.ASSISTED):
        res_unattended = await UnifiedToolDispatcher.dispatch("create_file_artifact", test_args)
        assert res_unattended.get("status") == "success"
        out_p = Path(res_unattended.get("output_path", ""))
        assert out_p.exists() and out_p.stat().st_size > 0
        if out_p.exists():
            out_p.unlink()
