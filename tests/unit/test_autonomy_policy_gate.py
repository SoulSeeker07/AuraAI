"""
Unit Tests for M24 Phase 4: AutonomyPolicyGate & Cryptographic PolicyDecision
Location: tests/unit/test_autonomy_policy_gate.py

Verifies:
1. Security Test 1: Bypass Resistance (unauthorized or missing PolicyDecision fails verification).
2. Security Test 2: Tampering Resistance (modifying any signed field fails HMAC verification).
3. Security Test 3: Expiration Test (expired authorization is rejected).
4. Security Test 4: Assessment Mismatch Test (authorization for A presented with B is rejected).
5. Security Test 5: Replay Resistance (reusing a one-shot authorization proof a second time is blocked).
6. Decision state enforcement: ALLOWED, RATE_LIMITED, APPROVAL_REQUIRED, BLOCKED.
7. Human cryptographic approval token flow for high-risk actions.
8. Complete E2E Causal Trace:
   event_id -> correlation_id -> assessment_id -> policy_decision_id
"""

from datetime import datetime, timezone, timedelta
import pytest

from core.orchestration.autonomy_mode import ActionRisk, AutonomyLevel
from autonomy.events import (
    AuraEvent,
    EventSource,
    EventType,
)
from autonomy.interpreter import EventAssessment, EventInterpreter
from autonomy.policy_gate import (
    AutonomyPolicyGate,
    PolicyDecision,
    PolicyDecisionType,
)


@pytest.fixture
def policy_gate():
    gate = AutonomyPolicyGate(
        token_secret="test_policy_secret_2026",
        autonomy_level=AutonomyLevel.ASSISTED,
        decision_ttl_seconds=10.0,
        rate_limit_window_seconds=2.0,
        max_rate_per_window=3,
    )
    yield gate
    gate.clear_caches()


@pytest.fixture
def mock_assessment_low_risk():
    return EventAssessment(
        assessment_id="asm_low_risk_001",
        event_id="evt_low_risk_001",
        correlation_id="corr_low_risk_001",
        relevance=0.80,
        confidence=0.85,
        is_actionable=True,
        candidate_intent="Diagnose python build failure in main.py",
        candidate_intent_type="engineering.diagnose",
        reason="Test failure in workspace.",
    )


@pytest.fixture
def mock_assessment_high_risk():
    return EventAssessment(
        assessment_id="asm_high_risk_001",
        event_id="evt_high_risk_001",
        correlation_id="corr_high_risk_001",
        relevance=0.90,
        confidence=0.90,
        is_actionable=True,
        candidate_intent="Delete corrupted cache files",
        candidate_intent_type="file.delete",
        reason="Corrupted file cleanup requested.",
    )


@pytest.fixture
def mock_assessment_prohibited():
    return EventAssessment(
        assessment_id="asm_prohibited_001",
        event_id="evt_prohibited_001",
        correlation_id="corr_prohibited_001",
        relevance=0.95,
        confidence=0.95,
        is_actionable=True,
        candidate_intent="Format storage volume",
        candidate_intent_type="system.format_disk",
        reason="Host disk wipe requested.",
    )


def test_security_1_low_risk_allowed(policy_gate, mock_assessment_low_risk):
    """Low-risk diagnostic assessment is ALLOWED under default ASSISTED autonomy."""
    decision = policy_gate.evaluate(mock_assessment_low_risk)

    assert decision.decision == PolicyDecisionType.ALLOWED
    assert decision.risk_tier == ActionRisk.LOW
    assert decision.assessment_id == mock_assessment_low_risk.assessment_id
    assert decision.policy_decision_id.startswith("pol_")
    assert decision.ticket_id is None

    # Verify authorization
    is_valid = policy_gate.verify_authorization(decision, expected_assessment_id="asm_low_risk_001")
    assert is_valid is True


def test_security_2_high_risk_requires_approval(policy_gate, mock_assessment_high_risk):
    """High-risk action without approval token transitions to APPROVAL_REQUIRED with a ticket_id."""
    decision = policy_gate.evaluate(mock_assessment_high_risk)

    assert decision.decision == PolicyDecisionType.APPROVAL_REQUIRED
    assert decision.risk_tier == ActionRisk.HIGH
    assert decision.ticket_id is not None
    assert decision.ticket_id.startswith("tkt_")

    # APPROVAL_REQUIRED decisions must fail verify_authorization
    is_valid = policy_gate.verify_authorization(decision, expected_assessment_id="asm_high_risk_001")
    assert is_valid is False


