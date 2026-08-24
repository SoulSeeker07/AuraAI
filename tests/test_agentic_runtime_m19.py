"""
M19 — Agentic Runtime & Workspace Intelligence End-to-End Test Suite
Location: tests/test_agentic_runtime_m19.py
"""

import pytest
import asyncio
from pathlib import Path

from brain.execution_coordinator import ExecutionCoordinator
from brain.goal_verifier import GoalVerifier
from core.orchestration.autonomy_mode import (
    AutonomyLevel,
    ActionRisk,
    classify_action_risk,
    should_require_confirmation,
)
from core.orchestration.execution_policy import ExecutionPolicy, PolicyAction
from core.orchestration.runtime_checkpoint import (
    RuntimeCheckpointManager,
    ActionReversibility,
)
from core.orchestration.task_worker import TaskWorker, ResearchProfile
from core.capabilities.capability_registry import CapabilityRegistry
from workspace.workspace_instruction_loader import WorkspaceInstructionLoader


@pytest.mark.asyncio
async def test_full_agentic_runtime_e2e(tmp_path):
    # 1. Workspace Instruction Loader (AURA.md)
    aura_file = tmp_path / "AURA.md"
    aura_file.write_text(
        "# Aura Project Instructions\n## Safety\nRequire confirmation for high-risk actions.\n",
        encoding="utf-8",
    )
    loader = WorkspaceInstructionLoader(workspace_root=tmp_path)
    instructions = loader.load_instructions()
    assert "Require confirmation" in instructions["raw_text"]

    # 2. Autonomy Policy Gate
    policy = ExecutionPolicy()
    policy.set_autonomy_level(AutonomyLevel.ASSISTED)
    assert should_require_confirmation(AutonomyLevel.ASSISTED, ActionRisk.HIGH) is True
    decision = policy.evaluate_action("filesystem", "file.delete", {"path": "important.doc"})
    assert decision.action == PolicyAction.ASK_USER

    # 3. Hybrid Checkpoint Creation
    db_file = tmp_path / "test_memory.db"
    cp_mgr = RuntimeCheckpointManager(db_path=db_file)
    cp = cp_mgr.create_checkpoint(
        session_id="sess_e2e",
        goal="Search YouTube",
        step_id=1,
        reversibility=ActionReversibility.REVERSIBLE,
    )
    assert cp.checkpoint_id is not None
    loaded_cp = cp_mgr.load_last_checkpoint("sess_e2e")
    assert loaded_cp.checkpoint_id == cp.checkpoint_id

    # 4. Scoped TaskWorker Execution
    worker = TaskWorker(worker_name="ResearchWorker", profile=ResearchProfile)
    w_res = worker.execute_task(
        task="Find Python playbooks",
        context={"tool": "web.search", "params": {"query": "python"}},
        coordinator_callback=lambda tool, params: "Found 5 candidates",
    )
    assert w_res.status == "SUCCESS"

    # 5. Capability Discovery
    cap_reg = CapabilityRegistry.get_instance()
    caps = cap_reg.discover()
    assert any(c.name == "filesystem.read" for c in caps)

    # 6. ExecutionCoordinator + GoalVerifier Integration
    coordinator = ExecutionCoordinator()

    def mock_browser_callback(action, params):
        return {
            "success": True,
            "observations": ["Navigated to YouTube", "Search completed"],
            "data": {
                "observation": {
                    "state": "search_results",
                    "evidence": {"url": "https://youtube.com/results", "text_content": "Candidates found"},
                },
                "verification_report": {"passed": True},
            },
        }

    coordinator.register_engine("browser", mock_browser_callback)

    execution_map = {
        "goal": "Search YouTube for Python tutorials",
        "steps": [
            {"engine": "browser", "action": "search", "parameters": {"query": "Python tutorials"}}
        ],
    }

    coord_result = await coordinator.coordinate(execution_map)
    assert coord_result.success is True
    assert "goal_verification" in coord_result.data
    assert coord_result.data["goal_verification"]["passed"] is True

    # Render Activity Trace (Levels 1, 2, 3)
    compact_trace = coord_result.render_trace(level=1)
    summary_trace = coord_result.render_trace(level=2)
    full_trace = coord_result.render_trace(level=3)

    assert "Worked for" in compact_trace
    assert "Engines: Browser" in summary_trace
    assert "Goal Verify : ✓ VERIFIED PASS" in full_trace
