"""
Software Engineering Supervisor
Location: src/core/orchestration/software_engineering_supervisor.py

Dedicated domain supervisor for software engineering execution:
- Receives high-level decomposition goals from CodingPlanner
- Manages persistent EngineeringSession lifecycle
- Spawns and coordinates AntigravityWorker alongside PytestWorker and GitDiffWorker
- Updates telemetry and handles retry loops
- Exposes pause/resume/cancel controls
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from ..backends.adapters.antigravity_backend import AntigravityBackendAdapter
from ..backends.adapters.validation_workers import GitDiffWorker, PytestWorker
from .artifact import Artifact
from .engineering_session import (
    EngineeringSession,
    EngineeringSessionStatus,
    WorkerState,
)
from .observation import Observation
from .worker_manager import WorkerManager

logger = logging.getLogger(__name__)


class SoftwareEngineeringSupervisor:
    """
    Supervisor responsible for executing, monitoring, and validating
    software engineering tasks via long-running worker sessions.
    """

    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or Path.cwd()
        self.worker_manager = WorkerManager.get_instance()
        self.antigravity_adapter = AntigravityBackendAdapter()

    async def execute_engineering_goal(
        self, goal: str, parameters: dict[str, Any] | None = None
    ) -> EngineeringSession:
        """
        Launch and supervise a software engineering goal across worker processes.
        """
        params = parameters or {}
        session = EngineeringSession(
            goal=goal,
            workspace=str(self.workspace),
            status=EngineeringSessionStatus.RUNNING,
            progress=5,
            current_action="Initializing Software Engineering Supervisor...",
        )

        # Register workers with initial state
        session.workers = [
            WorkerState(
                worker_id=f"{session.session_id}_antigravity",
                name="Antigravity CLI",
                worker_type="AntigravityWorker",
                status="RUNNING",
                current_action="Inspecting workspace repository...",
                progress=10,
            ),
            WorkerState(
                worker_id=f"{session.session_id}_pytest",
                name="Pytest Runner",
                worker_type="PytestWorker",
                status="IDLE",
                current_action="Waiting for code changes...",
                progress=0,
            ),
            WorkerState(
                worker_id=f"{session.session_id}_git",
                name="Git Tracker",
                worker_type="GitDiffWorker",
                status="IDLE",
                current_action="Monitoring repository diffs...",
                progress=0,
            ),
        ]

        self.worker_manager.register_engineering_session(session)
        logger.info(
            f"SoftwareEngineeringSupervisor: Started session {session.session_id} for goal: '{goal}'"
        )

        # Step 1: Pre-execution Git check
        session.update_progress(15, "Inspecting repository and modified files...")
        git_worker = GitDiffWorker(self.workspace)
        initial_files = await git_worker.get_modified_files()

        session.add_observation(
            Observation(
                obs_type="coding",
                source="SoftwareEngineeringSupervisor",
                content=f"Initialized engineering session {session.session_id}. Workspace: {self.workspace}",
            )
        )

        # Step 2: Execute Antigravity backend adapter
        session.update_progress(35, "Executing code changes via Antigravity Worker...")
        result = self.antigravity_adapter.execute(
            capability=params.get("capability", "code.modify"),
            goal=goal,
            arguments=params,
        )

        # Record modifications
        if hasattr(result, "data") and isinstance(result.data, dict):
            modified = result.data.get("modified_files", [])
            for f in modified:
                session.add_modified_file(f)

        session.update_progress(
            70, "Running asynchronous validation tests (pytest & git status)..."
        )

        # Step 3: Run Validation Workers asynchronously
        pytest_worker = PytestWorker(self.workspace)
        pytest_res, updated_git_files = await asyncio.gather(
            pytest_worker.run_tests(),
            git_worker.get_modified_files(),
        )

        for f in updated_git_files:
            session.add_modified_file(f)

        session.update_tests(
            passed=pytest_res.get("passed", 0),
            failed=pytest_res.get("failed", 0),
            total=pytest_res.get("total", 0),
            skipped=pytest_res.get("skipped", 0),
        )

        # Step 4: Finalize Session State
        if result.success and pytest_res.get("failed", 0) == 0:
            session.mark_completed(
                f"Successfully implemented goal: '{goal}'. {len(session.modified_files)} file(s) modified."
            )
            session.add_artifact(
                Artifact(
                    artifact_id=f"art_{session.session_id}",
                    artifact_type="markdown",
                    creator="SoftwareEngineeringSupervisor",
                    mime_type="text/markdown",
                    metadata={"summary": session.get_summary()},
                )
            )

        else:
            session.mark_failed(
                f"Validation reported issues. Pytest failures: {pytest_res.get('failed', 0)}"
            )

        logger.info(
            f"SoftwareEngineeringSupervisor: Completed session {session.session_id} with status {session.status.value}"
        )
        return session