def test_security_3_high_risk_authorized_with_token(policy_gate, mock_assessment_high_risk):
    """High-risk action with a valid HMAC human approval token transitions to ALLOWED."""
    # Generate human token for the assessment
    token = policy_gate.generate_human_approval_token(
        mock_assessment_high_risk.assessment_id
    )

    decision = policy_gate.evaluate(mock_assessment_high_risk, human_approval_token=token)

    assert decision.decision == PolicyDecisionType.ALLOWED
    assert decision.risk_tier == ActionRisk.HIGH
    assert decision.ticket_id is None

    is_valid = policy_gate.verify_authorization(decision, expected_assessment_id="asm_high_risk_001")
    assert is_valid is True


def test_security_4_prohibited_action_blocked(policy_gate, mock_assessment_prohibited):
    """Prohibited actions are unconditionally BLOCKED."""
    decision = policy_gate.evaluate(mock_assessment_prohibited)

    assert decision.decision == PolicyDecisionType.BLOCKED
    assert decision.risk_tier == ActionRisk.CRITICAL
    assert "prohibited from autonomous execution" in decision.reason

    is_valid = policy_gate.verify_authorization(decision, expected_assessment_id="asm_prohibited_001")
    assert is_valid is False


def test_security_5_tampering_resistance(policy_gate, mock_assessment_low_risk):
    """Modifying any signed field in PolicyDecision invalidates the cryptographic HMAC proof."""
    valid_decision = policy_gate.evaluate(mock_assessment_low_risk)
    assert policy_gate.verify_authorization(valid_decision, "asm_low_risk_001", consume=False) is True

    # Attack 1: Modify decision status from APPROVAL_REQUIRED to ALLOWED
    tampered_1 = PolicyDecision(
        policy_decision_id=valid_decision.policy_decision_id,
        assessment_id=valid_decision.assessment_id,
        decision=PolicyDecisionType.BLOCKED,  # Tampered field
        risk_tier=valid_decision.risk_tier,
        policy_version=valid_decision.policy_version,
        issued_at=valid_decision.issued_at,
        expires_at=valid_decision.expires_at,
        authorization_proof=valid_decision.authorization_proof,
        reason=valid_decision.reason,
    )
    assert policy_gate.verify_authorization(tampered_1, "asm_low_risk_001") is False

    # Attack 2: Tamper with HMAC signature
    tampered_2 = PolicyDecision(
        policy_decision_id=valid_decision.policy_decision_id,
        assessment_id=valid_decision.assessment_id,
        decision=valid_decision.decision,
        risk_tier=valid_decision.risk_tier,
        policy_version=valid_decision.policy_version,
        issued_at=valid_decision.issued_at,
        expires_at=valid_decision.expires_at,
        authorization_proof="0000000000000000000000000000000000000000000000000000000000000000",
        reason=valid_decision.reason,
    )
    assert policy_gate.verify_authorization(tampered_2, "asm_low_risk_001") is False


def test_security_6_assessment_mismatch_resistance(policy_gate, mock_assessment_low_risk):
    """Authorization generated for assessment A presented for assessment B is rejected."""
    decision_A = policy_gate.evaluate(mock_assessment_low_risk)

    # Present decision_A to verify assessment_B
    is_valid = policy_gate.verify_authorization(decision_A, expected_assessment_id="asm_different_b_999")
    assert is_valid is False


