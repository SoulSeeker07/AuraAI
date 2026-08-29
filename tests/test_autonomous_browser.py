"""
Unit Tests for Autonomous Browser Engine
Location: tests/test_autonomous_browser.py

Verifies:
1. Mode classification (DOM vs Native Screen-Vision).
2. High-Risk Action Gating & Safety Interceptor.
3. OCR / Vision Grounding Confidence Thresholding (>= 0.75).
4. Audit ledger recording.
5. IntentRouter dispatch for browser goals.
"""

import sys
import time
from pathlib import Path
import pytest

# Ensure src in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(1, str(PROJECT_ROOT))

from browser.autonomous_browser import AutonomousBrowserEngine, MIN_GROUNDING_CONFIDENCE
from brain.intent_router import IntentRouter
from Memory import Memory


@pytest.fixture
def browser_engine():
    return AutonomousBrowserEngine(headless=True)


@pytest.fixture
def intent_router():
    mem = Memory(db_path=":memory:", chat_log_path="Data/ChatLog_test.json")
    return IntentRouter(mem)


def test_mode_classification(browser_engine):
    """Verify DOM vs Vision-Native mode detection."""
    assert browser_engine.classify_mode("search google for python docs") == "dom"
    assert browser_engine.classify_mode("click on screen button at my chrome") == "vision_native"
    assert browser_engine.classify_mode("look at screen and scroll down") == "vision_native"


def test_high_risk_assessment_blocking(browser_engine):
    """Verify high-risk actions are flagged and blocked."""
    assert browser_engine.assess_risk("search wikipedia for quantum computing") == "LOW"
    assert browser_engine.assess_risk("go to store and checkout cart") == "HIGH"
    assert browser_engine.assess_risk("open paypal and pay 50 dollars") == "HIGH"
    assert browser_engine.assess_risk("delete account on settings page") == "HIGH"

    # Execution must fail-closed on high-risk
    res = browser_engine.run_autonomous_goal("go to shop and click checkout now")
    assert res["success"] is False
    assert res["risk_level"] == "HIGH"
    assert "Blocked by Safety Guardrail" in res["message"]


def test_grounding_confidence_threshold(browser_engine):
    """Verify coordinate grounding respects MIN_GROUNDING_CONFIDENCE."""
    assert MIN_GROUNDING_CONFIDENCE == 0.75
    
    # Common UI landmark matches heuristic with high confidence
    coords, conf = browser_engine.ground_coordinates("address bar")
    assert coords == (500, 80)
    assert conf >= MIN_GROUNDING_CONFIDENCE

    # Empty target fails
    coords, conf = browser_engine.ground_coordinates("")
    assert coords is None
    assert conf < MIN_GROUNDING_CONFIDENCE


def test_autonomous_goal_dry_run(browser_engine):
    """Verify autonomous goal execution builds a traceable action plan."""
    res = browser_engine.run_autonomous_goal("search wikipedia for artificial intelligence")
    assert res["success"] is True
    assert res["risk_level"] == "LOW"
    assert len(res["actions"]) >= 1
    assert res["audit_ledger_records"] >= 1


def test_ticket_confirmation_flow(browser_engine):
    """Verify high-risk block generates ticket, and confirmation authorizes execution on registered site."""
    res = browser_engine.run_autonomous_goal("search wikipedia for transfer funds")
    assert res["success"] is False
    assert res["risk_level"] == "HIGH"
    ticket_id = res.get("ticket_id")
    assert ticket_id and ticket_id.startswith("AUTH-")

    # Confirm valid ticket
    confirm_res = AutonomousBrowserEngine.confirm_ticket(ticket_id)
    assert confirm_res["success"] is True
    assert "Authorized" in confirm_res["message"]

    # Re-confirming same ticket must fail (one-time use)
    confirm_res_2 = AutonomousBrowserEngine.confirm_ticket(ticket_id)
    assert confirm_res_2["success"] is False


def test_ticket_ttl_expiry_enforcement(browser_engine):
    """Verify tickets older than 5 minutes (300s TTL) are rejected and purged."""
    import time
    res = browser_engine.run_autonomous_goal("browse to crypto and withdraw balance")
    ticket_id = res.get("ticket_id")
    assert ticket_id is not None

    # Simulate ticket created 301 seconds ago
    tickets = AutonomousBrowserEngine._load_tickets()
    tickets[ticket_id]["created_at"] = time.time() - 301
    AutonomousBrowserEngine._save_tickets(tickets)

    # Attempting to confirm an expired ticket must fail
    confirm_res = AutonomousBrowserEngine.confirm_ticket(ticket_id)
    assert confirm_res["success"] is False
    assert "Ticket Expired" in confirm_res["message"]

    # Verify ticket was purged from storage
    fresh_tickets = AutonomousBrowserEngine._load_tickets()
    assert ticket_id not in fresh_tickets


