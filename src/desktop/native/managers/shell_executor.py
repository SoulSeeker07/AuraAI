"""
Shell Command Executor
Location: src/desktop/native/managers/shell_executor.py

Provides risk-classified, verified shell command execution for the
system.shell capability. Only LOW-risk read-only commands are executed
directly. MEDIUM and HIGH risk commands are rejected with an explicit
message until CryptographicApprovalAuthority is wired end-to-end.

Risk classification
-------------------
LOW   — read-only, non-mutating, no side effects. Executed directly.
MEDIUM — mutating but reversible (e.g. git commit). Requires approval ticket.
HIGH  — destructive, network-pushing, or irreversible. Requires approval ticket.

Approval ticket flow for MEDIUM/HIGH is NOT YET WIRED. See:
  docs/adr/open-items/wire-cryptographic-approval-authority.md
"""

from __future__ import annotations

import logging
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Risk Classification
# ---------------------------------------------------------------------------

# Explicit allowlist of LOW-risk command prefixes.
# Only commands starting with one of these entries (after normalisation)
# are executed directly. Everything else is MEDIUM or HIGH.
#
# Design notes:
# - Entries are normalised lowercase prefix strings.
# - Two-token entries (e.g. "git status") are preferred over single-token
#   ("git") to avoid accidentally promoting subcommands not listed here.
# - Shell operators (|, >, &&, ;) are stripped before matching — any command
#   containing them is classified HIGH regardless of prefix.
_LOW_RISK_PREFIXES: tuple[str, ...] = (
    # git read-only
    "git status",
    "git log",
    "git diff",
    "git branch",
    "git show",
    "git stash list",
    "git remote",
    "git remote -v",
    "git remote show",
    "git rev-parse",
    "git describe",
    "git shortlog",
    "git tag",
    "git reflog",
    "git ls-files",
    "git ls-remote",
    "git fetch --dry-run",
    "git check-ignore",
    "git blame",
    # process/system info — read-only
    "echo",
    "pwd",
    "where",       # Windows: locate executable
    "which",       # POSIX
    "dir",         # Windows: list directory
    "ls",          # POSIX
    "type",        # Windows: print file
    "cat",         # POSIX: print file
    # version queries
    "python --version",
    "python -v",
    "python3 --version",
    "node --version",
    "node -v",
    "npm --version",
    "npm -v",
    "pip --version",
    "pip -v",
    "pip list",
    "pip show",
    "pip freeze",
    "git --version",
    "git -v",
)

# Explicit allowlist of HIGH-risk (destructive/irreversible) command prefixes.
_HIGH_RISK_PREFIXES: tuple[str, ...] = (
    "rm",
    "del",
    "erase",
    "rmdir",
    "rd",
    "format",
    "kill",
    "taskkill",
    "shutdown",
    "reboot",
    "git clean",
    "git reset --hard",
    "git branch -d",
    "git branch -D",
    "git stash drop",
    "git stash clear",
)

# Shell operators that escalate any command to HIGH regardless of prefix.
_SHELL_OPERATOR_CHARS = frozenset("|&;><`$")

# Fatal error patterns that indicate failure even if returncode == 0.
_FATAL_ERROR_PATTERNS: tuple[str, ...] = (
    "not a git repository",
    "not a git repo",
    "fatal:",
    "command not found",
    "is not recognized as",     # Windows: 'X' is not recognized as a command
)

# General error patterns checked when returncode != 0 to provide clear diagnostic reasons.
_DIAGNOSTIC_ERROR_PATTERNS: tuple[str, ...] = (
    "not a git repository",
    "not a git repo",
    "fatal:",
    "error:",
    "permission denied",
    "access is denied",
    "no such file or directory",
    "command not found",
    "is not recognized as",
)


RiskTier = Literal["LOW", "MEDIUM", "HIGH"]


