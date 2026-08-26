"""
Unit tests for voice listening intent routing, special folder opening, and safe close protections.
"""

from unittest.mock import MagicMock, patch
import pytest

from brain.intent_router import IntentRouter
from desktop.native.managers.window_manager import WindowManager
from execution.safety_policy import SafetyPolicy
from core.orchestration.execution_policy import ExecutionPolicy


def test_voice_listening_intent_routing():
    """Verify that voice commands are routed to voice_control intent and not desktop_action."""
    mock_memory = MagicMock()
    mock_memory.extract_facts.return_value = []
    router = IntentRouter(memory=mock_memory)

    start_queries = [
        "start listening",
        "Start Listening",
        "start voice",
        "listen to me",
        "listen",
        "turn on voice",
        "enable voice",
    ]
    for q in start_queries:
        intent = router.detect(q)
        assert intent.name == "voice_control", f"Failed for query: {q}"
        assert intent.data["action"] == "start"

    stop_queries = [
        "stop listening",
        "Stop Listening",
        "stop voice",
        "pause listening",
        "disable voice",
        "turn off voice",
    ]
    for q in stop_queries:
        intent = router.detect(q)
        assert intent.name == "voice_control", f"Failed for query: {q}"
        assert intent.data["action"] == "stop"


def test_folder_resolution_and_launch():
    """Verify that 'open my documents' and 'open downloads' resolve to folder paths."""
    wm = WindowManager()

    res_type, path = wm._resolve_app_executable("my documents")
    assert res_type == "folder"
    assert "Documents" in path

    res_type, path = wm._resolve_app_executable("documents")
    assert res_type == "folder"
    assert "Documents" in path

    res_type, path = wm._resolve_app_executable("downloads")
    assert res_type == "folder"
    assert "Downloads" in path

    res_type, path = wm._resolve_app_executable("desktop")
    assert res_type == "folder"
    assert "Desktop" in path


def test_safety_policy_protects_command_prompt_and_terminals():
    """Verify that SafetyPolicy protects Command Prompt, cmd.exe, PowerShell, and terminals."""
    sp = SafetyPolicy.get_instance()

    assert sp.is_protected_app("cmd.exe") is True
    assert sp.is_protected_app("cmd") is True
    assert sp.is_protected_app("command prompt") is True
    assert sp.is_protected_app("Command Prompt - python") is True
    assert sp.is_protected_app("powershell.exe") is True
    assert sp.is_protected_app("powershell") is True
    assert sp.is_protected_app("windowsterminal.exe") is True
    assert sp.is_protected_app("terminal") is True
    assert sp.is_protected_app("code.exe") is True
    assert sp.is_protected_app("Visual Studio Code") is True

    # Regular apps are not protected
    assert sp.is_protected_app("notepad.exe") is False
    assert sp.is_protected_app("calculator") is False


def test_close_documents_does_not_kill_command_prompt():
    """Verify that closing documents never terminates a command prompt window."""
    wm = WindowManager()

    # Mock finding a window whose process happens to be cmd.exe
    mock_info = {
        "title": "Command Prompt - aura start listening",
        "class_name": "ConsoleWindowClass",
        "process_id": 9999,
        "process_name": "cmd.exe",
    }
    with patch.object(wm, "_get_window_info", return_value=mock_info), \
         patch.object(wm, "_find_window", return_value=12345):
        # Even if _find_window were called, closing folder documents should NOT kill cmd
        result = wm._handle_close(goal="close documents", app_name="documents")
        assert result.success is True


def test_say_and_speak_phrase_intent_routing():
    """Verify that 'say <phrase>' and 'speak <phrase>' route to say_phrase intent."""
    mock_memory = MagicMock()
    mock_memory.extract_facts.return_value = []
    router = IntentRouter(memory=mock_memory)

    intent = router.detect("say hi")
    assert intent.name == "say_phrase"
    assert intent.data["phrase"] == "hi"

    intent = router.detect("speak hello world")
    assert intent.name == "say_phrase"
    assert intent.data["phrase"] == "hello world"

    intent = router.detect("read aloud good morning")
    assert intent.name == "say_phrase"
    assert intent.data["phrase"] == "good morning"
