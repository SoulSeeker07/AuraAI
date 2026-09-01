"""
Unit Tests for Scoped Sandbox Auto-Approval & Verification Screenshot Capture
Location: tests/unit/test_scoped_sandbox_auto_approval.py
"""

import os
import tempfile
import time
from pathlib import Path
import pytest

from core.orchestration.autonomy_mode import (
    ActionRisk,
    AutonomyLevel,
    classify_action_risk,
    is_safe_sandbox_path,
    should_require_confirmation,
)
from autonomy.interpreter import EventAssessment
from autonomy.policy_gate import AutonomyPolicyGate, PolicyDecisionType
from browser.run_browser_goal import format_for_chat


def test_is_safe_sandbox_path_system_temp():
    """System temp directory paths should be recognized as safe."""
    temp_dir = tempfile.gettempdir()
    sample_file = os.path.join(temp_dir, "test_file.tmp")
    assert is_safe_sandbox_path(sample_file) is True


def test_is_safe_sandbox_path_cache_folders():
    """Cache folders like __pycache__ and .pytest_cache should be recognized as safe."""
    assert is_safe_sandbox_path("d:/project/__pycache__/module.cpython-311.pyc") is True
    assert is_safe_sandbox_path("c:/repos/aura/.pytest_cache/v/cache/nodeids") is True
    assert is_safe_sandbox_path("c:/repos/aura/.mypy_cache/3.11/main.data.json") is True
    assert is_safe_sandbox_path("c:/repos/aura/.ruff_cache/content") is True


def test_is_safe_sandbox_path_runtime_temp():
    """Project Data/runtime/temp/ or screenshots should be safe."""
    assert is_safe_sandbox_path("d:/project/Data/runtime/temp/cleanup_temp.txt") is True
    assert is_safe_sandbox_path("d:/project/Data/runtime/screenshots/test_screenshot.png") is True


def test_is_safe_sandbox_path_unsafe_locations():
    """User personal directories, code files, and system drives should NOT be classified as safe."""
    assert is_safe_sandbox_path("C:/Users/User/Documents/tax_return.pdf") is False
    assert is_safe_sandbox_path("C:/Windows/System32/drivers/etc/hosts") is False
    assert is_safe_sandbox_path("d:/project/src/core/aura_core.py") is False
    assert is_safe_sandbox_path(None) is False
    assert is_safe_sandbox_path("") is False


def test_classify_action_risk_scoped_sandbox_auto_approval():
    """file.delete targeting safe sandbox paths should be classified as LOW risk."""
    temp_file = os.path.join(tempfile.gettempdir(), "test_trash.tmp")
    risk_temp = classify_action_risk("desktop", "file.delete", {"path": temp_file})
    assert risk_temp == ActionRisk.LOW

    pycache_file = "d:/project/__pycache__/temp.pyc"
    risk_pycache = classify_action_risk("desktop", "file.delete", {"path": pycache_file})
    assert risk_pycache == ActionRisk.LOW


def test_classify_action_risk_unsafe_path_remains_high():
    """file.delete targeting documents or critical files must remain HIGH risk."""
    doc_file = "C:/Users/User/Documents/important.docx"
    risk_doc = classify_action_risk("desktop", "file.delete", {"path": doc_file})
    assert risk_doc == ActionRisk.HIGH
    assert should_require_confirmation(AutonomyLevel.ASSISTED, risk_doc) is True


def test_policy_gate_evaluates_sandbox_cleanups_as_allowed():
    """AutonomyPolicyGate should allow safe sandbox cleanup unattended under ASSISTED autonomy."""
    from types import MappingProxyType
    gate = AutonomyPolicyGate(
        token_secret="test_secret",
        autonomy_level=AutonomyLevel.ASSISTED,
    )
    temp_path = os.path.join(tempfile.gettempdir(), "aura_clean_cache.tmp")
    assessment = EventAssessment(
        assessment_id="asm_cleanup_001",
        event_id="evt_cleanup_001",
        correlation_id="corr_cleanup_001",
        relevance=0.9,
        confidence=0.95,
        is_actionable=True,
        candidate_intent="Clean temp directory files",
        candidate_intent_type="file.delete",
        metadata=MappingProxyType({"path": temp_path}),
        reason="Daily temp clean",
    )

    decision = gate.evaluate(assessment)
    assert decision.decision == PolicyDecisionType.ALLOWED
    assert decision.risk_tier == ActionRisk.LOW
    assert decision.ticket_id is None


def test_policy_gate_blocks_unsafe_file_deletion():
    """AutonomyPolicyGate should require approval ticket for non-sandbox file deletion."""
    from types import MappingProxyType
    gate = AutonomyPolicyGate(
        token_secret="test_secret",
        autonomy_level=AutonomyLevel.ASSISTED,
    )
    assessment = EventAssessment(
        assessment_id="asm_cleanup_unsafe",
        event_id="evt_cleanup_unsafe",
        correlation_id="corr_cleanup_unsafe",
        relevance=0.9,
        confidence=0.95,
        is_actionable=True,
        candidate_intent="Delete user documents",
        candidate_intent_type="file.delete",
        metadata=MappingProxyType({"path": "C:/Users/User/Documents/file.txt"}),
        reason="Unsafe document deletion",
    )

    decision = gate.evaluate(assessment)
    assert decision.decision == PolicyDecisionType.APPROVAL_REQUIRED
    assert decision.risk_tier == ActionRisk.HIGH
    assert decision.ticket_id is not None


def test_browser_format_for_chat_includes_verification_screenshot():
    """format_for_chat should format and embed verification screenshot path."""
    result = {
        "status": "SUCCESS",
        "summary": "Searched and booked flight successfully.",
        "screenshot_path": "D:/project/Data/runtime/screenshots/browser_verification_123.png",
    }
    chat_msg = format_for_chat(result, goal="book flight")
    assert "Searched and booked flight successfully." in chat_msg
    assert "📸 **Verification Screenshot**" in chat_msg
    assert "browser_verification_123.png" in chat_msg
