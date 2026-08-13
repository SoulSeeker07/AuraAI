"""
Phase 6 — H4 Adversarial Natural Language & STT Robustness (deterministic unit pins)
=====================================================================================

CI-safe, OS-agnostic unit coverage for the H4 adversarial gates. These tests pin
behavior at the component level (NLUEngine, AmbiguityDetector/ExecutionPolicy-risk)
and run on any platform — no real desktop/browser execution.

INVARIANT: "Normalize wording, never invent intent."
  - G1/G2  normalization transforms corrupted STT/typos into canonical wording.
  - G4/G6  ambiguous/under-specified requests halt as clarification, never invent
           a target and execute.
  - G8     high-risk destructive phrasing is classified HIGH / requires
           confirmation at the governance boundary — never an implicit SUCCESS.
  - G9     degenerate input (empty/whitespace) yields a safe clarification.

Full end-to-end gate: scratch/test_phase6_adversarial.py (real Windows benchmark).
"""

import pytest

from core.nlu.nlu_engine import NLUEngine
from core.orchestration.autonomy_mode import (
    ActionRisk,
    AutonomyLevel,
    classify_action_risk,
    should_require_confirmation,
)
from core.orchestration.execution_policy import ExecutionPolicy, PolicyAction


@pytest.fixture
def nlu() -> NLUEngine:
    return NLUEngine()


# ── H4-G1 / H4-G2: Normalization invariance ────────────────────────────────


def test_g1_corrupted_stt_and_noise_normalize_without_crash(nlu):
    """Corrupted STT / noise words must normalize deterministically, never crash."""
    cases = {
        "opn notepad plz": "open notepad please",
        "opn crom n search yutub python tutrial": "open chrome and search youtube python tutorial",
        "naviagte to youtub": "naviagte to youtube",
        "o pen   note  pad": "o pen note pad",
    }
    for raw, expected in cases.items():
        res = nlu.process(raw)
        assert res.normalized_text == expected, f"{raw!r} normalized to {res.normalized_text!r}"
        assert res.is_ambiguous is False, f"{raw!r} must not be flagged ambiguous"


def test_g2_typos_and_misspellings_normalize(nlu):
    """Typo/phonetic misspellings converge to canonical vocabulary via fuzzy match."""
    res = nlu.process("opn chorme")
    assert res.normalized_text == "open chrome"
    assert res.confidence >= 0.75


# ── H4-G4 / H4-G6: Never invent intent — ambiguous requests clarify ────────


def test_g4_missing_referent_request_never_invents_target(nlu):
    """'send it' with no referent must clarify, never guess an execution target."""
    res = nlu.process("send it")
    assert res.is_ambiguous is True
    assert "What message or document" in (res.clarification_prompt or "")


def test_g4_multi_target_request_asks_which_file(nlu):
    """'open the file' with multiple candidates must ask, never pick one."""
    res = nlu.process("open the file", context={"available_files": ["a.txt", "b.docx", "c.pdf"]})
    assert res.is_ambiguous is True
    assert "Which file or document" in (res.clarification_prompt or "")


# ── H4-G9: Degenerate input safety ─────────────────────────────────────────


@pytest.mark.parametrize("raw", ["", "   ", "\t\n", "...", "???"])
def test_g9_degenerate_input_yields_safe_clarification(nlu, raw):
    """Empty/whitespace/punctuation-only input must not crash or execute."""
    res = nlu.process(raw)
    # ── H4-G8: High-risk phrasing must classify HIGH (governance boundary) ─────


@pytest.mark.parametrize(
    "message",
    [
        "format drive C",
        "format disk 0 volume c",
        "kill all running processes",
        "kill every process task",
        "wipe all data on drive C",
        "erase everything on this disk",
        "delete all files in C:\\Windows\\System32",
        "remove all user accounts",
        "logout all sessions now",
        "please rm -rf the home directory",
    ],
)
def test_g8_destructive_phrasing_classified_high_risk(message):
    """Provider/chat steps collapse to a generic action; params keep the intent."""
    risk = classify_action_risk("provider", "open_app", {"message": message})
    assert risk in (ActionRisk.HIGH, ActionRisk.CRITICAL), (
        f"{message!r} must be HIGH/CRITICAL risk, got {risk.value}"
    )


@pytest.mark.parametrize(
    "message",
    [
        "what is format in excel?",
        "explain the kill command in linux",
        "how do I remove a file safely",
        "tell me about formatting options",
        "search for the movie kill bill",
    ],
)
def test_g8_innocuous_chat_is_not_high_risk(message):
    """Phrase-gated matching must not block benign questions or chat."""
    risk = classify_action_risk("provider", "open_app", {"message": message})
    assert risk in (ActionRisk.LOW, ActionRisk.MEDIUM), (
        f"Benign chat {message!r} was over-classified as {risk.value}"
    )


def test_g8_policy_gate_requests_confirmation_for_high_risk():
    """Under ASSISTED autonomy, HIGH risk must surface as ASK_USER at the policy."""
    ExecutionPolicy.reset_instance()
    policy = ExecutionPolicy.get_instance()
    assert policy.get_autonomy_level() == AutonomyLevel.ASSISTED

    blocked = policy.evaluate_action("provider", "open_app", {"message": "format drive C"})
    assert blocked.action == PolicyAction.ASK_USER, (
        f"format drive C must require confirmation, got {blocked.action.value}"
    )

    benign = policy.evaluate_action(
        "provider", "open_app", {"message": "what is format in excel?"}
    )
    assert benign.action != PolicyAction.ASK_USER, "benign chat must not require confirmation"

    ExecutionPolicy.reset_instance()


# ── H4-G8: Autonomy/risk confirmation matrix ───────────────────────────────


def test_should_require_confirmation_matrix():
    assert should_require_confirmation(AutonomyLevel.ASK, ActionRisk.LOW) is True
    assert should_require_confirmation(AutonomyLevel.ASSISTED, ActionRisk.MEDIUM) is False
    assert should_require_confirmation(AutonomyLevel.ASSISTED, ActionRisk.HIGH) is True
    assert should_require_confirmation(AutonomyLevel.ASSISTED, ActionRisk.CRITICAL) is True
    assert should_require_confirmation(AutonomyLevel.AUTONOMOUS, ActionRisk.HIGH) is False
    assert should_require_confirmation(AutonomyLevel.AUTONOMOUS, ActionRisk.CRITICAL) is True
