"""
Workspace Walker Module

Unified, high-performance, .gitignore-aware repository and workspace walker.
Supports:
  1. Always-ignore defaults (.git, __pycache__, .venv, node_modules, etc.)
  2. Nested .gitignore hierarchies with directory scoping and pattern negations (!pattern)
  3. Additional .auraignore files and custom ignore rules
  4. Hard file caps (max_files safety net)
  5. Single-path point checks (is_ignored) for live file watchers and event systems
"""

import logging
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pathspec

logger = logging.getLogger(__name__)


class WorkspaceSizeError(Exception):
    """Raised when repository discovery exceeds the max_files safety cap."""


class BoundaryEscapeError(Exception):
    """Raised when a path escapes the workspace root boundary."""


class WorkspaceWalker:
    """
    Unified .gitignore-aware workspace walker.
    Designed for shared consumption across M20 (Coding Agent) and M18 (World Model).
    """

    # Always-ignore directory names across all workspaces
    ALWAYS_IGNORE_DIRS: set[str] = {
        ".git",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".idea",
        ".vscode",
        "dist",
        "build",
        ".cache",
        ".eggs",
        "*.egg-info",
    }

    # Always-ignore file extensions / names
    ALWAYS_IGNORE_FILES: set[str] = {
        ".DS_Store",
        "Thumbs.db",
        ".coverage",
    }

    ALWAYS_IGNORE_EXTENSIONS: set[str] = {
        ".pyc",
        ".pyo",
        ".pyd",
    }

    def __init__(
        self,
        root: Path | str,
        respect_gitignore: bool = True,
        max_files: int | None = 2000,
        custom_ignores: list[str] | None = None,
    ):
        self.root: Path = Path(root).resolve()
        self.respect_gitignore: bool = respect_gitignore
        self.max_files: int | None = max_files
        self.custom_ignores: list[str] = custom_ignores or []
        
        # Cache of parsed PathSpec instances per directory: (spec, mtimes_dict)
        self._specs_cache: dict[Path, tuple[pathspec.PathSpec | None, dict[str, float]]] = {}
        
        # Pre-compile root custom ignore spec if provided
        self._custom_spec: pathspec.PathSpec | None = None
        if self.custom_ignores:
            self._custom_spec = pathspec.PathSpec.from_lines("gitignore", self.custom_ignores)

    def invalidate(self, dir_path: Path | None = None) -> None:
        """Invalidate cached PathSpec instances for a directory or all directories."""
        if dir_path is not None:
            self._specs_cache.pop(Path(dir_path).resolve(), None)
        else:
            self._specs_cache.clear()

    def _is_safe(self, path: Path) -> bool:
        """Verify path is contained within the workspace root boundary."""
        try:
            path.resolve().relative_to(self.root)
            return True
        except ValueError:
            return False

    def _is_builtin_ignored(self, path: Path, is_dir: bool = False) -> bool:
        """
        Check if path matches always-ignore defaults (no .gitignore needed).
        Crucially scopes check relative to self.root to avoid false positives
        if the workspace root resides inside a parent folder named 'build' or 'dist'.
        """
        resolved = path.resolve()
        try:
            rel = resolved.relative_to(self.root)
            parts = rel.parts
        except ValueError:
            parts = resolved.parts

        for part in parts:
            if part in self.ALWAYS_IGNORE_DIRS or part.endswith(".egg-info"):
                return True

        if not is_dir:
            if resolved.name in self.ALWAYS_IGNORE_FILES:
                return True
            if resolved.suffix in self.ALWAYS_IGNORE_EXTENSIONS:
                return True

        return False

    def _get_directory_spec(self, dir_path: Path) -> pathspec.PathSpec | None:
        """
        Load, validate mtimes, and cache .gitignore and .auraignore PathSpec for a directory.
        Automatically detects file modifications on disk without needing a full process restart.
        """
        dir_path = dir_path.resolve()
        gitignore_file = dir_path / ".gitignore"
        auraignore_file = dir_path / ".auraignore"

        # Check current mtimes of ignore files
        current_mtimes: dict[str, float] = {}
        for f in (gitignore_file, auraignore_file):
            if f.is_file():
                try:
                    current_mtimes[f.name] = f.stat().st_mtime
                except OSError:
                    pass

        if dir_path in self._specs_cache:
            cached_spec, cached_mtimes = self._specs_cache[dir_path]
            if cached_mtimes == current_mtimes:
                return cached_spec

        # Cache miss or file changed: compile new PathSpec
        patterns: list[str] = []
        for f in (gitignore_file, auraignore_file):
            if f.is_file():
                try:
                    with open(f, "r", encoding="utf-8", errors="replace") as fh:
                        patterns.extend(fh.readlines())
                except Exception as e:
                    logger.debug(f"[WorkspaceWalker] Error reading {f}: {e}")

        spec = pathspec.PathSpec.from_lines("gitignore", patterns) if patterns else None
        self._specs_cache[dir_path] = (spec, current_mtimes)
        return spec

    def _get_ancestor_dirs(self, target_path: Path) -> list[Path]:
        """Return list of ancestor directories from root down to target_path's parent directory."""
        resolved = target_path.resolve()
        if not self._is_safe(resolved):
            return []

        ancestors = []
        curr = resolved if resolved.is_dir() else resolved.parent
        
        while True:
            ancestors.append(curr)
            if curr == self.root:
                break
            parent = curr.parent
            if parent == curr:  # Reached filesystem root
                break
            curr = parent

        ancestors.reverse()  # Root first -> leaf directory last
        return ancestors

    def is_ignored(self, path: Path | str, is_dir: bool | None = None) -> bool:
        """
        Point-check whether a single path is ignored.
        Evaluates:
          1. Always-ignore defaults (scoped relative to workspace root)
          2. Custom ignore patterns
          3. Nested .gitignore / .auraignore chain from root to target
        """
        target = Path(path)
        if not target.is_absolute():
            target = (self.root / target).resolve()
        else:
            target = target.resolve()

        if not self._is_safe(target):
            raise BoundaryEscapeError(f"Path '{target}' escapes workspace root boundary '{self.root}'")

        if is_dir is None:
            is_dir = target.is_dir()

        # 1. Always-ignore defaults
        if self._is_builtin_ignored(target, is_dir=is_dir):
            return True

        # 2. Custom ignore rules
        if self._custom_spec:
            rel_to_root = target.relative_to(self.root).as_posix()
            if is_dir and not rel_to_root.endswith("/"):
                rel_to_root += "/"
            if self._custom_spec.match_file(rel_to_root):
                return True

        # 3. .gitignore hierarchy
        if not self.respect_gitignore:
            return False

        ancestor_dirs = self._get_ancestor_dirs(target)
        ignored_state = False

        for ancestor in ancestor_dirs:
            spec = self._get_directory_spec(ancestor)
            if spec is not None:
                try:
                    rel_path = target.relative_to(ancestor).as_posix()
                    if is_dir and not rel_path.endswith("/"):
                        rel_path += "/"
                    check_res = spec.check_file(rel_path)
                    if check_res.include is True:
                        ignored_state = True
                    elif check_res.include is False:
                        # Negation rule (!pattern) un-ignores
                        ignored_state = False
                except ValueError:
                    continue

        return ignored_state

    def walk(self, pattern: str = "*", raise_on_limit: bool = True) -> Iterator[Path]:
        """
        Walk workspace and yield non-ignored file paths.
        Applies directory pruning, pattern filtering, and the max_files hard cap.
        
        Args:
            pattern: Glob pattern to filter files (e.g. '*.py')
            raise_on_limit: If True, raises WorkspaceSizeError when exceeding max_files;
                            if False, stops yielding and terminates cleanly.
        """
        if not self.root.exists():
            return

        count = 0

        for dirpath_str, dirnames, filenames in os.walk(self.root):
            dirpath = Path(dirpath_str)

            # Prune directories in-place
            i = 0
            while i < len(dirnames):
                sub_dir = dirpath / dirnames[i]
                if self.is_ignored(sub_dir, is_dir=True):
                    del dirnames[i]
                else:
                    i += 1

            for filename in filenames:
                file_path = dirpath / filename

                if pattern != "*" and not file_path.match(pattern):
                    continue

                if self.is_ignored(file_path, is_dir=False):
                    continue

                count += 1
                if self.max_files is not None and count > self.max_files:
                    if raise_on_limit:
                        raise WorkspaceSizeError(
                            f"Workspace traversal exceeded safety limit of {self.max_files} files "
                            f"in '{self.root}'. Use a more specific search pattern or explicit file list."
                        )
                    return

                yield file_path

    def walk_files(self, pattern: str = "*", raise_on_limit: bool = True) -> list[Path]:
        """Convenience method returning a sorted list of all non-ignored file paths."""
        return sorted(list(self.walk(pattern=pattern, raise_on_limit=raise_on_limit)))
