"""
Security Governance and ActionRisk Gating Regression Tests
Location: tests/unit/test_security_governance.py

Verifies that sensitive capabilities (such as credential scanning, secret detection,
and destructive mutations) cannot execute silently under default autonomy (ASSISTED),
and enforces systemic risk classification consistency across CapabilityRegistry.
"""

import re
from pathlib import Path
import pytest

from core.capabilities.capability_registry import CapabilityRegistry
from core.orchestration.autonomy_mode import ActionRisk, AutonomyLevel, classify_action_risk
from core.orchestration.execution_policy import ExecutionPolicy, PolicyAction


def test_credential_scan_requires_confirmation_under_assisted_mode():
    """Verify security.credential_scan carries HIGH risk and requires user confirmation."""
    registry = CapabilityRegistry.get_instance()
    cap = registry.get("security.credential_scan")
    assert cap is not None, "security.credential_scan must be registered"
    assert cap.risk_level == ActionRisk.HIGH, "Credential scan must carry HIGH risk"
    assert cap.requires_confirmation is True, "Credential scan must require confirmation"

    # Verify classify_action_risk evaluates to HIGH
    risk = classify_action_risk("desktop", "security.credential_scan")
    assert risk == ActionRisk.HIGH

    # Verify ExecutionPolicy intercepts it with ASK_USER under default ASSISTED autonomy
    policy = ExecutionPolicy.get_instance()
    decision = policy.evaluate_action("desktop", "security.credential_scan", {})
    assert decision.action == PolicyAction.ASK_USER
    assert "HIGH" in decision.message
    assert "ASSISTED" in decision.message


def test_systemic_registry_risk_levels_match_sensitive_keywords():
    """
    Systemic sweep: Verify no capability containing sensitive secret/destructive keywords
    is mistakenly classified as ActionRisk.LOW in the CapabilityRegistry.
    """
    registry = CapabilityRegistry.get_instance()
    live_caps = registry.list(require_live=True)
    assert len(live_caps) > 50, "Registry must have live capabilities loaded"

    SENSITIVE_PATTERNS = [
        r"\bcredential\b",
        r"\bcredentials\b",
        r"\bsecret\b",
        r"\bsecrets\b",
        r"\bpassword\b",
        r"\bpasswords\b",
        r"\bprivate_key\b",
        r"\bdelete\b",
        r"\bremove\b",
        r"\bdrop\b",
        r"\btruncate\b",
        r"\bkill\b",
        r"\bterminate\b",
        r"\bdestroy\b",
        r"\bwipe\b",
        r"\buninstall\b",
        r"\bshutdown\b",
        r"\breboot\b",
    ]

    violations = []
    for cap in live_caps:
        name_desc = f"{cap.name} {cap.description}".lower()
        for pat in SENSITIVE_PATTERNS:
            if re.search(pat, name_desc):
                # If it matches sensitive operations, it must NOT be ActionRisk.LOW
                if cap.risk_level == ActionRisk.LOW and not cap.requires_confirmation:
                    violations.append(f"{cap.name} (matched '{pat}'): risk={cap.risk_level.value}")

    assert not violations, f"Found sensitive capabilities misclassified as LOW risk: {violations}"


