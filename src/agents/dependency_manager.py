"""
Dependency Manager

Manages task dependencies and validation.
"""


import logging
from typing import List, Set, Dict, Any, Optional
from collections import defaultdict

from .execution_graph import ExecutionGraph
from .task import Task
from .models import TaskStatus


logger = logging.getLogger(__name__)


class DependencyManager:
    """
    Manages task dependencies and validation.

    The Dependency Manager ensures tasks execute in the correct order
    and validates dependency relationships.
    """

    def __init__(self, graph: ExecutionGraph):
        """
        Initialize dependency manager.

        Args:
            graph: Execution graph to manage
        """
        self.graph = graph
        self.resolved_dependencies: Dict[str, List[str]] = {}

        logger.debug(f"Initialized dependency manager for {len(graph.tasks)} tasks")

    def validate_dependencies(self) -> bool:
        """
        Validate all dependencies in the graph.

        Returns:
            True if all dependencies are valid
        """
        errors = []

        for task_id, task in self.graph.tasks.items():
            # Check for self-dependencies
            if task_id in task.dependencies:
                errors.append(
                    f"Task {task_id[:8]} depends on itself"
                )

            # Check if dependency tasks exist
            for dep_id in task.dependencies:
                if dep_id not in self.graph.tasks:
                    errors.append(
                        f"Task {task_id[:8]} depends on non-existent task {dep_id[:8]}"
                    )

                # Check if dependency is complete
                dep_task = self.graph.tasks[dep_id]
                if dep_task.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
                    errors.append(
                        f"Task {task_id[:8]} depends on incomplete task {dep_id[:8]}"
                    )

        if errors:
            for error in errors:
                logger.error(error)
            return False

        logger.debug("All dependencies validated successfully")
        return True

    def resolve_dependencies(self) -> Dict[str, List[str]]:
        """
        Resolve all dependencies into a hierarchical structure.

        Returns:
            Dictionary mapping task IDs to their dependencies
        """
        self.resolved_dependencies = {}

        for task_id, task in self.graph.tasks.items():
            self.resolved_dependencies[task_id] = self._get_all_dependencies(task_id)

        logger.debug(f"Resolved dependencies for {len(self.resolved_dependencies)} tasks")
        return self.resolved_dependencies

    def _get_all_dependencies(self, task_id: str, visited: Optional[Set[str]] = None) -> List[str]:
        """
        Get all direct and indirect dependencies for a task.

        Args:
            task_id: ID of task
            visited: Set of visited task IDs (for cycle detection)

        Returns:
            List of dependency task IDs
        """
        if visited is None:
            visited = set()

        # Prevent infinite recursion
        if task_id in visited:
            return []

        visited.add(task_id)
        dependencies = []

        # Get direct dependencies
        direct_deps = self.graph.get_task_dependencies(task_id)

        for dep_id in direct_deps:
            dependencies.append(dep_id)
            # Recursively get indirect dependencies
            dependencies.extend(self._get_all_dependencies(dep_id, visited))

        return dependencies

    def check_ready_tasks(self) -> List[Task]:
        """
        Get all tasks that are ready to execute.

        Returns:
            List of ready tasks
        """
        ready_tasks = []

        for task_id, task in self.graph.tasks.items():
            if self._is_task_ready(task):
                ready_tasks.append(task)

        return ready_tasks

    def _is_task_ready(self, task: Task) -> bool:
        """
        Check if a task is ready to execute.

        Args:
            task: Task to check

        Returns:
            True if task is ready
        """
        # Task must be created or queued
        if task.status not in [TaskStatus.CREATED, TaskStatus.QUEUED]:
            return False

        # All dependencies must be complete
        for dep_id in task.dependencies:
            dep_status = self.graph.metadata.get(f"dependency_{dep_id}", TaskStatus.QUEUED)
            if dep_status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
                return False

        return True

    def update_dependency_status(self, task_id: str, status: TaskStatus):
        """
        Update the status of a task's dependencies.

        Args:
            task_id: ID of task
            status: New status of the task
        """
        # Update task status in metadata
        self.graph.metadata[f"dependency_{task_id}"] = status

        # Check if any tasks become ready due to this update
        for dep_id, task in self.graph.tasks.items():
            if self._is_task_ready(task):
                logger.debug(f"Task {dep_id[:8]} is now ready")

    def get_dependency_chain(self, task_id: str) -> List[Task]:
        """
        Get the dependency chain leading to a task.

        Args:
            task_id: ID of task

        Returns:
            List of tasks in dependency chain
        """
        chain = []
        visited = set()

        def build_chain(tid: str):
            if tid in visited:
                return

            visited.add(tid)

            # Add task if it exists
            if tid in self.graph.tasks:
                chain.append(self.graph.tasks[tid])

            # Get dependencies
            for dep_id in self.graph.get_task_dependencies(tid):
                build_chain(dep_id)

        build_chain(task_id)
        return chain

    def get_critical_path(self) -> List[Task]:
        """
        Get the critical path (longest execution path) in the graph.

        Returns:
            List of tasks on the critical path
        """
        # Simple implementation - finds longest path from any start node
        critical_path = []

        # Get all independent tasks (no dependencies)
        independent = self.graph.get_independent_tasks()

        for task in independent:
            path = self._find_longest_path(task.task_id, set())
            if len(path) > len(critical_path):
                critical_path = path

        return critical_path

    def _find_longest_path(self, task_id: str, visited: set) -> List[Task]:
        """
        Find the longest path from a given task.

        Args:
            task_id: ID of starting task
            visited: Set of visited tasks

        Returns:
            Longest path as list of tasks
        """
        if task_id in visited:
            return []

        visited.add(task_id)
        path = [self.graph.tasks[task_id]]

        # Find the longest path through all dependencies
        longest_extension = []
        for dep_id in self.graph.get_task_dependencies(task_id):
            dep_path = self._find_longest_path(dep_id, visited.copy())
            if len(dep_path) > len(longest_extension):
                longest_extension = dep_path

        path.extend(longest_extension)
        return path

    def get_dependencies_summary(self) -> Dict[str, Any]:
        """
        Get a summary of dependencies.

        Returns:
            Summary dictionary
        """
        if not self.resolved_dependencies:
            self.resolve_dependencies()

        return {
            'total_tasks': len(self.graph.tasks),
            'dependency_count': sum(len(deps) for deps in self.resolved_dependencies.values()),
            'tasks_with_dependencies': sum(1 for deps in self.resolved_dependencies.values() if deps),
            'tasks_without_dependencies': sum(1 for deps in self.resolved_dependencies.values() if not deps)
        }

    def validate_no_cycles(self) -> bool:
        """
        Validate that the graph has no cycles.

        Returns:
            True if no cycles exist
        """
        return not self.graph.has_cycle()

    def check_cycles(self) -> List[List[str]]:
        """
        Find all cycles in the dependency graph.

        Returns:
            List of cycles (each cycle is a list of task IDs)
        """
        cycles = []
        visited = set()
        rec_stack = set()

        def visit(task_id: str, path: List[str]) -> None:
            if task_id in rec_stack:
                # Found a cycle
                cycle_start = path.index(task_id)
                cycle = path[cycle_start:]
                cycles.append(cycle)
                return

            if task_id in visited:
                return

            visited.add(task_id)
            rec_stack.add(task_id)
            path.append(task_id)

            for dep_id in self.graph.get_task_dependencies(task_id):
                visit(dep_id, path.copy())

            path.pop()
            rec_stack.remove(task_id)

        for task_id in self.graph.tasks:
            if task_id not in visited:
                visit(task_id, [])

        return cycles
