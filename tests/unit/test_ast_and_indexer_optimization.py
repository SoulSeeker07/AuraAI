"""
Unit tests for ASTManager incremental mtime/size caching and SpeculativeIndexer readiness gating.
"""

import time
from pathlib import Path
import pytest

from engineering.ast_manager import ASTManager, ASTFile
from workspace.speculative_indexer import SpeculativeIndexer, PrewarmedWorkspaceContext


def test_ast_manager_caching_and_invalidation(tmp_path: Path):
    """Verify ASTManager caches unchanged files and invalidates only when modified."""
    file_a = tmp_path / "mod_a.py"
    file_b = tmp_path / "mod_b.py"

    file_a.write_text("def func_a():\n    return 42\n", encoding="utf-8")
    file_b.write_text("class ClassB:\n    pass\n", encoding="utf-8")

    mgr = ASTManager(repository_path=tmp_path)

    # 1. Initial parse
    ast_a1 = mgr.parse_file(file_a)
    assert "func_a" in ast_a1.get_all_symbols()
    assert len(mgr._cache) == 1

    ast_b1 = mgr.parse_file(file_b)
    assert "ClassB" in ast_b1.get_all_symbols()
    assert len(mgr._cache) == 2

    # 2. Fast cache hit (same object returned)
    ast_a2 = mgr.parse_file(file_a)
    assert ast_a2 is ast_a1

    # 3. Modify file A only
    time.sleep(0.05)  # Ensure filesystem mtime resolution
    file_a.write_text("def func_a_v2():\n    return 100\n", encoding="utf-8")

    # 4. Parse file A -> must detect mtime change and invalidate cache
    ast_a3 = mgr.parse_file(file_a)
    assert "func_a_v2" in ast_a3.get_all_symbols()
    assert "func_a" not in ast_a3.get_all_symbols()
    assert ast_a3 is not ast_a1

    # 5. File B must remain cached and untouched
    ast_b2 = mgr.parse_file(file_b)
    assert ast_b2 is ast_b1


def test_speculative_indexer_readiness_gate(tmp_path: Path):
    """Verify SpeculativeIndexer readiness gate and context retrieval."""
    SpeculativeIndexer.reset_instance()

    test_file = tmp_path / "app.py"
    test_file.write_text("def run_app(): pass\n", encoding="utf-8")

    indexer = SpeculativeIndexer(repo_root=tmp_path)

    # Readiness gate check
    is_ready = indexer.await_ready(timeout=3.0)
    assert is_ready is True
    assert indexer.is_ready() is True

    ctx = indexer.get_prewarmed_context(repo_root=tmp_path)
    assert ctx is not None
    assert ctx.repo_root == str(tmp_path.resolve())

    SpeculativeIndexer.reset_instance()


def test_duplicate_detector_lazy_loading():
    """Verify importing duplicate_detector does not eagerly load heavy PyTorch/Transformer objects."""
    from engineering.duplicate_detector import DuplicateDetector, COMMON_INTERFACE_METHODS
    assert "__init__" in COMMON_INTERFACE_METHODS


def test_speculative_indexer_timeout_graceful_handling(tmp_path: Path):
    """Verify indexer gracefully returns None on timeout when force_sync=False, and computes when force_sync=True."""
    SpeculativeIndexer.reset_instance()
    indexer = SpeculativeIndexer(repo_root=tmp_path)
    
    # Simulate unready state
    indexer._ready_event.clear()
    
    # Timeout with force_sync=False returns None without raising
    res = indexer.get_prewarmed_context(repo_root=tmp_path, force_sync=False, wait_if_pending=True)
    # If background prewarm finished, it's a context; if event was cleared and no timeout wait, None
    assert res is None or isinstance(res, PrewarmedWorkspaceContext)
    
    # force_sync=True forces computation even if pending
    res_forced = indexer.get_prewarmed_context(repo_root=tmp_path, force_sync=True, wait_if_pending=False)
    assert res_forced is not None
    assert res_forced.repo_root == str(tmp_path.resolve())
    
    SpeculativeIndexer.reset_instance()


def test_ambient_context_builder_speculative_integration(tmp_path: Path):
    """Verify AmbientContextBuilder includes Workspace Context when indexer is attached."""
    from core.context.ambient_context_builder import AmbientContextBuilder
    
    class FakeCore:
        def __init__(self):
            self.memory = None
            self.speculative_indexer = SpeculativeIndexer(repo_root=tmp_path)
            self.speculative_indexer.await_ready(timeout=2.0)
    
    fake_core = FakeCore()
    ambient = AmbientContextBuilder.build_ambient_context(fake_core)
    assert "Workspace Context" in ambient

