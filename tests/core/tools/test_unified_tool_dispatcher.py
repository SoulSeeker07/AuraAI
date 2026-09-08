import pytest
import asyncio
from pathlib import Path
from core.tools.unified_tool_dispatcher import UnifiedToolDispatcher
from core.orchestration.agent_session import AgentSession
from desktop.native.security.approval_authority import CryptographicApprovalAuthority
from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_tool_definitions_count():
    tools = UnifiedToolDispatcher.get_tool_definitions()
    assert len(tools) == 21
    tool_names = [t["function"]["name"] for t in tools]
    expected = [
        "read_file", "edit_file", "run_tests",
        "terminal_run_command", "system_get_telemetry",
        "vision_inspect_screen", "browser_navigate_and_read",
        "browser_interact", "desktop_launch_app",
        "desktop_control_window", "desktop_clipboard",
        "desktop_set_volume", "desktop_set_brightness",
        "memory_save_fact", "memory_query_facts", "personal_os_agenda",
        "task_plan_update", "create_file_artifact",
        "smarthome_control", "email_action", "calendar_action"
    ]
    assert sorted(tool_names) == sorted(expected)

@pytest.mark.asyncio
async def test_read_file_safe_execution(tmp_path):
    # Test read_file on an existing file
    res = await UnifiedToolDispatcher.dispatch("read_file", {"path": "pyproject.toml", "start_line": 1, "end_line": 5})
    assert res["status"] == "success"
    assert "content" in res
    assert "1: " in res["content"]

@pytest.mark.asyncio
async def test_read_file_path_traversal_blocked():
    # Attempt to escape workspace
    res = await UnifiedToolDispatcher.dispatch("read_file", {"path": "../../../Windows/System32/drivers/etc/hosts"})
    assert res["status"] == "error"
    assert "Access denied" in res["error"]

@pytest.mark.asyncio
async def test_terminal_high_risk_requires_confirmation():
    session = AgentSession(goal="delete dangerous files")
    # Mutating command should be intercepted by policy
    res = await UnifiedToolDispatcher.dispatch(
        "terminal_run_command",
        {"command": "rm -rf some_dir"},
        session=session
    )
    assert res["status"] == "confirmation_required"
    assert res["requires_human_approval"] is True
    assert "ticket_id" in res
    assert res["ticket_id"].startswith("tkt_")
    assert session.pending_confirmation is not None

@pytest.mark.asyncio
async def test_task_plan_update():
    session = AgentSession(goal="test task plan")
    tasks = [
        {"task_id": "step_1", "title": "Inspect code", "status": "completed"},
        {"task_id": "step_2", "title": "Run tests", "status": "in_progress"}
    ]
    res = await UnifiedToolDispatcher.dispatch("task_plan_update", {"tasks": tasks}, session=session)
    assert res["status"] == "success"
    assert res["updated_count"] == 2
    assert session.data["task_plan"] == tasks

@pytest.mark.asyncio
async def test_terminal_valid_ticket_redemption():
    session = AgentSession(goal="delete files with ticket")
    # First attempt: generates ticket
    cmd = "echo 'testing high risk command' > some_temp_test.txt"
    res1 = await UnifiedToolDispatcher.dispatch("terminal_run_command", {"command": cmd}, session=session)
    assert res1["status"] == "confirmation_required"
    tkt_id = res1["ticket_id"]

    # Generate human signature / mark redeemable
    auth = CryptographicApprovalAuthority.get_instance()
    sig = auth.generate_human_signature(tkt_id)

    # Second attempt: with ticket_id and human signature, executes successfully
    res2 = await UnifiedToolDispatcher.dispatch(
        "terminal_run_command",
        {"command": cmd, "ticket_id": tkt_id, "signature": sig},
        session=session
    )
    assert res2["status"] in ("success", "executed")
    # Clean up created file if exists
    p = Path("some_temp_test.txt")
    if p.exists():
        p.unlink()

