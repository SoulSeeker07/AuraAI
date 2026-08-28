"""
Test Runner Adapter & Structured Failure Parser
Location: src/engineering/test_runner.py

Defines test runner abstractions and concrete Pytest adapter for parsing
test failure stack traces into structured coordinates for fault localization.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class StackFrame:
    """Individual frame in a test failure stack trace."""
    file_path: str
    line_number: int
    code_line: str = ""
    function_name: str = ""


@dataclass
class TestFailureFrame:
    """Structured representation of a failed test case."""
    __test__ = False
    test_id: str
    test_file: str
    error_type: str
    error_message: str
    stack_frames: list[StackFrame] = field(default_factory=list)
    failing_source_file: str | None = None
    failing_source_line: int | None = None


@dataclass
class TestRunResult:
    """Outcome of a test suite execution."""
    __test__ = False
    success: bool
    total_tests: int
    passed_tests: int
    failed_tests: int
    error_count: int
    duration_seconds: float
    failure_frames: list[TestFailureFrame] = field(default_factory=list)
    raw_output: str = ""


class TestRunnerAdapter(ABC):
    """Abstract interface for test runners."""

    @abstractmethod
    def run_tests(
        self,
        test_path: str | Path | None = None,
        filter_expr: str | None = None,
        timeout_seconds: int = 120,
    ) -> TestRunResult:
        """Run tests and return structured results."""
        pass

    @abstractmethod
    def parse_output(self, raw_output: str) -> list[TestFailureFrame]:
        """Parse raw test runner output into structured failure frames."""
        pass


class PytestRunnerAdapter(TestRunnerAdapter):
    """
    Concrete adapter for pytest executions, parsing tracebacks and failure summaries.
    """

    def __init__(self, repo_root: str | Path | None = None, python_executable: str | None = None):
        self.repo_root = Path(repo_root or os.getcwd()).resolve()
        self.python_exe = python_executable or sys.executable

    def run_tests(
        self,
        test_path: str | Path | None = None,
        filter_expr: str | None = None,
        timeout_seconds: int = 120,
    ) -> TestRunResult:
        """Execute pytest in the workspace and capture stdout/stderr."""
        cmd = [self.python_exe, "-m", "pytest", "-v", "--tb=short"]
        if test_path:
            cmd.append(str(test_path))
        if filter_expr:
            cmd.extend(["-k", filter_expr])

        try:
            res = subprocess.run(
                cmd,
                cwd=str(self.repo_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout_seconds,
            )
            raw_out = res.stdout or ""
            return self._build_run_result(res.returncode == 0, raw_out)
        except subprocess.TimeoutExpired as exc:
            return TestRunResult(
                success=False,
                total_tests=0,
                passed_tests=0,
                failed_tests=1,
                error_count=1,
                duration_seconds=float(timeout_seconds),
                failure_frames=[
                    TestFailureFrame(
                        test_id="timeout",
                        test_file=str(test_path or ""),
                        error_type="TimeoutExpired",
                        error_message=f"Test run timed out after {timeout_seconds}s",
                    )
                ],
                raw_output=exc.stdout or "",
            )

    def parse_output(self, raw_output: str) -> list[TestFailureFrame]:
        """
        Parse pytest output traceback sections into structured TestFailureFrame items.
        """
        frames: list[TestFailureFrame] = []
        if not raw_output:
            return frames

        # Regex for FAILURES block header: _ test_name _ or _ TestClass.test_name _
        failure_blocks = re.split(r"_{3,}\s+(.*?)\s+_{3,}", raw_output)
        
        # Split gives [preamble, title1, body1, title2, body2, ...]
        if len(failure_blocks) > 1:
            for i in range(1, len(failure_blocks), 2):
                test_title = failure_blocks[i].strip()
                block_body = failure_blocks[i + 1] if i + 1 < len(failure_blocks) else ""
                
                parsed_frame = self._parse_failure_block(test_title, block_body)
                if parsed_frame:
                    frames.append(parsed_frame)
        else:
            # Check for FAILED line summaries
            for line in raw_output.splitlines():
                if line.startswith("FAILED "):
                    parts = line.split("FAILED ", 1)[-1].split(" - ", 1)
                    test_id = parts[0].strip()
                    err_msg = parts[1].strip() if len(parts) > 1 else "Test failed"
                    frames.append(
                        TestFailureFrame(
                            test_id=test_id,
                            test_file=test_id.split("::")[0],
                            error_type="AssertionError",
                            error_message=err_msg,
                        )
                    )

        return frames

    def _parse_failure_block(self, test_title: str, block_body: str) -> TestFailureFrame:
        """Parse individual pytest failure block body into stack frames and root cause."""
        stack_frames: list[StackFrame] = []
        error_type = "AssertionError"
        error_msg = ""
        failing_src_file = None
        failing_src_line = None

        # Regex for traceback line: path/to/file.py:123: in function_name
        # or File "path/to/file.py", line 123, in function_name
        tb_pattern = re.compile(r'([\w./\\-]+(?:\.py))[:\s,]+line\s*(\d+)|\b([\w./\\-]+(?:\.py)):(\d+):')
        # Match error line: E   ZeroDivisionError: division by zero or ZeroDivisionError: ...
        err_pattern = re.compile(r"^(?:E\s+)?([A-Z]\w*(?:Error|Exception|Violation))(?::\s*(.*))?$", re.MULTILINE)

        err_match = err_pattern.search(block_body)
        if err_match:
            error_type = err_match.group(1).strip()
            error_msg = (err_match.group(2) or "").strip()
        else:
            # Fallback to lines starting with E   
            e_lines = [l[2:].strip() for l in block_body.splitlines() if l.startswith("E   ")]
            if e_lines:
                error_msg = "\n".join(e_lines)

        for line in block_body.splitlines():
            # Check for file line references
            m = re.search(r"([\w./\\-]+\.py):(\d+):", line)
            if m:
                fpath = m.group(1).replace("\\", "/")
                lineno = int(m.group(2))
                stack_frames.append(StackFrame(file_path=fpath, line_number=lineno))
                # Update root cause candidate (non-test files prioritized)
                if not fpath.startswith("tests/") and not fpath.endswith("_test.py"):
                    failing_src_file = fpath
                    failing_src_line = lineno

        # If all frames were test files, the failing line is the last frame
        if not failing_src_file and stack_frames:
            failing_src_file = stack_frames[-1].file_path
            failing_src_line = stack_frames[-1].line_number

        test_file = stack_frames[0].file_path if stack_frames else "unknown_test.py"

        return TestFailureFrame(
            test_id=test_title,
            test_file=test_file,
            error_type=error_type,
            error_message=error_msg or "Assertion failed",
            stack_frames=stack_frames,
            failing_source_file=failing_src_file,
            failing_source_line=failing_src_line,
        )

    def _build_run_result(self, is_success: bool, raw_output: str) -> TestRunResult:
        """Parse pytest summary stats into TestRunResult."""
        total = 0
        passed = 0
        failed = 0
        errors = 0

        # Pattern: = 1 failed, 2 passed, 1 error in 0.12s =
        summary_match = re.search(r"=+\s+([0-9\s\w,]+)\s+in\s+([0-9.]+)s", raw_output)
        duration = 0.0

        if summary_match:
            stat_str = summary_match.group(1)
            duration = float(summary_match.group(2))
            
            p_match = re.search(r"(\d+)\s+passed", stat_str)
            f_match = re.search(r"(\d+)\s+failed", stat_str)
            e_match = re.search(r"(\d+)\s+error", stat_str)

            if p_match:
                passed = int(p_match.group(1))
            if f_match:
                failed = int(f_match.group(1))
            if e_match:
                errors = int(e_match.group(1))
            total = passed + failed + errors
        elif is_success:
            passed = 1
            total = 1

        failures = self.parse_output(raw_output)

        return TestRunResult(
            success=is_success and (failed == 0 and errors == 0),
            total_tests=total,
            passed_tests=passed,
            failed_tests=failed,
            error_count=errors,
            duration_seconds=duration,
            failure_frames=failures,
            raw_output=raw_output,
        )


class SandboxedPytestRunnerAdapter(PytestRunnerAdapter):
    """
    Executes Pytest runs under OS-enforced sandbox containment:
    - Runs under AuraSandboxUser via RestrictedUserSandbox using CreateProcessWithLogonW.
    - Bound to Win32 Job Object with process limits and kill-on-close.
    - Redirects cache and temporary files to .aura_staging/ (granted Modify to AuraSandboxUser).
    - Scrubbed minimal environment free of host credentials / API keys.
    - Strict fail-closed security invariant: raises RuntimeError if sandbox is unavailable.
    """

    def __init__(
        self,
        repo_root: str | Path | None = None,
        python_executable: str | None = None,
        staging_dir: str | Path | None = None,
        sandbox: Any | None = None,
    ):
        super().__init__(repo_root=repo_root, python_executable=python_executable)
        self.staging_dir = Path(staging_dir or (self.repo_root / ".aura_staging")).resolve()
        self.pytest_cache_dir = self.staging_dir / "pytest_cache"
        self.pytest_tmp_dir = self.staging_dir / "tmp"
        self._sandbox = sandbox

    def _get_sandbox(self) -> Any:
        if self._sandbox is not None:
            if hasattr(self._sandbox, "is_available") and not self._sandbox.is_available():
                raise RuntimeError(
                    "Fail-Closed Security Invariant: RestrictedUserSandbox is unavailable (AuraSandboxUser unconfigured or missing)."
                )
            return self._sandbox
        if os.name == "nt":
            from desktop.native.sandbox.restricted_user_sandbox import RestrictedUserSandbox
            sandbox = RestrictedUserSandbox(workspace_root=str(self.repo_root))
            if not sandbox.is_available():
                raise RuntimeError(
                    "Fail-Closed Security Invariant: RestrictedUserSandbox is unavailable (AuraSandboxUser unconfigured or missing)."
                )
            self._sandbox = sandbox
            return self._sandbox
        else:
            raise RuntimeError(
                "Fail-Closed Security Invariant: SandboxedPytestRunnerAdapter requires a Windows host with Win32 Job Object & RestrictedUserSandbox."
            )

    def _ensure_staging_permissions(self) -> None:
        self.pytest_cache_dir.mkdir(parents=True, exist_ok=True)
        self.pytest_tmp_dir.mkdir(parents=True, exist_ok=True)
        try:
            from desktop.native.sandbox.account_provisioner import grant_staging_access
            grant_staging_access(self.staging_dir)
        except Exception:
            pass

    def run_tests(

        self,
        test_path: str | Path | None = None,
        filter_expr: str | None = None,
        timeout_seconds: int = 120,
    ) -> TestRunResult:
        """Execute pytest inside the sandbox and capture structured results."""
        self._ensure_staging_permissions()
        sandbox = self._get_sandbox()

        # Use relative paths for staging cache and temp to keep PowerShell encoded command under 1024 chars
        cmd_parts = [
            f'& "{self.python_exe}"',
            "-m",
            "pytest",
            "-v",
            "--tb=short",
            "-o",
            "cache_dir=.aura_staging/pytest_cache",
            "--basetemp=.aura_staging/tmp",
        ]
        if test_path:
            cmd_parts.append(f'"{test_path}"')
        if filter_expr:
            cmd_parts.extend(["-k", f'"{filter_expr}"'])

        command_str = " ".join(cmd_parts)

        exit_code, stdout, stderr = sandbox.execute(
            command=command_str,
            cwd=str(self.repo_root),
            timeout=float(timeout_seconds),
        )
        raw_out = f"{stdout}\n{stderr}".strip()
        return self._build_run_result(exit_code == 0, raw_out)





__all__ = [
    "StackFrame",
    "TestFailureFrame",
    "TestRunResult",
    "TestRunnerAdapter",
    "PytestRunnerAdapter",
    "SandboxedPytestRunnerAdapter",
]

