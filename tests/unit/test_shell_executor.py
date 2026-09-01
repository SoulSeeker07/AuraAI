import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from desktop.native.managers.shell_executor import (
    classify_command,
    execute_low_risk,
    ShellExecutionResult,
)
from brain.conversation_engine import ConversationEngine
from brain.intent_router import IntentRouter
from tools.file_service import FileService
from Memory import Memory


@pytest.fixture
def memory_instance():
    return Memory()


@pytest.fixture
def router(memory_instance):
    return IntentRouter(memory_instance)


@pytest.fixture
def engine(memory_instance):
    return ConversationEngine(memory=memory_instance, provider_manager=None)


def test_classify_command():
    # LOW risk
    assert classify_command("git status") == "LOW"
    assert classify_command("git log --oneline -5") == "LOW"
    assert classify_command("git diff") == "LOW"
    assert classify_command("git branch -a") == "LOW"
    assert classify_command("git remote -v") == "LOW"
    assert classify_command("echo hello") == "LOW"
    assert classify_command("where git") == "LOW"
    assert classify_command("pip list") == "LOW"

    # MEDIUM risk
    assert classify_command("git commit -m 'fix'") == "MEDIUM"
    assert classify_command("git add .") == "MEDIUM"
    assert classify_command("git checkout main") == "MEDIUM"
    assert classify_command("pip install requests") == "MEDIUM"
    assert classify_command("npm install") == "MEDIUM"

    # HIGH risk (destructive prefixes or shell operators)
    assert classify_command("rm -rf node_modules") == "HIGH"
    assert classify_command("del /f /q temp.txt") == "HIGH"
    assert classify_command("git clean -fd") == "HIGH"
    assert classify_command("git reset --hard HEAD") == "HIGH"
    assert classify_command("git status | grep M") == "HIGH"
    assert classify_command("echo a && echo b") == "HIGH"
    assert classify_command("git log > out.txt") == "HIGH"


def test_execute_low_risk_real():
    result = execute_low_risk("git status")
    assert result.success is True
    assert result.returncode == 0
    assert "On branch" in result.stdout or "fatal" not in result.stdout
    formatted = result.format_response()
    assert "✅ `git status`" in formatted


def test_execute_low_risk_fatal_error(tmp_path):
    # Running git status in a non-git directory returns returncode 128 + fatal error
    result = execute_low_risk("git status", cwd=str(tmp_path))
    assert result.success is False
    assert result.returncode != 0
    assert "not a git repository" in (result.stderr + (result.error or "")).lower()
    formatted = result.format_response()
    assert "❌ `git status` failed." in formatted


def test_conversation_engine_run_git_status(router, engine):
    intent = router.detect("run git status")
    assert intent.name == "desktop_action"
    response = engine._answer_local_intent(intent)
    assert response is not None
    assert "✅ `git status`" in response


def test_conversation_engine_run_medium_risk(router, engine):
    intent = router.detect("run git commit -m 'test'")
    assert intent.name == "desktop_action"
    response = engine._answer_local_intent(intent)
    assert response is not None
    assert "classified as a **MEDIUM-risk** command" in response
    assert "requires an approval ticket" in response


def test_conversation_engine_run_high_risk(router, engine):
    intent = router.detect("run rm -rf node_modules")
    assert intent.name == "desktop_action"
    response = engine._answer_local_intent(intent)
    assert response is not None
    assert "classified as a **HIGH-risk** command" in response
    assert "requires an approval ticket" in response


def test_file_service_threshold_blocks_noise():
    fs = FileService.get_instance()
    # "git status" should NOT match unrelated files
    assert fs.find_best_file("git status") is None

    # Real file query should match
    best = fs.find_best_file("architecture.md")
    assert best is not None
    assert "architecture.md" in best.name.lower()


def test_direct_git_command_intent_routing(router):
    # Direct git commands
    assert router.detect("git status").name == "desktop_action"
    assert router.detect("git diff").name == "desktop_action"
    assert router.detect("git log").name == "desktop_action"
    assert router.detect("git push").name == "desktop_action"
    assert router.detect("git pull").name == "desktop_action"

    # Natural git phrasing
    intent_push = router.detect("push git")
    assert intent_push.name == "desktop_action"
    assert (intent_push.data or {}).get("verb") == "run"
    assert (intent_push.data or {}).get("target") == "git push"

    intent_pull = router.detect("pull git")
    assert intent_pull.name == "desktop_action"
    assert (intent_pull.data or {}).get("verb") == "run"
    assert (intent_pull.data or {}).get("target") == "git pull"

    intent_status = router.detect("check git status")
    assert intent_status.name == "desktop_action"
    assert (intent_status.data or {}).get("verb") == "run"
    assert (intent_status.data or {}).get("target") == "git status"


def test_git_push_approval_and_execution_flow(router, engine):
    # 1. User requests git push
    intent = router.detect("push git")
    assert intent.name == "desktop_action"
    response = engine._answer_local_intent(intent)
    assert response is not None
    assert "classified as a **MEDIUM-risk** command" in response
    assert "Approval ticket:" in response

    # 2. User confirms with 'yes'
    confirm_intent = router.detect("yes")
    assert confirm_intent.name == "confirm_ticket"
    assert (confirm_intent.data or {}).get("decision") == "approve"

    with patch("desktop.native.managers.shell_executor.subprocess.run") as mock_sub:
        mock_sub.return_value = MagicMock(
            returncode=0,
            stdout="Everything up-to-date\nTo https://github.com/SoulSeeker07/AuraAI.git",
            stderr="",
        )
        approved_response = engine._answer_local_intent(confirm_intent)
        assert approved_response is not None
        assert "✅ `git push`" in approved_response
        assert "Everything up-to-date" in approved_response


def test_git_push_denial_flow(router, engine):
    # 1. User requests git push
    intent = router.detect("push git")
    assert intent.name == "desktop_action"
    engine._answer_local_intent(intent)

    # 2. User denies with 'no'
    deny_intent = router.detect("no")
    assert deny_intent.name == "confirm_ticket"
    assert (deny_intent.data or {}).get("decision") == "deny"

    denied_response = engine._answer_local_intent(deny_intent)
    assert denied_response is not None
    assert "Cancelled" in denied_response

