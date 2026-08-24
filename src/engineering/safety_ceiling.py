"""
Safety Ceiling & Protected Path Registry
Location: src/engineering/safety_ceiling.py

Enforces the self-modification safety ceiling for Autonomous Engineering loops.
Unconditionally blocks autonomous tasks from modifying security-critical,
orchestration, policy, write-gate, and test-configuration files.
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Iterable


class ProtectedCeilingViolation(Exception):
    """Raised when an autonomous task attempts to modify a protected safety-critical file."""
    pass


class RewardHackingViolation(Exception):
    """Raised when an autonomous patch modifies test assertions to artificially pass tests."""
    pass


# Normalized path patterns (forward-slash, relative to repo root)
PROTECTED_SAFETY_CEILING_PATTERNS: tuple[str, ...] = (
    "src/core/orchestration/execution_policy.py",
    "src/core/orchestration/master_orchestrator.py",
    "src/core/orchestration/request_source.py",
    "src/autonomy/trigger_scheduler.py",
    "src/daemon/governance.py",
    "src/desktop/native/security/*",
    "src/desktop/native/security/**/*",
    "src/security/*",
    "src/security/**/*",
    "src/engineering/workspace_policy.py",
    "src/engineering/safety_ceiling.py",
    "core/aura_core.py",
    "AGENTS.md",
    "docs/SYSTEM_CONTRACT.md",
    "docs/technical_debt.md",
    "conftest.py",
    "*/conftest.py",
    "**/*/conftest.py",
    "pytest.ini",
    "*/pytest.ini",
    "**/*/pytest.ini",
    "pyproject.toml",
    "*/pyproject.toml",
    "**/*/pyproject.toml",
    "*.env*",
    "**/*.env*",
    "*.pem",
    "**/*.pem",
    "*.key",
    "**/*.key",
    "*.secret*",
    "**/*.secret*",
)

TEST_FILE_PATTERNS: tuple[str, ...] = (
    "tests/*",
    "tests/**/*",
    "test_*.py",
    "*/test_*.py",
    "**/*/test_*.py",
    "*_test.py",
    "*/*_test.py",
    "**/*/*_test.py",
    "conftest.py",
    "*/conftest.py",
    "**/*/conftest.py",
    "pytest.ini",
    "*/pytest.ini",
    "**/*/pytest.ini",
    "pyproject.toml",
    "*/pyproject.toml",
    "**/*/pyproject.toml",
)


def normalize_relative_path(path: str | Path, repo_root: str | Path | None = None) -> str:
    """
    Normalize path to relative forward-slash canonical representation.
    Handles Windows drive-letter case normalization and collapses '..' traversal segments.
    """
    raw_p = Path(path)
    if repo_root:
        root = Path(repo_root).resolve()
        if raw_p.is_absolute():
            resolved = raw_p.resolve()
        else:
            resolved = (root / raw_p).resolve()
        
        try:
            rel = resolved.relative_to(root)
            return str(rel).replace("\\", "/")
        except ValueError:
            # Path is outside repo root; return forward-slash normalized string
            return str(resolved).replace("\\", "/")
    else:
        # Normalize redundant '.' and '..' segments
        norm = os.path.normpath(str(path)).replace("\\", "/")
        norm = norm.lstrip("/")
        while norm.startswith("./"):
            norm = norm[2:]
        return norm


def _matches_pattern(normalized_path: str, pattern: str) -> bool:
    """Evaluate pattern match supporting recursive wildcard prefix matching."""
    norm_p = normalized_path.lower()
    pat = pattern.lower()

    if pat.endswith("/**/*"):
        prefix = pat[:-5].rstrip("/")
        return norm_p.startswith(f"{prefix}/") or norm_p == prefix
    if pat.endswith("/*"):
        prefix = pat[:-2].rstrip("/")
        if norm_p.startswith(f"{prefix}/"):
            rel = norm_p[len(prefix) + 1:]
            return "/" not in rel
        return False
    if "**/" in pat:
        # Standard recursive wildcard match
        suffix = pat.split("**/")[-1]
        return fnmatch.fnmatch(norm_p, f"*{suffix}") or fnmatch.fnmatch(norm_p, suffix)
    
    return fnmatch.fnmatch(norm_p, pat) or norm_p == pat


def is_path_protected(path: str | Path, repo_root: str | Path | None = None) -> bool:
    """
    Check if a file path falls under the Protected-File Ceiling.
    Unconditionally returns True for safety-critical and policy files.
    """
    norm = normalize_relative_path(path, repo_root)
    for pattern in PROTECTED_SAFETY_CEILING_PATTERNS:
        if _matches_pattern(norm, pattern):
            return True
    return False


def is_test_file(path: str | Path, repo_root: str | Path | None = None) -> bool:
    """
    Check if a file is a test suite file, fixture, or test runner configuration.
    """
    norm = normalize_relative_path(path, repo_root)
    for pattern in TEST_FILE_PATTERNS:
        if _matches_pattern(norm, pattern):
            return True
    return False


__all__ = [
    "ProtectedCeilingViolation",
    "RewardHackingViolation",
    "PROTECTED_SAFETY_CEILING_PATTERNS",
    "TEST_FILE_PATTERNS",
    "normalize_relative_path",
    "is_path_protected",
    "is_test_file",
]
