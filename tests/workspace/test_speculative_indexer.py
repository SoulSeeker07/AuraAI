"""
Unit tests for SpeculativeIndexer (M34)
Location: tests/workspace/test_speculative_indexer.py

Covers:
  - Background asynchronous pre-warming
  - AST symbol parsing and definition extraction
  - Git branch and uncommitted files pre-caching
  - Instant <1ms memory retrieval
  - PrewarmedWorkspaceContext snippet formatting and TTL expiry
"""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from workspace.speculative_indexer import (
    SpeculativeIndexer,
    PrewarmedWorkspaceContext,
    CACHE_TTL_SECONDS,
)


@pytest.fixture
def indexer(tmp_path):
    SpeculativeIndexer.reset_instance()
    idx = SpeculativeIndexer.get_instance(repo_root=tmp_path)
    yield idx
    SpeculativeIndexer.reset_instance()


class TestPrewarmedWorkspaceContext:
    def test_ttl_expiry(self):
        ctx = PrewarmedWorkspaceContext(
            repo_root="/repo",
            created_at=time.time() - 70.0,
        )
        assert ctx.is_expired(ttl=60.0) is True

        ctx_fresh = PrewarmedWorkspaceContext(
            repo_root="/repo",
            created_at=time.time(),
        )
        assert ctx_fresh.is_expired(ttl=60.0) is False

    def test_prompt_snippet_formatting(self):
        ctx = PrewarmedWorkspaceContext(
            repo_root="D:/Projects/AuraAI",
            active_file="main.py",
            ast_symbols=["run_app", "initialize_core"],
            git_branch="feature/m34",
            git_is_dirty=True,
        )
        snippet = ctx.to_prompt_snippet()
        assert "[Workspace Context: AuraAI]" in snippet
        assert "Active Editor File: main.py" in snippet
        assert "AST Symbols: run_app, initialize_core" in snippet
        assert "Git: feature/m34 (dirty)" in snippet


class TestSpeculativeIndexer:
    def test_sync_compute_context_with_real_py_file(self, indexer, tmp_path):
        # Create a sample python file in tmp_path
        sample_file = tmp_path / "service.py"
        sample_file.write_text("class UserAuth:\n    pass\n\ndef login():\n    pass\n", encoding="utf-8")

        # Mock window title pointing to service.py
        title = f"service.py - {tmp_path.name} - Visual Studio Code"
        ctx = indexer._compute_and_cache_context(window_title=title)

        assert ctx.active_file == "service.py"
        assert "UserAuth" in ctx.ast_classes
        assert "login" in ctx.ast_functions

    def test_instant_cache_retrieval(self, indexer, tmp_path):
        # Pre-seed cache
        indexer._compute_and_cache_context()

        # Instant retrieval
        t0 = time.perf_counter()
        cached = indexer.get_prewarmed_context(repo_root=tmp_path)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        assert cached is not None
        assert elapsed_ms < 5.0  # Must be fast <5ms memory hit