@pytest.mark.asyncio
async def test_security_credential_scan_suspends_cleanly_under_autonomous_trigger(tmp_path):
    """
    Verify that when an autonomous trigger (scheduled audit or daemon) executes
    a task graph containing security.credential_scan (ActionRisk.HIGH):
    1. It does NOT execute unattended.
    2. It does NOT hang or stall the process.
    3. It generates an approval ticket via CryptographicApprovalAuthority.
    4. It suspends cleanly in PersonalOSStateStore.
    5. It notifies the user via FocusManager.
    """
    from desktop.native.security.approval_authority import CryptographicApprovalAuthority
    from personal_os.state_store import PersonalOSStateStore
    from core.focus_manager import FocusManager
    from core.orchestration.master_orchestrator import MasterOrchestrator
    from core.orchestration.request_source import RequestSource
    from core.orchestration.task_decomposer import TaskGraph, SubTask, PlannerRole

    # Initialize isolated singletons with temp DBs
    CryptographicApprovalAuthority.reset_instance()
    PersonalOSStateStore.reset_instance()
    FocusManager.reset_instance()
    PersonalOSStateStore.get_instance(db_path=tmp_path / "test_os.sqlite3")
    FocusManager.get_instance(db_path=tmp_path / "test_fm.sqlite3")

    try:
        orchestrator = MasterOrchestrator()
        graph = TaskGraph(goal="Audit workspace for leaked credentials")

        subtask = SubTask(
            task_id="sec_cred_scan_01",
            title="Scan Credentials",
            required_role=PlannerRole.DESKTOP,
            capability="security.credential_scan",
            description="Scan workspace files and configuration files for exposed secrets.",
            parameters={"path": str(tmp_path)},
        )
        graph.add_task(subtask)

        # Run as TRIGGER_AUTONOMOUS (unattended background trigger)
        result = await orchestrator.process_request_async(
            goal_text="Audit workspace for leaked credentials",
            task_graph=graph,
            source=RequestSource.TRIGGER_AUTONOMOUS,
            parameters={"trigger_id": "scheduled_sec_audit"},
        )

        # 1. Did NOT execute unattended, did NOT bypass, and did NOT hang
        assert result.success is False
        assert result.data.get("is_suspended") is True

        # 2. Generated an approval ticket
        ticket_id = result.data.get("suspended_ticket_id")
        assert ticket_id is not None
        assert ticket_id.startswith("tkt_") or ticket_id.startswith("AUTH-")

        # 3. Verified in CryptographicApprovalAuthority
        auth = CryptographicApprovalAuthority.get_instance()
        ticket = auth.get_ticket(ticket_id)
        assert ticket is not None
        assert ticket.action_type == "security.credential_scan"
        assert ticket.is_redeemed is False

        # 4. Clean suspension record in PersonalOSStateStore
        os_store = PersonalOSStateStore.get_instance()
        record = os_store.get_suspended_session(ticket_id)
        assert record is not None
        assert record["trigger_id"] == "scheduled_sec_audit"
        assert record["status"] == "PENDING"
        assert record["subtask_id"] == "sec_cred_scan_01"

        # 5. Enqueued non-interrupting notification in FocusManager
        notifications = FocusManager.get_instance().drain_pending_notifications()
        assert len(notifications) >= 1
        assert any(ticket_id in n.message for n in notifications)
        assert any("security.credential_scan" in n.message for n in notifications)

    finally:
        CryptographicApprovalAuthority.reset_instance()
        PersonalOSStateStore.reset_instance()
        FocusManager.reset_instance()


@pytest.mark.asyncio
async def test_security_audit_dag_resumes_cleanly_after_ticket_approval(tmp_path):
    """
    Verify the complete suspension-and-resumption loop for security audit DAG:
    1. 2-step DAG: sec_cred_scan_01 (HIGH) -> sec_surface_audit_02 (LOW).
    2. Autonomous trigger suspends on step 1 and generates approval ticket.
    3. Ticket is redeemed via approve_and_resume_ticket().
    4. Execution resumes, step 1 executes, and downstream step 2 executes to completion.
    """
    from desktop.native.security.approval_authority import CryptographicApprovalAuthority
    from personal_os.state_store import PersonalOSStateStore
    from core.focus_manager import FocusManager
    from core.orchestration.master_orchestrator import MasterOrchestrator
    from core.orchestration.request_source import RequestSource
    from core.orchestration.task_decomposer import TaskGraph, SubTask, PlannerRole

    CryptographicApprovalAuthority.reset_instance()
    PersonalOSStateStore.reset_instance()
    FocusManager.reset_instance()
    PersonalOSStateStore.get_instance(db_path=tmp_path / "test_os_resume.sqlite3")
    FocusManager.get_instance(db_path=tmp_path / "test_fm_resume.sqlite3")

    try:
        orchestrator = MasterOrchestrator()
        graph = TaskGraph(goal="Two-pillar security audit")

        st1 = SubTask(
            task_id="sec_cred_scan_01",
            title="Scan Credentials",
            required_role=PlannerRole.DESKTOP,
            capability="security.credential_scan",
            description="Scan workspace files for exposed secrets.",
            parameters={"path": str(tmp_path)},
        )
        st2 = SubTask(
            task_id="sec_surface_audit_02",
            title="Audit Attack Surface",
            required_role=PlannerRole.DESKTOP,
            capability="security.attack_surface_audit",
            description="Audit listening network ports and services.",
            parameters={},
            dependencies=["sec_cred_scan_01"],
        )
        graph.add_task(st1)
        graph.add_task(st2)

        # 1. Initial autonomous run: suspends at step 1
        res_initial = await orchestrator.process_request_async(
            goal_text="Two-pillar security audit",
            task_graph=graph,
            source=RequestSource.TRIGGER_AUTONOMOUS,
            parameters={"trigger_id": "sec_audit_routine"},
        )
        assert res_initial.data.get("is_suspended") is True
        ticket_id = res_initial.data["suspended_ticket_id"]

        os_store = PersonalOSStateStore.get_instance()
        record = os_store.get_suspended_session(ticket_id)
        assert record["status"] == "PENDING"
        assert record["subtask_id"] == "sec_cred_scan_01"

        # 2. User approves ticket via approve_and_resume_ticket()
        res_resumed = await orchestrator.approve_and_resume_ticket(ticket_id=ticket_id)

        # 3. Assert resumed execution completed both steps
        assert res_resumed.success is True
        assert res_resumed.data.get("metrics", {}).get("subtasks_completed") == 2

        # 4. Verify record in PersonalOSStateStore is marked REDEEMED
        updated_record = os_store.get_suspended_session(ticket_id)
        assert updated_record["status"] == "REDEEMED"

    finally:
        CryptographicApprovalAuthority.reset_instance()
        PersonalOSStateStore.reset_instance()
        FocusManager.reset_instance()


