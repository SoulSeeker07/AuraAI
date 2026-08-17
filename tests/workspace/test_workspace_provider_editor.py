"""
Integration tests for WorkspaceProvider active_file perception and CodingBackendAdapter world context formatting.
Location: tests/workspace/test_workspace_provider_editor.py
"""

from pathlib import Path
import pytest
from unittest.mock import MagicMock

from brain.providers.workspace_provider import WorkspaceProvider
from brain.world_model import WorldModel
from core.backends.adapters.antigravity_backend import CodingBackendAdapter
from workspace.editor_tracker import EditorTracker


@pytest.fixture
def test_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "AuraAI"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("print('hello')", encoding="utf-8")
    return repo


@pytest.mark.asyncio
async def test_workspace_provider_active_file_query(test_repo: Path):
    mock_tracker = MagicMock(spec=EditorTracker)
    mock_tracker.get_active_editor_file_sync.return_value = {
        "filename": "app.py",
        "relative_path": "src/app.py",
        "workspace": "AuraAI",
        "is_dirty": False,
    }

    provider = WorkspaceProvider(root=test_repo, editor_tracker=mock_tracker)
    
    # Query specific entity
    facts = await provider.query("active_file")
    assert len(facts) == 1
    assert facts[0].domain == "workspace"
    assert facts[0].entity == "active_file"
    assert facts[0].value == "src/app.py"

    # Query 'all' entity
    all_facts = await provider.query("all")
    active_facts = [f for f in all_facts if f.entity == "active_file"]
    assert len(active_facts) == 1
    assert active_facts[0].value == "src/app.py"


@pytest.mark.asyncio
async def test_workspace_provider_no_editor_open(test_repo: Path):
    mock_tracker = MagicMock(spec=EditorTracker)
    mock_tracker.get_active_editor_file_sync.return_value = None

    provider = WorkspaceProvider(root=test_repo, editor_tracker=mock_tracker)
    facts = await provider.query("active_file")
    assert facts == []


def test_coding_backend_world_context_includes_active_editor(test_repo: Path):
    mock_wm = MagicMock()
    
    from brain.providers.base import ProviderFact, QueryResult
    
    mock_wm.query_sync.return_value = QueryResult(
        entity="all",
        facts=[
            ProviderFact(domain="workspace", entity="git_branch", value="main"),
            ProviderFact(domain="workspace", entity="active_file", value="src/app.py"),
        ],
        summary="Workspace facts",
    )
    mock_wm.query_multi_sync.return_value = []

    adapter = CodingBackendAdapter(world_model=mock_wm)
    context = adapter._get_world_context("Fix the bug in app.py", test_repo)
    
    assert "Active Editor File: `src/app.py`" in context
    assert "• git_branch: main" in context


def test_coding_backend_world_context_empty_when_no_active_editor(test_repo: Path):
    mock_wm = MagicMock()
    
    from brain.providers.base import ProviderFact, QueryResult
    
    mock_wm.query_sync.return_value = QueryResult(
        entity="all",
        facts=[
            ProviderFact(domain="workspace", entity="git_branch", value="main"),
        ],
        summary="Workspace facts",
    )
    mock_wm.query_multi_sync.return_value = []

    adapter = CodingBackendAdapter(world_model=mock_wm)
    context = adapter._get_world_context("Fix the bug", test_repo)
    
    assert "Active Editor File:" not in context
    assert "• git_branch: main" in context
