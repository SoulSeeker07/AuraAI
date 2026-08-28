"""
Gate G1 Automated Verification Suite — Workspace Staging, Protected Ceiling & Isolation
Location: tests/test_engineering_g1_isolation.py

Verifies:
- G1-1: Protected safety ceiling blocks security, governance, orchestration, and policy files.
- G1-2: Recursive glob patterns block arbitrary subdirectories under protected paths.
- G1-3: Self-modification of workspace policy and ceiling registry is strictly blocked.
- G1-4: Staging workspace creates isolated task directory.
- G1-5: Atomic OS-level repository lock prevents concurrent autonomous task execution.
- G1-6: WorkspacePolicy single-write gate authorizes valid writes and blocks traversal/ceiling violations.
- G1-7: RequestSource.AGENT_DELEGATED respects parent context autonomy floor.
"""

import asyncio
import os
import tempfile
from pathlib import Path
import pytest

from core.orchestration.request_source import RequestSource
from core.orchestration.execution_policy import ExecutionPolicy
from core.orchestration.autonomy_mode import AutonomyLevel
from engineering.safety_ceiling import (
    ProtectedCeilingViolation,
    RewardHackingViolation,
    is_path_protected,
    is_test_file,
    normalize_relative_path,
)
from engineering.workspace_policy import (
    WorkspacePolicy,
    WorkspaceTraversalError,
)
from engineering.staging_workspace import (
    StagingWorkspace,
    RepositoryLockError,
)


def test_protected_ceiling_blocks_security_files():
    """G1-1: Verifies safety-critical and orchestration files are recognized as protected."""
    protected_files = [
        "src/core/orchestration/execution_policy.py",
        "src/core/orchestration/master_orchestrator.py",
        "src/core/orchestration/request_source.py",
        "src/autonomy/trigger_scheduler.py",
        "src/daemon/governance.py",
        "core/aura_core.py",
        "AGENTS.md",
        "docs/SYSTEM_CONTRACT.md",
        "docs/technical_debt.md",
        "conftest.py",
        "pyproject.toml",
        "pytest.ini",
        ".env",
        "secrets.key",
    ]
    for p in protected_files:
        assert is_path_protected(p), f"Expected '{p}' to be protected by safety ceiling."

    non_protected_files = [
        "src/research/scraper.py",
        "src/engineering/code_editor.py",
        "src/personal_os/daily_context.py",
    ]
    for p in non_protected_files:
        assert not is_path_protected(p), f"Expected '{p}' NOT to be protected by safety ceiling."


def test_protected_ceiling_recursive_glob_subdirectories():
    """G1-2: Verifies recursive subdirectories under protected roots are blocked."""
    nested_protected = [
        "src/desktop/native/security/dacl_sandbox.py",
        "src/desktop/native/security/subpkg/deep_module.py",
        "src/security/crypto/keys.py",
        "src/security/audit/sink.py",
        "nested/sub/conftest.py",
        "config/production.env",
    ]
    for p in nested_protected:
        assert is_path_protected(p), f"Expected nested path '{p}' to be protected by recursive ceiling."


def test_protected_ceiling_blocks_write_gate_self_modification():
    """G1-3: Verifies workspace policy and safety ceiling cannot be edited autonomously."""
    assert is_path_protected("src/engineering/workspace_policy.py")
    assert is_path_protected("src/engineering/safety_ceiling.py")


def test_staging_workspace_lifecycle():
    """G1-4: Verifies staging workspace prepares task directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        staging = StagingWorkspace(task_id="test_001", repo_root=tmp_dir)
        with staging:
            assert staging.task_staging_path.exists()
            assert staging.task_staging_path.name == "task_test_001"
            assert staging._is_locked is True

        assert not staging.task_staging_path.exists()
        assert staging._is_locked is False


def test_single_task_repository_lock_concurrency():
    """G1-5: Verifies exclusive OS-level atomic lock prevents concurrent tasks."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        staging1 = StagingWorkspace(task_id="task_A", repo_root=tmp_dir)
        staging2 = StagingWorkspace(task_id="task_B", repo_root=tmp_dir)

        staging1.acquire_lock()
        try:
            assert staging1._is_locked is True
            # Second task must fail to acquire lock
            with pytest.raises(RepositoryLockError):
                staging2.acquire_lock()
        finally:
            staging1.release_lock()

        # After task 1 releases, task 2 can acquire lock
        staging2.acquire_lock()
        assert staging2._is_locked is True
        staging2.release_lock()


