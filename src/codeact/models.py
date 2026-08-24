"""
CodeAct Data Models
Location: src/codeact/models.py

Defines request, attempt, validation, and outcome models for the
DynamicCodeActExecutor and staging sandbox.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


@dataclass
class CodeActRequest:
    """Specification for a sandboxed code synthesis and execution task."""

    goal: str
    output_filename: str
    allowed_libraries: list[str] = field(default_factory=list)
    input_files: list[Path] = field(default_factory=list)
    max_repair_attempts: int = 3
    max_static_retries: int = 2
    timeout_seconds: int = 30
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StaticCheckResult:
    """Outcome of pre-execution AST static analysis on generated code."""

    passed: bool
    blocked_imports: list[str] = field(default_factory=list)
    disallowed_imports: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    reason: str | None = None


@dataclass
class ValidationResult:
    """Outcome of post-execution output file validation."""

    passed: bool
    checks: list[tuple[str, bool]] = field(default_factory=list)
    error_message: str | None = None


@dataclass
class ExecutionAttempt:
    """Audit record for a single execution cycle within the repair loop."""

    attempt_number: int
    code: str
    stdout: str
    stderr: str
    traceback: str | None
    exit_code: int
    duration_ms: int
    validation_result: ValidationResult | None = None


@dataclass
class CodeActResult:
    """Final result returned by DynamicCodeActExecutor."""

    status: Literal["success", "failed", "rejected"]
    output_path: Path | None = None
    attempts: list[ExecutionAttempt] = field(default_factory=list)
    final_error: str | None = None
    target_destination: Path | None = None
