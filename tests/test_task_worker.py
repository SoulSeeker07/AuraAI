"""
Tests for M19.5 Generic TaskWorker & Scoped Profiles
Location: tests/test_task_worker.py
"""

import pytest
from core.orchestration.task_worker import (
    TaskWorker,
    ResearchProfile,
    TestProfile,
    WorkerResult,
)


def test_task_worker_allowed_tool_execution():
    worker = TaskWorker(worker_name="ResearchWorker", profile=ResearchProfile)

    def mock_callback(tool, params):
        return {"results": ["Candidate 1", "Candidate 2"]}

    res = worker.execute_task(
        task="Find playbooks",
        context={"tool": "web.search", "params": {"query": "python"}},
        coordinator_callback=mock_callback,
    )

    assert res.status == "SUCCESS"
    assert res.actions_taken == 1
    assert len(res.observations) == 1
    assert "Candidate 1" in res.observations[0]


def test_task_worker_forbidden_tool_guardrail():
    worker = TaskWorker(worker_name="ResearchWorker", profile=ResearchProfile)

    res = worker.execute_task(
        task="Edit code file",
        context={"tool": "code.edit", "params": {"file": "main.py"}},
    )

    assert res.status == "FAILED"
    assert "is forbidden for worker profile" in res.errors[0]