@pytest.mark.asyncio
async def test_edit_file_and_run_tests(tmp_path):
    test_file = Path("scratch/test_calc_temp.py")
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")

    try:
        # Edit file: change subtraction to addition
        edit_res = await UnifiedToolDispatcher.dispatch(
            "edit_file",
            {
                "path": "scratch/test_calc_temp.py",
                "target_content": "return a - b",
                "replacement_content": "return a + b"
            }
        )
        assert edit_res["status"] == "success"
        # Append a test function to test_calc_temp.py
        with open(test_file, "a", encoding="utf-8") as f:
            f.write("\ndef test_addition():\n    assert add(2, 2) == 4\n")

        # Run targeted tests on scratch/test_calc_temp.py
        test_res = await UnifiedToolDispatcher.dispatch(
            "run_tests",
            {"test_target": "scratch/test_calc_temp.py"}
        )
        assert test_res["status"] == "success"
        assert test_res["returncode"] == 0
        assert "1 passed" in test_res["stdout"]
    finally:
        if test_file.exists():
            test_file.unlink()

@pytest.mark.asyncio
async def test_edit_file_ticket_substitution_attack_blocked():
    from core.orchestration.execution_policy import ExecutionPolicy
    from core.orchestration.autonomy_mode import AutonomyLevel

    safe_file = Path("scratch/test_safe_sub.txt")
    safe_file.parent.mkdir(parents=True, exist_ok=True)
    safe_file.write_text("initial_state", encoding="utf-8")

    evil_file = Path("scratch/test_evil_sub.txt")
    evil_file.write_text("do_not_touch", encoding="utf-8")

    try:
        # 1. Under ASK autonomy, all actions require approval tickets
        with ExecutionPolicy.autonomy_scope(AutonomyLevel.ASK):
            res1 = await UnifiedToolDispatcher.dispatch(
                "edit_file",
                {
                    "path": str(safe_file),
                    "target_content": "initial_state",
                    "replacement_content": "approved_state"
                }
            )
            assert res1["status"] == "confirmation_required"
            tkt_id = res1["ticket_id"]

            auth = CryptographicApprovalAuthority.get_instance()
            sig = auth.generate_human_signature(tkt_id)
            assert sig is not None

            # 2. SUBSTITUTION ATTACK 1: Swap the target file
            attack1 = await UnifiedToolDispatcher.dispatch(
                "edit_file",
                {
                    "path": str(evil_file),  # Changed target path!
                    "target_content": "do_not_touch",
                    "replacement_content": "hacked_state",
                    "ticket_id": tkt_id,
                    "signature": sig,
                }
            )
            assert attack1["status"] == "error"
            assert attack1.get("security_alert") == "SUBSTITUTION_ATTACK_BLOCKED"
            assert "Action payload or command does not match" in attack1["error"]
            assert evil_file.read_text(encoding="utf-8") == "do_not_touch"

            # 3. SUBSTITUTION ATTACK 2: Same file, but swap replacement content
            attack2 = await UnifiedToolDispatcher.dispatch(
                "edit_file",
                {
                    "path": str(safe_file),
                    "target_content": "initial_state",
                    "replacement_content": "unapproved_evil_state",  # Changed content!
                    "ticket_id": tkt_id,
                    "signature": sig,
                }
            )
            assert attack2["status"] == "error"
            assert attack2.get("security_alert") == "SUBSTITUTION_ATTACK_BLOCKED"
            assert safe_file.read_text(encoding="utf-8") == "initial_state"

            # 4. LEGITIMATE REDEMPTION: Exact parameters match
            legit = await UnifiedToolDispatcher.dispatch(
                "edit_file",
                {
                    "path": str(safe_file),
                    "target_content": "initial_state",
                    "replacement_content": "approved_state",
                    "ticket_id": tkt_id,
                    "signature": sig,
                }
            )
            assert legit["status"] == "success"
            assert safe_file.read_text(encoding="utf-8") == "approved_state"
    finally:
        if safe_file.exists():
            safe_file.unlink()
        if evil_file.exists():
            evil_file.unlink()