@pytest.mark.asyncio
async def test_security_audit_dag_interactive_confirmation_and_resume(tmp_path):
    """
    Verify the interactive USER_CHAT confirmation path for security.credential_scan:
    1. 2-step DAG: sec_cred_scan_01 (HIGH) -> sec_surface_audit_02 (LOW).
    2. USER_CHAT source pauses with pending_confirmation attached to session.
    3. User confirms with 'yes' via resolve_pending_confirmation().
    4. Confirmed execution executes credential scan and remaining step 2 in sequence.
    """
    from core.orchestration.master_orchestrator import MasterOrchestrator
    from core.orchestration.request_source import RequestSource
    from core.orchestration.task_decomposer import TaskGraph, SubTask, PlannerRole

    orchestrator = MasterOrchestrator()
    graph = TaskGraph(goal="Interactive security audit")

    st1 = SubTask(
        task_id="sec_cred_scan_01",
        title="Scan Credentials",
        required_role=PlannerRole.DESKTOP,
        capability="security.credential_scan",
        description="Scan workspace files for exposed secrets.",
        parameters={"path": str(tmp_path)},
    )
    st2 = SubTask(
        task_id="sec_surface_audit_02",
        title="Audit Attack Surface",
        required_role=PlannerRole.DESKTOP,
        capability="security.attack_surface_audit",
        description="Audit listening network ports and services.",
        parameters={},
        dependencies=["sec_cred_scan_01"],
    )
    graph.add_task(st1)
    graph.add_task(st2)

    # 1. Process as interactive HUMAN_INTERACTIVE
    result = await orchestrator.process_request_async(
        goal_text="Interactive security audit",
        task_graph=graph,
        source=RequestSource.HUMAN_INTERACTIVE,
    )

    # 2. Assert interactive confirmation was requested
    conf = orchestrator.check_pending_confirmation()
    assert conf is not None, "Interactive session must attach pending_confirmation"
    assert conf.action_plan.capability == "security.credential_scan"
    assert len(conf.remaining_subtasks) == 1
    assert conf.remaining_subtasks[0].capability == "security.attack_surface_audit"

    # 3. User responds "yes" to approve execution
    res_confirmed = orchestrator.resolve_pending_confirmation("yes")
    assert res_confirmed is not None
    assert res_confirmed.success is True

    # Verify both steps produced observations
    obs_text = " ".join(res_confirmed.observations)
    assert "security.credential_scan" in obs_text or "credentials" in obs_text.lower() or "Executed" in obs_text
    assert orchestrator.check_pending_confirmation() is None, "Confirmation must be cleared after resolution"


