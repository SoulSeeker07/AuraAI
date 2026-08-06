"""
Validation Workers (Pytest, Ruff, Black, Git)
Location: src/core/backends/adapters/validation_workers.py

Implements lightweight asynchronous validation workers that run concurrently
alongside Antigravity CLI to execute tests, run linters, and capture git diffs.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PytestWorker:
    """Async worker that runs pytest against a workspace."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.name = "PytestWorker"

    async def run_tests(self, target_path: str | None = None) -> dict[str, Any]:
        """Execute pytest asynchronously and parse outputs."""
        cmd = ["pytest", "-q", "--tb=short"]
        if target_path:
            cmd.append(target_path)

        logger.info(f"PytestWorker running: {' '.join(cmd)} in {self.workspace}")
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.workspace),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            out = stdout.decode("utf-8", errors="replace")

            passed = out.count(" PASSED")
            failed = out.count(" FAILED")
            skipped = out.count(" SKIPPED")
            total = passed + failed + skipped

            return {
                "success": process.returncode == 0,
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "total": total,
                "output": out,
            }
        except Exception as e:
            logger.warning(f"PytestWorker execution error: {e}")
            return {
                "success": False,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "total": 0,
                "output": f"Pytest execution failed: {e}",
            }


class RuffWorker:
    """Async worker that runs ruff linter/formatter check."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.name = "RuffWorker"

    async def run_check(self) -> dict[str, Any]:
        """Run ruff check asynchronously."""
        cmd = ["ruff", "check", "."]
        logger.info(f"RuffWorker running in {self.workspace}")
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.workspace),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            out = stdout.decode("utf-8", errors="replace")

            return {
                "success": process.returncode == 0,
                "issues_count": out.count("\n") if out.strip() else 0,
                "output": out,
            }
        except Exception as e:
            logger.warning(f"RuffWorker execution error: {e}")
            return {"success": False, "issues_count": 0, "output": str(e)}


class GitDiffWorker:
    """Async worker that inspects git status and diffs."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.name = "GitDiffWorker"

    async def get_modified_files(self) -> list[str]:
        """Get list of modified/untracked files via git status."""
        cmd = ["git", "status", "--porcelain"]
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.workspace),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await process.communicate()
            lines = stdout.decode("utf-8", errors="replace").splitlines()
            files = []
            for line in lines:
                if len(line) > 3:
                    files.append(line[3:].strip())
            return files
        except Exception as e:
            logger.warning(f"GitDiffWorker error: {e}")
            return []
