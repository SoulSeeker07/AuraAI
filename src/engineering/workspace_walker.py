import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import pathspec

logger = logging.getLogger(__name__)


class WorkspaceSizeError(Exception):
    """Raised when repository discovery exceeds the max_files safety cap."""


class BoundaryEscapeError(Exception):
    """Raised when a path explicitly breaks the workspace boundary."""


@dataclass
class WorkspaceScope:
    """Structured scope information returned by the workspace walker."""
    files: list[Path]
    ignored_count: int = 0
    excluded_count: int = 0
    explicit_count: int = 0
    truncated: bool = False
    max_files: int | None = None
    source: str = ""


class WorkspaceFileWalker:
    """
    Unified repository-walking component that centralizes boundary enforcement
    and ignore-pattern handling across the Aura coding agent.
    """

    # Built-in exclusions that apply to all workspaces
    BUILTIN_EXCLUSIONS = {
        ".git",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".idea",
        ".vscode",
        "dist",
        "build",
        ".tox",
    }

    def __init__(self, repository_path: Path, max_files: int | None = 2000):
        self.repository_path = Path(repository_path).resolve()
        self.max_files = max_files
        self._ignore_spec: pathspec.PathSpec | None = None
        self._build_ignore_spec()

    def _build_ignore_spec(self):
        """Build the combined pathspec from .gitignore and .auraignore."""
        patterns = []
        
        # Load root .gitignore
        gitignore_path = self.repository_path / ".gitignore"
        if gitignore_path.is_file():
            try:
                with open(gitignore_path, "r", encoding="utf-8") as f:
                    patterns.extend(f.readlines())
            except Exception as e:
                logger.warning(f"Failed to read root .gitignore: {e}")

        # Load root .auraignore (additive)
        auraignore_path = self.repository_path / ".auraignore"
        if auraignore_path.is_file():
            try:
                with open(auraignore_path, "r", encoding="utf-8") as f:
                    patterns.extend(f.readlines())
            except Exception as e:
                logger.warning(f"Failed to read root .auraignore: {e}")
        
        if patterns:
            self._ignore_spec = pathspec.PathSpec.from_lines("gitignore", patterns)

    def _is_safe(self, path: Path) -> bool:
        """Check if path is inside the workspace boundary."""
        try:
            path.resolve().relative_to(self.repository_path)
            return True
        except ValueError:
            return False

    def _is_builtin_excluded(self, path: Path) -> bool:
        """Check if path is in built-in exclusions."""
        for part in path.parts:
            if part in self.BUILTIN_EXCLUSIONS:
                return True
        return False

    def _is_ignored(self, path: Path) -> bool:
        """Check if path matches root ignore spec."""
        if not self._ignore_spec:
            return False
        
        try:
            rel_path = path.relative_to(self.repository_path)
        except ValueError:
            return False
            
        posix_path = rel_path.as_posix()
        if path.is_dir() and not posix_path.endswith("/"):
            posix_path += "/"
            
        return self._ignore_spec.match_file(posix_path)

    def validate_explicit_targets(self, target_files: list[str | Path]) -> list[Path]:
        """Validate explicit targets against boundaries."""
        valid_targets = []
        for target in target_files:
            target_path = Path(target)
            if not target_path.is_absolute():
                target_path = (self.repository_path / target_path)
            
            target_path = target_path.resolve()
            
            if not self._is_safe(target_path):
                raise BoundaryEscapeError(
                    f"Target file {target_path} escapes workspace boundary {self.repository_path}"
                )
            
            if target_path.is_file():
                valid_targets.append(target_path)
        return valid_targets

    def walk(
        self, 
        pattern: str = "*", 
        target_files: list[str | Path] | None = None
    ) -> WorkspaceScope:
        """
        Walk the workspace to find files, applying safety boundaries and ignore rules.
        """
        scope = WorkspaceScope(
            files=[],
            max_files=self.max_files,
            source="explicit targets" if target_files else "repository discovery"
        )
        
        # 1. Handle Explicit Targets
        if target_files:
            valid_targets = self.validate_explicit_targets(target_files)
            
            for target in valid_targets:
                if target.match(pattern) or pattern == "*":
                    scope.files.append(target)
                    scope.explicit_count += 1
            
            scope.files.sort()
            return scope
            
        # 2. Unbounded Discovery
        
        # Helper for nested gitignores
        def matches_any_ignore(p: Path) -> bool:
            if self._is_builtin_excluded(p):
                return True
            if self._is_ignored(p):
                return True
                
            curr = p.parent
            while curr != self.repository_path and self._is_safe(curr):
                nested_ignore = curr / ".gitignore"
                if nested_ignore.is_file():
                    try:
                        with open(nested_ignore, "r", encoding="utf-8") as f:
                            spec = pathspec.PathSpec.from_lines("gitignore", f.readlines())
                            rel_to_nested = p.relative_to(curr).as_posix()
                            if p.is_dir() and not rel_to_nested.endswith("/"):
                                rel_to_nested += "/"
                            if spec.match_file(rel_to_nested):
                                return True
                    except Exception:
                        pass
                curr = curr.parent
            return False

        discovered_files = []
        count = 0
        
        for dirpath_str, dirnames, filenames in os.walk(self.repository_path):
            dirpath = Path(dirpath_str)
            
            # Prune directories
            i = 0
            while i < len(dirnames):
                d_path = dirpath / dirnames[i]
                if self._is_builtin_excluded(d_path):
                    scope.excluded_count += 1
                    del dirnames[i]
                elif matches_any_ignore(d_path):
                    scope.ignored_count += 1
                    del dirnames[i]
                else:
                    i += 1
                    
            for filename in filenames:
                file_path = dirpath / filename
                
                if pattern != "*" and not file_path.match(pattern):
                    continue
                    
                if self._is_builtin_excluded(file_path):
                    scope.excluded_count += 1
                    continue
                    
                if matches_any_ignore(file_path):
                    scope.ignored_count += 1
                    continue
                    
                discovered_files.append(file_path)
                count += 1
                
                if self.max_files is not None and count > self.max_files:
                    scope.truncated = True
                    raise WorkspaceSizeError(
                        f"Repository discovery exceeded {self.max_files} files limit. "
                        f"Found {count}+ files before stopping. "
                        f"Target explicit files to avoid unbounded traversal."
                    )
                    
        scope.files = sorted(discovered_files)
        return scope
