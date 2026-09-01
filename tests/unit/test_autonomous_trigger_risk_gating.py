"""
Comprehensive Test Suite for M26 Autonomous Trigger Risk Gating & Resumable Approval.

Verifies:
1. HIGH-Risk Autonomous Bypass is Closed (default-deny for non-interactive sources).
2. Tamper Detection on Cryptographically Signed Capability Whitelist.
3. End-to-End Clean DAG Suspension and Resumption via Cryptographic Approval Ticket.
4. Singleton-Pending-Per-Trigger Deduplication (no approval pile-up on recurring triggers).
5. Expired Approval Ticket Clean Abort.
"""

import json
import time
from pathlib import Path
import pytest

from desktop.native.security.approval_authority import CryptographicApprovalAuthority
from personal_os.state_store import PersonalOSStateStore
from core.focus_manager import FocusManager
from core.orchestration.master_orchestrator import MasterOrchestrator
from core.orchestration.request_source import RequestSource
from core.orchestration.task_decomposer import TaskGraph, SubTask, PlannerRole


@pytest.fixture(autouse=True)
def reset_singletons(tmp_path):
    CryptographicApprovalAuthority.reset_instance()
    PersonalOSStateStore.reset_instance()
    FocusManager.reset_instance()

    # Initialize with isolated temp DBs
    db_file = tmp_path / "test_os_state.sqlite3"
    PersonalOSStateStore.get_instance(db_path=db_file)
    FocusManager.get_instance(db_path=tmp_path / "test_focus.sqlite3")

    yield

    CryptographicApprovalAuthority.reset_instance()
    PersonalOSStateStore.reset_instance()
    FocusManager.reset_instance()


@pytest.mark.asyncio
async def test_trigger_high_risk_bypass_closed():
    """
    Test 1: Proves that an autonomous trigger with an unwhitelisted HIGH-risk action
    does NOT execute unattended and does NOT hang silently.
    It must generate an AUTH-XXXXXX ticket and cleanly suspend.
    """
    orchestrator = MasterOrchestrator()
    graph = TaskGraph(goal="Delete critical configuration file")
    
    # Add a HIGH-risk subtask
    subtask = SubTask(
        task_id="st_1",
        title="Delete Config",
        required_role=PlannerRole.CODEACT,
        capability="file.delete",
        description="Delete system config file",
        parameters={"path": "C:/config.json"},
    )
    graph.add_task(subtask)

    # Run as TRIGGER_AUTONOMOUS without pre-authorization
    result = await orchestrator.process_request_async(
        goal_text="Delete critical configuration file",
        task_graph=graph,
        source=RequestSource.TRIGGER_AUTONOMOUS,
        parameters={"trigger_id": "nightly_clean_trigger"},
    )

    # Assert that execution did NOT bypass to success, and did NOT hang
    assert result.success is False
    assert result.data.get("is_suspended") is True
    
    ticket_id = result.data.get("suspended_ticket_id")
    assert ticket_id is not None
    assert ticket_id.startswith("tkt_") or ticket_id.startswith("AUTH-")

    # Verify ticket exists in CryptographicApprovalAuthority
    auth = CryptographicApprovalAuthority.get_instance()
    ticket = auth.get_ticket(ticket_id)
    assert ticket is not None
    assert ticket.action_type == "file.delete"
    assert ticket.is_redeemed is False

    # Verify suspended state exists in PersonalOSStateStore
    os_store = PersonalOSStateStore.get_instance()
    record = os_store.get_suspended_session(ticket_id)
    assert record is not None
    assert record["trigger_id"] == "nightly_clean_trigger"
    assert record["status"] == "PENDING"

    # Verify FocusManager received a notification
    from core.focus_manager import FocusManager
    notifications = FocusManager.get_instance().drain_pending_notifications()
    assert any(ticket_id in n.message for n in notifications)
    assert any(n.severity == "MEDIUM" for n in notifications)