@pytest.mark.asyncio
async def test_terminal_ticket_substitution_attack_blocked():
    auth = CryptographicApprovalAuthority.get_instance()
    cmd1 = "rm -rf clean_dir"
    cmd2 = "rm -rf evil_dir"

    # 1. Trigger confirmation
    res1 = await UnifiedToolDispatcher.dispatch("terminal_run_command", {"command": cmd1})
    assert res1["status"] == "confirmation_required"
    tkt_id = res1["ticket_id"]

    sig = auth.generate_human_signature(tkt_id)

    # 2. Tampered command substitution attempt
    attack = await UnifiedToolDispatcher.dispatch(
        "terminal_run_command",
        {"command": cmd2, "ticket_id": tkt_id, "signature": sig}
    )
    assert attack["status"] == "error"
    assert attack.get("security_alert") == "SUBSTITUTION_ATTACK_BLOCKED"
    assert "Command or working directory does not match" in attack["error"]

@pytest.mark.asyncio
async def test_edit_file_outside_workspace_escalates_to_high_risk():
    # Attempting to edit outside workspace must escalate to HIGH risk and require confirmation
    res = await UnifiedToolDispatcher.dispatch(
        "edit_file",
        {
            "path": "../../../system_critical.txt",
            "target_content": "a",
            "replacement_content": "b"
        }
    )
    assert res["status"] == "confirmation_required"
    assert res["requires_human_approval"] is True
    assert res["risk_level"] == "high"

@pytest.mark.asyncio
async def test_llm_self_approval_without_human_signature_blocked():
    """
    Isolate the LLM self-approval scenario:
    The model receives a valid ticket_id from a confirmation_required response.
    The model immediately attempts to re-call dispatch() with that ticket_id
    and NO signature — with no simulated user confirmation step in between.
    It MUST be rejected with UNAUTHORIZED_LLM_SELF_APPROVAL_BLOCKED.
    """
    # 1. High risk terminal command triggers approval gate and issues ticket
    res1 = await UnifiedToolDispatcher.dispatch(
        "terminal_run_command",
        {"command": "rm -rf sensitive_prod_db"}
    )
    assert res1["status"] == "confirmation_required"
    assert "ticket_id" in res1
    tkt_id = res1["ticket_id"]

    # 2. LLM attempts self-approval by presenting ticket_id without human signature
    # (NO auth.generate_human_signature call is made!)
    res2 = await UnifiedToolDispatcher.dispatch(
        "terminal_run_command",
        {"command": "rm -rf sensitive_prod_db", "ticket_id": tkt_id}
    )
    assert res2["status"] == "error"
    assert res2.get("security_alert") == "UNAUTHORIZED_LLM_SELF_APPROVAL_BLOCKED"
    assert "requires human authorization" in res2["error"]

    # 3. Repeat for file edit tool under ASK autonomy
    from core.orchestration.execution_policy import ExecutionPolicy
    from core.orchestration.autonomy_mode import AutonomyLevel

    with ExecutionPolicy.autonomy_scope(AutonomyLevel.ASK):
        res_edit1 = await UnifiedToolDispatcher.dispatch(
            "edit_file",
            {"path": "pyproject.toml", "target_content": "version = \"0.32.0\"", "replacement_content": "version = \"0.33.0\""}
        )
        assert res_edit1["status"] == "confirmation_required"
        edit_tkt = res_edit1["ticket_id"]

        # Re-call with ticket_id and no signature
        res_edit2 = await UnifiedToolDispatcher.dispatch(
            "edit_file",
            {
                "path": "pyproject.toml",
                "target_content": "version = \"0.32.0\"",
                "replacement_content": "version = \"0.33.0\"",
                "ticket_id": edit_tkt
            }
        )
        assert res_edit2["status"] == "error"
        assert res_edit2.get("security_alert") == "UNAUTHORIZED_LLM_SELF_APPROVAL_BLOCKED"
        assert "requires human authorization" in res_edit2["error"]