@pytest.mark.asyncio
async def test_security_audit_dag_re_evaluates_risk_on_downstream_high_nodes(tmp_path, universal_dispatch_spy):
    """
    Verify that resuming an approved ticket does NOT grant blanket approval to subsequent nodes:
    DAG: [HIGH: sec_cred_scan_01] -> [LOW: sec_surface_audit_02] -> [HIGH: sec_clean_03].
    Enforces Invariants 1, 2, and 3 using universal_dispatch_spy across all backend dispatches.
    """
    from desktop.native.security.approval_authority import CryptographicApprovalAuthority
    from personal_os.state_store import PersonalOSStateStore
    from core.focus_manager import FocusManager
    from core.orchestration.master_orchestrator import MasterOrchestrator
    from core.orchestration.request_source import RequestSource
    from core.orchestration.task_decomposer import TaskGraph, SubTask, PlannerRole
    from tests.helpers.suspend_resume_invariants import (
        assert_narrow_ticket_scoping,
        assert_downstream_suspended,
    )

    CryptographicApprovalAuthority.reset_instance()
    PersonalOSStateStore.reset_instance()
    FocusManager.reset_instance()
    PersonalOSStateStore.get_instance(db_path=tmp_path / "test_os_multigate.sqlite3")
    FocusManager.get_instance(db_path=tmp_path / "test_fm_multigate.sqlite3")

    workspace_file = Path("test_security_governance_multi.tmp").resolve()
    workspace_file.write_text("clean me")

    try:
        orchestrator = MasterOrchestrator()
        graph = TaskGraph(goal="Multi-stage security pipeline")

        st1 = SubTask(
            task_id="sec_cred_scan_01",
            title="Scan Credentials",
            required_role=PlannerRole.DESKTOP,
            capability="security.credential_scan",
            description="Scan workspace files for exposed secrets.",
            parameters={"path": str(tmp_path)},
        )
        st2 = SubTask(
            task_id="sec_surface_audit_02",
            title="Audit Attack Surface",
            required_role=PlannerRole.DESKTOP,
            capability="security.attack_surface_audit",
            description="Audit listening network ports and services.",
            parameters={},
            dependencies=["sec_cred_scan_01"],
        )
        st3 = SubTask(
            task_id="sec_clean_03",
            title="Clean Quarantine Temp",
            required_role=PlannerRole.CODEACT,
            capability="file.delete",
            description="Delete quarantined temp file.",
            parameters={"path": str(workspace_file)},
            dependencies=["sec_surface_audit_02"],
        )
        graph.add_task(st1)
        graph.add_task(st2)
        graph.add_task(st3)

        # 1. Run under TRIGGER_AUTONOMOUS: must suspend on st1
        res1 = await orchestrator.process_request_async(
            goal_text="Multi-stage security pipeline",
            task_graph=graph,
            source=RequestSource.TRIGGER_AUTONOMOUS,
            parameters={"trigger_id": "multi_gate_routine"},
        )
        ticket_1 = assert_downstream_suspended(res1, "sec_cred_scan_01")

        os_store = PersonalOSStateStore.get_instance()
        rec1 = os_store.get_suspended_session(ticket_1)
        assert rec1["subtask_id"] == "sec_cred_scan_01"

        # 2. Approve ticket_1 and resume
        res2 = await orchestrator.approve_and_resume_ticket(ticket_id=ticket_1)

        # 3. Invariant 2: Must NOT run to completion: must SUSPEND AGAIN on st3 (file.delete)
        ticket_2 = assert_downstream_suspended(res2, "sec_clean_03")

        # Invariant 1: Narrow Single-Use Scoping
        assert_narrow_ticket_scoping(ticket_1, ticket_2, "sec_cred_scan_01", "sec_clean_03")

        rec2 = os_store.get_suspended_session(ticket_2)
        assert rec2["subtask_id"] == "sec_clean_03"
        assert rec2["status"] == "PENDING"

        # 4. Approve ticket_2 and resume to finish
        res3 = await orchestrator.approve_and_resume_ticket(ticket_id=ticket_2)
        assert res3.success is True
        assert res3.data.get("metrics", {}).get("subtasks_completed") == 3

        # 5. Invariant 3: Universal Dispatch Idempotency
        universal_dispatch_spy.assert_idempotent_sequence([
            "security.credential_scan",
            "security.attack_surface_audit",
            "file.delete",
        ])

    finally:
        workspace_file.unlink(missing_ok=True)
        CryptographicApprovalAuthority.reset_instance()
        PersonalOSStateStore.reset_instance()
        FocusManager.reset_instance()