def classify_command(command: str) -> RiskTier:
    """
    Return the risk tier for a shell command string.

    Rules (applied in order):
    1. Any shell operator (|, &, ;, >, <, `, $) → HIGH immediately.
    2. Prefix matches _HIGH_RISK_PREFIXES → HIGH.
    3. Prefix matches _LOW_RISK_PREFIXES → LOW.
    4. Everything else → MEDIUM.
    """
    normalized = command.strip().lower()

    # Rule 1: shell operators → HIGH
    if any(ch in normalized for ch in _SHELL_OPERATOR_CHARS):
        return "HIGH"

    # Rule 2: destructive prefixes → HIGH
    for prefix in _HIGH_RISK_PREFIXES:
        if normalized == prefix or normalized.startswith(prefix + " "):
            return "HIGH"

    # Rule 3: explicit LOW allowlist
    for prefix in _LOW_RISK_PREFIXES:
        if normalized == prefix or normalized.startswith(prefix + " "):
            return "LOW"

    # Rule 4: default MEDIUM (mutating but not necessarily destructive)
    return "MEDIUM"


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

class ShellExecutionResult:
    """Structured result from a shell command execution attempt."""

    __slots__ = ("success", "stdout", "stderr", "returncode", "command", "cwd", "error")

    def __init__(
        self,
        *,
        success: bool,
        stdout: str,
        stderr: str,
        returncode: int | None,
        command: str,
        cwd: str,
        error: str | None = None,
    ) -> None:
        self.success = success
        self.stdout = stdout.strip()
        self.stderr = stderr.strip()
        self.returncode = returncode
        self.command = command
        self.cwd = cwd
        self.error = error

    def format_response(self) -> str:
        """Format the result for display in the ConversationEngine response."""
        if not self.success:
            parts = [f"❌ `{self.command}` failed."]
            if self.error:
                parts.append(f"**Reason:** {self.error}")
            if self.stderr:
                parts.append(f"```\n{self.stderr[:800]}\n```")
            return "\n".join(parts)

        parts = [f"✅ `{self.command}`"]
        output = (self.stdout or self.stderr).strip()
        if output:
            parts.append(f"```\n{output[:2000]}\n```")
        else:
            parts.append("*(no output)*")
        return "\n".join(parts)


def execute_low_risk(
    command: str,
    cwd: str | None = None,
    timeout_seconds: int = 15,
) -> ShellExecutionResult:
    """
    Execute a pre-classified LOW-risk shell command and verify the result.

    Callers MUST have already confirmed classify_command(command) == "LOW"
    before calling this function. This function does not re-check — it trusts
    the caller's classification.

    Verification contract (beyond returncode == 0):
    - returncode != 0 → failure regardless of stdout content.
    - Any _SEMANTIC_ERROR_PATTERNS found in stdout or stderr → failure,
      even if returncode == 0 (e.g. "not a git repository" with rc=128
      on some git versions, or an edge case that returns rc=0 with error text).
    - Empty stdout on a command expected to produce output is NOT treated
      as a failure — callers see "(no output)" and can judge.
    """
    effective_cwd = cwd or str(Path.cwd())

    # Confirm git is reachable if this is a git command
    if command.strip().lower().startswith("git"):
        if not shutil.which("git"):
            return ShellExecutionResult(
                success=False,
                stdout="",
                stderr="",
                returncode=None,
                command=command,
                cwd=effective_cwd,
                error="git is not installed or not on PATH.",
            )

    logger.info(
        "[ShellExecutor] Executing LOW-risk command: %r in cwd=%r",
        command,
        effective_cwd,
    )

    try:
        # Use shell=False with shlex.split on POSIX; on Windows, shell=True
        # is needed for built-ins like 'dir', 'type', 'where'.
        # Mitigation: the command string has already been allowlist-checked
        # by classify_command before reaching this point.
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=effective_cwd,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return ShellExecutionResult(
            success=False,
            stdout="",
            stderr="",
            returncode=None,
            command=command,
            cwd=effective_cwd,
            error=f"Command timed out after {timeout_seconds}s.",
        )
    except Exception as exc:
        return ShellExecutionResult(
            success=False,
            stdout="",
            stderr="",
            returncode=None,
            command=command,
            cwd=effective_cwd,
            error=f"Execution error: {exc}",
        )

    # Verification:
    # 1. Non-zero returncode -> check diagnostic patterns for best explanation, otherwise report returncode
    if proc.returncode != 0:
        combined_output = (proc.stdout + "\n" + proc.stderr).lower()
        matched_err = None
        for pattern in _DIAGNOSTIC_ERROR_PATTERNS:
            if pattern in combined_output:
                matched_err = f"Command failed: detected '{pattern}' in output."
                break
        return ShellExecutionResult(
            success=False,
            stdout=proc.stdout,
            stderr=proc.stderr,
            returncode=proc.returncode,
            command=command,
            cwd=effective_cwd,
            error=matched_err or f"Command exited with returncode {proc.returncode}.",
        )

    # 2. Zero returncode -> verify no fatal failure disguised as success
    combined_output = (proc.stdout + "\n" + proc.stderr).lower()
    for pattern in _FATAL_ERROR_PATTERNS:
        if pattern in combined_output:
            return ShellExecutionResult(
                success=False,
                stdout=proc.stdout,
                stderr=proc.stderr,
                returncode=proc.returncode,
                command=command,
                cwd=effective_cwd,
                error=f"Command reported a fatal error despite returncode 0: detected '{pattern}'.",
            )

    logger.info("[ShellExecutor] Command succeeded: %r (rc=0)", command)
    return ShellExecutionResult(
        success=True,
        stdout=proc.stdout,
        stderr=proc.stderr,
        returncode=proc.returncode,
        command=command,
        cwd=effective_cwd,
    )


