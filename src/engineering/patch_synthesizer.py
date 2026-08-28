"""
Patch Synthesizer & Test Immunity Engine
Location: src/engineering/patch_synthesizer.py

Synthesizes AST-verified candidate code patches, generates unified diffs,
and strictly enforces Protected Ceiling and Test-File Immunity rules via WorkspacePolicy.
"""

from __future__ import annotations

import ast
import difflib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from core.orchestration.request_source import RequestSource
except (ImportError, ModuleNotFoundError):
    from core.orchestration.request_source import RequestSource

from .safety_ceiling import (
    ProtectedCeilingViolation,
    RewardHackingViolation,
    is_path_protected,
    is_test_file,
    normalize_relative_path,
)
from .workspace_policy import WorkspacePolicy, WorkspaceTraversalError


@dataclass
class CodePatch:
    """Represents a validated code modification to be applied to a file."""
    file_path: str
    original_content: str
    new_content: str
    diff_text: str
    is_new_file: bool = False
    start_line: int | None = None
    end_line: int | None = None


@dataclass
class PatchSynthesisResult:
    """Outcome of patch synthesis."""
    success: bool
    patches: list[CodePatch] = field(default_factory=list)
    error_message: str | None = None
    violation_type: str | None = None


class PatchSynthesizer:
    """
    Synthesizes and validates candidate patches with strict syntax validation
    and single-write gate policy authorization.
    """

    def __init__(self, repo_root: str | Path | None = None):
        self.repo_root = Path(repo_root or os.getcwd()).resolve()
        self.policy = WorkspacePolicy(repo_root=self.repo_root)

    def synthesize_file_patch(
        self,
        target_file: str | Path,
        new_content: str,
        task_type: str = "BUG_FIX",
        is_new_file: bool = False,
        source: RequestSource = RequestSource.DAEMON_BACKGROUND,
    ) -> CodePatch:
        """
        Validate and assemble a single file patch.
        Enforces syntax validity, path containment, safety ceiling, and test immunity.
        """
        # 1. Authoritative write-gate check (raises Traversal, ProtectedCeiling, or RewardHacking)
        abs_path = self.policy.authorize_write(
            target_path=target_file,
            source=source,
            task_type=task_type,
            is_new_file=is_new_file,
        )
        rel_path = normalize_relative_path(abs_path, self.repo_root)

        # 2. Syntax validation for Python files
        if rel_path.endswith(".py"):
            try:
                ast.parse(new_content, filename=rel_path)
            except SyntaxError as syn_err:
                raise SyntaxError(
                    f"Synthesized code for '{rel_path}' is syntactically invalid: {syn_err}"
                ) from syn_err

        # 3. Read original content
        original_content = ""
        if abs_path.exists() and abs_path.is_file() and not is_new_file:
            original_content = abs_path.read_text(encoding="utf-8", errors="replace")

        # 4. Generate unified diff
        diff_lines = list(
            difflib.unified_diff(
                original_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{rel_path}",
                tofile=f"b/{rel_path}",
            )
        )
        diff_text = "".join(diff_lines)

        return CodePatch(
            file_path=rel_path,
            original_content=original_content,
            new_content=new_content,
            diff_text=diff_text,
            is_new_file=is_new_file or not abs_path.exists(),
        )

    def apply_patch(
        self,
        patch: CodePatch,
        source: RequestSource = RequestSource.DAEMON_BACKGROUND,
    ) -> Path:
        """
        Write validated patch content to disk with authoritative write-gate re-verification.
        Ensures the physical disk modification itself is unconditionally checked against WorkspacePolicy.
        """
        target = self.policy.authorize_write(
            target_path=patch.file_path,
            source=source,
            task_type="ADD_TEST" if patch.is_new_file and is_test_file(patch.file_path, self.repo_root) else "BUG_FIX",
            is_new_file=patch.is_new_file,
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(patch.new_content, encoding="utf-8")
        return target


__all__ = [
    "CodePatch",
    "PatchSynthesisResult",
    "PatchSynthesizer",
]
