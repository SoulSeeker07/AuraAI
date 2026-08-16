"""
Engineering Workspace Walker Adapter

Bridges the shared WorkspaceWalker from workspace.workspace_walker
into the engineering subsystem, preserving the WorkspaceFileWalker and WorkspaceScope
contracts for engineering components.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from workspace.workspace_walker import (
    BoundaryEscapeError,
    WorkspaceSizeError,
    WorkspaceWalker,
)

logger = logging.getLogger(__name__)


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
    Engineering-level workspace walker adapter.
    Delegates ignore parsing, nested .gitignore evaluation, and directory traversal
    to the shared WorkspaceWalker in src.workspace.workspace_walker.
    """

    def __init__(self, repository_path: Path, max_files: int | None = 2000):
        self.repository_path: Path = Path(repository_path).resolve()
        self.max_files: int | None = max_files
        self._walker = WorkspaceWalker(
            root=self.repository_path,
            respect_gitignore=True,
            max_files=self.max_files,
        )

    def _is_safe(self, path: Path) -> bool:
        """Check if path is inside the workspace boundary."""
        return self._walker._is_safe(path)

    def _is_builtin_excluded(self, path: Path) -> bool:
        """Check if path is in built-in exclusions."""
        return self._walker._is_builtin_ignored(path)

    def _is_ignored(self, path: Path) -> bool:
        """Point-check whether a single path is ignored."""
        try:
            return self._walker.is_ignored(path)
        except BoundaryEscapeError:
            return True

    def validate_explicit_targets(self, target_files: list[str | Path]) -> list[Path]:
        """
        Validate explicit targets against workspace boundary and built-in denylist.
        Explicit targets can override project .gitignore patterns, but can NEVER
        target hard built-in exclusions (.git, .venv, node_modules, __pycache__, etc.).
        """
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
            
            if self._is_builtin_excluded(target_path):
                raise BoundaryEscapeError(
                    f"Target file {target_path} is in built-in exclusion denylist and cannot be targeted."
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
            
        # 2. Unbounded Discovery using shared WorkspaceWalker
        try:
            discovered = self._walker.walk_files(pattern=pattern)
            scope.files = discovered
            return scope
        except WorkspaceSizeError as e:
            raise WorkspaceSizeError(
                f"Repository discovery exceeded {self.max_files} files limit. "
                f"Target explicit files to avoid unbounded traversal."
            ) from e
