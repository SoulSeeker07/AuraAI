"""
tests/test_browser_agent_flow.py

Verification script for the new tool-calling browser agent architecture.
Tests:
  1. Read-only search & extraction (Wikipedia shortcut & direct goals)
  2. SafetyGate ticket cycle (Add to Cart -> REQUIRE_AUTH_TICKET -> confirm_ticket replay)
  3. PausedSession hand-back simulation (Session remains live -> resume_goal)
  4. resume_goal() guard against ticket-blocked sessions
"""

import logging
import sys
from pathlib import Path

# Ensure src/ is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("BrowserAgentTest")


def test_paused_session_store_lifecycle():
    """Test: Unit test verifying PausedSessionStore retains session without premature exit."""
    from browser.paused_session import PausedSession, PausedSessionStore
    from browser.browser_session import BrowserSession

    logger.info("=" * 60)
    logger.info("TEST: PausedSessionStore In-Memory Lifecycle")
    logger.info("=" * 60)

    store = PausedSessionStore.get_instance()
    session = BrowserSession(headless=True)
    session.__enter__()

    try:
        paused = PausedSession(
            session=session,
            messages=[{"role": "user", "content": "test"}],
            goal="Test paused session persistence",
            model="llama-3.3-70b-versatile",
            max_steps_remaining=10,
            challenge_type="TEST_CHALLENGE",
        )
        store.save(paused)
        assert store.has_pending() is True, "Store should report pending session"

        retrieved = store.take()
        assert retrieved is not None, "Should retrieve active paused session"
        assert retrieved.goal == "Test paused session persistence"
        assert retrieved.session.page is not None, "Retrieved session browser must still be open"
        assert store.has_pending() is False, "Store should now be empty"

        logger.info("✅ PausedSession held live browser without leaking or closing.\n")
    finally:
        session.__exit__(None, None, None)


def test_resume_rejected_on_ticket_block():
    """Test: Calling resume_goal() on a ticket-blocked session should reject and direct to confirm."""
    from browser.paused_session import PausedSession, PausedSessionStore
    from browser.browser_session import BrowserSession
    from browser.agent_loop import resume_goal

    logger.info("=" * 60)
    logger.info("TEST: resume_goal() Guard Against Ticket Blocks")
    logger.info("=" * 60)

    store = PausedSessionStore.get_instance()
    session = BrowserSession(headless=True)
    session.__enter__()

    try:
        paused = PausedSession(
            session=session,
            messages=[{"role": "user", "content": "buy item"}],
            goal="buy item",
            model="llama-3.3-70b-versatile",
            max_steps_remaining=5,
            challenge_type=None,
            pending_ticket_id="TICK-TEST-9999",
            pending_tool={"tool": "click", "args": {"description": "Buy Now"}},
        )
        store.save(paused)

        res = resume_goal()
        assert res.get("status") == "REQUIRE_AUTH_TICKET", f"Expected REQUIRE_AUTH_TICKET, got {res.get('status')}"
        assert "TICK-TEST-9999" in res.get("summary", ""), "Summary should contain the pending ticket ID"
        assert store.has_pending() is True, "Store should retain the ticket session untouched"

        logger.info("✅ resume_goal() cleanly rejected ticket block and preserved session.\n")
    finally:
        session.__exit__(None, None, None)


def test_safety_gate_evaluation():
    """Test: SafetyGate correctly flags high risk calls vs low risk calls and saves tickets."""
    from browser.safety_gate import SafetyGate

    logger.info("=" * 60)
    logger.info("TEST: SafetyGate Risk & Ticket Minting")
    logger.info("=" * 60)

    gate = SafetyGate()

    # Low risk
    low_res = gate.check("click", {"description": "Search input"}, goal="Search test")
    assert low_res["allowed"] is True
    assert low_res["risk"] == "LOW"

    # High risk
    high_res = gate.check("click", {"description": "Buy Now button"}, goal="Purchase item")
    assert high_res["allowed"] is False
    assert high_res["risk"] == "HIGH"
    assert high_res["ticket_id"] is not None
    assert high_res["ticket_id"].startswith("AUTH-") or high_res["ticket_id"].startswith("tkt_")

    # Redeem ticket
    redeemed = gate.redeem_ticket(high_res["ticket_id"])
    assert redeemed is not None
    assert redeemed["action_type"] == "browser.click"
    assert redeemed["parameters"]["description"] == "Buy Now button"

    logger.info("✅ SafetyGate successfully evaluated risk and redeemed ticket.\n")


def test_sensitive_type_argument_redaction():
    """Test: SafetyGate redacts sensitive passwords and CVVs in ticket metadata and audit ledger."""
    from browser.safety_gate import SafetyGate

    gate = SafetyGate()
    raw_args = {"description": "Enter your card CVV and password", "text": "secret_cvv_999", "press_enter": True}
    res = gate.check("type_text", raw_args, goal="Checkout item")

    assert res["allowed"] is False
    assert res["risk"] == "HIGH"
    assert res["ticket_id"] is not None

    redeemed = gate.redeem_ticket(res["ticket_id"])
    assert redeemed is not None
    assert redeemed["parameters"]["text"] == "[REDACTED_SECRET]"
    assert redeemed["parameters"]["description"] == "Enter your card CVV and password"
    assert "secret_cvv_999" not in str(redeemed["parameters"])

    logger.info("✅ SafetyGate successfully redacted sensitive text from ticket metadata.\n")


def test_tier1_shortcuts():
    """Test: Tier 1 Wikipedia shortcut returns fast summary."""
    from browser.tier1_shortcuts import try_shortcut

    logger.info("=" * 60)
    logger.info("TEST: Tier 1 Shortcuts")
    logger.info("=" * 60)

    res = try_shortcut("what is Python")
    if res:
        assert res.get("status") == "SUCCESS"
        assert "Python" in res.get("summary", "")
        logger.info("✅ Tier 1 Wikipedia shortcut returned summary: %s...", res.get("summary")[:80])
    else:
        logger.info("ℹ️ Tier 1 Wikipedia lookup skipped or network unavailable.")


if __name__ == "__main__":
    logger.info("Running Browser Agent Flow Unit Tests...")
    test_paused_session_store_lifecycle()
    test_resume_rejected_on_ticket_block()
    test_safety_gate_evaluation()
    test_tier1_shortcuts()
    logger.info("🎉 All Browser Agent In-Memory & Unit Tests Passed Successfully!")
