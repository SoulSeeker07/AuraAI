"""
Workspace Policy & Single-Write Gate
Location: src/engineering/workspace_policy.py

Authoritative write-authorization backstop for the Autonomous Engineering Platform.
Enforces workspace containment, protected-file ceiling hard-blocks, and test-file immunity.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    from core.orchestration.request_source import RequestSource
except (ImportError, ModuleNotFoundError):
    from src.core.orchestration.request_source import RequestSource

from .safety_ceiling import (
    ProtectedCeilingViolation,
    RewardHackingViolation,
    is_path_protected,
    is_test_file,
    normalize_relative_path,
)


class WorkspaceTraversalError(Exception):
    """Raised when an edit path escapes the workspace root."""
    pass


class WorkspacePolicy:
    """
    Authoritative single-write gate for file system modifications across
    both autonomous and human-initiated engineering operations.
    """

    def __init__(self, repo_root: str | Path | None = None):
        self.repo_root = Path(repo_root or os.getcwd()).resolve()

    def validate_containment(self, target_path: str | Path) -> Path:
        """
        Validate that the target path resides strictly inside repo_root.
        Prevents directory traversal attacks ('../').
        """
        raw_target = Path(target_path)
        if not raw_target.is_absolute():
            resolved = (self.repo_root / raw_target).resolve()
        else:
            resolved = raw_target.resolve()

        try:
            resolved.relative_to(self.repo_root)
        except ValueError:
            raise WorkspaceTraversalError(
                f"Path traversal blocked: '{target_path}' resolves outside repo root '{self.repo_root}'"
            )
        return resolved

    def authorize_write(
        self,
        target_path: str | Path,
        source: RequestSource = RequestSource.DAEMON_BACKGROUND,
        task_type: str = "BUG_FIX",
        is_new_file: bool = False,
    ) -> Path:
        """
        Authoritative write authorization gate.
        
        Rules:
        1. Must not escape repo_root (traversal check).
        2. If source is non-interactive (DAEMON_BACKGROUND, TRIGGER_AUTONOMOUS, AGENT_DELEGATED):
           a. Target must NOT match PROTECTED_SAFETY_CEILING -> ProtectedCeilingViolation.
           b. Target must NOT match TEST_FILE_PATTERNS unless task_type == 'ADD_TEST' and is_new_file == True
              -> RewardHackingViolation.
        
        Returns:
            Resolved Path if write is authorized.
        """
        resolved = self.validate_containment(target_path)
        rel_path = normalize_relative_path(resolved, self.repo_root)

        # Interactive human turns bypass ceiling and test immunity with explicit intention
        if source == RequestSource.HUMAN_INTERACTIVE:
            return resolved

        # Non-interactive / autonomous checks
        if is_path_protected(rel_path, self.repo_root):
            raise ProtectedCeilingViolation(
                f"Autonomous write to protected safety-ceiling path is blocked: '{rel_path}'"
            )

        if is_test_file(rel_path, self.repo_root):
            # Only net-new test files under an explicit ADD_TEST task type are allowed autonomously
            if not (task_type.upper() == "ADD_TEST" and is_new_file):
                raise RewardHackingViolation(
                    f"Autonomous edit to test file or fixture is blocked by Test-File Immunity: '{rel_path}'"
                )

        return resolved


__all__ = [
    "WorkspacePolicy",
    "WorkspaceTraversalError",
]
