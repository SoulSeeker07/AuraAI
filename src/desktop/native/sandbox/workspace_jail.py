"""
Workspace Jail & Path Boundary Enforcer
Location: src/desktop/native/sandbox/workspace_jail.py

Enforces workspace boundary confinement on file operations and command arguments.
Detects traversal tricks and unauthorized absolute path access to sensitive host directories.
"""

import os
import re
from pathlib import Path
from typing import Any


from collections.abc import Iterable
import logging

logger = logging.getLogger(__name__)


class WorkspaceJail:
    """
    Confines execution paths and command arguments strictly within allowed workspace directories.
    """

    # Path segments that stay strictly blocked inside allowed roots (credentials, private keys, cloud tokens, appdata, git metadata in external roots)
    _BLOCKED_SEGMENTS = frozenset({
        ".ssh", ".aws", ".gnupg", ".azure", ".kube", ".docker",
        ".git", ".npmrc", ".netrc", "appdata",
    })

    def __init__(
        self,
        workspace_root: str | None = None,
        allowed_roots: Iterable[str | Path] | None = None,
    ):
        self._workspace_root = Path(workspace_root or os.getcwd()).resolve()
        roots = {self._workspace_root}
        if allowed_roots:
            roots.update(Path(r).resolve() for r in allowed_roots)
        self._allowed_roots: set[Path] = roots

    @property
    def workspace_root(self) -> Path:
        return self._workspace_root

    @property
    def allowed_roots(self) -> frozenset[Path]:
        return frozenset(self._allowed_roots)

    def set_workspace_root(self, root: str) -> None:
        self._workspace_root = Path(root).resolve()
        self._allowed_roots.add(self._workspace_root)

    def add_allowed_root(self, root: str | Path) -> None:
        """Grant access to an additional directory root. Fails eagerly if root does not exist."""
        resolved = Path(root).resolve()
        if not resolved.exists():
            raise ValueError(f"Cannot allow-list nonexistent root: {resolved}")
        logger.info(f"WorkspaceJail: granting access to additional root: {resolved}")
        self._allowed_roots.add(resolved)

    def _is_blocked_segment(self, resolved: Path, root: Path) -> bool:
        """Check if relative path from root contains any forbidden credential or system configuration segment."""
        try:
            rel_parts = resolved.relative_to(root).parts
        except Exception:
            return True
        # In the primary workspace root, allow .git (project version control), while keeping all other credential segments blocked
        blocked = (
            (self._BLOCKED_SEGMENTS - {".git"})
            if root == self._workspace_root
            else self._BLOCKED_SEGMENTS
        )
        return any(part.lower() in blocked for part in rel_parts)

    def is_path_inside_workspace(self, target_path: str | Path) -> bool:
        """Check if target_path resolves strictly within any allowed workspace root and contains no blocked segments."""
        try:
            resolved = Path(target_path).resolve()
        except Exception:
            return False

        for root in self._allowed_roots:
            if resolved == root or root in resolved.parents:
                if not self._is_blocked_segment(resolved, root):
                    return True

        return False

    def validate_command_paths(self, command: str, cwd: str) -> tuple[bool, str]:
        """
        Inspect command string for out-of-workspace absolute or relative file access.
        
        Returns:
            (is_valid, error_message)
        """
        active_cwd = Path(cwd).resolve()

        # 1. Verify working directory is within workspace
        if not self.is_path_inside_workspace(active_cwd):
            return False, f"Working directory '{active_cwd}' is outside allowed workspace root '{self._workspace_root}'"

        # 2. Extract potential file path tokens (absolute Windows paths or ~ paths)
        # Matches paths like C:\..., D:/..., ~/.ssh/..., %USERPROFILE%\...
        path_patterns = [
            r"\b[A-Za-z]:[/\\][^\s\"';|&<>]+",
            r"~[/\\][^\s\"';|&<>]+",
            r"%[A-Za-z0-9_]+%[/\\][^\s\"';|&<>]+",
            r"\$env:[A-Za-z0-9_]+[/\\][^\s\"';|&<>]+",
        ]

        for pattern in path_patterns:
            for match in re.finditer(pattern, command, re.I):
                raw_path = match.group(0)
                # Expand ~ or environment variables
                expanded = os.path.expanduser(os.path.expandvars(raw_path))
                # If path contains $env:
                if "$env:" in expanded.lower():
                    var_name = re.search(r"\$env:([A-Za-z0-9_]+)", expanded, re.I)
                    if var_name:
                        var_val = os.environ.get(var_name.group(1), "")
                        expanded = re.sub(r"\$env:[A-Za-z0-9_]+", var_val, expanded, flags=re.I)

                try:
                    resolved = Path(expanded).resolve()
                    # If this is an existing file or directory on the host, it must be inside the workspace
                    if resolved.exists():
                        if not self.is_path_inside_workspace(resolved):
                            return False, f"Access to host path '{resolved}' outside workspace root is blocked."
                except Exception:
                    continue

        return True, "All command paths are valid within workspace."
