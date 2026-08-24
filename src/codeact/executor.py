"""
Dynamic CodeAct Executor & Closed-Loop Repair State Machine
Location: src/codeact/executor.py

Coordinates the multi-attempt synthesis, static safety verification,
sandboxed execution, output validation, and diagnostic repair loop.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable

from .drafters import CodeDrafter, GroqDrafter
from .models import (
    CodeActRequest,
    CodeActResult,
    ExecutionAttempt,
    StaticCheckResult,
    ValidationResult,
)
from .staging_sandbox import StagingSandbox
from .static_checker import check_imports
from .validators import validate

logger = logging.getLogger(__name__)


class DynamicCodeActExecutor:
    """
    General-purpose artifact synthesis and sandboxed code execution engine.
    """

    def __init__(
        self,
        drafter: CodeDrafter | None = None,
        sandbox_factory: Callable[..., StagingSandbox] = StagingSandbox,
    ):
        self.drafter = drafter or GroqDrafter()
        self.sandbox_factory = sandbox_factory

    def _build_initial_prompt(self, request: CodeActRequest) -> str:
        """Construct the prompt for initial code synthesis."""
        lines = [
            f"GOAL: {request.goal}",
            f"OUTPUT FILENAME: {request.output_filename}",
        ]
        if request.allowed_libraries:
            lines.append(f"ALLOWED LIBRARIES: {', '.join(request.allowed_libraries)}")
        if request.input_files:
            file_names = [Path(f).name for f in request.input_files]
            lines.append(
                f"AVAILABLE INPUT FILES (in current directory): {', '.join(file_names)}"
            )

        lines.extend(
            [
                "",
                "INSTRUCTIONS:",
                f"1. Write a complete Python script to generate '{request.output_filename}'.",
                "2. Ensure the output file is saved directly to the current working directory.",
                "3. Ensure the generated artifact is well-formatted, non-empty, and valid.",
                "4. Enclose all code in a ```python ... ``` code block.",
            ]
        )
        return "\n".join(lines)

    def _build_static_repair_prompt(
        self, request: CodeActRequest, code: str, static_res: StaticCheckResult
    ) -> str:
        """Construct repair prompt when AST static check rejects imports or calls."""
        return (
            f"Your previous Python script was REJECTED by static safety verification.\n"
            f"REASON: {static_res.reason}\n\n"
            f"VIOLATIONS:\n"
            f"- Blocked: {static_res.blocked_imports}\n"
            f"- Disallowed: {static_res.disallowed_imports}\n"
            f"- Violations: {static_res.violations}\n\n"
            f"GOAL: {request.goal}\n"
            f"OUTPUT FILENAME: {request.output_filename}\n"
            f"ALLOWED LIBRARIES: {', '.join(request.allowed_libraries) if request.allowed_libraries else 'Standard library only'}\n\n"
            "Please rewrite the script without using any blocked or disallowed modules or functions."
        )

    def _build_execution_repair_prompt(
        self,
        request: CodeActRequest,
        attempt: ExecutionAttempt,
        validation: ValidationResult,
    ) -> str:
        """Construct repair prompt after execution crash or validation failure."""
        lines = [
            f"GOAL: {request.goal}",
            f"OUTPUT FILENAME: {request.output_filename}",
            f"ATTEMPT {attempt.attempt_number} RESULT:",
        ]

        if attempt.exit_code != 0:
            lines.extend(
                [
                    f"The script crashed with exit code {attempt.exit_code}.",
                    "STDERR / TRACEBACK:",
                    attempt.stderr.strip() or "(No stderr captured)",
                    "STDOUT:",
                    attempt.stdout.strip() or "(No stdout captured)",
                ]
            )
        else:
            failed_checks = [name for name, passed in validation.checks if not passed]
            lines.extend(
                [
                    "The script executed with exit code 0, but output artifact validation FAILED.",
                    f"FAILED CHECKS: {', '.join(failed_checks)}",
                    f"VALIDATION ERROR: {validation.error_message}",
                    "STDOUT:",
                    attempt.stdout.strip() or "(No stdout captured)",
                ]
            )

        lines.extend(
            [
                "",
                "PREVIOUS CODE:",
                "```python",
                attempt.code,
                "```",
                "",
                "Please fix the error and provide a corrected, complete Python script in a ```python ... ``` block.",
            ]
        )
        return "\n".join(lines)

    def run(self, request: CodeActRequest) -> CodeActResult:
        """
        Execute the closed-loop CodeAct state machine for the given request.
        """
        attempts: list[ExecutionAttempt] = []
        static_retries_used = 0
        repair_attempts_used = 0

        prompt = self._build_initial_prompt(request)

        with self.sandbox_factory(request) as sandbox:
            while repair_attempts_used < request.max_repair_attempts:
                # 1. DRAFT state
                try:
                    code = self.drafter.draft(prompt)
                except Exception as exc:
                    logger.error(f"Drafter error: {exc}")
                    return CodeActResult(
                        status="failed",
                        attempts=attempts,
                        final_error=f"Code drafter exception: {exc}",
                    )

                if not code.strip():
                    repair_attempts_used += 1
                    prompt = (
                        f"Drafter returned empty code. Please write Python code for: {request.goal}"
                    )
                    continue

                # 2. STATIC_CHECK state
                static_res = check_imports(code, request.allowed_libraries)
                if not static_res.passed:
                    static_retries_used += 1
                    logger.warning(
                        f"CodeAct static check rejected code (retry {static_retries_used}/{request.max_static_retries}): {static_res.reason}"
                    )
                    if static_retries_used > request.max_static_retries:
                        return CodeActResult(
                            status="rejected",
                            attempts=attempts,
                            final_error=f"Static safety check failed repeatedly: {static_res.reason}",
                        )
                    # Static retry does not count against execution repair budget
                    prompt = self._build_static_repair_prompt(request, code, static_res)
                    continue

                # 3. EXECUTE state
                repair_attempts_used += 1
                script_path = sandbox.write_script(
                    code, filename=f"attempt_{repair_attempts_used}.py"
                )
                exit_code, stdout, stderr, dur_ms = sandbox.execute(
                    script_path, timeout=request.timeout_seconds
                )

                attempt = ExecutionAttempt(
                    attempt_number=repair_attempts_used,
                    code=code,
                    stdout=stdout,
                    stderr=stderr,
                    traceback=stderr if exit_code != 0 else None,
                    exit_code=exit_code,
                    duration_ms=dur_ms,
                )

                # 4. VALIDATE state
                val_result = validate(request, sandbox.staging_dir, attempt)
                attempt.validation_result = val_result
                attempts.append(attempt)

                logger.info(
                    f"CodeAct attempt {repair_attempts_used}/{request.max_repair_attempts} -> "
                    f"Exit: {exit_code}, Valid: {val_result.passed} ({dur_ms}ms)"
                )

                if val_result.passed:
                    # SUCCESS: Copy output artifact to a persistent staging result
                    staged_out = sandbox.staging_dir / request.output_filename
                    persistent_dir = Path(os.environ.get("TEMP", tempfile.gettempdir())) / "aura_artifacts"
                    persistent_dir.mkdir(parents=True, exist_ok=True)
                    final_target = persistent_dir / request.output_filename
                    shutil.copy2(staged_out, final_target)

                    return CodeActResult(
                        status="success",
                        output_path=final_target,
                        attempts=attempts,
                        final_error=None,
                    )

                # 5. REPAIR state: build contextual repair prompt and retry
                prompt = self._build_execution_repair_prompt(request, attempt, val_result)

        # Exhausted retries
        last_error = attempts[-1].validation_result.error_message if attempts and attempts[-1].validation_result else "Max repair attempts exhausted"
        return CodeActResult(
            status="failed",
            output_path=None,
            attempts=attempts,
            final_error=f"Exhausted {request.max_repair_attempts} attempts: {last_error}",
        )
