"""
Execution Graph

Represents a Directed Acyclic Graph (DAG) of tasks to be executed.
"""

import logging
from collections import defaultdict
from typing import Any

from .goal import Goal
from .models import TaskStatus
from .task import Task

logger = logging.getLogger(__name__)


class ExecutionGraph:
    """
    A Directed Acyclic Graph (DAG) for task execution.

    The Execution Graph manages task dependencies and determines
    the order in which tasks should be executed, enabling
    parallel execution of independent tasks.
    """

    def __init__(self, goal: Goal):
        """
        Initialize execution graph.

        Args:
            goal: Parent goal
        """
        self.goal = goal
        self.tasks: dict[str, Task] = {}
        self.adjacency: dict[str, set[str]] = defaultdict(
            set
        )  # task_id -> dependent task_ids
        self.reverse_adjacency: dict[str, set[str]] = defaultdict(
            set
        )  # task_id -> predecessor task_ids
        self.execution_order: list[str] = []
        self.execution_time: float = 0.0

        logger.debug(f"Created execution graph for goal {goal.goal_id[:8]}")

    def add_task(self, task: Task):
        """
        Add a task to the graph.

        Args:
            task: Task to add
        """
        if task.task_id in self.tasks:
            logger.warning(f"Task {task.task_id[:8]} already exists, skipping")
            return

        self.tasks[task.task_id] = task

        # Add dependencies
        for dep_id in task.dependencies:
            self.add_dependency(task.task_id, dep_id)

        logger.debug(f"Added task {task.task_id[:8]} to graph")

    def add_dependency(self, dependent_id: str, dependency_id: str):
        """
        Add a dependency relationship.

        Args:
            dependent_id: ID of task that depends on another task
            dependency_id: ID of task that must complete first
        """
        if dependency_id not in self.tasks:
            logger.warning(f"Dependency task {dependency_id[:8]} not found")
            return

        self.adjacency[dependent_id].add(dependency_id)
        self.reverse_adjacency[dependency_id].add(dependent_id)
        logger.debug(f"Added dependency: {dependency_id[:8]} -> {dependent_id[:8]}")

    def remove_task(self, task_id: str):
        """
        Remove a task and its dependencies from the graph.

        Args:
            task_id: ID of task to remove
        """
        if task_id not in self.tasks:
            logger.warning(f"Task {task_id[:8]} not found")
            return

        # Remove from adjacency lists
        for dependent_id in self.adjacency[task_id]:
            self.reverse_adjacency[dependent_id].discard(task_id)
        for predecessor_id in self.reverse_adjacency[task_id]:
            self.adjacency[predecessor_id].discard(task_id)

        # Remove task
        del self.tasks[task_id]
        del self.adjacency[task_id]
        del self.reverse_adjacency[task_id]

        logger.debug(f"Removed task {task_id[:8]} from graph")

    def get_ready_tasks(self) -> list[Task]:
        """
        Get all tasks that are ready to execute.

        Returns:
            List of ready tasks
        """
        ready_tasks = []

        for task_id, task in self.tasks.items():
            if task.is_ready and not task.is_complete:
                ready_tasks.append(task)

        return ready_tasks

    def get_independent_tasks(self) -> list[Task]:
        """
        Get all tasks with no dependencies.

        Returns:
            List of independent tasks
        """
        independent = []

        for task_id, task in self.tasks.items():
            if not self.reverse_adjacency[task_id] and not task.is_complete:
                independent.append(task)

        return independent

    def get_tasks_by_status(self, status: TaskStatus) -> list[Task]:
        """
        Get tasks by status.

        Args:
            status: Status to filter by

        Returns:
            List of tasks with matching status
        """
        return [task for task in self.tasks.values() if task.status == status]

    def get_all_dependencies(self, task_id: str) -> list[str]:
        """
        Get all direct and indirect dependencies for a task.

        Args:
            task_id: ID of task

        Returns:
            List of dependency task IDs
        """
        dependencies = []
        visited = set()

        def get_dependencies(tid: str):
            if tid in visited:
                return

            visited.add(tid)
            dependencies.append(tid)

            for dep_id in self.adjacency[tid]:
                get_dependencies(dep_id)

        get_dependencies(task_id)
        return dependencies

    def has_cycle(self) -> bool:
        """
        Check if graph contains a cycle.

        Returns:
            True if cycle exists, False otherwise
        """
        visited = set()
        rec_stack = set()

        def visit(task_id: str) -> bool:
            if task_id in visited:
                return False

            visited.add(task_id)
            rec_stack.add(task_id)

            for dep_id in self.adjacency[task_id]:
                if dep_id in rec_stack:
                    return True
                if visit(dep_id):
                    return True

            rec_stack.remove(task_id)
            return False

        for task_id in self.tasks:
            if task_id not in visited:
                if visit(task_id):
                    return True

        return False

    def topological_sort(self) -> list[str]:
        """
        Perform topological sort to get execution order.

        Returns:
            List of task IDs in execution order
        """
        if self.has_cycle():
            logger.error("Execution graph contains a cycle")
            self.execution_order = []
            return []

        # Kahn's algorithm
        in_degree = defaultdict(int)
        for task_id in self.tasks:
            in_degree[task_id] = len(self.reverse_adjacency[task_id])

        queue = [task_id for task_id in self.tasks if in_degree[task_id] == 0]
        result = []

        while queue:
            task_id = queue.pop(0)
            result.append(task_id)

            for dependent_id in self.adjacency[task_id]:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    queue.append(dependent_id)

        self.execution_order = result
        logger.debug(f"Topological sort complete: {len(result)} tasks")

        return result

    def get_parallel_execution_groups(self) -> list[list[Task]]:
        """
        Get tasks that can execute in parallel.

        Returns:
            List of task groups where each group can execute simultaneously
        """
        parallel_groups = []
        processed = set()

        # Get independent tasks
        independent = self.get_independent_tasks()

        for task in independent:
            if task.task_id in processed:
                continue

            # Find all tasks that can execute with this task
            group = [task]
            group_ids = {task.task_id}

            # Check if dependent tasks can also execute
            for dependent_id in self.adjacency[task.task_id]:
                dependent_task = self.tasks[dependent_id]
                if not dependent_task.is_complete and all(
                    dep.task_id in group_ids
                    for dep in self.get_all_dependencies(dependent_id)
                ):
                    group.append(dependent_task)
                    group_ids.add(dependent_id)

            parallel_groups.append(group)
            processed.update(group_ids)

        logger.debug(f"Found {len(parallel_groups)} parallel execution groups")
        return parallel_groups

    def get_task_dependencies(self, task_id: str) -> list[str]:
        """
        Get direct dependencies for a task.

        Args:
            task_id: ID of task

        Returns:
            List of dependency task IDs
        """
        return list(self.adjacency[task_id])

    def get_execution_summary(self) -> dict[str, Any]:
        """
        Get execution graph summary.

        Returns:
            Summary dictionary
        """
        return {
            "total_tasks": len(self.tasks),
            "completed_tasks": sum(
                1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED
            ),
            "failed_tasks": sum(
                1 for t in self.tasks.values() if t.status == TaskStatus.FAILED
            ),
            "running_tasks": sum(
                1 for t in self.tasks.values() if t.status == TaskStatus.RUNNING
            ),
            "ready_tasks": len(self.get_ready_tasks()),
            "parallel_groups": len(self.get_parallel_execution_groups()),
            "has_cycle": self.has_cycle(),
            "execution_order": len(self.execution_order),
        }

    def to_dict(self) -> dict[str, Any]:
        """
        Convert graph to dictionary.

        Returns:
            Graph as dictionary
        """
        return {
            "goal_id": self.goal.goal_id,
            "tasks": [task.to_dict() for task in self.tasks.values()],
            "execution_order": self.execution_order,
            "parallel_groups": len(self.get_parallel_execution_groups()),
        }

    @classmethod
    def from_goal(cls, goal: Goal) -> "ExecutionGraph":
        """
        Create execution graph from goal and tasks.

        Args:
            goal: Goal to create graph for

        Returns:
            ExecutionGraph instance
        """
        graph = cls(goal)

        for task in goal.tasks:
            graph.add_task(task)

        return graph