def test_workspace_policy_write_authorization_integration():
    """G1-6: Verifies WorkspacePolicy single write gate rules."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        policy = WorkspacePolicy(repo_root=tmp_dir)

        # 1. Traversal outside repo root is blocked
        with pytest.raises(WorkspaceTraversalError):
            policy.authorize_write("../outside.py", source=RequestSource.DAEMON_BACKGROUND)

        # 2. Autonomous edit to protected file is blocked
        with pytest.raises(ProtectedCeilingViolation):
            policy.authorize_write(
                "src/core/orchestration/execution_policy.py",
                source=RequestSource.DAEMON_BACKGROUND,
            )

        # 3. Autonomous edit to existing test file is blocked (RewardHackingViolation)
        with pytest.raises(RewardHackingViolation):
            policy.authorize_write(
                "tests/test_existing.py",
                source=RequestSource.DAEMON_BACKGROUND,
                task_type="BUG_FIX",
                is_new_file=False,
            )

        # 4. Autonomous addition of a net-new test file under ADD_TEST is permitted
        new_test = policy.authorize_write(
            "tests/test_new_feature.py",
            source=RequestSource.DAEMON_BACKGROUND,
            task_type="ADD_TEST",
            is_new_file=True,
        )
        assert new_test.name == "test_new_feature.py"

        # 5. Autonomous edit to normal source file is permitted
        valid_src = policy.authorize_write(
            "src/features/calc.py",
            source=RequestSource.DAEMON_BACKGROUND,
            task_type="BUG_FIX",
        )
        assert valid_src.name == "calc.py"

        # 6. Interactive human can author edits across files
        human_edit = policy.authorize_write(
            "src/core/orchestration/execution_policy.py",
            source=RequestSource.HUMAN_INTERACTIVE,
        )
        assert human_edit.name == "execution_policy.py"


@pytest.mark.asyncio
async def test_agent_delegated_request_source_floor_inheritance():
    """G1-7: Verifies RequestSource.AGENT_DELEGATED respects parent context autonomy in MasterOrchestrator."""
    policy = ExecutionPolicy.get_instance()
    
    # 1. In human context (default ASSISTED), AGENT_DELEGATED runs at ASSISTED
    assert policy.get_autonomy_level() == AutonomyLevel.ASSISTED
    
    # Verify MasterOrchestrator evaluates AGENT_DELEGATED without forcing floor override
    from core.orchestration.master_orchestrator import MasterOrchestrator
    orchestrator = MasterOrchestrator.__new__(MasterOrchestrator)

    observed_floor_human = None

    async def _mock_inner_human(**kwargs):
        nonlocal observed_floor_human
        observed_floor_human = policy.get_autonomy_level()
        # Verify skip_confirmation_intercept is False in human context
        assert kwargs.get("skip_confirmation_intercept") is False
        assert kwargs.get("source") == RequestSource.AGENT_DELEGATED

    orchestrator._process_request_async_inner = _mock_inner_human
    await orchestrator.process_request_async(
        goal_text="Test delegated task under human context",
        source=RequestSource.AGENT_DELEGATED,
    )
    assert observed_floor_human == AutonomyLevel.ASSISTED

    # 2. In autonomous daemon context (parent task set AUTONOMOUS ContextVar floor)
    token = policy.set_autonomy_level(AutonomyLevel.AUTONOMOUS)
    observed_floor_auto = None
    try:
        assert policy.get_autonomy_level() == AutonomyLevel.AUTONOMOUS

        async def _mock_inner_auto(**kwargs):
            nonlocal observed_floor_auto
            observed_floor_auto = policy.get_autonomy_level()
            # Verify skip_confirmation_intercept is True in autonomous context
            assert kwargs.get("skip_confirmation_intercept") is True
            assert kwargs.get("source") == RequestSource.AGENT_DELEGATED

        orchestrator._process_request_async_inner = _mock_inner_auto
        await orchestrator.process_request_async(
            goal_text="Test delegated task under autonomous context",
            source=RequestSource.AGENT_DELEGATED,
        )
        assert observed_floor_auto == AutonomyLevel.AUTONOMOUS
    finally:
        policy.reset_autonomy_level(token)

    # 3. ContextVar level properly restored
    assert policy.get_autonomy_level() == AutonomyLevel.ASSISTED
