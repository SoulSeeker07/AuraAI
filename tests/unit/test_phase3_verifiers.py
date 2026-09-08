"""
tests/unit/test_phase3_verifiers.py

Unit tests for Phase 3 verifiers and session continuity:
1. verify_terminal_run_command (returncode and fatal shell stderr signatures).
2. verify_edit_file (AST syntax validation on Python files).
3. Browser session continuity across AWAITING_USER boundary via BrowserSessionManager.
4. Eviction tombstone diagnostics (ttl_expired, bumped_by_new_goal, never_established).
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest

from browser.browser_session_manager import BrowserSessionManager
from core.orchestration.agent_loop import (
    AgentLoop,
    verify_terminal_run_command,
    verify_edit_file,
    verify_browser_interact,
)
from core.orchestration.agent_session import AgentSession
from core.orchestration.goal_state import GoalStatus, StepStatus
from core.tools.unified_tool_dispatcher import UnifiedToolDispatcher


@pytest.fixture(autouse=True)
def clean_manager():
    BrowserSessionManager.reset_for_testing()
    yield
    BrowserSessionManager.reset_for_testing()


# ── 1. Terminal Run Command Verifier Tests ────────────────────────────────────

def test_terminal_run_command_verifier_success():
    args = {"command": "git status"}
    result = {"status": "success", "returncode": 0, "stdout": "On branch main", "stderr": ""}
    verified, reason = verify_terminal_run_command("terminal_run_command", args, result)
    assert verified is True
    assert "executed successfully" in reason


def test_terminal_run_command_verifier_rejects_nonzero_returncode():
    args = {"command": "python broken_script.py"}
    result = {"status": "success", "returncode": 1, "stdout": "", "stderr": "FileNotFoundError: [Errno 2]"}
    verified, reason = verify_terminal_run_command("terminal_run_command", args, result)
    assert verified is False
    assert "non-zero returncode 1" in reason


def test_terminal_run_command_verifier_rejects_fatal_patterns():
    args = {"command": "python -c 'print(1'"}
    result = {"status": "success", "returncode": 0, "stderr": "SyntaxError: unexpected EOF while parsing"}
    verified, reason = verify_terminal_run_command("terminal_run_command", args, result)
    assert verified is False
    assert "fatal error signature: 'syntaxerror:'" in reason


# ── 2. Edit File AST Verifier Tests ──────────────────────────────────────────

def test_edit_file_verifier_valid_python_syntax(tmp_path):
    valid_file = tmp_path / "valid_code.py"
    valid_file.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

    args = {"path": str(valid_file)}
    result = {"status": "success", "path": str(valid_file)}
    verified, reason = verify_edit_file("edit_file", args, result)
    assert verified is True
    assert "File edit verified" in reason


def test_edit_file_verifier_rejects_ast_syntax_error(tmp_path):
    invalid_file = tmp_path / "syntax_error.py"
    invalid_file.write_text("def broken_func(\n    print('missing paren')\n", encoding="utf-8")

    args = {"path": str(invalid_file)}
    result = {"status": "success", "path": str(invalid_file)}
    verified, reason = verify_edit_file("edit_file", args, result)
    assert verified is False
    assert "AST SyntaxError" in reason
    assert "line" in reason


def test_edit_file_verifier_non_python_file(tmp_path):
    text_file = tmp_path / "config.json"
    text_file.write_text("{\"key\": \"value\"}", encoding="utf-8")

    args = {"path": str(text_file)}
    result = {"status": "success", "path": str(text_file)}
    verified, reason = verify_edit_file("edit_file", args, result)
    assert verified is True
    assert "File edit verified" in reason


# ── 3. Browser Session Continuity & Tombstones ───────────────────────────────

@pytest.mark.asyncio
async def test_browser_session_continuity_across_turns():
    """
    Proves that a page handle attached to BrowserSessionManager survives
    when an AgentSession is reconstructed for the same goal_id.
    """
    mgr = BrowserSessionManager.get_instance()
    mock_page = MagicMock()
    mock_session = MagicMock()
    mock_session.page = mock_page
    mock_session.active_page.return_value = mock_page

    goal_id = "goal_interactive_continuity_1"
    mgr.attach_session(goal_id, mock_session)

    # Reconstruct an AgentSession for the same goal (as happens when a turn resumes)
    resumed_session = AgentSession(goal="resume and click", goal_id=goal_id)

    res = await UnifiedToolDispatcher.dispatch(
        "browser_interact",
        {"action": "click", "selector": "#continue-btn"},
        session=resumed_session,
    )

    assert res["status"] == "success"
    assert "Clicked element '#continue-btn'" in res["result"]
    mock_page.click.assert_called_once_with("#continue-btn", timeout=5000)


@pytest.mark.asyncio
async def test_browser_interact_tombstone_ttl_expired():
    mgr = BrowserSessionManager.get_instance()
    goal_id = "goal_timed_out_1"

    # Simulate tombstone recorded by idle reaper
    mgr._tombstones[goal_id] = {"reason": "ttl_expired", "timestamp": 123456.0}

    session = AgentSession(goal="delayed resume", goal_id=goal_id)
    res = await UnifiedToolDispatcher.dispatch(
        "browser_interact",
        {"action": "click", "selector": "#any"},
        session=session,
    )

    assert res["status"] == "error"
    assert "closed after 15 minutes of inactivity" in res["error"]
    assert res.get("eviction_reason") == "ttl_expired"


@pytest.mark.asyncio
async def test_browser_interact_tombstone_bumped_by_new_goal():
    mgr = BrowserSessionManager.get_instance()
    goal_id = "goal_evicted_1"

    # Simulate tombstone recorded when 1-browser cap evicted this goal
    mgr._tombstones[goal_id] = {"reason": "bumped_by_new_goal", "timestamp": 123456.0}

    session = AgentSession(goal="delayed resume", goal_id=goal_id)
    res = await UnifiedToolDispatcher.dispatch(
        "browser_interact",
        {"action": "click", "selector": "#any"},
        session=session,
    )

    assert res["status"] == "error"
    assert "because a new browser task was started" in res["error"]
    assert res.get("eviction_reason") == "bumped_by_new_goal"
