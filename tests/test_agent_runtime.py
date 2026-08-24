"""
Agent Runtime Integration Tests

Tests for the complete Agent Runtime system.
"""

from datetime import timedelta
from enum import Enum

import pytest

from agents.agent_runtime import AgentRuntime
from agents.execution_graph import ExecutionGraph
from agents.goal import Goal, GoalPriority, GoalStatus
from agents.planner import Planner
from agents.scheduler import ExecutionStrategy, Scheduler
from agents.task import (
    ApprovalRequired,
    RetryPolicy,
    Task,
    TaskPriority,
    TaskRiskLevel,
    TaskStatus,
)


class TestGoalModel:
    """Tests for Goal model."""

    def test_goal_creation(self):
        """Test goal creation."""
        goal = Goal(
            description="Test goal",
            priority=GoalPriority.NORMAL,
            estimated_total_duration=timedelta(minutes=10),
        )

        assert goal.description == "Test goal"
        assert goal.goal_id is not None
        assert goal.status == GoalStatus.CREATED
        assert len(goal.tasks) == 0

    def test_goal_progress(self):
        """Test goal progress calculation."""
        goal = Goal("Test goal", estimated_steps=5)

        # Initially 0 progress
        assert goal.progress == 0.0

        # After adding tasks
        task1 = Task("Task 1")
        task2 = Task("Task 2")
        goal.add_task(task1)
        goal.add_task(task2)
        assert goal.progress == 0.0

        task1.status = TaskStatus.COMPLETED
        assert goal.progress == 0.5

    def test_goal_add_task(self):
        """Test adding tasks to goal."""
        goal = Goal("Test goal", estimated_steps=3)

        task1 = Task("Task 1")
        task2 = Task("Task 2")
        task3 = Task("Task 3")

        goal.add_task(task1)
        goal.add_task(task2)
        goal.add_task(task3)

        assert len(goal.tasks) == 3
        assert task1.parent_goal_id == goal.goal_id
        assert task2.parent_goal_id == goal.goal_id
        assert task3.parent_goal_id == goal.goal_id


class TestTaskModel:
    """Tests for Task model."""

    def test_task_creation(self):
        """Test task creation."""
        task = Task(
            goal="Analyze files",
            task_type="file_operation",
            priority=TaskPriority.HIGH,
            estimated_duration=timedelta(minutes=5),
        )

        assert task.goal == "Analyze files"
        assert task.task_type == "file_operation"
        assert task.priority == TaskPriority.HIGH
        assert task.task_id is not None
        assert task.status == TaskStatus.CREATED
        assert task.dependencies == []

    def test_task_dependencies(self):
        """Test task dependencies."""
        task1 = Task("Task 1")
        task2 = Task("Task 2", dependencies=[task1.task_id])
        task3 = Task("Task 3", dependencies=[task1.task_id, task2.task_id])

        assert task2.is_ready
        assert not task3.is_ready

    def test_task_complete(self):
        """Test task completion."""
        task = Task("Test task")

        task.mark_started()
        task.mark_completed("Task done")

        assert task.status == TaskStatus.COMPLETED
        assert task.output == "Task done"
        assert task.completed_at is not None
        assert task.duration is not None

    def test_task_failure(self):
        """Test task failure."""
        task = Task("Test task")

        task.mark_started()
        task.mark_failed("Task failed")

        assert task.status == TaskStatus.FAILED
        assert task.error == "Task failed"

    def test_task_retry(self):
        """Test task retry policy."""
        task = Task(
            "Test task", retry_policy=RetryPolicy.RETRY_WITH_BACKOFF, max_retries=3
        )

        assert task.should_retry
        assert task.retry_count == 0

        task.mark_failed("Failed")
        assert not task.should_retry

        task.retry_count = 2
        assert task.should_retry

        task.retry_count = 3
        assert not task.should_retry


