"""
Unit tests for TaskDecomposer (Cognitive Orchestration Layer).
"""

from core.orchestration.task_decomposer import PlannerRole, TaskDecomposer


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


def test_implicit_app_type_decomposition():
    decomposer = TaskDecomposer()
    goal = "type test successful in notepad"

    graph = decomposer.decompose(goal)

    assert len(graph.subtasks) == 2
    task1 = graph.subtasks["task_1"]
    task2 = graph.subtasks["task_2"]

    assert task1.capability == "app_open"
    assert task1.parameters["app_name"] == "notepad"

    assert task2.capability == "keyboard.type"
    assert task2.parameters["text"] == "test successful"
    assert task2.dependencies == ["task_1"]


from unittest.mock import MagicMock

def test_single_clause_intent_gating():
    decomposer = TaskDecomposer()
    decision = MagicMock()
    decision.intent_type.value = "coding"
    
    # Even though "calculator" and "app" are in the text, it should trust the coding intent
    goal = "create a python calculator app"
    
    graph = decomposer.decompose(goal, decision=decision)
    
    # Should only have one coding task, no desktop task
    assert len(graph.subtasks) == 1
    task = list(graph.subtasks.values())[0]
    assert task.required_role == PlannerRole.CODING

def test_multi_clause_mixed_intent():
    decomposer = TaskDecomposer()
    decision = MagicMock()
    decision.intent_type.value = "coding"
    
    # Coding intent globally, but second clause is clearly desktop
    goal = "create a python calculator app and open the file explorer"
    
    graph = decomposer.decompose(goal, decision=decision)
    
    # Should have two tasks: coding, and desktop (app_open)
    assert len(graph.subtasks) == 2
    roles = [t.required_role for t in graph.subtasks.values()]
    assert PlannerRole.CODING in roles
    assert PlannerRole.DESKTOP in roles