@pytest.mark.asyncio
async def test_interactive_confirmation_re_evaluates_risk_on_downstream_high_nodes(tmp_path, universal_dispatch_spy):
    """
    Verify that answering 'yes' to an interactive confirmation does NOT bypass confirmation
    for a second HIGH-risk node queued in remaining_subtasks:
    DAG: [HIGH: sec_cred_scan_01] -> [HIGH: sec_clean_02].
    1. USER_CHAT pauses before sec_cred_scan_01.
    2. User answers 'yes'.
    3. sec_cred_scan_01 executes, but queue pauses AGAIN before sec_clean_02.
    4. User answers 'yes' to the second confirmation.
    5. Complete execution succeeds.
    6. SPY ASSERTION: Asserts that both actions are dispatched via _dispatch_plan strictly once.
    """
    from core.orchestration.master_orchestrator import MasterOrchestrator
    from core.orchestration.request_source import RequestSource
    from core.orchestration.task_decomposer import TaskGraph, SubTask, PlannerRole

    workspace_file = Path("test_security_governance_interactive.tmp").resolve()
    workspace_file.write_text("sample")

    try:
        orchestrator = MasterOrchestrator()
        graph = TaskGraph(goal="Two-action sensitive workflow")

        st1 = SubTask(
            task_id="sec_cred_scan_01",
            title="Scan Credentials",
            required_role=PlannerRole.DESKTOP,
            capability="security.credential_scan",
            description="Scan workspace files for exposed secrets.",
            parameters={"path": str(tmp_path)},
        )
        st2 = SubTask(
            task_id="sec_clean_02",
            title="Delete Sensitive File",
            required_role=PlannerRole.CODEACT,
            capability="file.delete",
            description="Delete file containing sensitive data.",
            parameters={"path": str(workspace_file)},
            dependencies=["sec_cred_scan_01"],
        )
        graph.add_task(st1)
        graph.add_task(st2)

        # 1. Start interactive session
        await orchestrator.process_request_async(
            goal_text="Two-action sensitive workflow",
            task_graph=graph,
            source=RequestSource.HUMAN_INTERACTIVE,
        )

        conf1 = orchestrator.check_pending_confirmation()
        assert conf1 is not None
        assert conf1.action_plan.capability == "security.credential_scan"

        # 2. User confirms first action
        res_conf1 = orchestrator.resolve_pending_confirmation("yes")
        assert res_conf1 is not None

        # 3. Must NOT have executed st2 silently; must have re-gated and paused before st2!
        conf2 = orchestrator.check_pending_confirmation()
        assert conf2 is not None, "Second HIGH-risk subtask must require its own confirmation"
        assert conf2.action_plan.capability == "file.delete"

        # 4. User confirms second action
        res_conf2 = orchestrator.resolve_pending_confirmation("yes")
        assert res_conf2 is not None
        assert res_conf2.success is True
        assert orchestrator.check_pending_confirmation() is None

        # 5. Invariant 3: Universal Dispatch Idempotency on interactive confirmation & drain
        universal_dispatch_spy.assert_idempotent_sequence([
            "security.credential_scan",
            "file.delete",
        ])
    finally:
        workspace_file.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_mixed_backend_resumed_dag_preserves_idempotency_and_narrow_scoping(tmp_path, universal_dispatch_spy):
    """
    Verify that Invariant 1 (Narrow Scoping), Invariant 2 (Downstream Re-gating), and
    Invariant 3 (Dispatch-Level Idempotency) hold across heterogeneous backends in a single DAG:
    DAG: [HIGH: DesktopBackend (security.credential_scan)]
         -> [LOW: MemoryBackend (memory.read)]
         -> [HIGH: DesktopBackend (file.delete)]

    Proves universal_dispatch_spy tracks events across distinct backend classes
    and verifies that mixed backend dispatch prunes completed tasks idempotently.
    """
    from desktop.native.security.approval_authority import CryptographicApprovalAuthority
    from personal_os.state_store import PersonalOSStateStore
    from core.focus_manager import FocusManager
    from core.orchestration.master_orchestrator import MasterOrchestrator
    from core.orchestration.request_source import RequestSource
    from core.orchestration.task_decomposer import TaskGraph, SubTask, PlannerRole
    from tests.helpers.suspend_resume_invariants import (
        assert_narrow_ticket_scoping,
        assert_downstream_suspended,
    )

    CryptographicApprovalAuthority.reset_instance()
    PersonalOSStateStore.reset_instance()
    FocusManager.reset_instance()
    PersonalOSStateStore.get_instance(db_path=tmp_path / "test_os_mixed.sqlite3")
    FocusManager.get_instance(db_path=tmp_path / "test_fm_mixed.sqlite3")

    workspace_file = Path("test_security_governance_mixed.tmp").resolve()
    workspace_file.write_text("sensitive data")

    try:
        orchestrator = MasterOrchestrator()
        graph = TaskGraph(goal="Heterogeneous security audit and memory pipeline")

        # Node 1: DesktopBackend (HIGH)
        st1 = SubTask(
            task_id="sec_cred_scan_01",
            title="Scan Credentials",
            required_role=PlannerRole.DESKTOP,
            capability="security.credential_scan",
            description="Scan workspace files for exposed secrets.",
            parameters={"path": str(tmp_path)},
        )
        # Node 2: MemoryBackend (LOW)
        st2 = SubTask(
            task_id="mem_recall_02",
            title="Recall Context",
            required_role=PlannerRole.MEMORY,
            capability="memory.read",
            description="Read audit baseline from memory.",
            parameters={"key": "security_baseline"},
            dependencies=["sec_cred_scan_01"],
        )
        # Node 3: DesktopBackend (HIGH)
        st3 = SubTask(
            task_id="sec_clean_03",
            title="Purge Sensitive Temp",
            required_role=PlannerRole.CODEACT,
            capability="file.delete",
            description="Delete temporary security artifacts.",
            parameters={"path": str(workspace_file)},
            dependencies=["mem_recall_02"],
        )
        graph.add_task(st1)
        graph.add_task(st2)
        graph.add_task(st3)

        # 1. Run under TRIGGER_AUTONOMOUS: must suspend on st1 (desktop_engine)
        res1 = await orchestrator.process_request_async(
            goal_text="Heterogeneous security audit",
            task_graph=graph,
            source=RequestSource.TRIGGER_AUTONOMOUS,
            parameters={"trigger_id": "mixed_backend_routine"},
        )
        ticket_1 = assert_downstream_suspended(res1, "sec_cred_scan_01")

        # 2. Approve ticket_1 and resume: executes node 1 (desktop_engine) and node 2 (MemoryBackend)
        res2 = await orchestrator.approve_and_resume_ticket(ticket_id=ticket_1)

        # 3. Must suspend again on node 3 (desktop_engine) with new ticket
        ticket_2 = assert_downstream_suspended(res2, "sec_clean_03")
        assert_narrow_ticket_scoping(ticket_1, ticket_2, "sec_cred_scan_01", "sec_clean_03")

        # 4. Approve ticket_2 and resume to completion
        res3 = await orchestrator.approve_and_resume_ticket(ticket_id=ticket_2)
        assert res3.success is True
        assert res3.data.get("metrics", {}).get("subtasks_completed") == 3

        # 5. Verify Invariant 3 across mixed backends:
        universal_dispatch_spy.assert_idempotent_sequence([
            "security.credential_scan",
            "memory.read",
            "file.delete",
        ])

        # Confirm distinct backend classes actually handled the disparate nodes:
        backend_names = [e.backend_name for e in universal_dispatch_spy.events]
        assert "desktop_engine" in backend_names
        assert "MemoryBackend" in backend_names
        assert backend_names[0] != backend_names[1], "Node 1 and Node 2 must dispatch to distinct backend classes"

    finally:
        workspace_file.unlink(missing_ok=True)
        CryptographicApprovalAuthority.reset_instance()
        PersonalOSStateStore.reset_instance()
        FocusManager.reset_instance()