class TestExecutionGraph:
    """Tests for Execution Graph."""

    def test_graph_creation(self):
        """Test execution graph creation."""
        goal = Goal("Test goal", estimated_steps=2)
        task1 = Task("Task 1")
        task2 = Task("Task 2")

        goal.add_task(task1)
        goal.add_task(task2)

        graph = ExecutionGraph(goal)

        assert len(graph.tasks) == 2
        assert task1.task_id in graph.tasks
        assert task2.task_id in graph.tasks

    def test_task_dependencies(self):
        """Test adding dependencies."""
        goal = Goal("Test goal")
        task1 = Task("Task 1")
        task2 = Task("Task 2")
        task3 = Task("Task 3", dependencies=[task1.task_id, task2.task_id])

        graph = ExecutionGraph(goal)
        graph.add_task(task1)
        graph.add_task(task2)
        graph.add_task(task3)

        graph.add_dependency(task3.task_id, task1.task_id)
        graph.add_dependency(task3.task_id, task2.task_id)

        assert task3.task_id in graph.adjacency
        assert len(graph.adjacency[task3.task_id]) == 2

    def test_parallel_execution_groups(self):
        """Test parallel execution groups."""
        goal = Goal("Test goal")
        task1 = Task("Task 1")
        task2 = Task("Task 2")
        task3 = Task("Task 3", dependencies=[task1.task_id])

        graph = ExecutionGraph(goal)
        graph.add_task(task1)
        graph.add_task(task2)
        graph.add_task(task3)

        groups = graph.get_parallel_execution_groups()

        # Task 1 and 2 can execute in parallel
        assert len(groups) >= 1

    def test_topological_sort(self):
        """Test topological sort."""
        goal = Goal("Test goal")
        task1 = Task("Task 1")
        task2 = Task("Task 2", dependencies=[task1.task_id])
        task3 = Task("Task 3", dependencies=[task1.task_id, task2.task_id])

        graph = ExecutionGraph(goal)
        graph.add_task(task1)
        graph.add_task(task2)
        graph.add_task(task3)

        order = graph.topological_sort()

        assert task1.task_id in order
        assert task2.task_id in order
        assert task3.task_id in order

        # Task 1 should come before Task 2 and 3
        task1_idx = order.index(task1.task_id)
        task2_idx = order.index(task2.task_id)
        task3_idx = order.index(task3.task_id)

        assert task1_idx < task2_idx
        assert task1_idx < task3_idx

    def test_no_cycles(self):
        """Test cycle detection."""
        goal = Goal("Test goal")
        task1 = Task("Task 1")
        task2 = Task("Task 2", dependencies=[task1.task_id])
        task3 = Task("Task 3", dependencies=[task2.task_id])
        task4 = Task("Task 4", dependencies=[task3.task_id])

        graph = ExecutionGraph(goal)
        graph.add_task(task1)
        graph.add_task(task2)
        graph.add_task(task3)
        graph.add_task(task4)

        # Add cycle
        graph.add_dependency(task1.task_id, task4.task_id)

        assert graph.has_cycle()


class TestPlanner:
    """Tests for Planner."""

    def test_planner_creation(self):
        """Test planner creation."""
        planner = Planner()

        assert planner.on_plan_generated is not None

    def test_plan_general_task(self):
        """Test planning general task."""
        goal = Goal("Test general task", estimated_steps=1)
        planner = Planner()

        graph = planner.plan_goal(goal)

        assert len(graph.tasks) == 1
        assert graph.tasks[goal.tasks[0].task_id].goal == "Test general task"

    def test_plan_git_operation(self):
        """Test planning git operation."""
        goal = Goal("Commit all changes and push", estimated_steps=1)
        planner = Planner()

        graph = planner.plan_goal(goal)

        assert len(graph.tasks) >= 2  # Analyze, create backup, execute
        task_types = [t.task_type for t in graph.tasks.values()]
        assert "git_operation" in task_types

    def test_plan_file_operation(self):
        """Test planning file operation."""
        goal = Goal("Create backup of project files", estimated_steps=1)
        planner = Planner()

        graph = planner.plan_goal(goal)

        assert len(graph.tasks) >= 2  # Analyze, execute
        task_types = [t.task_type for t in graph.tasks.values()]
        assert "file_operation" in task_types


