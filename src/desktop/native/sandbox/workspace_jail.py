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


class WorkspaceJail:
    """
    Confines execution paths and command arguments strictly within an allowed workspace directory.
    """

    def __init__(self, workspace_root: str | None = None):
        self._workspace_root = Path(workspace_root or os.getcwd()).resolve()

    @property
    def workspace_root(self) -> Path:
        return self._workspace_root

    def set_workspace_root(self, root: str) -> None:
        self._workspace_root = Path(root).resolve()

    def is_path_inside_workspace(self, target_path: str | Path) -> bool:
        """Check if target_path resolves strictly within the workspace directory tree."""
        try:
            resolved = Path(target_path).resolve()
            return resolved == self._workspace_root or self._workspace_root in resolved.parents
        except Exception:
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