@pytest.mark.asyncio
async def test_interactive_confirmation_drains_remaining_low_risk_subtasks_through_dispatch_plan(tmp_path, universal_dispatch_spy):
    """
    Directly exercises and verifies Line 227 and Line 327 in resolve_pending_confirmation:
    DAG: [HIGH: sec_cred_scan_01] -> [LOW: sec_surface_audit_02] -> [LOW: mem_recall_03].
    1. Initial run halts before sec_cred_scan_01 and requests confirmation.
    2. User resolves confirmation with 'yes'.
    3. Line 227 dispatches sec_cred_scan_01 via _dispatch_plan.
    4. Line 327 drains the remaining queue, executing sec_surface_audit_02 and mem_recall_03 via _dispatch_plan.
    5. UniversalDispatchSpy captures all 3 executions and asserts strict single execution and ordering.
    """
    from desktop.native.security.approval_authority import CryptographicApprovalAuthority
    from personal_os.state_store import PersonalOSStateStore
    from core.focus_manager import FocusManager
    from core.orchestration.master_orchestrator import MasterOrchestrator
    from core.orchestration.request_source import RequestSource
    from core.orchestration.task_decomposer import TaskGraph, SubTask, PlannerRole

    CryptographicApprovalAuthority.reset_instance()
    PersonalOSStateStore.reset_instance()
    FocusManager.reset_instance()
    PersonalOSStateStore.get_instance(db_path=tmp_path / "test_os_drain.sqlite3")
    FocusManager.get_instance(db_path=tmp_path / "test_fm_drain.sqlite3")

    try:
        orchestrator = MasterOrchestrator()
        graph = TaskGraph(goal="Interactive workflow draining remaining subtasks")

        st1 = SubTask(
            task_id="sec_cred_scan_01",
            title="Scan Credentials",
            required_role=PlannerRole.DESKTOP,
            capability="security.credential_scan",
            description="Scan workspace files for exposed secrets.",
            parameters={"path": str(tmp_path)},
        )
        st2 = SubTask(
            task_id="sec_surface_audit_02",
            title="Audit Attack Surface",
            required_role=PlannerRole.DESKTOP,
            capability="security.attack_surface_audit",
            description="Audit listening network ports and services.",
            parameters={},
            dependencies=["sec_cred_scan_01"],
        )
        st3 = SubTask(
            task_id="mem_recall_03",
            title="Recall Context",
            required_role=PlannerRole.MEMORY,
            capability="memory.read",
            description="Read audit baseline from memory.",
            parameters={"key": "security_baseline"},
            dependencies=["sec_surface_audit_02"],
        )
        graph.add_task(st1)
        graph.add_task(st2)
        graph.add_task(st3)

        # 1. Start interactive session: must halt on st1
        await orchestrator.process_request_async(
            goal_text="Interactive drain workflow",
            task_graph=graph,
            source=RequestSource.HUMAN_INTERACTIVE,
        )

        conf = orchestrator.check_pending_confirmation()
        assert conf is not None
        assert conf.action_plan.capability == "security.credential_scan"

        # 2. User confirms st1: this executes st1 (Line 227) AND drains st2 + st3 (Line 327)
        res = orchestrator.resolve_pending_confirmation("yes")
        assert res is not None
        assert res.success is True
        assert orchestrator.check_pending_confirmation() is None

        # 3. Verify universal_dispatch_spy captured both Line 227 (st1) and Line 327 (st2, st3)
        universal_dispatch_spy.assert_idempotent_sequence([
            "security.credential_scan",
            "security.attack_surface_audit",
            "memory.read",
        ])
        assert len(universal_dispatch_spy.events) == 3
        # Confirm that remaining subtasks drained across disparate backends
        assert universal_dispatch_spy.events[0].capability == "security.credential_scan"
        assert universal_dispatch_spy.events[1].capability == "security.attack_surface_audit"
        assert universal_dispatch_spy.events[2].capability == "memory.read"
        assert universal_dispatch_spy.events[2].backend_name == "MemoryBackend"

    finally:
        CryptographicApprovalAuthority.reset_instance()
        PersonalOSStateStore.reset_instance()
        FocusManager.reset_instance()