def test_hmac_tamper_detection_on_whitelist():
    """
    Test 2: Verifies that mutating allowed_capabilities without re-signing
    fails HMAC cryptographic verification.
    """
    auth = CryptographicApprovalAuthority.get_instance()
    trigger_id = "backup_trigger_01"
    goal = "Backup project repository"
    exec_map = {"step": "run_backup"}
    legit_caps = ["backup.create", "archive.compress"]

    # Legitimate signature
    valid_sig = auth.sign_trigger(
        trigger_id=trigger_id,
        action_goal=goal,
        execution_map=exec_map,
        allowed_capabilities=legit_caps,
    )

    # 1. Valid signature passes
    is_valid, _ = auth.verify_trigger_signature(
        trigger_id=trigger_id,
        action_goal=goal,
        execution_map=exec_map,
        signature=valid_sig,
        allowed_capabilities=legit_caps,
    )
    assert is_valid is True

    # 2. Tampered allowed_capabilities (adversary adds 'file.delete')
    tampered_caps = ["backup.create", "archive.compress", "file.delete"]
    is_tampered_valid, err_msg = auth.verify_trigger_signature(
        trigger_id=trigger_id,
        action_goal=goal,
        execution_map=exec_map,
        signature=valid_sig,  # Old signature without 'file.delete'
        allowed_capabilities=tampered_caps,
    )
    assert is_tampered_valid is False
    assert "tampered" in err_msg.lower() or "mismatch" in err_msg.lower()


@pytest.mark.asyncio
async def test_trigger_suspension_and_resume_loop():
    """
    Test 3: Real End-to-End Execution of Suspension and Resumption.
    DAG has Step 1 (Safe read) -> Step 2 (High-Risk action).
    Trigger runs -> Step 1 completes -> Step 2 suspends -> AUTH ticket issued.
    User approves ticket -> DAG resumes -> Step 2 completes cleanly.
    """
    orchestrator = MasterOrchestrator()
    graph = TaskGraph(goal="Multi-step maintenance workflow")

    # Step 1: Safe read-only step
    st1 = SubTask(
        task_id="step_1",
        title="Check Memory",
        required_role=PlannerRole.CODEACT,
        capability="system.info",
        description="Check system memory info",
        parameters={},
    )
    # Step 2: High-risk file modification step
    test_file = Path("test_temp_logs.txt").resolve()
    st2 = SubTask(
        task_id="step_2",
        title="Delete Logs",
        required_role=PlannerRole.CODEACT,
        capability="file.delete",
        description="Remove temp logs",
        parameters={"path": str(test_file)},
        dependencies=["step_1"],
    )
    graph.add_task(st1)
    graph.add_task(st2)

    # 1. Run as autonomous trigger (halts on step 2)
    res_initial = await orchestrator.process_request_async(
        goal_text="Multi-step maintenance workflow",
        task_graph=graph,
        source=RequestSource.TRIGGER_AUTONOMOUS,
        parameters={"trigger_id": "cleanup_routine_1"},
    )

    assert res_initial.data.get("is_suspended") is True
    ticket_id = res_initial.data["suspended_ticket_id"]
    assert ticket_id.startswith("tkt_") or ticket_id.startswith("AUTH-")

    os_store = PersonalOSStateStore.get_instance()
    record = os_store.get_suspended_session(ticket_id)
    assert record["status"] == "PENDING"
    assert record["subtask_id"] == "step_2"

    # Verify Step 1 completed before suspension
    saved_graph_data = json.loads(record["task_graph_json"])
    assert "step_1" in saved_graph_data["completed_ids"]

    # 2. User approves ticket via approve_and_resume_ticket()
    res_resumed = await orchestrator.approve_and_resume_ticket(ticket_id=ticket_id)

    # 3. Assert resumed execution completed
    assert res_resumed.success is True
    assert res_resumed.data.get("metrics", {}).get("subtasks_completed") == 2

    # Verify store record marked as REDEEMED
    updated_record = os_store.get_suspended_session(ticket_id)
    assert updated_record["status"] == "REDEEMED"


@pytest.mark.asyncio
async def test_duplicate_trigger_firing_deduplication():
    """
    Test 4: Verifies Singleton-Pending-Per-Trigger Policy.
    A recurring trigger that already has an unexpired pending ticket does not
    create duplicate tickets upon repeated firings.
    """
    orchestrator = MasterOrchestrator()
    graph = TaskGraph(goal="Recurring disk cleanup")
    st = SubTask(
        task_id="st_clean",
        title="Clean Disk",
        required_role=PlannerRole.CODEACT,
        capability="file.delete",
        description="Clean disk space",
        parameters={"target": "temp_dir"},
    )
    graph.add_task(st)

    # Firing 1
    res1 = await orchestrator.process_request_async(
        goal_text="Recurring disk cleanup",
        task_graph=graph,
        source=RequestSource.TRIGGER_AUTONOMOUS,
        parameters={"trigger_id": "daily_disk_clean"},
    )
    ticket_1 = res1.data["suspended_ticket_id"]

    # Firing 2 (next scheduled occurrence while ticket 1 is still unapproved)
    graph2 = TaskGraph(goal="Recurring disk cleanup")
    st2 = SubTask(
        task_id="st_clean",
        title="Clean Disk",
        required_role=PlannerRole.CODEACT,
        capability="file.delete",
        description="Clean disk space",
        parameters={"target": "temp_dir"},
    )
    graph2.add_task(st2)

    res2 = await orchestrator.process_request_async(
        goal_text="Recurring disk cleanup",
        task_graph=graph2,
        source=RequestSource.TRIGGER_AUTONOMOUS,
        parameters={"trigger_id": "daily_disk_clean"},
    )
    ticket_2 = res2.data["suspended_ticket_id"]

    # Must reuse the same pending ticket and NOT create a second ticket
    assert ticket_1 == ticket_2