@pytest.mark.asyncio
async def test_browser_interact_fails_closed_without_live_session():
    """Fail-closed invariant: browser_interact must return error when no live session is attached."""
    res = await UnifiedToolDispatcher.dispatch("browser_interact", {"action": "click", "selector": "#btn"})
    assert res["status"] == "error"
    assert "No active browser session available" in res["error"]


@pytest.mark.asyncio
async def test_browser_interact_executes_on_attached_page():
    """When an active page is attached to the session, browser_interact delegates to real page calls."""
    from unittest.mock import MagicMock
    mock_page = MagicMock()
    mock_session_obj = MagicMock(page=mock_page)

    session = AgentSession(goal="interact with page")
    session.data["browser_session"] = mock_session_obj

    res = await UnifiedToolDispatcher.dispatch(
        "browser_interact",
        {"action": "click", "selector": "#submit"},
        session=session,
    )
    assert res["status"] == "success"
    assert "Clicked element '#submit'" in res["result"]
    mock_page.click.assert_called_once_with("#submit", timeout=5000)


@pytest.mark.asyncio
async def test_browser_navigate_returns_busy_when_other_goal_in_flight(monkeypatch):
    """
    When Goal A is actively in-flight, Goal B calling browser_navigate_and_read
    must return a structured busy error rather than launching a secondary browser.
    """
    monkeypatch.setenv("AURA_ENABLE_AGENT_LOOP", "1")
    from browser.browser_session_manager import BrowserSessionManager
    BrowserSessionManager.reset_for_testing()
    mgr = BrowserSessionManager.get_instance()

    mock_sess_a = MagicMock()
    mock_sess_a.page = MagicMock()
    mgr.acquire_session("goal-A", session_factory=lambda: mock_sess_a)

    # Hold in-flight lease on Goal A
    with mgr.operation_scope("goal-A"):
        session_b = AgentSession(goal="Goal B web search", goal_id="goal-B")
        res = await UnifiedToolDispatcher.dispatch(
            "browser_navigate_and_read",
            {"url": "https://example.com"},
            session=session_b,
        )

        assert res["status"] == "error"
        assert res.get("busy") is True
        assert "Browser is currently busy" in res["error"]
        # Goal A must still be intact
        assert mgr.get_session("goal-A") is mock_sess_a
        assert mgr.get_session("goal-B") is None

    BrowserSessionManager.reset_for_testing()


@pytest.mark.asyncio
async def test_browser_interact_returns_busy_when_other_goal_in_flight():
    """
    When Goal A is actively in-flight, Goal B calling browser_interact
    must return a structured busy error rather than crashing or interleaving.
    """
    from browser.browser_session_manager import BrowserSessionManager
    BrowserSessionManager.reset_for_testing()
    mgr = BrowserSessionManager.get_instance()

    mock_sess_a = MagicMock()
    mgr.acquire_session("goal-A", session_factory=lambda: mock_sess_a)

    with mgr.operation_scope("goal-A"):
        session_b = AgentSession(goal="Goal B interact", goal_id="goal-B")
        res = await UnifiedToolDispatcher.dispatch(
            "browser_interact",
            {"action": "click", "selector": "#btn"},
            session=session_b,
        )

        assert res["status"] == "error"
        assert res.get("busy") is True
        assert "Browser is currently busy" in res["error"]

    mgr.reset_for_testing()


@pytest.mark.asyncio
async def test_desktop_control_window_close_requires_ticket():
    """
    Destructive window close action must be gated as HIGH risk and require a cryptographic approval ticket.
    """
    # 1. Unconfirmed attempt: must generate ticket
    res = await UnifiedToolDispatcher.dispatch(
        "desktop_control_window",
        {"window_title": "test_app_dummy", "action": "close"}
    )
    assert res["status"] == "confirmation_required"
    assert res["risk_level"] == "high"
    assert res["action"] == "desktop_control_window"
    assert res.get("ticket_id", "").startswith("tkt_")
    tkt_id = res["ticket_id"]

    # 2. Redeemed attempt: with valid human signature, passes gate to tool execution
    auth = CryptographicApprovalAuthority.get_instance()
    sig = auth.generate_human_signature(tkt_id)
    assert sig is not None

    res_redeemed = await UnifiedToolDispatcher.dispatch(
        "desktop_control_window",
        {
            "window_title": "test_app_dummy",
            "action": "close",
            "ticket_id": tkt_id,
            "signature": sig,
        }
    )
    # Reached tool body (which reports window not found for dummy title, NOT confirmation_required)
    assert res_redeemed["status"] == "error"
    assert "No active window found" in res_redeemed["message"]


