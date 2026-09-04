import pytest
import asyncio
from pathlib import Path
from core.tools.unified_tool_dispatcher import UnifiedToolDispatcher
from core.orchestration.agent_session import AgentSession
from desktop.native.security.approval_authority import CryptographicApprovalAuthority

@pytest.mark.asyncio
async def test_tool_definitions_count():
    tools = UnifiedToolDispatcher.get_tool_definitions()
    assert len(tools) == 14
    tool_names = [t["function"]["name"] for t in tools]
    expected = [
        "read_file", "edit_file", "run_tests",
        "terminal_run_command", "system_get_telemetry",
        "vision_inspect_screen", "browser_navigate_and_read",
        "browser_interact", "desktop_launch_app",
        "desktop_control_window", "memory_save_fact",
        "memory_query_facts", "personal_os_agenda",
        "task_plan_update"
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