@pytest.mark.asyncio
async def test_ticket_ttl_expiry_aborts_cleanly():
    """
    Test 5: Verifies that an expired approval ticket rejects redemption
    and aborts cleanly without executing side effects.
    """
    orchestrator = MasterOrchestrator()
    auth = CryptographicApprovalAuthority.get_instance()
    os_store = PersonalOSStateStore.get_instance()

    # Generate a ticket with 0.001-second TTL (instant expiry)
    ticket_id = auth.create_ticket(
        action_type="file.delete",
        target="C:/important_file.txt",
        parameters={"path": "C:/important_file.txt"},
        ttl_seconds=0.001,
    )
    ticket = auth.get_ticket(ticket_id)
    time.sleep(0.01)  # Ensure expiry

    # Save mock suspended session
    os_store.save_suspended_session(
        ticket_id=ticket.ticket_id,
        trigger_id="expired_trigger",
        session_id="session_expired",
        task_graph_json=json.dumps({"goal_text": "Delete file", "subtasks": {}}),
        subtask_id="st_exp",
        expires_at=ticket.expires_at,
    )

    # Attempt to approve expired ticket
    result = await orchestrator.approve_and_resume_ticket(ticket_id=ticket.ticket_id)

    assert result.success is False
    assert result.data.get("error") == "TICKET_EXPIRED"

    # Verify store status is updated to EXPIRED_ABORTED
    record = os_store.get_suspended_session(ticket.ticket_id)
    assert record["status"] == "EXPIRED_ABORTED"


@pytest.mark.asyncio
async def test_end_to_end_trigger_registration_and_preauthorized_execution():
    """
    Test 6: Verifies real trigger registration via PersonalOSBackend/StateStore.
    1. Creates trigger with allowed_capabilities=['file.delete'] -> binds HMAC auth_signature.
    2. Runs autonomous trigger with the pre-authorized capability -> executes without suspension.
    """
    from core.backends.adapters.personal_os_backend import PersonalOSBackendAdapter

    backend = PersonalOSBackendAdapter()
    test_file = Path("test_cleanup_file.txt").resolve()

    # 1. Register trigger via personal_os.trigger.create
    create_result = backend.execute(
        capability="personal_os.trigger.create",
        goal="Create daily cleanup trigger",
        arguments={
            "name": "daily_temp_cleaner",
            "goal_text": "Clean temporary test files",
            "schedule": "0 2 * * *",
            "allowed_capabilities": ["file.delete"],
        },
    )
    assert create_result.success is True
    trigger_data = create_result.data["trigger"]
    assert "auth_signature" in trigger_data["metadata"]
    assert trigger_data["metadata"]["allowed_capabilities"] == ["file.delete"]

    # 2. Run MasterOrchestrator with this pre-authorized trigger
    orchestrator = MasterOrchestrator()
    graph = TaskGraph(goal="Clean temporary test files")
    st = SubTask(
        task_id="st_clean",
        title="Delete Temp File",
        required_role=PlannerRole.CODEACT,
        capability="file.delete",
        description="Delete temporary test file",
        parameters={"path": str(test_file)},
    )
    graph.add_task(st)

    exec_result = await orchestrator.process_request_async(
        goal_text="Clean temporary test files",
        task_graph=graph,
        source=RequestSource.TRIGGER_AUTONOMOUS,
        parameters={
            "trigger_id": trigger_data["trigger_id"],
            "auth_signature": trigger_data["metadata"]["auth_signature"],
            "allowed_capabilities": trigger_data["metadata"]["allowed_capabilities"],
        },
    )

    # Pre-authorized trigger succeeds directly without suspension
    assert exec_result.data.get("is_suspended") is not True
    assert exec_result.success is True

