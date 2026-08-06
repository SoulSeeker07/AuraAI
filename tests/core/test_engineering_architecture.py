"""
Unit Tests for Software Engineering Architecture Evolution & Worker Management
Location: tests/core/test_engineering_architecture.py
"""

import asyncio
from pathlib import Path

import pytest

from src.core.backends.adapters.validation_workers import GitDiffWorker, PytestWorker
from src.core.orchestration.engineering_session import (
    EngineeringSession,
    EngineeringSessionStatus,
    WorkerState,
)
from src.core.orchestration.software_engineering_supervisor import (
    SoftwareEngineeringSupervisor,
)
from src.core.orchestration.worker_manager import DomainWorker, WorkerManager


def test_engineering_session_lifecycle():
    session = EngineeringSession(goal="Create hello.py", workspace="D:/AuraAI")
    assert session.status == EngineeringSessionStatus.RUNNING
    assert session.progress == 0

    session.update_progress(50, "Modifying hello.py...")
    assert session.progress == 50
    assert session.current_action == "Modifying hello.py..."

    session.add_modified_file("src/hello.py")
    assert "src/hello.py" in session.modified_files

    session.pause()
    assert session.status == EngineeringSessionStatus.PAUSED

    session.resume()
    assert session.status == EngineeringSessionStatus.RUNNING

    session.mark_completed("Successfully created hello.py")
    assert session.status == EngineeringSessionStatus.COMPLETED
    assert session.progress == 100


def test_worker_manager_registration_and_status():
    wm = WorkerManager()
    wm._workers.clear()
    wm._active_sessions["engineering"].clear()

    session = EngineeringSession(goal="Test Task", workspace="D:/AuraAI")
    wm.register_engineering_session(session)

    active = wm.list_active_workers(domain="engineering")
    assert len(active) == 1
    assert active[0].domain == "engineering"

    summary = wm.get_status_summary()
    assert "Active Workers (1)" in summary
    assert "Test Task" in summary

    paused = wm.pause_domain("engineering")
    assert paused is True
    assert session.status == EngineeringSessionStatus.PAUSED

    resumed = wm.resume_domain("engineering")
    assert resumed is True
    assert session.status == EngineeringSessionStatus.RUNNING

    cancelled = wm.cancel_worker("1")
    assert cancelled is True


@pytest.mark.asyncio
async def test_software_engineering_supervisor_execution(tmp_path):
    supervisor = SoftwareEngineeringSupervisor(workspace=tmp_path)
    session = await supervisor.execute_engineering_goal("Add hello.py in project root")

    assert session.goal == "Add hello.py in project root"
    assert session.status in (
        EngineeringSessionStatus.COMPLETED,
        EngineeringSessionStatus.FAILED,
    )
    assert len(session.workers) >= 3
    assert any(w.name == "Antigravity CLI" for w in session.workers)
