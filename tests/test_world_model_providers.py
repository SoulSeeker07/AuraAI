"""
Unit Tests for M18 Phase 2: World Model Providers & Query Aggregation

Tests:
  1. Domain filtering (query only dispatches to selected domain)
  2. Per-provider timeout handling with graceful degradation
  3. Dedicated ThreadPoolExecutor isolation
  4. SymbolGraphProvider mtime-based cache invalidation
  5. DesktopProvider entity queries
  6. WorkspaceProvider entity queries
  7. BrowserProvider entity queries
  8. MemoryProvider entity queries
  9. Multi-domain query aggregation & summary formatting
"""

import asyncio
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.brain.providers.base import IWorldProvider, ProviderFact, QueryResult
from src.brain.providers.browser_provider import BrowserProvider
from src.brain.providers.desktop_provider import DesktopProvider
from src.brain.providers.memory_provider import MemoryProvider
from src.brain.providers.symbol_provider import SymbolGraphProvider
from src.brain.providers.workspace_provider import WorkspaceProvider
from src.brain.world_model import WorldModel
from src.workspace.models import ActiveWindow, GitRepository, RunningApplication


# ── 1. Domain Filtering Test ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_world_model_query_domain_filtering():
    """Verify specifying domain filters execution to only target providers."""
    mock_desktop = AsyncMock(spec=IWorldProvider)
    mock_desktop.domain = "desktop"
    mock_desktop.query.return_value = [
        ProviderFact(domain="desktop", entity="focused_app", value="VS Code")
    ]

    mock_workspace = AsyncMock(spec=IWorldProvider)
    mock_workspace.domain = "workspace"
    mock_workspace.query.return_value = [
        ProviderFact(domain="workspace", entity="git_branch", value="main")
    ]

    wm = WorldModel(providers=[mock_desktop, mock_workspace])

    # Query desktop domain only
    res = await wm.query(entity="focused_app", domain="desktop")
    assert len(res.facts) == 1
    assert res.facts[0].domain == "desktop"
    assert res.facts[0].value == "VS Code"

    mock_desktop.query.assert_called_once_with("focused_app")
    mock_workspace.query.assert_not_called()


# ── 2. Per-Provider Timeout & Graceful Degradation Test ──────────────────────

@pytest.mark.asyncio
async def test_world_model_query_timeout_graceful_degradation():
    """Verify a hanging provider times out without stalling the other providers or the query."""
    fast_provider = AsyncMock(spec=IWorldProvider)
    fast_provider.domain = "desktop"
    fast_provider.query.return_value = [
        ProviderFact(domain="desktop", entity="active_window", value="Editor")
    ]

    class HangingProvider(IWorldProvider):
        @property
        def domain(self) -> str:
            return "symbol"

        async def get_state(self):
            return {}

        async def query(self, entity: str):
            await asyncio.sleep(2.0)  # Hang longer than timeout
            return [ProviderFact(domain="symbol", entity="class:X", value="file.py")]

    wm = WorldModel(providers=[fast_provider, HangingProvider()])

    start = time.time()
    res = await wm.query(entity="status", timeout=0.1)
    duration = time.time() - start

    # Must finish around 0.1s rather than 2.0s
    assert duration < 0.5
    assert len(res.facts) == 1
    assert res.facts[0].domain == "desktop"
    assert res.facts[0].value == "Editor"
    wm.shutdown()


@pytest.mark.asyncio
async def test_world_model_query_executor_thread_timeout():
    """
    Verify that when a provider's blocking work runs via the dedicated executor:
    1. Query times out and returns promptly (unblocking callers like the voice loop).
    2. The thread finishes in the isolated pool without corrupting or hanging the query engine.
    """
    worker_completed = [False]

    def slow_blocking_os_call():
        time.sleep(0.4)
        worker_completed[0] = True

    class SlowExecutorProvider(IWorldProvider):
        def __init__(self, executor):
            self._executor = executor

        @property
        def domain(self) -> str:
            return "workspace"

        async def get_state(self):
            return {}

        async def query(self, entity: str):
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(self._executor, slow_blocking_os_call)
            return [ProviderFact(domain="workspace", entity="git", value="ok")]

    wm = WorldModel(providers=[])
    slow_provider = SlowExecutorProvider(executor=wm._executor)
    wm.register_provider(slow_provider)

    start = time.time()
    # Query with 0.1s timeout
    res = await wm.query(entity="git", timeout=0.1)
    duration = time.time() - start

    # 1. Query returned promptly
    assert duration < 0.3
    assert len(res.facts) == 0  # Provider timed out gracefully

    # 2. Worker thread was not finished at return time
    assert worker_completed[0] is False

    # 3. Wait for worker thread to naturally complete in dedicated pool
    await asyncio.sleep(0.45)
    assert worker_completed[0] is True
    wm.shutdown()


# ── 3. Dedicated ThreadPoolExecutor Isolation ────────────────────────────────

def test_world_model_dedicated_executor():
    """Verify WorldModel has dedicated bounded executor named world-model-worker."""
    wm = WorldModel(providers=[])
    assert wm._executor._max_workers == 4
    assert "world-model-worker" in getattr(wm._executor, "_thread_name_prefix", "")
    wm.shutdown()


