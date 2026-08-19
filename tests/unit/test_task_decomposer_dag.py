"""
Unit Tests for TaskDecomposer Execution Level Computation & Cycle Detection
Location: tests/unit/test_task_decomposer_dag.py
"""

import pytest
from core.orchestration.task_decomposer import (
    PlannerRole,
    SubTask,
    TaskDecomposer,
    TaskGraph,
)


def test_task_graph_valid_parallel_stages():
    """Verify valid multi-stage DAG correctly groups parallel subtasks."""
    graph = TaskGraph(goal="Multi-stage Fan-Out")
    
    # Level 1: Producer
    graph.add_task(SubTask(
        task_id="task_1",
        title="Research",
        required_role=PlannerRole.RESEARCH,
        capability="research.search",
        dependencies=[],
    ))
    # Level 2: 3 parallel consumers depending on task_1
    graph.add_task(SubTask(
        task_id="task_2",
        title="Coding",
        required_role=PlannerRole.CODING,
        capability="code.edit",
        dependencies=["task_1"],
    ))
    graph.add_task(SubTask(
        task_id="task_3",
        title="Browser",
        required_role=PlannerRole.BROWSER,
        capability="browser.navigate",
        dependencies=["task_1"],
    ))
    graph.add_task(SubTask(
        task_id="task_4",
        title="Desktop UIA",
        required_role=PlannerRole.DESKTOP,
        capability="app_open",
        dependencies=["task_1"],
    ))

    decomposer = TaskDecomposer()
    decomposer._compute_execution_levels(graph)

    assert len(graph.execution_order) == 2
    assert graph.execution_order[0] == ["task_1"]
    assert set(graph.execution_order[1]) == {"task_2", "task_3", "task_4"}


def test_task_graph_fail_closed_on_cyclic_dependency():
    """Verify cycle detection raises ValueError and lists stuck tasks."""
    graph = TaskGraph(goal="Cyclic Goal")
    graph.add_task(SubTask(
        task_id="task_a",
        title="A",
        required_role=PlannerRole.CODING,
        capability="code.edit",
        dependencies=["task_b"],
    ))
    graph.add_task(SubTask(
        task_id="task_b",
        title="B",
        required_role=PlannerRole.CODING,
        capability="code.edit",
        dependencies=["task_a"],
    ))

    decomposer = TaskDecomposer()
    with pytest.raises(ValueError, match="Cyclic or unresolvable dependencies detected"):
        decomposer._compute_execution_levels(graph)


def test_task_graph_fail_closed_on_missing_dependency():
    """Verify unresolvable missing dependency raises ValueError."""
    graph = TaskGraph(goal="Missing Dep Goal")
    graph.add_task(SubTask(
        task_id="task_1",
        title="Consumer",
        required_role=PlannerRole.CODING,
        capability="code.edit",
        dependencies=["non_existent_task"],
    ))

    decomposer = TaskDecomposer()
    with pytest.raises(ValueError, match="Cyclic or unresolvable dependencies detected"):
        decomposer._compute_execution_levels(graph)
