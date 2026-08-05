"""
Unit tests for MasterOrchestrator (Milestone 16 Phases 1-6).
"""

import pytest
from src.execution.orchestration_engine import MasterOrchestrator


def test_master_orchestrator_end_to_end():
    orchestrator = MasterOrchestrator()
    goal = "Research Python 3.14 changes, summarize them, open my VS Code project, create a markdown report, and ask Antigravity to update the affected files."

    result = orchestrator.execute_goal(goal)

    assert result.status == "success"
    assert len(result.execution_trace) >= 3
    assert len(result.observations) >= 2
    assert "PYTHON_3_14_RELEASE_NOTES.md" in result.modified_files

    # Verify backends executed in trace
    backends_used = [t["backend"] for t in result.execution_trace]
    assert "Antigravity CLI" in backends_used
    assert "Native Desktop Engine" in backends_used