# ── 4. SymbolGraphProvider mtime Cache Invalidation ──────────────────────────

@pytest.mark.asyncio
async def test_symbol_graph_provider_mtime_invalidation():
    """Verify modifying a Python file updates SymbolGraphProvider queries on the fly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir).resolve()
        py_file = root / "app.py"
        
        # 1. Initial version
        py_file.write_text("class OriginalClass:\n    def helper(self):\n        pass\n", encoding="utf-8")

        provider = SymbolGraphProvider(root=root)
        
        facts = await provider.query("classes")
        assert len(facts) == 1
        assert "OriginalClass" in facts[0].value

        # 2. Modify file content and timestamp
        time.sleep(0.02)
        py_file.write_text("class UpdatedClass:\n    def new_helper(self):\n        pass\n", encoding="utf-8")

        # Query again — mtime detection should re-parse
        facts_after = await provider.query("classes")
        assert len(facts_after) == 1
        assert "UpdatedClass" in facts_after[0].value
        assert "OriginalClass" not in facts_after[0].value


# ── 5. DesktopProvider Entity Queries ────────────────────────────────────────

@pytest.mark.asyncio
async def test_desktop_provider_queries():
    """Verify DesktopProvider resolves active window and running applications."""
    mock_win_mon = MagicMock()
    mock_win_mon.get_active_window_sync.return_value = ActiveWindow(
        title="Project - VS Code",
        app_name="VS Code",
        process_name="code",
    )

    mock_apps_mon = MagicMock()
    mock_apps_mon.get_running_apps_sync.return_value = [
        RunningApplication(name="VS Code", process_name="code", is_foreground=True),
        RunningApplication(name="Chrome", process_name="chrome", is_foreground=False),
    ]

    provider = DesktopProvider(window_monitor=mock_win_mon, apps_monitor=mock_apps_mon)

    # Test is_running query
    is_chrome = await provider.query("is_running:chrome")
    assert is_chrome[0].value is True

    is_spotify = await provider.query("is_running:spotify")
    assert is_spotify[0].value is False

    # Test focused app query
    focused = await provider.query("focused_app")
    assert focused[0].value == "VS Code"


# ── 6. WorkspaceProvider Entity Queries ──────────────────────────────────────

@pytest.mark.asyncio
async def test_workspace_provider_queries():
    """Verify WorkspaceProvider resolves git state and project type."""
    mock_git = MagicMock()
    mock_git.get_git_repo_sync.return_value = GitRepository(
        path="C:/Repo",
        branch="feature/world-model",
        uncommitted_changes=2,
        modified_files=["app.py", "README.md"],
        is_dirty=True,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        provider = WorkspaceProvider(root=Path(tmpdir), git_context=mock_git)
        
        branch_fact = await provider.query("git_branch")
        assert branch_fact[0].value == "feature/world-model"

        dirty_facts = await provider.query("dirty_files")
        assert any(f.entity == "uncommitted_changes" and f.value == 2 for f in dirty_facts)


# ── 7. BrowserProvider Entity Queries ────────────────────────────────────────

@pytest.mark.asyncio
async def test_browser_provider_queries():
    """Verify BrowserProvider queries tabs and open URLs."""
    provider = BrowserProvider()
    with patch.object(provider, "_probe_sync", return_value=MagicMock(to_dict=lambda: {
        "open_tabs": [{"url": "https://github.com", "title": "GitHub"}],
        "running_browsers": ["chrome"],
    })):
        tab_facts = await provider.query("active_tab")
        assert len(tab_facts) == 1
        assert "https://github.com" in tab_facts[0].value


# ── 8. MemoryProvider Entity Queries ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_memory_provider_queries():
    """Verify MemoryProvider queries user preferences and context."""
    mock_mem = MagicMock()
    mock_mem.get_all_preferences.return_value = {"favorite_editor": "VS Code"}

    provider = MemoryProvider(memory_manager=mock_mem)
    pref_facts = await provider.query("user_preferences")
    assert len(pref_facts) == 1
    assert pref_facts[0].value.get("favorite_editor") == "VS Code"


# ── 9. Multi-Domain Query Aggregation & Summary ──────────────────────────────

@pytest.mark.asyncio
async def test_world_model_multi_domain_aggregation_and_summary():
    """Verify multi-domain query aggregates facts and formats consistent summary."""
    p1 = AsyncMock(spec=IWorldProvider)
    p1.domain = "desktop"
    p1.query.return_value = [
        ProviderFact(domain="desktop", entity="focused_app", value="VS Code")
    ]

    p2 = AsyncMock(spec=IWorldProvider)
    p2.domain = "workspace"
    p2.query.return_value = [
        ProviderFact(domain="workspace", entity="git_branch", value="main")
    ]

    wm = WorldModel(providers=[p1, p2])
    res = await wm.query("all")

    assert len(res.facts) == 2
    assert "World Model Facts for 'all':" in res.summary
    assert "• [Desktop] focused_app: VS Code" in res.summary
    assert "• [Workspace] git_branch: main" in res.summary
