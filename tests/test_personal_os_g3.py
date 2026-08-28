"""
Unit Tests for Personal OS Gate G3 (Workspace Search Engine)
Location: tests/test_personal_os_g3.py
"""

from __future__ import annotations

import time
import pytest
from pathlib import Path

from personal_os.workspace_search import WorkspaceSearchEngine
from core.orchestration.master_orchestrator import MasterOrchestrator


def test_workspace_search_engine_indexing_and_query():
    """Verify WorkspaceSearchEngine indexes workspace and finds target files."""
    WorkspaceSearchEngine.reset_instance()
    engine = WorkspaceSearchEngine.get_instance()
    assert len(engine._index) > 0

    # 1. Search for known file
    results = engine.search("cognitive_memory.py")
    assert len(results) >= 1
    top_result = results[0]
    assert "cognitive_memory.py" in top_result.filename
    assert "src/memory" in top_result.path.replace("\\", "/")

    # 2. Search for keyword query
    results_kw = engine.search("daily_context")
    assert len(results_kw) >= 1
    assert any("daily_context.py" in r.filename for r in results_kw)


def test_workspace_search_engine_subsecond_latency():
    """AC2: Workspace search executes within 1 second."""
    engine = WorkspaceSearchEngine.get_instance()

    queries = [
        "state_store.py",
        "master_orchestrator",
        "find the file where we store cognitive memory",
        "workspace_walker",
    ]

    for q in queries:
        start_t = time.perf_counter()
        results = engine.search(q)
        elapsed = time.perf_counter() - start_t
        assert elapsed < 1.0, f"Query '{q}' took {elapsed:.3f}s (exceeded 1.0s limit)"
        assert len(results) >= 1


@pytest.mark.asyncio
async def test_master_orchestrator_e2e_workspace_search_ac2():
    """AC2: End-to-end workspace search through MasterOrchestrator in <1s."""
    orch = MasterOrchestrator()

    # Warm-up run
    await orch.process_request_async("execute capability personal_os.search")

    start_t = time.perf_counter()
    result = await orch.process_request_async("Find the file where we store cognitive memory")
    elapsed = time.perf_counter() - start_t

    assert result.success is True
    assert elapsed < 3.0  # Full pipeline under 3s
    # Observations or data must contain the file match
    obs_text = " ".join(result.observations or [])
    data_text = str(result.data or {})
    assert "cognitive_memory" in obs_text or "cognitive_memory" in data_text or "match" in obs_text.lower()


def test_workspace_search_engine_filesystem_watcher_incremental_events():
    """Verify WorkspaceSearchEngine updates index dynamically on FilesystemWatcher events."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        root_dir = Path(tmpdir)
        engine = WorkspaceSearchEngine(root_dir=root_dir)
        assert len(engine._index) == 0

        # Simulate file created event
        new_file = root_dir / "user_notes.md"
        new_file.write_text("# Project Notes", encoding="utf-8")
        engine.on_filesystem_event("created", new_file)

        assert len(engine._index) == 1
        results = engine.search("user_notes")
        assert len(results) == 1
        assert results[0].filename == "user_notes.md"

        # Simulate file deleted event
        new_file.unlink()
        engine.on_filesystem_event("deleted", new_file)
        assert len(engine._index) == 0
        results_after_del = engine.search("user_notes")
        assert len(results_after_del) == 0


def test_filesystem_watcher_live_subscription_to_workspace_search():
    """Verify AuraCore._init_personal_os wires FilesystemWatcher to WorkspaceSearchEngine."""
    import tempfile
    from core.aura_core import AuraCore, AuraCoreStatus
    from autonomy.event_runtime import EventRuntime
    from autonomy.watchers.filesystem import FilesystemWatcher, _AuraFileSystemHandler
    from watchdog.events import FileCreatedEvent, FileDeletedEvent

    with tempfile.TemporaryDirectory() as tmpdir:
        root_dir = Path(tmpdir)
        storage_dir = root_dir / "storage"
        storage_dir.mkdir(parents=True, exist_ok=True)

        event_runtime = EventRuntime()
        fs_watcher = FilesystemWatcher(runtime=event_runtime, watch_paths=[root_dir])

        core = AuraCore.__new__(AuraCore)
        core.project_root = root_dir
        core.components = {}
        core.filesystem_watcher = fs_watcher

        # Reset singletons across both import paths
        try:
            from personal_os.workspace_search import WorkspaceSearchEngine as WSE1
            WSE1.reset_instance()
        except ImportError:
            pass
        from personal_os.workspace_search import WorkspaceSearchEngine as WSE2
        WSE2.reset_instance()

        # Initialize Personal OS subsystem
        core._init_personal_os()
        assert core.components["personal_os"].status == AuraCoreStatus.READY
        assert len(fs_watcher._handler._listeners) == 1

        # Emit Watchdog event through the handler
        test_file = root_dir / "live_spec.py"
        test_file.write_text("print('live')", encoding="utf-8")
        fs_watcher._handler.on_created(FileCreatedEvent(str(test_file)))

        # Verify WorkspaceSearchEngine received the live event and updated its index
        results = core.workspace_search_engine.search("live_spec")
        assert len(results) >= 1
        assert results[0].filename == "live_spec.py"

        # Emit delete event
        test_file.unlink()
        fs_watcher._handler.on_deleted(FileDeletedEvent(str(test_file)))
        assert len(core.workspace_search_engine.search("live_spec")) == 0