@pytest.mark.asyncio
async def test_desktop_control_window_focus_auto_approved():
    """
    Benign window focus/activation must be auto-approved without ticket gating.
    """
    res = await UnifiedToolDispatcher.dispatch(
        "desktop_control_window",
        {"window_title": "test_app_dummy", "action": "focus"}
    )
    # Passes directly to tool body without ticket
    assert res["status"] == "error"
    assert "No active window found" in res["message"]


@pytest.mark.asyncio
async def test_desktop_launch_dangerous_app_requires_ticket():
    """
    Launching dangerous command interpreters or system shells must require approval tickets.
    """
    res = await UnifiedToolDispatcher.dispatch(
        "desktop_launch_app",
        {"application": "powershell.exe"}
    )
    assert res["status"] == "confirmation_required"
    assert res["risk_level"] == "high"
    assert res.get("ticket_id", "").startswith("tkt_")


@pytest.mark.asyncio
async def test_desktop_clipboard_dispatch():
    test_text = "Aura UnifiedToolDispatcher TD-020 Test"
    write_res = await UnifiedToolDispatcher.dispatch(
        "desktop_clipboard",
        {"action": "write", "text": test_text}
    )
    assert write_res["status"] == "success"

    read_res = await UnifiedToolDispatcher.dispatch(
        "desktop_clipboard",
        {"action": "read"}
    )
    assert read_res["status"] == "success"
    assert test_text in read_res["text"]


@pytest.mark.asyncio
async def test_desktop_volume_and_brightness_dispatch():
    vol_res = await UnifiedToolDispatcher.dispatch(
        "desktop_set_volume",
        {"level": 50, "mute": False}
    )
    assert vol_res["status"] in ("success", "error")

    bright_res = await UnifiedToolDispatcher.dispatch(
        "desktop_set_brightness",
        {"level": 60}
    )
    assert bright_res["status"] in ("success", "error")


@pytest.mark.asyncio
async def test_email_action_gating_and_dispatch():
    session = AgentSession(goal="email operations")

    # 1. Read inbox is LOW risk -> executes immediately without ticket
    read_res = await UnifiedToolDispatcher.dispatch(
        "email_action",
        {"action": "read_inbox", "limit": 2},
        session=session
    )
    assert read_res["status"] in ("success", "error")

    # 2. Send email is HIGH risk -> requires confirmation ticket
    send_args = {
        "action": "send",
        "recipient": "security@example.com",
        "subject": "Critical Update",
        "body": "System integrity verified."
    }
    gated_res = await UnifiedToolDispatcher.dispatch(
        "email_action",
        send_args,
        session=session
    )
    assert gated_res["status"] == "confirmation_required"
    assert gated_res["risk_level"] == "high"
    tkt_id = gated_res["ticket_id"]
    assert tkt_id.startswith("tkt_")

    # 3. Redeem with human signature -> executes
    auth = CryptographicApprovalAuthority.get_instance()
    sig = auth.generate_human_signature(tkt_id)
    send_args_with_sig = dict(send_args)
    send_args_with_sig["ticket_id"] = tkt_id
    send_args_with_sig["signature"] = sig

    exec_res = await UnifiedToolDispatcher.dispatch(
        "email_action",
        send_args_with_sig,
        session=session
    )
    assert exec_res["status"] in ("success", "error")


