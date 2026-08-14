"""
AgySubprocessClient — synchronous wrapper around the `agy` CLI binary.

Design constraints:
    - PLAN mode only. There is no code path to invoke `agy` in a mutating
      mode from this client. All file mutations still go through
      WorkspacePolicy + EngineeringManager.
    - Timeout + retry. run_plan() uses subprocess.run(timeout=...) so a
      hung `agy` process never blocks Aura indefinitely.
    - Retry is narrow. Only AgyTimeoutError and AgyParseError get one retry.
      AgyProcessError (non-zero exit) does not retry — that's almost always
      a bad prompt, not a transient blip.
    - dangerously_skip_permissions defaults to env var
      AURA_AGY_SKIP_PERMISSIONS (defaults True for local dev). Set to False
      in production / CI if you want the permission prompt to gate mutations.
"""

import json
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── Exceptions ─────────────────────────────────────────────────────────────────

class AgyError(Exception):
    """Base class for all AgySubprocessClient errors."""


class AgyNotFoundError(AgyError):
    """Raised when the `agy` binary is not found on PATH."""


class AgyProcessError(AgyError):
    """Raised when `agy` exits with a non-zero return code."""

    def __init__(self, returncode: int, stderr: str):
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"agy exited with code {returncode}: {stderr[:200]}")


class AgyTimeoutError(AgyError):
    """Raised when `agy` does not return within the configured timeout."""

    def __init__(self, timeout_s: float):
        self.timeout_s = timeout_s
        super().__init__(f"agy did not respond within {timeout_s}s")


class AgyParseError(AgyError):
    """Raised when agy's JSON output cannot be parsed or validated."""

    def __init__(self, reason: str, raw_text: str = ""):
        self.raw_text = raw_text
        super().__init__(f"Failed to parse agy output: {reason}")


# ── Mode enum ─────────────────────────────────────────────────────────────────

class AgyMode(str, Enum):
    """
    Only PLAN is exposed. There is deliberately no ACCEPT_EDITS variant —
    agy must never autonomously mutate files on Aura's behalf.
    """
    PLAN = "plan"


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class AgyPlanResult:
    """
    The structured result returned by AgySubprocessClient.run_plan().
    `raw` is the parsed JSON dict from agy's response field.
    """
    raw: dict[str, Any]
    conversation_id: str
    elapsed_s: float
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


# ── Config ────────────────────────────────────────────────────────────────────

@dataclass
class AgyConfig:
    """
    Configuration for AgySubprocessClient.

    agy_binary:
        Path or name of the `agy` executable. Defaults to 'agy' (resolved
        from PATH at call time).

    default_timeout_s:
        Hard kill timeout for the subprocess. Set a bit above your observed
        15-30s latency so legitimate long tasks aren't killed prematurely.

    max_attempts:
        Total attempts. Only AgyTimeoutError and AgyParseError trigger a
        retry; AgyProcessError does not.

    dangerously_skip_permissions:
        Maps to agy's --dangerously-skip-permissions flag. Reads from
        AURA_AGY_SKIP_PERMISSIONS env var (defaults to True for local dev).
        Set the env var to "0" or "false" to disable.

    output_format:
        Always "json" — we need structured output to parse plan results.
    """
    agy_binary: str = "agy"
    default_timeout_s: float = 45.0  # 15s above observed P95 of ~30s
    max_attempts: int = 2
    dangerously_skip_permissions: bool = field(
        default_factory=lambda: os.environ.get(
            "AURA_AGY_SKIP_PERMISSIONS", "true"
        ).lower() not in ("0", "false", "no")
    )
    output_format: str = "json"


# ── Client ────────────────────────────────────────────────────────────────────

