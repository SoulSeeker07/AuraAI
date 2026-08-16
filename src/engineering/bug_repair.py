"""
Bug Repair Loop

Automates bug fixing using test-driven approach.

This module enables Aura to:
- Run tests
- Detect failures
- Analyze failures
- Apply fixes
- Retest
- Repeat until fixed
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BugFixAttempt:
    """Represents a bug fix attempt."""

    attempt_number: int
    test_file: str
    test_name: str
    status: str  # "passed", "failed", "error"
    fix_applied: str | None = None
    error_traceback: str | None = None
    duration: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "attempt_number": self.attempt_number,
            "test_file": self.test_file,
            "test_name": self.test_name,
            "status": self.status,
            "fix_applied": self.fix_applied,
            "error_traceback": self.error_traceback,
            "duration": self.duration,
        }


@dataclass
class BugRepairResult:
    """Result of bug repair process."""

    success: bool
    test_file: str
    attempts: list[BugFixAttempt]
    total_attempts: int
    total_duration: float
    final_status: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "test_file": self.test_file,
            "attempts": [a.to_dict() for a in self.attempts],
            "total_attempts": self.total_attempts,
            "total_duration": self.total_duration,
            "final_status": self.final_status,
            "error": self.error,
        }


class BugRepairLoop:
    """
    Automates bug fixing using test-driven approach.

    Usage:
        loop = BugRepairLoop(
            repository_path="/path/to/repo",
            test_engine=test_engine,
            ast_manager=ast_manager
        )

        # Repair a bug
        result = loop.repair_bug(
            test_file="tests/test_auth.py",
            test_name="test_login_success",
            expected_output=None
        )
    """

    def __init__(self, repository_path: Path, test_engine, ast_manager, code_editor=None):
        """
        Initialize the Bug Repair Loop.

        Args:
            repository_path: Path to the repository
            test_engine: Test engine for running tests
            ast_manager: AST manager for analyzing code
            code_editor: Code editor for backups and rollback
        """
        self.repository_path = Path(repository_path).resolve()
        self.test_engine = test_engine
        self.ast_manager = ast_manager
        self.code_editor = code_editor
        self.max_attempts = 3

    def repair_bug(
        self,
        test_file: str,
        test_name: str,
        expected_output: Any = None,
        max_attempts: int | None = None,
        target_file: str | None = None,
    ) -> BugRepairResult:
        """
        Repair a bug using test-driven approach.

        Args:
            test_file: Path to test file
            test_name: Name of test to run
            expected_output: Expected test output
            max_attempts: Maximum number of attempts
            target_file: The source file suspected of the bug

        Returns:
            BugRepairResult
        """
        if max_attempts:
            self.max_attempts = max_attempts

        attempts = []
        total_duration = 0.0
        
        backup_id = None
        if self.code_editor and target_file:
            backup_id = self.code_editor.create_backup(target_file)

        for attempt in range(1, self.max_attempts + 1):
            # Run test
            test_result = self._run_test(test_file, test_name)
            test_result.attempt_number = attempt
            attempts.append(test_result)
            total_duration += test_result.duration

            if test_result.status == "passed":
                return BugRepairResult(
                    success=True,
                    test_file=test_file,
                    attempts=attempts,
                    total_attempts=attempt,
                    total_duration=total_duration,
                    final_status="passed",
                    error=None,
                )
            elif test_result.status in ("failed", "error", "collection_error"):
                # Analyze and try to fix
                try:
                    fix = self._analyze_and_fix(test_result, target_file)
                    attempts[-1].fix_applied = fix
                    total_duration += 0.1
                except Exception as e:
                    logger.error(f"Repair iteration failed: {e}")

        # Exhaustion rollback
        if self.code_editor and backup_id and target_file:
            self.code_editor.restore_backup(backup_id)

        return BugRepairResult(
            success=False,
            test_file=test_file,
            attempts=attempts,
            total_attempts=self.max_attempts,
            total_duration=total_duration,
            final_status="failed",
            error="Max attempts reached without success, rolled back.",
        )

    def _run_test(self, test_file: str, test_name: str) -> BugFixAttempt:
        """Run a single test."""
        try:
            result = self.test_engine.run_tests(test_file)
            
            status = result.get("status", "error")
            traceback = result.get("error")
            
            for r in result.get("results", []):
                if not test_name or r.test_name == test_name:
                    status = r.status
                    traceback = r.traceback
                    break
                    
            return BugFixAttempt(
                attempt_number=1,
                test_file=test_file,
                test_name=test_name,
                status=status,
                error_traceback=traceback,
                duration=result.get("total_duration", 0.0),
            )
        except Exception as e:
            return BugFixAttempt(
                attempt_number=1,
                test_file=test_file,
                test_name=test_name,
                status="error",
                error_traceback=str(e),
                duration=0.0,
            )

    def _analyze_and_fix(self, test_result: BugFixAttempt, target_file: str | None) -> str:
        """Analyze a test failure and apply a fix."""
        import re
        failing_symbol = None
        
        # Simple heuristic: extract last function name from traceback
        # Attempt to extract symbol context from WorldModel
        # Note: This is a fragile best-effort heuristic. It will misfire on class methods, 
        # decorated functions, or multi-frame tracebacks.
        matches = re.findall(r"def (\w+)\(", test_result.error_traceback or "")
        if matches:
            failing_symbol = matches[-1]
                
        symbol_data = None
        if failing_symbol:
            try:
                from brain.world_model import WorldModel
                wm = WorldModel.get_instance()
                
                # Query World Model exactly as validated
                symbol_data = wm.query_sync(entity=f"function:{failing_symbol}", domain="symbol")
                if not symbol_data:
                    symbol_data = wm.query_sync(entity=f"class:{failing_symbol}", domain="symbol")
            except ImportError:
                pass
                
        prompt = f"Fix the test failure in {target_file or test_result.test_file}.\n"
        if test_result.error_traceback:
            prompt += f"\nTraceback:\n{test_result.error_traceback}\n"
            
        if symbol_data:
            prompt += f"\nSymbol Context from World Model:\n{symbol_data}\n"
            
        try:
            # Delegate to code.debug via Antigravity bridge without fallback
            from engineering.antigravity_bridge import AntigravityCodingBridge
            bridge = AntigravityCodingBridge()
            bridge.execute_capability(
                capability="code.debug",
                arguments={"description": prompt, "file_path": target_file or test_result.test_file}
            )
            return "Delegated to code.debug"
        except Exception as e:
            logger.error(f"Failed to delegate to code.debug: {e}")
            raise e

    def repair_all_failed_tests(self) -> dict[str, Any]:
        """
        Repair all failed tests.

        Returns:
            Dictionary with repair results
        """
        failed_tests = self.test_engine.get_failed_tests()

        results = []
        for test in failed_tests:
            result = self.repair_bug(test_file=test.test_file, test_name=test.test_name)
            results.append(result)

        return {
            "total_failed_tests": len(failed_tests),
            "repaired": sum(1 for r in results if r.success),
            "unrepaired": sum(1 for r in results if not r.success),
            "results": [r.to_dict() for r in results],
        }