@pytest.mark.asyncio
async def test_calendar_action_gating_and_dispatch():
    session = AgentSession(goal="calendar operations")

    # 1. Create event is MEDIUM risk -> auto-approved under ASSISTED autonomy
    create_args = {
        "action": "create_event",
        "title": "Aura AI Standup",
        "start_time": "2026-09-09 09:30",
        "end_time": "2026-09-09 10:00"
    }
    create_res = await UnifiedToolDispatcher.dispatch(
        "calendar_action",
        create_args,
        session=session
    )
    assert create_res["status"] == "success"
    event_id = create_res["data"]["id"]

    # 2. List events is LOW risk -> executes immediately
    list_res = await UnifiedToolDispatcher.dispatch(
        "calendar_action",
        {"action": "list_events"},
        session=session
    )
    assert list_res["status"] == "success"
    assert any(e["id"] == event_id for e in list_res["data"]["events"])

    # 3. Delete event is HIGH risk -> requires confirmation ticket
    del_args = {
        "action": "delete_event",
        "event_id": event_id
    }
    gated_del = await UnifiedToolDispatcher.dispatch(
        "calendar_action",
        del_args,
        session=session
    )
    assert gated_del["status"] == "confirmation_required"
    assert gated_del["risk_level"] == "high"
    tkt_id = gated_del["ticket_id"]

    # 4. Redeem ticket and verify deletion
    auth = CryptographicApprovalAuthority.get_instance()
    sig = auth.generate_human_signature(tkt_id)
    del_args["ticket_id"] = tkt_id
    del_args["signature"] = sig

    del_res = await UnifiedToolDispatcher.dispatch(
        "calendar_action",
        del_args,
        session=session
    )
    assert del_res["status"] == "success"


@pytest.mark.asyncio
async def test_smarthome_control_gating_and_dispatch():
    session = AgentSession(goal="smarthome device control")

    # 1. Querying state is LOW risk -> executes without ticket
    state_res = await UnifiedToolDispatcher.dispatch(
        "smarthome_control",
        {"action": "get_state", "entity_id": "light.office"},
        session=session
    )
    assert state_res["status"] in ("success", "error")

    # 2. Smart lock action is HIGH risk -> requires confirmation ticket
    lock_args = {
        "action": "lock",
        "entity_id": "lock.front_door"
    }
    gated_res = await UnifiedToolDispatcher.dispatch(
        "smarthome_control",
        lock_args,
        session=session
    )
    assert gated_res["status"] == "confirmation_required"
    assert gated_res["risk_level"] == "high"
    tkt_id = gated_res["ticket_id"]

    # 3. Redeem ticket and execute
    auth = CryptographicApprovalAuthority.get_instance()
    sig = auth.generate_human_signature(tkt_id)
    lock_args["ticket_id"] = tkt_id
    lock_args["signature"] = sig

    lock_res = await UnifiedToolDispatcher.dispatch(
        "smarthome_control",
        lock_args,
        session=session
    )
    assert lock_res["status"] in ("success", "error")


@pytest.mark.asyncio
async def test_email_action_ticket_substitution_attack_blocked():
    session = AgentSession(goal="secure email dispatch")
    auth = CryptographicApprovalAuthority.get_instance()

    # 1. Mint ticket for safe colleague email
    safe_args = {
        "action": "send",
        "recipient": "colleague@work.com",
        "subject": "Meeting Agenda",
        "body": "Let us review quarterly goals."
    }
    gated_res = await UnifiedToolDispatcher.dispatch("email_action", safe_args, session=session)
    assert gated_res["status"] == "confirmation_required"
    tkt_id = gated_res["ticket_id"]
    sig = auth.generate_human_signature(tkt_id)

    # 2. Attacker attempts substitution: change recipient to evil external server
    evil_recipient_args = dict(safe_args)
    evil_recipient_args["recipient"] = "attacker@evil.com"
    evil_recipient_args["ticket_id"] = tkt_id
    evil_recipient_args["signature"] = sig

    blocked_res1 = await UnifiedToolDispatcher.dispatch("email_action", evil_recipient_args, session=session)
    assert blocked_res1["status"] == "error"
    assert blocked_res1["security_alert"] == "SUBSTITUTION_ATTACK_BLOCKED"
    assert "Authorization failed" in blocked_res1["error"]

    # 3. Attacker attempts substitution: change subject to confidential exfiltration
    evil_subject_args = dict(safe_args)
    evil_subject_args["subject"] = "Confidential Credentials"
    evil_subject_args["ticket_id"] = tkt_id
    evil_subject_args["signature"] = sig

    blocked_res2 = await UnifiedToolDispatcher.dispatch("email_action", evil_subject_args, session=session)
    assert blocked_res2["status"] == "error"
    assert blocked_res2["security_alert"] == "SUBSTITUTION_ATTACK_BLOCKED"


