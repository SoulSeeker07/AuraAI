"""
Tests for memory_policy.apply_policy() — the deterministic gate between
LLM-extracted candidates and Chroma storage.
"""
import pytest
from memory.manager.memory_policy import apply_policy, PolicyVerdict


# ---------------------------------------------------------------------------
# Gate 1: Hard exclusion
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fact, expected_reason_prefix", [
    ("User's password is hunter2", "hard_exclusion"),
    ("API key is sk-abc123XYZ987654321abc", "hard_exclusion"),
    ("Access token: Bearer eyJhbGci...", "hard_exclusion"),
    ("PIN for bank account: 4821", "hard_exclusion"),
    ("OTP received: 847201", "hard_exclusion"),
    ("Credit card number 4111 1111 1111 1111", "hard_exclusion"),
    ("Private key starts with -----BEGIN", "hard_exclusion"),
    ("Session cookie: abc123def456", "hard_exclusion"),
    # Groq-style key literal
    ("gsk_abcdefghijklmnopqrstuvwxyz123456", "hard_exclusion"),
])
def test_hard_exclusion_credentials_rejected(fact, expected_reason_prefix):
    verdict = apply_policy({"fact": fact, "topic": "security", "importance": 5})
    assert not verdict.store, f"Expected rejection for: {fact!r}"
    assert verdict.reason.startswith(expected_reason_prefix), (
        f"Expected reason to start with {expected_reason_prefix!r}, got {verdict.reason!r}"
    )


# ---------------------------------------------------------------------------
# Gate 2: Sensitive info (conservative M2 default)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fact", [
    "User has been diagnosed with type 2 diabetes",
    "User takes medication for anxiety",
    "User's annual salary is $80,000",
    "Net worth is approximately $200,000",
    "SSN ends in 4821",
    "Passport number AB1234567",
    "User's national ID: 123456789",
])
def test_sensitive_info_rejected_by_default(fact):
    verdict = apply_policy({"fact": fact, "topic": "personal", "importance": 5})
    assert not verdict.store, f"Expected rejection for sensitive fact: {fact!r}"
    assert verdict.reason.startswith("sensitive_info"), (
        f"Expected sensitive_info reason, got: {verdict.reason!r}"
    )


# ---------------------------------------------------------------------------
# Gate 3: Importance threshold
# ---------------------------------------------------------------------------

def test_low_importance_rejected():
    verdict = apply_policy({
        "fact": "User mentioned they like mornings",
        "topic": "general",
        "importance": 2,
    })
    assert not verdict.store
    assert "importance_too_low" in verdict.reason


def test_importance_at_threshold_accepted():
    verdict = apply_policy({
        "fact": "User prefers dark mode in all apps",
        "topic": "preferences",
        "importance": 3,
    })
    assert verdict.store
    assert verdict.reason == "passed_all_gates"


def test_high_importance_accepted():
    verdict = apply_policy({
        "fact": "User's favorite browser is Firefox",
        "topic": "preferences",
        "importance": 5,
    })
    assert verdict.store
    assert verdict.reason == "passed_all_gates"


# ---------------------------------------------------------------------------
# LLM authority: "store" field in item is irrelevant
# ---------------------------------------------------------------------------

def test_llm_store_field_ignored():
    """LLM must not be able to bypass policy by including store=True."""
    verdict = apply_policy({
        "fact": "API key is sk-abcdef12345678901234",
        "topic": "credentials",
        "importance": 5,
        "store": True,  # LLM hallucination — must be ignored
    })
    assert not verdict.store, "Policy must override LLM 'store: true'"


# ---------------------------------------------------------------------------
# Normal durable preference — passes all gates
# ---------------------------------------------------------------------------

def test_durable_preference_accepted():
    verdict = apply_policy({
        "fact": "User prefers Python over JavaScript for backend work",
        "topic": "preferences",
        "importance": 4,
    })
    assert verdict.store
    assert verdict.reason == "passed_all_gates"