def test_intent_routing_autonomous_browser(intent_router):
    """Verify natural browser commands route to autonomous_browser intent."""
    test_queries = [
        "aura browse to youtube and search lo-fi",
        "aura go to wikipedia and search quantum computing",
        "aura search google for python tutorials",
        "browse amazon.com and find headphones",
        "aura in amazon add iphone 17 to cart and checkout",
    ]
    for q in test_queries:
        intent = intent_router.detect(q)
        assert intent.name == "autonomous_browser", f"Failed for query: {q} (got {intent.name})"

    # Test confirm ticket routing
    confirm_intent = intent_router.detect("aura confirm AUTH-A1B2C3")
    assert confirm_intent.name == "confirm_ticket"
    assert confirm_intent.data["ticket_id"] == "AUTH-A1B2C3"

    # Test resume browser routing
    resume_intent = intent_router.detect("aura resume")
    assert resume_intent.name == "resume_browser"


def test_tier1_fast_api_connector(browser_engine):
    """Verify Tier 1 fast REST API connector resolves factual queries instantly."""
    res = browser_engine.run_autonomous_goal("browse to wikipedia and search Python programming language")
    assert res["success"] is True
    assert res["mode"] == "TIER_1_API_CONNECTOR"
    assert "Python" in res["title"]
    assert len(res["summary"]) > 20


def test_challenge_handback_and_resume_lifecycle(browser_engine):
    """Verify challenge hand-back state, session saving, and resume with TTL."""
    # Test challenge pattern detection
    class MockPage:
        def content(self):
            return "<html><body><div>Please verify you are human to continue.</div></body></html>"
        def locator(self, sel):
            class MockLoc:
                def first(self):
                    return self
                def is_visible(self, timeout=500):
                    return False
            return MockLoc()

    challenge = browser_engine.detect_challenges(MockPage())
    assert challenge == "HUMAN_VERIFICATION"

    # Save a paused session
    session_data = {
        "url": "https://example.com/login",
        "goal": "check private dashboard",
        "challenge_type": "HUMAN_VERIFICATION",
        "timestamp": time.time(),
    }
    AutonomousBrowserEngine._save_session(session_data)

    # Verify session loaded
    loaded = AutonomousBrowserEngine._load_session()
    assert loaded is not None
    assert loaded["challenge_type"] == "HUMAN_VERIFICATION"

    # Test Session TTL expiry (>600s)
    session_data["timestamp"] = time.time() - 605
    AutonomousBrowserEngine._save_session(session_data)
    resume_res = AutonomousBrowserEngine.resume_session()
    assert resume_res["success"] is False
    assert "Expired" in resume_res["message"]


def test_unregistered_platform_fails_closed(browser_engine):
    """Verify named platform not in SiteRegistry halts without silent Google substitution."""
    res = browser_engine.run_autonomous_goal("in unknownfakestore add item to cart", risk_override=True)
    assert res["success"] is False
    assert res["state"] == "UNRECOGNIZED_PLATFORM"
    assert "Unrecognized Platform" in res["message"]
    assert "unknownfakestore" in res["message"]


def test_domain_mismatch_assertion_fails_closed(browser_engine):
    """Verify landing on a mismatched domain or bot-wall triggers domain assertion failure."""
    # Unit check on domain transition validation
    assert AutonomousBrowserEngine._is_valid_domain_transition("https://www.facebook.com", "https://m.facebook.com/home") is True
    assert AutonomousBrowserEngine._is_valid_domain_transition("https://www.amazon.in", "https://www.amazon.com/dp/123") is True
    assert AutonomousBrowserEngine._is_valid_domain_transition("https://www.amazon.in", "https://www.google.com/search?q=test") is False
    assert AutonomousBrowserEngine._is_valid_domain_transition("https://www.facebook.com", "https://www.google.com/sorry/index") is False
    assert AutonomousBrowserEngine._is_valid_domain_transition("https://www.google.com", "https://www.google.com/sorry/index") is False


def test_confirm_ticket_fail_closed_on_downstream_failure(browser_engine):
    """Verify confirm_ticket reports execution failure and logs honest audit status when goal fails."""
    # Issue ticket for an unresolvable platform
    res = browser_engine.run_autonomous_goal("in phantomportal buy widget and checkout")
    assert res["success"] is False
    ticket_id = res.get("ticket_id")
    assert ticket_id is not None

    # Confirm ticket - downstream execution should halt on UNRECOGNIZED_PLATFORM and fail closed
    confirm_res = AutonomousBrowserEngine.confirm_ticket(ticket_id)
    assert confirm_res["success"] is False
    assert "Execution Failed" in confirm_res["message"] or "Unrecognized Platform" in confirm_res["message"]
    assert confirm_res["audit_status"] == "UNRECOGNIZED_PLATFORM"

