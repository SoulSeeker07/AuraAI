"""
Unit and integration tests for Natural Language Human-in-the-loop Approvals and Denials.
"""

from unittest.mock import patch, MagicMock
from brain.intent_router import IntentRouter
from brain.conversation_engine import ConversationEngine
from brain.models import Intent
from Memory import Memory
from desktop.native.security.approval_authority import CryptographicApprovalAuthority


def test_intent_router_natural_approvals():
    mem = Memory(db_path=":memory:")
    router = IntentRouter(mem)

    # Natural approvals
    for utterance in ("approve", "approve it", "yes approve", "confirm", "go ahead", "allow", "i approve"):
        intent = router.detect(utterance)
        assert intent.name == "confirm_ticket", f"Failed for {utterance}"
        assert intent.data["decision"] == "approve", f"Failed decision for {utterance}"
        assert intent.data["ticket_id"] is None

    # Natural denials
    for utterance in ("reject", "deny", "cancel", "disapprove", "don't do it", "block it"):
        intent = router.detect(utterance)
        assert intent.name == "confirm_ticket", f"Failed for {utterance}"
        assert intent.data["decision"] == "deny", f"Failed decision for {utterance}"
        assert intent.data["ticket_id"] is None

    # Explicit ticket approvals
    intent = router.detect("approve tkt_b0c10aa12508")
    assert intent.name == "confirm_ticket"
    assert intent.data["decision"] == "approve"
    assert intent.data["ticket_id"] == "tkt_b0c10aa12508"

    intent = router.detect("reject tkt_b0c10aa12508")
    assert intent.name == "confirm_ticket"
    assert intent.data["decision"] == "deny"
    assert intent.data["ticket_id"] == "tkt_b0c10aa12508"


def test_conversation_engine_natural_approval_execution():
    mem = Memory(db_path=":memory:")
    pm = MagicMock()
    engine = ConversationEngine(memory=mem, provider_manager=pm)

    # 1. When no ticket is pending
    res = engine._answer_local_intent(Intent("confirm_ticket", {"ticket_id": None, "decision": "approve"}))
    assert "no pending tasks" in res.lower()

    # 2. When a ticket is created in ApprovalAuthority
    auth = CryptographicApprovalAuthority.get_instance()
    t_id = auth.create_ticket(action_type="security.credential_scan", target="system")

    # Natural approve
    res = engine._answer_local_intent(Intent("confirm_ticket", {"ticket_id": None, "decision": "approve"}))
    assert "Approved" in res
    assert "Security Credential Scan" in res

    # 3. Create another ticket and test natural deny
    t_id2 = auth.create_ticket(action_type="file.delete", target="temp.log")
    res = engine._answer_local_intent(Intent("confirm_ticket", {"ticket_id": None, "decision": "deny"}))
    assert "Denied" in res
    assert "File Delete" in res


def test_intent_router_bulk_approvals():
    mem = Memory(db_path=":memory:")
    router = IntentRouter(mem)

    for utterance in ("approve all", "approve all tickets", "confirm all", "authorize all", "allow all", "aura approve all"):
        intent = router.detect(utterance)
        assert intent.name == "confirm_ticket", f"Failed for {utterance}"
        assert intent.data["decision"] == "approve"
        assert intent.data.get("all") is True

    for utterance in ("deny all", "deny all tickets", "reject all", "cancel all", "aura deny all"):
        intent = router.detect(utterance)
        assert intent.name == "confirm_ticket", f"Failed for {utterance}"
        assert intent.data["decision"] == "deny"
        assert intent.data.get("all") is True


def test_conversation_engine_bulk_approval_execution():
    mem = Memory(db_path=":memory:")
    pm = MagicMock()
    engine = ConversationEngine(memory=mem, provider_manager=pm)
    auth = CryptographicApprovalAuthority.get_instance()

    t1 = auth.create_ticket(action_type="system.restart", target="service_a")
    t2 = auth.create_ticket(action_type="app_open", target="notepad")

    # Approve all
    res = engine._answer_local_intent(Intent("confirm_ticket", {"ticket_id": None, "decision": "approve", "all": True}))
    assert "Approved" in res
    assert "System Restart" in res
    assert "App Open" in res

    # Verify both tickets are no longer pending
    pending = auth.get_pending_tickets()
    assert not any(t.ticket_id in (t1, t2) for t in pending)


def test_conversation_engine_bulk_denial_execution():
    mem = Memory(db_path=":memory:")
    pm = MagicMock()
    engine = ConversationEngine(memory=mem, provider_manager=pm)
    auth = CryptographicApprovalAuthority.get_instance()

    t1 = auth.create_ticket(action_type="file.delete", target="file1.txt")
    t2 = auth.create_ticket(action_type="file.delete", target="file2.txt")

    # Deny all
    res = engine._answer_local_intent(Intent("confirm_ticket", {"ticket_id": None, "decision": "deny", "all": True}))
    assert "Denied" in res
    assert "file1.txt" in res or "File Delete" in res

    pending = auth.get_pending_tickets()
    assert not any(t.ticket_id in (t1, t2) for t in pending)


def test_focus_manager_prunes_expired_ticket_notifications(tmp_path):
    import time
    from core.focus_manager import FocusManager
    fm = FocusManager.get_instance(db_path=tmp_path / "focus_test.db")
    auth = CryptographicApprovalAuthority.get_instance()

    # Create an expired ticket (TTL negative so it's already expired)
    expired_tkt = auth.create_ticket(action_type="app_open", target="calc", ttl_seconds=-10)
    # Create an active unexpired ticket
    active_tkt = auth.create_ticket(action_type="app_open", target="notepad", ttl_seconds=3600)

    fm.enqueue_notification("task_expired", f"🔒 Permission requested for app_open [Ticket: {expired_tkt}].", "MEDIUM")
    fm.enqueue_notification("task_active", f"🔒 Permission requested for app_open [Ticket: {active_tkt}].", "MEDIUM")

    # Drain notifications: the expired one must be pruned/suppressed, and only active_tkt delivered
    drained = fm.drain_pending_notifications()
    assert len(drained) == 1
    assert active_tkt in drained[0].message
    assert expired_tkt not in drained[0].message
