"""
Unit tests for EditorTracker and fail-closed window title parsing.
Location: tests/workspace/test_editor_tracker.py
"""

from pathlib import Path
import pytest

from workspace.editor_tracker import EditorTracker


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    """Create a temporary mock repo structure."""
    repo = tmp_path / "AuraAI"
    repo.mkdir()
    (repo / "src" / "core").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_orchestration.py").write_text("# test", encoding="utf-8")
    (repo / "src" / "core" / "master_orchestrator.py").write_text("# core", encoding="utf-8")
    (repo / "README.md").write_text("# Readme", encoding="utf-8")
    return repo


def test_parse_valid_format_a_antigravity(repo_root: Path):
    tracker = EditorTracker(root=repo_root)
    title = "test_orchestration.py - AuraAI - Antigravity IDE"
    res = tracker.parse_window_title(title, expected_workspace="AuraAI", repo_path=repo_root)
    assert res is not None
    assert res["filename"] == "test_orchestration.py"
    assert res["relative_path"] == "tests/test_orchestration.py"
    assert res["workspace"] == "AuraAI"
    assert res["is_dirty"] is False


def test_parse_valid_format_a_dirty_marker(repo_root: Path):
    tracker = EditorTracker(root=repo_root)
    title = "● test_orchestration.py - AuraAI - Antigravity IDE"
    res = tracker.parse_window_title(title, expected_workspace="AuraAI", repo_path=repo_root)
    assert res is not None
    assert res["filename"] == "test_orchestration.py"
    assert res["is_dirty"] is True


def test_parse_valid_format_a_vscode(repo_root: Path):
    tracker = EditorTracker(root=repo_root)
    title = "master_orchestrator.py - AuraAI - Visual Studio Code"
    res = tracker.parse_window_title(title, expected_workspace="AuraAI", repo_path=repo_root)
    assert res is not None
    assert res["filename"] == "master_orchestrator.py"
    assert res["relative_path"] == "src/core/master_orchestrator.py"
    assert res["workspace"] == "AuraAI"


def test_parse_valid_format_b(repo_root: Path):
    tracker = EditorTracker(root=repo_root)
    title = "AuraAI - Antigravity IDE - test_orchestration.py"
    res = tracker.parse_window_title(title, expected_workspace="AuraAI", repo_path=repo_root)
    assert res is not None
    assert res["filename"] == "test_orchestration.py"


def test_reject_non_code_ui_views(repo_root: Path):
    tracker = EditorTracker(root=repo_root)
    
    # Artifact views / settings / welcome
    assert tracker.parse_window_title("AuraAI - Antigravity IDE - Implementation Plan", expected_workspace="AuraAI", repo_path=repo_root) is None
    assert tracker.parse_window_title("AuraAI - Antigravity IDE - Walkthrough", expected_workspace="AuraAI", repo_path=repo_root) is None
    assert tracker.parse_window_title("AuraAI - Antigravity IDE - Settings", expected_workspace="AuraAI", repo_path=repo_root) is None
    assert tracker.parse_window_title("Welcome - Antigravity IDE", expected_workspace="AuraAI", repo_path=repo_root) is None
    assert tracker.parse_window_title("Settings - AuraAI - Visual Studio Code", expected_workspace="AuraAI", repo_path=repo_root) is None


def test_reject_cross_project_window(repo_root: Path):
    tracker = EditorTracker(root=repo_root)
    # Editor window open on different project
    title = "test_orchestration.py - OtherProject - Antigravity IDE"
    res = tracker.parse_window_title(title, expected_workspace="AuraAI", repo_path=repo_root)
    assert res is None


def test_reject_non_existent_file_in_workspace(repo_root: Path):
    tracker = EditorTracker(root=repo_root)
    # File with code extension that does not exist in repo
    title = "ghost_file_xyz.py - AuraAI - Antigravity IDE"
    res = tracker.parse_window_title(title, expected_workspace="AuraAI", repo_path=repo_root)
    assert res is None


def test_reject_bare_workspace_title(repo_root: Path):
    tracker = EditorTracker(root=repo_root)
    # When no file is open, editor shows only workspace name
    assert tracker.parse_window_title("AuraAI - Antigravity IDE", expected_workspace="AuraAI", repo_path=repo_root) is None
    assert tracker.parse_window_title("AuraAI - Visual Studio Code", expected_workspace="AuraAI", repo_path=repo_root) is None


def test_reject_malformed_and_non_editor_titles(repo_root: Path):
    tracker = EditorTracker(root=repo_root)
    assert tracker.parse_window_title("", expected_workspace="AuraAI", repo_path=repo_root) is None
    assert tracker.parse_window_title("Chrome Browser - Google", expected_workspace="AuraAI", repo_path=repo_root) is None
    assert tracker.parse_window_title("Calculator", expected_workspace="AuraAI", repo_path=repo_root) is None
    assert tracker.parse_window_title("Random Window - Antigravity IDE", expected_workspace="AuraAI", repo_path=repo_root) is None