@pytest.mark.asyncio
async def test_calendar_action_ticket_substitution_attack_blocked():
    session = AgentSession(goal="calendar delete security")
    auth = CryptographicApprovalAuthority.get_instance()

    # 1. Mint ticket for deleting safe event evt_safe_001
    safe_del_args = {
        "action": "delete_event",
        "event_id": "evt_safe_001"
    }
    gated_res = await UnifiedToolDispatcher.dispatch("calendar_action", safe_del_args, session=session)
    assert gated_res["status"] == "confirmation_required"
    tkt_id = gated_res["ticket_id"]
    sig = auth.generate_human_signature(tkt_id)

    # 2. Attacker attempts substitution: delete critical meeting evt_critical_999 instead
    evil_del_args = {
        "action": "delete_event",
        "event_id": "evt_critical_999",
        "ticket_id": tkt_id,
        "signature": sig
    }
    blocked_res = await UnifiedToolDispatcher.dispatch("calendar_action", evil_del_args, session=session)
    assert blocked_res["status"] == "error"
    assert blocked_res["security_alert"] == "SUBSTITUTION_ATTACK_BLOCKED"
    assert "Authorization failed" in blocked_res["error"]


@pytest.mark.asyncio
async def test_smarthome_control_ticket_substitution_attack_blocked():
    session = AgentSession(goal="smarthome security")
    auth = CryptographicApprovalAuthority.get_instance()

    # 1. Mint ticket to unlock front door
    safe_lock_args = {
        "action": "unlock",
        "entity_id": "lock.front_door"
    }
    gated_res = await UnifiedToolDispatcher.dispatch("smarthome_control", safe_lock_args, session=session)
    assert gated_res["status"] == "confirmation_required"
    tkt_id = gated_res["ticket_id"]
    sig = auth.generate_human_signature(tkt_id)

    # 2. Attacker attempts substitution: swap entity_id to lock.server_room
    evil_lock_args = {
        "action": "unlock",
        "entity_id": "lock.server_room",
        "ticket_id": tkt_id,
        "signature": sig
    }
    blocked_res = await UnifiedToolDispatcher.dispatch("smarthome_control", evil_lock_args, session=session)
    assert blocked_res["status"] == "error"
    assert blocked_res["security_alert"] == "SUBSTITUTION_ATTACK_BLOCKED"
    assert "Authorization failed" in blocked_res["error"]


@pytest.mark.asyncio
async def test_smarthome_control_no_false_positive_lock_escalation():
    """
    Substrings like 'clock' or 'blocker' must NOT trigger ActionRisk.HIGH escalation.
    """
    session = AgentSession(goal="routine smarthome toggle")

    # 1. light.alarm_clock should NOT be high risk
    clock_res = await UnifiedToolDispatcher.dispatch(
        "smarthome_control",
        {"action": "turn_on", "entity_id": "light.alarm_clock"},
        session=session
    )
    assert clock_res.get("status") != "confirmation_required"
    assert clock_res.get("risk_level") != "high"

    # 2. switch.adblocker should NOT be high risk
    blocker_res = await UnifiedToolDispatcher.dispatch(
        "smarthome_control",
        {"action": "turn_off", "entity_id": "switch.adblocker"},
        session=session
    )
    assert blocker_res.get("status") != "confirmation_required"
    assert blocker_res.get("risk_level") != "high"