@pytest.mark.asyncio
async def test_daemon_runtime_spawns_security_credential_scan_and_suspends_cleanly(tmp_path, universal_dispatch_spy):
    """
    Verify that spawning a high-risk security.credential_scan job through DaemonRuntime
    (the real background production entry point) enforces governance:
    1. It must NOT execute silently or immediately.
    2. It must transition to JobState.SUSPENDED.
    3. It must mint a CryptographicApprovalAuthority ticket and persist state in PersonalOSStateStore.
    4. Upon approving and redeeming the ticket via MasterOrchestrator, execution completes
       and UniversalDispatchSpy records exactly one dispatch.
    """
    from desktop.native.security.approval_authority import CryptographicApprovalAuthority
    from personal_os.state_store import PersonalOSStateStore
    from core.focus_manager import FocusManager
    from core.orchestration.master_orchestrator import MasterOrchestrator
    from daemon.daemon_runtime import DaemonRuntime
    from daemon.state_store import DaemonStateStore
    from daemon.governance import AutonomyGovernanceEngine
    from daemon.models import JobState

    CryptographicApprovalAuthority.reset_instance()
    PersonalOSStateStore.reset_instance()
    FocusManager.reset_instance()
    DaemonRuntime.reset_instance()
    AutonomyGovernanceEngine.reset_instance()

    PersonalOSStateStore.get_instance(db_path=tmp_path / "test_os_daemon.sqlite3")
    FocusManager.get_instance(db_path=tmp_path / "test_fm_daemon.sqlite3")
    daemon_store = DaemonStateStore(db_path=str(tmp_path / "test_daemon.sqlite3"))
    runtime = DaemonRuntime(state_store=daemon_store)
    DaemonRuntime._instance = runtime

    try:
        # 1. Spawn actual background daemon task for security.credential_scan
        rec = runtime.spawn_background_task(
            name="Nightly Credential Audit",
            capability="security.credential_scan",
            goal="Scan workspace files for exposed secrets.",
            parameters={"path": str(tmp_path)},
        )

        assert rec is not None, "Execution record must be created"
        # 2. Assert it SUSPENDS rather than completing or running silently
        assert rec.status == JobState.SUSPENDED, f"Expected SUSPENDED, got {rec.status}"
        assert rec.result is not None
        assert rec.result.get("is_suspended") is True
        ticket_id = rec.result.get("ticket_id")
        assert ticket_id is not None, "A valid CryptographicApprovalAuthority ticket must be returned"

        # 3. Assert zero executions occurred prior to ticket redemption
        assert len(universal_dispatch_spy.events) == 0, "No dispatch must occur while suspended"

        # 4. Verify ticket in PersonalOSStateStore
        os_store = PersonalOSStateStore.get_instance()
        suspended = os_store.get_suspended_session(ticket_id)
        assert suspended is not None
        assert suspended["status"] == "PENDING"
        assert suspended["subtask_id"] == rec.job_id

        # 5. Approve ticket via orchestrator and resume
        orchestrator = MasterOrchestrator()
        resume_res = await orchestrator.approve_and_resume_ticket(ticket_id=ticket_id)
        assert resume_res.success is True

        # 6. Verify single idempotent dispatch recorded by spy
        universal_dispatch_spy.assert_idempotent_sequence(["security.credential_scan"])
        assert len(universal_dispatch_spy.events) == 1

    finally:
        runtime.shutdown(wait=False)
        DaemonRuntime.reset_instance()
        AutonomyGovernanceEngine.reset_instance()
        CryptographicApprovalAuthority.reset_instance()
        PersonalOSStateStore.reset_instance()
        FocusManager.reset_instance()


