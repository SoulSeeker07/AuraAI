"""
Unit tests for TaskDecomposer (Cognitive Orchestration Layer).
"""

from src.core.orchestration.task_decomposer import PlannerRole, TaskDecomposer


def test_task_decomposition_multi_intent():
    decomposer = TaskDecomposer()
    goal = "Research Python 3.14 changes, summarize them, open my VS Code project, and ask Antigravity to update affected files."

    graph = decomposer.decompose(goal)

    assert len(graph.subtasks) >= 3
    assert len(graph.execution_order) >= 2

    roles = [subtask.required_role for subtask in graph.subtasks.values()]
    assert PlannerRole.RESEARCH in roles
    assert PlannerRole.DESKTOP in roles
    assert PlannerRole.CODING in roles


def test_task_graph_execution_levels():
    decomposer = TaskDecomposer()
    goal = "Research Python 3.14, open VS Code, and update code."

    graph = decomposer.decompose(goal)
    level_1 = graph.execution_order[0]

    assert len(level_1) >= 2