def test_security_7_expiration_resistance(policy_gate, mock_assessment_low_risk):
    """Expired authorization proofs fail verification."""
    # Create an expired decision
    now = datetime.now(timezone.utc)
    past_issued = (now - timedelta(seconds=600)).isoformat()
    past_expires = (now - timedelta(seconds=300)).isoformat()

    proof = policy_gate._generate_proof(
        "pol_expired_01",
        mock_assessment_low_risk.assessment_id,
        PolicyDecisionType.ALLOWED,
        ActionRisk.LOW,
        past_issued,
        past_expires,
    )

    expired_decision = PolicyDecision(
        policy_decision_id="pol_expired_01",
        assessment_id=mock_assessment_low_risk.assessment_id,
        decision=PolicyDecisionType.ALLOWED,
        risk_tier=ActionRisk.LOW,
        policy_version="1.0",
        issued_at=past_issued,
        expires_at=past_expires,
        authorization_proof=proof,
        reason="Expired test",
    )

    assert expired_decision.is_expired() is True
    assert policy_gate.verify_authorization(expired_decision, mock_assessment_low_risk.assessment_id) is False


def test_security_8_replay_resistance(policy_gate, mock_assessment_low_risk):
    """Reusing the same one-shot authorization proof a second time is blocked."""
    decision = policy_gate.evaluate(mock_assessment_low_risk)

    # First verification consumes proof -> PASS
    first_verify = policy_gate.verify_authorization(decision, mock_assessment_low_risk.assessment_id, consume=True)
    assert first_verify is True

    # Second verification with same proof -> BLOCKED (replay)
    second_verify = policy_gate.verify_authorization(decision, mock_assessment_low_risk.assessment_id, consume=True)
    assert second_verify is False


def test_rate_limiting_enforcement(policy_gate, mock_assessment_low_risk):
    """Rapid recurring triggers of the same intent type are RATE_LIMITED after limit is hit."""
    # policy_gate has max_rate_per_window=3 within 2.0s
    d1 = policy_gate.evaluate(mock_assessment_low_risk)
    d2 = policy_gate.evaluate(mock_assessment_low_risk)
    d3 = policy_gate.evaluate(mock_assessment_low_risk)
    d4 = policy_gate.evaluate(mock_assessment_low_risk)

    assert d1.decision == PolicyDecisionType.ALLOWED
    assert d2.decision == PolicyDecisionType.ALLOWED
    assert d3.decision == PolicyDecisionType.ALLOWED
    # 4th call exceeds max_rate_per_window=3
    assert d4.decision == PolicyDecisionType.RATE_LIMITED
    assert "rate limit exceeded" in d4.reason


@pytest.mark.asyncio
async def test_end_to_end_causal_trace_e2e(policy_gate):
    """
    Verifies complete causal identity preservation across the entire autonomous pipeline:
    AuraEvent -> EventRuntime -> EventInterpreter -> AutonomyPolicyGate -> PolicyDecision
    """
    import asyncio
    from autonomy.event_runtime import EventRuntime, EventTraceRecord

    completed_chain: dict[str, Any] = {}
    interpreter = EventInterpreter()

    async def runtime_handler(event: AuraEvent, trace: EventTraceRecord):
        # 1. Ingress trace recorded
        completed_chain["event_id"] = event.event_id
        completed_chain["correlation_id"] = event.correlation_id
        completed_chain["trace_id"] = trace.event_id

        # 2. Interpret event
        assessment = await interpreter.interpret(event)
        completed_chain["assessment_id"] = assessment.assessment_id

        # 3. Policy Gate Evaluation
        decision = policy_gate.evaluate(assessment)
        completed_chain["policy_decision_id"] = decision.policy_decision_id
        completed_chain["decision"] = decision.decision.value
        completed_chain["is_authorized"] = policy_gate.verify_authorization(decision, assessment.assessment_id)

    runtime = EventRuntime(dispatch_handler=runtime_handler)
    await runtime.start()

    evt = AuraEvent.create(
        event_type=EventType.PROCESS_EXITED,
        source=EventSource.PROCESS,
        payload={"process_name": "pytest.exe", "exit_code": 1},
        correlation_id="corr_full_causal_chain_001",
    )
    runtime.ingest(evt)

    await asyncio.sleep(0.1)
    await runtime.stop()

    assert completed_chain["event_id"] == evt.event_id
    assert completed_chain["correlation_id"] == "corr_full_causal_chain_001"
    assert completed_chain["trace_id"] == evt.event_id
    assert completed_chain["assessment_id"].startswith("asm_")
    assert completed_chain["policy_decision_id"].startswith("pol_")
    assert completed_chain["decision"] == "ALLOWED"
    assert completed_chain["is_authorized"] is True
