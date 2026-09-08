"""
Unit tests for GoalState and GoalStore persistence.
Location: tests/unit/test_goal_store.py
"""

import sqlite3
import pytest
from core.orchestration.goal_state import Goal, GoalStatus, Step, StepStatus
from core.orchestration.goal_store import GoalStore, MAX_OBSERVATION_LENGTH
from core.orchestration.orchestration_store import OrchestrationStore


@pytest.fixture
def temp_db(tmp_path):
    """Provides a fresh, isolated SQLite database path."""
    return tmp_path / "test_Memory.db"


@pytest.fixture
def goal_store(temp_db):
    """Provides a GoalStore connected to a temporary database."""
    return GoalStore(db_path=temp_db)


def test_schema_and_no_fk_to_orchestration_sessions(goal_store, temp_db):
    """
    Assert that goals table does NOT require session_id to exist in orchestration_sessions.
    Interactive caller sessions (sess_gui_..., sess_voice_...) must insert cleanly.
    """
    with goal_store.store._get_connection() as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        # Verify orchestration_sessions is completely empty
        row = conn.execute("SELECT COUNT(*) as cnt FROM orchestration_sessions;").fetchone()
        assert row["cnt"] == 0

    # Creating a goal with an arbitrary interactive session_id must succeed
    goal = Goal.new(session_id="sess_gui_test999", user_prompt="test prompt")
    goal_store.create_goal(goal)

    retrieved = goal_store.get_goal(goal.goal_id)
    assert retrieved is not None
    assert retrieved.goal_id == goal.goal_id
    assert retrieved.session_id == "sess_gui_test999"
    assert retrieved.user_prompt == "test prompt"
    assert retrieved.status == GoalStatus.ACTIVE


def test_goal_steps_fk_and_cascade_delete(goal_store):
    """
    Assert that goal_steps has a foreign key to goals and cascades on delete.
    """
    goal = Goal.new(session_id="sess_voice_123", user_prompt="do something")
    goal_store.create_goal(goal)

    step1 = Step.new(goal_id=goal.goal_id, tool_name="web_search", tool_args={"query": "test"})
    step2 = Step.new(goal_id=goal.goal_id, tool_name=None, tool_args={}, status=StepStatus.VERIFIED)
    goal_store.add_step(step1)
    goal_store.add_step(step2)

    # Hydrated goal should contain 2 steps
    retrieved = goal_store.get_goal(goal.goal_id)
    assert len(retrieved.steps) == 2
    assert retrieved.steps[0].tool_name == "web_search"
    assert retrieved.steps[0].tool_args == {"query": "test"}
    assert retrieved.steps[1].tool_name is None
    assert retrieved.steps[1].status == StepStatus.VERIFIED

    # Cascade delete verification
    with goal_store.store._lock, goal_store.store._get_connection() as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("DELETE FROM goals WHERE goal_id = ?;", (goal.goal_id,))
        conn.commit()

    steps = goal_store.get_steps_for_goal(goal.goal_id)
    assert len(steps) == 0


def test_goal_lifecycle_and_session_filtering(goal_store):
    """
    Test updating goal status and listing goals filtered by session.
    """
    g1 = Goal.new(session_id="sess_gui_aaa", user_prompt="first task")
    g2 = Goal.new(session_id="sess_gui_aaa", user_prompt="second task")
    g3 = Goal.new(session_id="sess_voice_bbb", user_prompt="voice task")

    goal_store.create_goal(g1)
    goal_store.create_goal(g2)
    goal_store.create_goal(g3)

    # Update g1 status
    goal_store.update_goal_status(g1.goal_id, GoalStatus.DONE)
    retrieved_g1 = goal_store.get_goal(g1.goal_id)
    assert retrieved_g1.status == GoalStatus.DONE

    # List for sess_gui_aaa
    gui_goals = goal_store.list_goals_for_session("sess_gui_aaa")
    assert len(gui_goals) == 2
    assert [g.goal_id for g in gui_goals] == [g1.goal_id, g2.goal_id]

    # List for sess_voice_bbb
    voice_goals = goal_store.list_goals_for_session("sess_voice_bbb")
    assert len(voice_goals) == 1
    assert voice_goals[0].goal_id == g3.goal_id


def test_step_observation_truncation(goal_store):
    """
    Confirm large observations are truncated to MAX_OBSERVATION_LENGTH to prevent DB bloat.
    """
    goal = Goal.new(session_id="sess_gui_large", user_prompt="heavy tool output")
    goal_store.create_goal(goal)

    huge_output = "X" * (MAX_OBSERVATION_LENGTH + 500)
    step = Step.new(
        goal_id=goal.goal_id,
        tool_name="terminal_run_command",
        tool_args={"cmd": "cat bigfile"},
        observation=huge_output,
        status=StepStatus.OBSERVED,
    )
    goal_store.add_step(step)

    stored_steps = goal_store.get_steps_for_goal(goal.goal_id)
    assert len(stored_steps) == 1
    assert len(stored_steps[0].observation) <= MAX_OBSERVATION_LENGTH + 50
    assert stored_steps[0].observation.endswith("[TRUNCATED]")

    # Also test update_step_status truncation
    huge_update = "Y" * (MAX_OBSERVATION_LENGTH + 500)
    goal_store.update_step_status(
        step.step_id,
        status=StepStatus.VERIFIED,
        observation=huge_update,
        verify_reason="output checked",
    )
    updated_steps = goal_store.get_steps_for_goal(goal.goal_id)
    assert updated_steps[0].status == StepStatus.VERIFIED
    assert updated_steps[0].verify_reason == "output checked"
    assert updated_steps[0].observation.endswith("[TRUNCATED]")