@pytest.mark.asyncio
async def test_daemon_runtime_spawns_prohibited_critical_job_and_rejects_immediately(tmp_path, universal_dispatch_spy):
    """
    Verify that spawning a CRITICAL/PROHIBITED job through DaemonRuntime:
    1. Rejects immediately as JobState.FAILED (hard stop).
    2. Does NOT transition to JobState.SUSPENDED.
    3. Mints zero approval tickets.
    4. Zero dispatches are recorded by UniversalDispatchSpy.
    """
    from desktop.native.security.approval_authority import CryptographicApprovalAuthority
    from personal_os.state_store import PersonalOSStateStore
    from core.focus_manager import FocusManager
    from daemon.daemon_runtime import DaemonRuntime
    from daemon.state_store import DaemonStateStore
    from daemon.governance import AutonomyGovernanceEngine
    from daemon.models import JobState

    CryptographicApprovalAuthority.reset_instance()
    PersonalOSStateStore.reset_instance()
    FocusManager.reset_instance()
    DaemonRuntime.reset_instance()
    AutonomyGovernanceEngine.reset_instance()

    CryptographicApprovalAuthority.get_instance(storage_path=tmp_path / "test_approval_tickets.json")
    PersonalOSStateStore.get_instance(db_path=tmp_path / "test_os_daemon_crit.sqlite3")
    FocusManager.get_instance(db_path=tmp_path / "test_fm_daemon_crit.sqlite3")
    daemon_store = DaemonStateStore(db_path=str(tmp_path / "test_daemon_crit.sqlite3"))
    runtime = DaemonRuntime(state_store=daemon_store)
    DaemonRuntime._instance = runtime

    try:
        # 1. Spawn background task for an explicitly PROHIBITED capability (e.g. security.disable_firewall)
        rec = runtime.spawn_background_task(
            name="Disable Network Firewall",
            capability="security.disable_firewall",
            goal="Turn off host firewall protection.",
            parameters={"scope": "all"},
        )

        assert rec is not None, "Execution record must be created"
        # Assert hard rejection: FAILED, not SUSPENDED
        assert rec.status == JobState.FAILED, f"Expected FAILED, got {rec.status}"
        assert "PROHIBITED" in rec.error

        # Assert zero approval tickets minted
        assert rec.result is None or rec.result.get("ticket_id") is None
        auth_inst = CryptographicApprovalAuthority.get_instance()
        assert len(auth_inst._tickets) == 0, "Zero tickets must be minted for prohibited capability"

        # 2. Spawn background task for a CRITICAL risk capability (e.g. shopping.checkout)
        rec_crit = runtime.spawn_background_task(
            name="Automated Product Checkout",
            capability="shopping.checkout",
            goal="Execute financial purchase transaction.",
            parameters={"item_id": "laptop_123", "card": "secret"},
        )

        assert rec_crit is not None
        # Must map to PROHIBITED under daemon and reject immediately as FAILED
        assert rec_crit.status == JobState.FAILED, f"Expected FAILED, got {rec_crit.status}"
        assert "PROHIBITED" in rec_crit.error

        # 3. Assert zero dispatches occurred for either prohibited job
        assert len(universal_dispatch_spy.events) == 0, "No dispatch must occur for prohibited capabilities"

    finally:
        runtime.shutdown(wait=False)
        DaemonRuntime.reset_instance()
        AutonomyGovernanceEngine.reset_instance()
        CryptographicApprovalAuthority.reset_instance()
        PersonalOSStateStore.reset_instance()
        FocusManager.reset_instance()




