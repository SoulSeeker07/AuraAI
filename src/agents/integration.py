"""
Integration Framework - Coordinates multiple agents.

The Integration Framework handles:
- Multi-agent task coordination
- Agent communication and coordination
- Complex task dependencies
- Agent workflow orchestration
- Result aggregation
- Error handling and fallbacks
"""

from __future__ import annotations

from typing import Any, List, Optional, Dict
import asyncio
from dataclasses import dataclass
from enum import Enum

from .task_model import (
    Task,
    TaskStatus,
    TaskType,
    TaskPriority
)
from .agent_registry import AgentRegistry, AgentCapability


class CoordinationStrategy(Enum):
    """Strategies for coordinating agents."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HYBRID = "hybrid"


@dataclass
class AgentCoordination:
    """Represents coordination of agents."""
    agents: List[Any]
    tasks: List[Task]
    strategy: CoordinationStrategy
    dependencies: List[tuple[int, int]]  # List of (task_index, depends_on_task_index)
    timeout: int = 300


class AgentCoordinator:
    """
    Coordinates multiple agents for complex tasks.

    Features:
    - Multi-agent task coordination
    - Parallel and sequential execution
    - Task dependency management
    - Result aggregation
    - Error handling and fallbacks
    """

    def __init__(self, registry: AgentRegistry):
        """
        Initialize the coordinator.

        Args:
            registry: AgentRegistry instance
        """
        self._registry = registry
        self._callbacks = []

    def register_callback(self, callback):
        """Register a callback for coordination events."""
        self._callbacks.append(callback)

    def _notify_callback(self, event_type: str, data: dict):
        """Notify all callbacks of an event."""
        for callback in self._callbacks:
            try:
                callback(event_type, data)
            except Exception:
                pass

    async def coordinate_agents(self, coordination: AgentCoordination) -> Dict[str, Any]:
        """
        Coordinate multiple agents to complete tasks.

        Args:
            coordination: AgentCoordination configuration

        Returns:
            Coordination results
        """
        try:
            self._notify_callback("start", {
                "strategy": coordination.strategy.value,
                "agent_count": len(coordination.agents),
                "task_count": len(coordination.tasks),
                "dependencies": len(coordination.dependencies)
            })

            if coordination.strategy == CoordinationStrategy.SEQUENTIAL:
                return await self._execute_sequential(coordination)
            elif coordination.strategy == CoordinationStrategy.PARALLEL:
                return await self._execute_parallel(coordination)
            else:  # HYBRID
                return await self._execute_hybrid(coordination)

        except Exception as e:
            self._notify_callback("error", {"error": str(e)})
            return {
                "success": False,
                "error": str(e),
                "tasks_completed": 0,
                "tasks_failed": 0
            }

    async def _execute_sequential(self, coordination: AgentCoordination) -> Dict[str, Any]:
        """Execute tasks sequentially."""
        results = []
        failed_tasks = []

        for i, task in enumerate(coordination.tasks):
            self._notify_callback("task_start", {"task_index": i, "task": task})

            # Wait for dependencies
            for dep in coordination.dependencies:
                if dep[1] == i and dep[0] < i:
                    # Task depends on previous task
                    if not results[dep[0]]["success"]:
                        failed_tasks.append(i)
                        break

            if i in failed_tasks:
                results.append({
                    "success": False,
                    "task_index": i,
                    "error": "Dependency failed"
                })
                continue

            # Execute task
            result = await self._execute_task(i, task)
            results.append(result)

            if not result["success"]:
                failed_tasks.append(i)

            self._notify_callback("task_complete", {
                "task_index": i,
                "success": result["success"]
            })

        return {
            "success": len(failed_tasks) == 0,
            "strategy": "sequential",
            "tasks_completed": len(results) - len(failed_tasks),
            "tasks_failed": len(failed_tasks),
            "results": results
        }

    async def _execute_parallel(self, coordination: AgentCoordination) -> Dict[str, Any]:
        """Execute tasks in parallel."""
        results = {}
        failed_tasks = set()

        # Create tasks
        async_tasks = []

        for i, task in enumerate(coordination.tasks):
            async_tasks.append(self._execute_task(i, task))

        # Execute all tasks concurrently
        try:
            completed = await asyncio.gather(
                *async_tasks,
                return_exceptions=True
            )

            for i, result in enumerate(completed):
                if isinstance(result, Exception):
                    results[i] = {"success": False, "error": str(result)}
                    failed_tasks.add(i)
                else:
                    results[i] = result

        except Exception as e:
            return {
                "success": False,
                "strategy": "parallel",
                "error": str(e),
                "tasks_completed": len(results),
                "tasks_failed": len(failed_tasks)
            }

        return {
            "success": len(failed_tasks) == 0,
            "strategy": "parallel",
            "tasks_completed": len(results) - len(failed_tasks),
            "tasks_failed": len(failed_tasks),
            "results": results
        }

    async def _execute_hybrid(self, coordination: AgentCoordination) -> Dict[str, Any]:
        """Execute tasks using hybrid strategy."""
        # Group tasks by dependency
        task_groups = self._group_tasks_by_dependencies(coordination)

        all_results = {}
        failed_tasks = set()

        # Execute each group
        for group_index, group_tasks in enumerate(task_groups):
            group_results = await self._execute_sequential(
                AgentCoordination(
                    agents=coordination.agents,
                    tasks=group_tasks,
                    strategy=CoordinationStrategy.SEQUENTIAL,
                    timeout=coordination.timeout
                )
            )

            # Update results
            for task in group_tasks:
                if not group_results["results"][task]["success"]:
                    failed_tasks.add(task)

            all_results.update(group_results["results"])

        return {
            "success": len(failed_tasks) == 0,
            "strategy": "hybrid",
            "groups_executed": len(task_groups),
            "tasks_completed": len(coordination.tasks) - len(failed_tasks),
            "tasks_failed": len(failed_tasks),
            "results": all_results
        }

    def _group_tasks_by_dependencies(self, coordination: AgentCoordination) -> List[List[int]]:
        """Group tasks by dependencies."""
        if not coordination.dependencies:
            # No dependencies, all in one group
            return [list(range(len(coordination.tasks)))]

        groups = []
        remaining_tasks = set(range(len(coordination.tasks)))

        while remaining_tasks:
            # Find tasks with no dependencies
            group = []
            for task_idx in remaining_tasks:
                deps = [d[0] for d in coordination.dependencies if d[1] == task_idx]
                if not deps or not any(d in remaining_tasks for d in deps):
                    group.append(task_idx)

            if not group:
                # Circular dependency detected
                break

            groups.append(group)

            # Remove these tasks from remaining
            remaining_tasks.difference_update(group)

        return groups

    async def _execute_task(self, task_index: int, task: Task) -> Dict[str, Any]:
        """Execute a single task."""
        try:
            # Find suitable agent
            agent = self._registry.find_agent_for_task(task)

            if not agent:
                return {
                    "success": False,
                    "task_index": task_index,
                    "error": "No suitable agent found for task"
                }

            # Instantiate agent
            agent_instance = agent.instantiate()

            # Execute task
            result = agent_instance.execute_task(task)

            return {
                "success": result.success,
                "task_index": task_index,
                "message": result.message,
                "data": result.data,
                "error": result.error
            }

        except Exception as e:
            return {
                "success": False,
                "task_index": task_index,
                "error": str(e)
            }

    def aggregate_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregate results from multiple agent executions.

        Args:
            results: List of task results

        Returns:
            Aggregated result
        """
        successful = sum(1 for r in results if r.get("success"))
        failed = len(results) - successful

        return {
            "success": failed == 0,
            "total_tasks": len(results),
            "successful_tasks": successful,
            "failed_tasks": failed,
            "task_results": results
        }

    def resolve_dependencies(self, tasks: List[Task], dependencies: List[tuple[int, int]]) -> List[List[Task]]:
        """
        Resolve task dependencies into execution order.

        Args:
            tasks: List of tasks
            dependencies: List of (task_index, depends_on_task_index)

        Returns:
            List of task groups
        """
        return self._group_tasks_by_dependencies(
            AgentCoordination(
                agents=[],
                tasks=tasks,
                strategy=CoordinationStrategy.SEQUENTIAL,
                dependencies=dependencies
            )
        )


# Helper function for simple multi-agent task execution
async def execute_multi_agent_task(
    task: Task,
    registry: AgentRegistry,
    coordination_strategy: CoordinationStrategy = CoordinationStrategy.SEQUENTIAL,
    timeout: int = 300
) -> Dict[str, Any]:
    """
    Execute a task using a coordinated multi-agent approach.

    Args:
        task: Task to execute
        registry: AgentRegistry instance
        coordination_strategy: Strategy for coordination
        timeout: Timeout in seconds

    Returns:
        Execution result
    """
    coordinator = AgentCoordinator(registry)

    coordination = AgentCoordination(
        agents=[],
        tasks=[task],
        strategy=coordination_strategy,
        timeout=timeout
    )

    return await coordinator.coordinate_agents(coordination)
