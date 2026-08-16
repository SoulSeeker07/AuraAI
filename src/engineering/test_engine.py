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
        Run tests in a specific file using pytest.

        Args:
            test_file: Path to test file

        Returns:
            Dictionary with test results
        """
        import subprocess
        import sys
        import tempfile
        import xml.etree.ElementTree as ET
        import time
        import os

        try:
            with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
                tmp_name = tmp.name

            start_time = time.time()
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", test_file, f"--junitxml={tmp_name}"],
                cwd=str(self.repository_path),
                capture_output=True,
                text=True,
                timeout=120
            )
            total_duration = time.time() - start_time

            if proc.returncode in (2, 5):
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
                return {
                    "test_file": test_file,
                    "status": "collection_error",
                    "error": proc.stderr or proc.stdout,
                    "results": [],
                    "total_duration": total_duration,
                    "passed": 0,
                    "failed": 0
                }

            results = []
            passed = 0
            failed = 0

            try:
                tree = ET.parse(tmp_name)
                root = tree.getroot()

                for testsuite in root.iter("testsuite"):
                    for testcase in testsuite.iter("testcase"):
                        name = testcase.get("name", "")
                        file = testcase.get("file", test_file)
                        duration = float(testcase.get("time", 0.0))

                        failure = testcase.find("failure")
                        error_node = testcase.find("error")
                        skipped = testcase.find("skipped")

                        if failure is not None:
                            status = "failed"
                            message = failure.get("message", "")
                            traceback = failure.text
                            failed += 1
                        elif error_node is not None:
                            status = "error"
                            message = error_node.get("message", "")
                            traceback = error_node.text
                            failed += 1
                        elif skipped is not None:
                            status = "skipped"
                            message = skipped.get("message", "")
                            traceback = None
                        else:
                            status = "passed"
                            message = None
                            traceback = None
                            passed += 1

                        results.append(TestResult(
                            test_file=file,
                            test_name=name,
                            status=status,
                            duration=duration,
                            message=message,
                            traceback=traceback
                        ))
            except Exception as xml_e:
                logger.error(f"Failed to parse junitxml: {xml_e}")

            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

            overall_status = "passed" if failed == 0 else "failed"

            return {
                "test_file": test_file,
                "status": overall_status,
                "error": None,
                "results": results,
                "total_duration": total_duration,
                "passed": passed,
                "failed": failed
            }
        except subprocess.TimeoutExpired as e:
            return {
                "test_file": test_file,
                "status": "collection_error",
                "error": "Test execution timed out after 120s",
                "results": [],
                "total_duration": 120.0,
                "passed": 0,
                "failed": 0
            }
        except Exception as e:
            logger.error(f"Error running tests in {test_file}: {e}")
            return {
                "test_file": test_file,
                "status": "collection_error",
                "error": str(e),
                "results": [],
                "total_duration": 0.0,
                "passed": 0,
                "failed": 0
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

    def validate_after_change(self, file_path: str, new_content: str) -> dict[str, Any]:
        """
        Validate code after a change using dependency-scoped tests.

        Args:
            file_path: Path to the file
            new_content: New content

        Returns:
            Dictionary with execution results and status
        """
        from .dependency_graph import DependencyGraph

        if not hasattr(self, "dependency_graph"):
            self.dependency_graph = DependencyGraph(self.repository_path, self.workspace_walker)
            self.dependency_graph.build_from_files()

        module_name = Path(file_path).stem
        dependents = self.dependency_graph.get_dependents(module_name)
        
        test_modules = [d for d in dependents if d.startswith("test_")]
        if not test_modules:
            return {"status": "no scoped tests found", "results": []}

        all_results = []
        overall_status = "passed"

        for test_mod in test_modules:
            # Resolve the module to a file path using the workspace walker
            matched_files = self.workspace_walker.walk(f"{test_mod}.py").files
            if not matched_files:
                continue
                
            test_file_path = matched_files[0]
            result = self.run_tests(str(test_file_path))
            all_results.append(result)
            
            if result.get("status") != "passed":
                overall_status = "failed"

        return {
            "status": overall_status,
            "results": all_results
        }

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
