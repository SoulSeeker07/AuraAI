"""
Speculative Workspace Context Pre-Fetching Subsystem
Location: src/workspace/speculative_indexer.py

Asynchronously pre-warms AST symbols, active editor document structures,
and Git repository diff summaries in background threads on foreground window
or file change events, providing <1ms instant context retrieval.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from engineering.ast_manager import ASTManager
from workspace.editor_tracker import EditorTracker
from workspace.git_context import GitContext

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60.0


@dataclass
class PrewarmedWorkspaceContext:
    """Pre-assembled context ready for instantaneous injection into LLM prompts."""
    repo_root: str
    active_file: str | None = None
    ast_symbols: list[str] = field(default_factory=list)
    ast_classes: list[str] = field(default_factory=list)
    ast_functions: list[str] = field(default_factory=list)
    git_branch: str = "main"
    git_is_dirty: bool = False
    uncommitted_files: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def is_expired(self, ttl: float = CACHE_TTL_SECONDS) -> bool:
        return (time.time() - self.created_at) > ttl

    def to_prompt_snippet(self) -> str:
        """Render a concise context header for prompt injection."""
        lines = [f"[Workspace Context: {Path(self.repo_root).name}]"]
        if self.active_file:
            lines.append(f"Active Editor File: {self.active_file}")
            if self.ast_symbols:
                syms = ", ".join(self.ast_symbols[:15])
                lines.append(f"AST Symbols: {syms}")
        if self.git_branch:
            dirty_str = " (dirty)" if self.git_is_dirty else " (clean)"
            lines.append(f"Git: {self.git_branch}{dirty_str}")
        return "\n".join(lines)


class SpeculativeIndexer:
    """
    Background speculative context pre-warmer.

    Monitors active editor state and asynchronously pre-indexes AST & Git metadata.
    """

    _instance: Optional["SpeculativeIndexer"] = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self, repo_root: str | Path | None = None):
        self.repo_root = Path(repo_root or Path.cwd()).resolve()
        self._editor_tracker = EditorTracker(root=self.repo_root)
        self._git_context = GitContext(cache_ttl_seconds=30)
        self._ast_manager = ASTManager(repository_path=self.repo_root)

        self._cache: dict[str, PrewarmedWorkspaceContext] = {}
        self._worker_thread: Optional[threading.Thread] = None
        self._cache_lock = threading.Lock()

    @classmethod
    def get_instance(cls, repo_root: str | Path | None = None) -> "SpeculativeIndexer":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(repo_root=repo_root)
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None

    def trigger_speculative_prewarm(self, window_title: str | None = None) -> None:
        """
        Non-blocking trigger to pre-warm workspace context in a background daemon thread.
        """
        def _prewarm_job():
            try:
                self._compute_and_cache_context(window_title)
            except Exception as e:
                logger.debug(f"[SpeculativeIndexer] Pre-warm job notice: {e}")

        t = threading.Thread(target=_prewarm_job, daemon=True)
        t.start()

    def _compute_and_cache_context(self, window_title: str | None = None) -> PrewarmedWorkspaceContext:
        """Compute the full context and store in thread-safe memory cache."""
        active_file_rel = None

        # 1. Parse active editor window title if available
        if window_title:
            doc_info = self._editor_tracker.parse_window_title(window_title)
            if doc_info and doc_info.get("filename"):
                active_file_rel = doc_info["filename"]

        ast_symbols = []
        ast_classes = []
        ast_functions = []

        # 2. Parse AST for active file if it exists
        if active_file_rel:
            full_path = self.repo_root / active_file_rel
            if not full_path.exists():
                # Fast targeted search in src/ and tests/ (avoiding .venv / .git)
                for sub in ("src", "tests"):
                    sub_dir = self.repo_root / sub
                    if sub_dir.exists():
                        for cand in sub_dir.rglob(active_file_rel):
                            full_path = cand
                            break
                        if full_path.exists():
                            break

            if full_path.exists() and full_path.suffix == ".py":
                try:
                    ast_file = self._ast_manager.parse_file(full_path)
                    ast_symbols = ast_file.get_all_symbols()
                    ast_classes = [c.name for c in ast_file.classes if c]
                    ast_functions = [f.name for f in ast_file.functions if f]
                except Exception as e:
                    logger.debug(f"[SpeculativeIndexer] AST parse note: {e}")

        # 3. Query Git Context (TTL cached)
        git_branch = "main"
        git_is_dirty = False
        uncommitted = []
        try:
            repo_info = self._git_context.get_git_repo_sync(str(self.repo_root))
            if repo_info:
                git_branch = repo_info.branch or "main"
                git_is_dirty = repo_info.is_dirty
                uncommitted = repo_info.modified_files or []
        except Exception as e:
            logger.debug(f"[SpeculativeIndexer] Git query note: {e}")

        ctx = PrewarmedWorkspaceContext(
            repo_root=str(self.repo_root),
            active_file=active_file_rel,
            ast_symbols=ast_symbols,
            ast_classes=ast_classes,
            ast_functions=ast_functions,
            git_branch=git_branch,
            git_is_dirty=git_is_dirty,
            uncommitted_files=uncommitted,
        )

        with self._cache_lock:
            self._cache[str(self.repo_root)] = ctx

        logger.debug(
            f"[SpeculativeIndexer] Pre-warmed context for {self.repo_root.name} "
            f"(active_file={active_file_rel}, symbols={len(ast_symbols)}, git={git_branch})"
        )
        return ctx

    def get_prewarmed_context(
        self,
        repo_root: str | Path | None = None,
        force_sync: bool = False,
    ) -> Optional[PrewarmedWorkspaceContext]:
        """
        Instant (<1ms) retrieval of pre-warmed context from memory.
        If cache is missing or expired and force_sync is True, synchronously computes it.
        """
        root_key = str(Path(repo_root or self.repo_root).resolve())

        with self._cache_lock:
            cached = self._cache.get(root_key)
            if cached and not cached.is_expired():
                return cached

        if force_sync:
            return self._compute_and_cache_context()

        return None