class TestAgentRuntime:
    """Tests for Agent Runtime."""

    def test_agent_creation(self):
        """Test agent creation."""
        runtime = AgentRuntime()

        assert runtime.is_running is False
        assert runtime.current_goal is None
        assert runtime.planner is not None
        assert runtime.scheduler is not None

    def test_create_goal(self):
        """Test creating a goal."""
        runtime = AgentRuntime()
        goal_id = runtime.create_goal("Test goal")

        assert goal_id is not None
        assert isinstance(goal_id, str)
        assert len(goal_id) > 0

    def test_plan_goal(self):
        """Test planning a goal."""
        runtime = AgentRuntime()
        goal_id = runtime.create_goal("Test goal")
        success = runtime.plan_goal(goal_id)

        assert success
        assert runtime.execution_graph is not None
        assert len(runtime.execution_graph.tasks) > 0

    def test_execute_goal(self):
        """Test executing a goal."""
        runtime = AgentRuntime()
        goal_id = runtime.create_goal("Test goal")
        runtime.plan_goal(goal_id)

        # Mock task execution
        original_execute = runtime.scheduler._run_task
        runtime.scheduler._run_task = lambda t: f"Result for {t.goal}"

        success = runtime.execute_goal(goal_id)

        assert success
        assert runtime.is_running is True

        # Wait for completion
        runtime.scheduler.wait_for_completion()

        # Cleanup
        runtime.scheduler.shutdown()

    def test_pause_goal(self):
        """Test pausing a goal."""
        runtime = AgentRuntime()
        goal_id = runtime.create_goal("Test goal")
        runtime.plan_goal(goal_id)

        success = runtime.execute_goal(goal_id)

        assert success
        assert runtime.is_running is True

        # Pause
        paused = runtime.pause_goal(goal_id)
        assert paused
        assert runtime.is_running is False

    def test_cancel_goal(self):
        """Test canceling a goal."""
        runtime = AgentRuntime()
        goal_id = runtime.create_goal("Test goal")
        runtime.plan_goal(goal_id)

        success = runtime.execute_goal(goal_id)

        assert success
        assert runtime.is_running is True

        # Cancel
        cancelled = runtime.cancel_goal(goal_id)
        assert cancelled
        assert runtime.is_running is False

    def test_get_statistics(self):
        """Test getting runtime statistics."""
        runtime = AgentRuntime()
        goal_id = runtime.create_goal("Test goal")
        runtime.plan_goal(goal_id)

        stats = runtime.get_statistics()

        assert "is_running" in stats
        assert "current_goal_id" in stats
        assert "execution_graph" in stats
        assert "scheduler_stats" in stats


class TestApprovalManager:
    """Tests for Approval Manager."""

    def test_approval_required(self):
        """Test approval requirement check."""
        manager = ApprovalManager()

        # High risk always requires approval
        assert manager.requires_approval(TaskRiskLevel.CRITICAL, "delete")

        # High risk for critical types requires approval
        assert manager.requires_approval(TaskRiskLevel.HIGH, "delete_file")

        # Low risk doesn't require approval
        assert not manager.requires_approval(TaskRiskLevel.LOW, "read_file")

    def test_request_approval(self):
        """Test approval request."""
        granted = [False]

        def callback(manager, description, risk, required_by, approval_id):
            granted[0] = True
            return True

        manager = ApprovalManager(on_approval_request=callback)
        approved = manager.request_approval(
            approval_id="test_approval",
            task_id="test_task",
            task_description="Test operation",
            risk_level="CRITICAL",
            required_by="TestManager",
        )

        assert granted[0]
        assert approved

    def test_statistics(self):
        """Test approval statistics."""
        manager = ApprovalManager()

        manager.request_approval("test1", "t1", "desc1", "CRITICAL", "mgr1")
        manager.request_approval("test2", "t2", "desc2", "MEDIUM", "mgr2")
        manager.grant_approval("test1")
        manager.deny_approval("test2", "Too risky")

        stats = manager.get_statistics()

        assert stats["total_approvals_requested"] == 2
        assert stats["total_approvals_granted"] == 1
        assert stats["total_approvals_denied"] == 1


class TestRecoveryManager:
    """Tests for Recovery Manager."""

    def test_determine_recovery_action(self):
        """Test recovery action determination."""
        manager = RecoveryManager()

        # Network error should retry
        task = Task("Test task", retry_policy=RetryPolicy.DEFAULT)
        task.error = "Network timeout"
        action = manager._determine_recovery_action(task)
        assert action == "retry"

        # File error should pause
        task.error = "Permission denied"
        action = manager._determine_recovery_action(task)
        assert action == "pause"

        # Too many retries should continue
        task.retry_count = 3
        task.max_retries = 3
        action = manager._determine_recovery_action(task)
        assert action == "continue"

    def test_statistics(self):
        """Test recovery statistics."""
        manager = RecoveryManager()

        # Simulate failures
        task1 = Task("Task 1")
        task1.error = "Network error"
        manager.handle_task_failure(task1)

        task2 = Task("Task 2")
        task2.error = "File error"
        manager.handle_task_failure(task2)

        stats = manager.get_statistics()

        assert stats["total_failures"] == 2
        assert stats["total_recovered"] == 1  # One retry
        assert stats["total_permanently_failed"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
