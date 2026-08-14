"""
Test Engine

Handles test execution and validation.

This module enables Aura to:
- Run tests
- Check test results
- Validate code after changes
- Report test coverage
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Result of a test run."""

    test_file: str
    test_name: str
    status: str  # "passed", "failed", "error", "skipped"
    duration: float
    message: str | None = None
    traceback: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "test_file": self.test_file,
            "test_name": self.test_name,
            "status": self.status,
            "duration": self.duration,
            "message": self.message,
            "traceback": self.traceback,
        }


@dataclass
class TestCoverage:
    """Test coverage information."""

    file_path: str
    covered_lines: list[int]
    total_lines: int
    coverage_percent: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "file_path": self.file_path,
            "covered_lines": self.covered_lines,
            "total_lines": self.total_lines,
            "coverage_percent": self.covered_percent,
        }


class TestEngine:
    """
    Handles test execution and validation.

    Usage:
        engine = TestEngine(repository_path="/path/to/repo")

        # Run all tests
        results = engine.run_all_tests()

        # Run specific test file
        results = engine.run_tests("tests/test_auth.py")

        # Check coverage
        coverage = engine.get_coverage("src/main.py")

        # Validate changes
        valid = engine.validate_after_change("src/main.py", "new_content")
    """

    def __init__(self, repository_path: Path, workspace_walker=None):
        """
        Initialize the Test Engine.

        Args:
            repository_path: Path to the repository
            workspace_walker: Walker instance for repository discovery
        """
        self.repository_path = Path(repository_path).resolve()
        if workspace_walker is None:
            from .workspace_walker import WorkspaceFileWalker
            self.workspace_walker = WorkspaceFileWalker(repository_path=self.repository_path)
        else:
            self.workspace_walker = workspace_walker

    def run_all_tests(self) -> dict[str, Any]:
        """
        Run all tests.

        Returns:
            Dictionary with test results
        """
        # Find all test files
        test_files = self.workspace_walker.walk("test_*.py").files

        all_results = []
        total_duration = 0.0
        passed = 0
        failed = 0

        for test_file in test_files:
            results = self.run_tests(str(test_file))
            all_results.extend(results["results"])
            total_duration += results["total_duration"]
            passed += results["passed"]
            failed += results["failed"]

        return {
            "results": all_results,
            "total_duration": total_duration,
            "passed": passed,
            "failed": failed,
            "total_tests": len(all_results),
        }

    def run_tests(self, test_file: str) -> dict[str, Any]:
        """
        Run tests in a specific file.

        Args:
            test_file: Path to test file

        Returns:
            Dictionary with test results
        """
        try:
            # Run pytest or unittest
            # Placeholder implementation
            return {
                "test_file": test_file,
                "results": [],
                "total_duration": 0.0,
                "passed": 0,
                "failed": 0,
                "error": None,
            }
        except Exception as e:
            logger.error(f"Error running tests in {test_file}: {e}")
            return {
                "test_file": test_file,
                "results": [],
                "total_duration": 0.0,
                "passed": 0,
                "failed": 0,
                "error": str(e),
            }

    def get_coverage(self, file_path: str) -> TestCoverage | None:
        """
        Get test coverage for a file.

        Args:
            file_path: Path to the file

        Returns:
            TestCoverage or None
        """
        # This would run coverage tools
        # Placeholder implementation
        return None

    def validate_after_change(self, file_path: str, new_content: str) -> bool:
        """
        Validate code after a change.

        Args:
            file_path: Path to the file
            new_content: New content

        Returns:
            True if validation passes
        """
        # Run tests and linting
        # Placeholder implementation
        return True

    def get_failed_tests(self) -> list[TestResult]:
        """
        Get list of failed tests.

        Returns:
            List of failed test results
        """
        results = self.run_all_tests()
        return [r for r in results["results"] if r.status == "failed"]

    def get_test_summary(self) -> dict[str, Any]:
        """
        Get summary of all tests.

        Returns:
            Dictionary with summary
        """
        results = self.run_all_tests()

        return {
            "total_tests": results["total_tests"],
            "passed": results["passed"],
            "failed": results["failed"],
            "success_rate": (
                results["passed"] / results["total_tests"]
                if results["total_tests"] > 0
                else 0
            ),
            "total_duration": results["total_duration"],
        }