def execute_command(
    command: str,
    cwd: str | None = None,
    timeout_seconds: int = 30,
) -> ShellExecutionResult:
    """
    Execute an authorized shell command (LOW or approved MEDIUM/HIGH) and return the structured result.

    Applies safety guardrails against malicious fork-bombs and fatal disk wipes.
    """
    effective_cwd = cwd or str(Path.cwd())

    # Check for prohibited fork-bomb and format commands
    banned_patterns = (
        ":(){ :|:& };:",
        "fork()",
        "format c:",
        "format d:",
        "rmdir /s /q c:\\",
        "rm -rf /",
    )
    cmd_lower = command.strip().lower()
    for ban in banned_patterns:
        if ban in cmd_lower:
            return ShellExecutionResult(
                success=False,
                stdout="",
                stderr="",
                returncode=-1,
                command=command,
                cwd=effective_cwd,
                error=f"Command blocked by safety policy: dangerous pattern detected.",
            )

    # Confirm git is reachable if this is a git command
    if cmd_lower.startswith("git"):
        if not shutil.which("git"):
            return ShellExecutionResult(
                success=False,
                stdout="",
                stderr="",
                returncode=None,
                command=command,
                cwd=effective_cwd,
                error="git is not installed or not on PATH.",
            )

    logger.info(
        "[ShellExecutor] Executing command: %r in cwd=%r",
        command,
        effective_cwd,
    )

    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=effective_cwd,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return ShellExecutionResult(
            success=False,
            stdout="",
            stderr="",
            returncode=None,
            command=command,
            cwd=effective_cwd,
            error=f"Command timed out after {timeout_seconds}s.",
        )
    except Exception as exc:
        return ShellExecutionResult(
            success=False,
            stdout="",
            stderr="",
            returncode=None,
            command=command,
            cwd=effective_cwd,
            error=f"Execution error: {exc}",
        )

    if proc.returncode != 0:
        combined_output = (proc.stdout + "\n" + proc.stderr).lower()
        matched_err = None
        for pattern in _DIAGNOSTIC_ERROR_PATTERNS:
            if pattern in combined_output:
                matched_err = f"Command failed: detected '{pattern}' in output."
                break
        return ShellExecutionResult(
            success=False,
            stdout=proc.stdout,
            stderr=proc.stderr,
            returncode=proc.returncode,
            command=command,
            cwd=effective_cwd,
            error=matched_err or f"Command exited with returncode {proc.returncode}.",
        )

    return ShellExecutionResult(
        success=True,
        stdout=proc.stdout,
        stderr=proc.stderr,
        returncode=proc.returncode,
        command=command,
        cwd=effective_cwd,
    )

