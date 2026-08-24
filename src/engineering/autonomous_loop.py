"""
Autonomous Engineering Loop & Fail-Closed Rollback Engine
Location: src/engineering/autonomous_loop.py

Coordinates closed-loop software engineering:
Task Intake -> Staging -> Fault Localization -> Patch Synthesis -> Sandboxed Test Running -> Multi-Attempt Repair -> Fail-Closed Byte-Exact Rollback.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .fault_localizer import FaultCandidate, FaultLocalizer
from .patch_synthesizer import CodePatch, PatchSynthesizer
from .safety_ceiling import ProtectedCeilingViolation, RewardHackingViolation
from .staging_workspace import StagingWorkspace
from .test_runner import PytestRunnerAdapter, TestFailureFrame, TestRunResult, TestRunnerAdapter

logger = logging.getLogger(__name__)


@dataclass
class EngineeringTask:
    """Specification for an autonomous engineering task."""
    task_id: str
    goal: str
    task_type: str = "BUG_FIX"  # "BUG_FIX", "ADD_TEST", "REFACTOR"
    test_target: str | None = None
    target_files: list[str] = field(default_factory=list)


@dataclass
class LoopExecutionResult:
    """Outcome of an autonomous engineering loop execution."""
    success: bool
    task_id: str
    attempts_used: int
    applied_patches: list[CodePatch] = field(default_factory=list)
    test_results: list[TestRunResult] = field(default_factory=list)
    final_status: str = "COMPLETED"  # "COMPLETED", "FAILED", "ABORTED_VIOLATION"
    error: str | None = None
    rolled_back: bool = False


IGNORED_WORKSPACE_DIRS: tuple[str, ...] = (
    ".git",
    ".aura_staging",
    ".aura_backups",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
)


class AutonomousEngineeringLoop:
    """
    Closed-loop autonomous development engine with bounded retry and byte-exact rollback.
    """

    def __init__(
        self,
        repo_root: str | Path | None = None,
        test_runner: TestRunnerAdapter | None = None,
        synthesizer: PatchSynthesizer | None = None,
        localizer: FaultLocalizer | None = None,
        max_retries: int = 3,
    ):
        self.repo_root = Path(repo_root or os.getcwd()).resolve()
        self.test_runner = test_runner or PytestRunnerAdapter(repo_root=self.repo_root)
        self.synthesizer = synthesizer or PatchSynthesizer(repo_root=self.repo_root)
        self.localizer = localizer or FaultLocalizer(repo_root=self.repo_root)
        self.max_retries = max_retries

    def _snapshot_baseline(self) -> dict[str, bytes]:
        """
        Record exact byte contents of all files in workspace to guarantee byte-exact rollback.
        Fails closed with a loud RuntimeError if any file cannot be read.
        """
        snapshot: dict[str, bytes] = {}
        for root, dirs, files in os.walk(self.repo_root):
            # Prune ignored dependency and cache directories from traversal
            dirs[:] = [d for d in dirs if d not in IGNORED_WORKSPACE_DIRS]
            for f in files:
                p = Path(root) / f
                rel = str(p.relative_to(self.repo_root)).replace("\\", "/")
                try:
                    snapshot[rel] = p.read_bytes()
                except Exception as exc:
                    raise RuntimeError(
                        f"[AutonomousEngineeringLoop] Critical failure during baseline snapshot: "
                        f"cannot read '{rel}' ({exc}). Refusing to proceed with task."
                    ) from exc
        return snapshot

    def _rollback_to_baseline(self, baseline: dict[str, bytes]) -> bool:
        """
        Restore repository strictly to baseline state.
        Deletes any newly created untracked files/directories and restores original file bytes.
        Returns True if rollback completed with zero residual errors, False otherwise.
        """
        rollback_clean = True

        # 1. Remove untracked / newly added files and directories created during task
        for root, dirs, files in os.walk(self.repo_root, topdown=False):
            # When topdown=False, check path components directly to skip ignored directories
            if any(part in IGNORED_WORKSPACE_DIRS for part in Path(root).parts):
                continue

            for f in files:
                p = Path(root) / f
                rel = str(p.relative_to(self.repo_root)).replace("\\", "/")
                if rel not in baseline:
                    try:
                        p.unlink(missing_ok=True)
                    except Exception as exc:
                        logger.warning(
                            f"[AutonomousEngineeringLoop] Failed to unlink untracked file '{rel}' during rollback: {exc}"
                        )
                        rollback_clean = False
            for d in dirs:
                dp = Path(root) / d
                if dp.name in IGNORED_WORKSPACE_DIRS:
                    continue
                try:
                    if dp.exists() and not any(dp.iterdir()):
                        dp.rmdir()
                except Exception as exc:
                    logger.warning(
                        f"[AutonomousEngineeringLoop] Failed to prune empty directory '{dp}' during rollback: {exc}"
                    )
                    rollback_clean = False

        # 2. Restore modified/deleted baseline files with exact original bytes
        for rel_path, content in baseline.items():
            try:
                p = self.repo_root / rel_path
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(content)
            except Exception as exc:
                logger.warning(
                    f"[AutonomousEngineeringLoop] Failed to restore baseline file '{rel_path}' during rollback: {exc}"
                )
                rollback_clean = False

        return rollback_clean

    def run_task(
        self,
        task: EngineeringTask,
        patch_generator_fn: Any | None = None,
    ) -> LoopExecutionResult:
        """
        Execute closed-loop engineering task.
        """
        baseline_snapshot = self._snapshot_baseline()
        staging = StagingWorkspace(task_id=task.task_id, repo_root=self.repo_root)
        
        applied_patches: list[CodePatch] = []
        test_history: list[TestRunResult] = []
        attempt = 0

        try:
            with staging:
                # 1. Initial test run to detect failing assertions
                initial_test_res = self.test_runner.run_tests(test_path=task.test_target)
                test_history.append(initial_test_res)

                if initial_test_res.success and task.task_type == "BUG_FIX":
                    logger.info(f"[AutonomousEngineeringLoop] Initial tests already pass for {task.task_id}")
                    return LoopExecutionResult(
                        success=True,
                        task_id=task.task_id,
                        attempts_used=0,
                        applied_patches=[],
                        test_results=test_history,
                        final_status="COMPLETED",
                    )

                latest_failures = initial_test_res.failure_frames

                # 2. Repair loop
                while attempt < self.max_retries:
                    attempt += 1
                    logger.info(f"[AutonomousEngineeringLoop] Repair attempt {attempt}/{self.max_retries}")

                    # Localize fault from failure frames
                    candidates: list[FaultCandidate] = []
                    for failure in latest_failures:
                        candidates.extend(self.localizer.localize_fault(failure, self.repo_root))

                    # If no candidate found via traceback, fallback to target files
                    if not candidates and task.target_files:
                        for tf in task.target_files:
                            candidates.append(
                                FaultCandidate(
                                    file_path=tf,
                                    line_number=1,
                                    symbol_name=Path(tf).stem,
                                    symbol_type="module",
                                )
                            )

                    if not candidates:
                        raise RuntimeError(f"Could not localize fault candidates for task {task.task_id}")

                    # Synthesize patch for the top candidate
                    chosen_candidate = candidates[0]
                    
                    if patch_generator_fn:
                        new_content = patch_generator_fn(chosen_candidate, attempt)
                    else:
                        raise NotImplementedError("No patch generator function provided for loop.")

                    try:
                        patch = self.synthesizer.synthesize_file_patch(
                            target_file=chosen_candidate.file_path,
                            new_content=new_content,
                            task_type=task.task_type,
                        )
                    except (ProtectedCeilingViolation, RewardHackingViolation) as violation:
                        # Hard stop: do NOT consume retries, immediately fail closed and roll back
                        logger.error(
                            f"[AutonomousEngineeringLoop] Security/Immunity violation: {violation} — aborting loop immediately."
                        )
                        clean_rb = self._rollback_to_baseline(baseline_snapshot)
                        return LoopExecutionResult(
                            success=False,
                            task_id=task.task_id,
                            attempts_used=attempt,
                            applied_patches=[],
                            test_results=test_history,
                            final_status="ABORTED_VIOLATION",
                            error=f"{violation.__class__.__name__}: {violation}",
                            rolled_back=clean_rb,
                        )

                    # Apply candidate patch
                    self.synthesizer.apply_patch(patch)
                    applied_patches.append(patch)

                    # Run tests against modified workspace
                    test_run = self.test_runner.run_tests(test_path=task.test_target)
                    test_history.append(test_run)

                    if test_run.success:
                        logger.info(f"[AutonomousEngineeringLoop] Task {task.task_id} succeeded on attempt {attempt}")
                        return LoopExecutionResult(
                            success=True,
                            task_id=task.task_id,
                            attempts_used=attempt,
                            applied_patches=applied_patches,
                            test_results=test_history,
                            final_status="COMPLETED",
                        )

                    latest_failures = test_run.failure_frames
                    # Roll back to baseline before next retry attempt
                    self._rollback_to_baseline(baseline_snapshot)
                    applied_patches.clear()

                # Exhausted retries without passing tests
                logger.warning(f"[AutonomousEngineeringLoop] Max retries exhausted ({self.max_retries}) for {task.task_id}")
                clean_rb = self._rollback_to_baseline(baseline_snapshot)
                return LoopExecutionResult(
                    success=False,
                    task_id=task.task_id,
                    attempts_used=attempt,
                    applied_patches=[],
                    test_results=test_history,
                    final_status="FAILED",
                    error=f"Max retries exhausted ({self.max_retries}) without passing test suite",
                    rolled_back=clean_rb,
                )

        except Exception as exc:
            logger.error(f"[AutonomousEngineeringLoop] Unhandled exception in loop: {exc}", exc_info=True)
            clean_rb = self._rollback_to_baseline(baseline_snapshot)
            return LoopExecutionResult(
                success=False,
                task_id=task.task_id,
                attempts_used=attempt,
                applied_patches=[],
                test_results=test_history,
                final_status="FAILED",
                error=f"Unhandled error: {exc}",
                rolled_back=clean_rb,
            )


__all__ = [
    "EngineeringTask",
    "LoopExecutionResult",
    "AutonomousEngineeringLoop",
]