class AgySubprocessClient:
    """
    Synchronous subprocess wrapper around the `agy` CLI.

    Usage:
        client = AgySubprocessClient(AgyConfig())
        result = client.run_plan(goal="...", add_dir="/path/to/repo")
        files = result.raw.get("files", [])

    Injected into CodingBackendAdapter via __init__(agy_client=...) so
    tests can pass a mock without shelling out to the real binary.
    """

    def __init__(self, config: AgyConfig | None = None):
        self.config = config or AgyConfig()
        self._binary: str | None = None  # lazily resolved

    def _resolve_binary(self) -> str:
        """Return the path to the `agy` binary, raising AgyNotFoundError if absent."""
        if self._binary:
            return self._binary
        resolved = shutil.which(self.config.agy_binary)
        if not resolved:
            raise AgyNotFoundError(
                f"'{self.config.agy_binary}' binary not found on PATH. "
                "Install Antigravity CLI and ensure it is on your PATH."
            )
        self._binary = resolved
        return resolved

    def _build_command(
        self,
        goal: str,
        add_dir: str | None,
        mode: AgyMode,
        json_schema: str | None,
    ) -> list[str]:
        binary = self._resolve_binary()
        cmd = [
            binary,
            "--print", goal,
            "--output-format", self.config.output_format,
            "--mode", mode.value,
        ]
        if self.config.dangerously_skip_permissions:
            cmd.append("--dangerously-skip-permissions")
        if add_dir:
            cmd += ["--add-dir", add_dir]
        if json_schema:
            cmd += ["--json-schema", json_schema]
        return cmd

    def run_plan(
        self,
        goal: str,
        add_dir: str | None = None,
        json_schema: str | None = None,
        timeout_s: float | None = None,
    ) -> AgyPlanResult:
        """
        Invoke `agy --print <goal> --mode plan --output-format json`.

        Returns:
            AgyPlanResult with the parsed JSON and timing metadata.

        Raises:
            AgyNotFoundError    — binary not on PATH
            AgyProcessError     — non-zero exit (not retried)
            AgyTimeoutError     — subprocess timed out (retried once)
            AgyParseError       — output not valid JSON / missing fields (retried once)
        """
        timeout = timeout_s or self.config.default_timeout_s
        cmd = self._build_command(goal, add_dir, AgyMode.PLAN, json_schema)
        last_error: AgyError | None = None

        for attempt in range(1, self.config.max_attempts + 1):
            if attempt > 1:
                logger.info("agy: retry attempt %d/%d", attempt, self.config.max_attempts)

            t0 = time.monotonic()
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                elapsed = time.monotonic() - t0
                logger.warning("agy subprocess timed out after %.1fs", elapsed)
                last_error = AgyTimeoutError(timeout)
                # Timeout is retryable — try again
                continue

            elapsed = time.monotonic() - t0
            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()

            if proc.returncode != 0:
                logger.error(
                    "agy exited %d after %.1fs. stderr: %s",
                    proc.returncode, elapsed, stderr[:400],
                )
                # Process error is NOT retried — bad prompt, not a transient blip
                raise AgyProcessError(proc.returncode, stderr)

            logger.debug("agy completed in %.1fs (%d chars)", elapsed, len(stdout))

            # Parse the outer envelope that --output-format json wraps around
            # agy's response:
            #   {"conversation_id": "...", "status": "SUCCESS", "response": "...", ...}
            try:
                envelope = json.loads(stdout)
            except json.JSONDecodeError as e:
                logger.warning("agy: outer envelope not valid JSON: %s", e)
                last_error = AgyParseError(f"Outer JSON decode failed: {e}", stdout)
                continue  # Retryable

            if envelope.get("status") not in ("SUCCESS", None):
                last_error = AgyParseError(
                    f"agy status was '{envelope.get('status')}', expected SUCCESS",
                    stdout,
                )
                continue  # Retryable

            # The actual agent response is in the "response" field as a string.
            # We asked for JSON output, so it should itself be a JSON string.
            response_text: str = envelope.get("response", "")
            if not response_text:
                last_error = AgyParseError("agy envelope had empty 'response' field", stdout)
                continue

            # Strip markdown fences if the model wrapped the JSON anyway
            response_text = _strip_markdown_fences(response_text)

            try:
                parsed: dict[str, Any] = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.warning("agy: response field not valid JSON: %s", e)
                last_error = AgyParseError(f"Response JSON decode failed: {e}", response_text)
                continue  # Retryable

            usage = envelope.get("usage", {})
            return AgyPlanResult(
                raw=parsed,
                conversation_id=envelope.get("conversation_id", ""),
                elapsed_s=elapsed,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            )

        # All attempts exhausted
        assert last_error is not None
        raise last_error


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_markdown_fences(text: str) -> str:
    """
    Strip ```json / ``` fences that models sometimes add even when told not to.
    Returns the inner content, or the original string if no fence is found.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        # Remove opening fence line and closing fence line
        inner_lines = []
        in_fence = False
        for line in lines:
            if line.startswith("```") and not in_fence:
                in_fence = True
                continue
            if line.startswith("```") and in_fence:
                break
            if in_fence:
                inner_lines.append(line)
        return "\n".join(inner_lines).strip()
    return stripped
