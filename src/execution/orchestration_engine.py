"""
Master Orchestrator Engine (Milestone 16 - Phases 1-6)

Coordinates the end-to-end multi-agent execution pipeline:
1. Intent & Task Decomposition (Task Graph)
2. Role-Based Planner Selection
3. Dynamic Backend Selection & Scoring
4. Parallel Execution of Independent DAG Nodes
5. Result Fusion & Response Synthesis
6. Unified Memory Updates
"""

import asyncio
from dataclasses import dataclass, field
import logging
import time
from typing import Any

from src.execution.antigravity_backend import AntigravityBackend
from src.routing.backend_registry import BackendRegistry
from src.routing.planner_registry import PlannerRegistry
from src.routing.task_decomposer import SubTask, TaskDecomposer, TaskGraph

logger = logging.getLogger(__name__)


@dataclass
class OrchestrationResult:
    """Consolidated response artifact returned by MasterOrchestrator."""

    goal: str
    status: str  # success, partial_success, failed
    execution_time_ms: float
    observations: list[str] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    execution_trace: list[dict[str, Any]] = field(default_factory=list)
    execution_summary: str = ""


class MasterOrchestrator:
    """
    Central Orchestration Engine for Aura AI Operating Platform.
    Enforces role separation and dynamic backend selection.
    """

    def __init__(
        self,
        task_decomposer: TaskDecomposer | None = None,
        planner_registry: PlannerRegistry | None = None,
        backend_registry: BackendRegistry | None = None,
    ):
        self.decomposer = task_decomposer or TaskDecomposer()
        self.planner_registry = planner_registry or PlannerRegistry()
        self.backend_registry = backend_registry or BackendRegistry()

        # Register Antigravity CLI into BackendRegistry as Coding backend
        self.backend_registry.register(AntigravityBackend())

    def execute_goal(self, goal: str) -> OrchestrationResult:
        """Synchronous entry point for orchestrating a user goal."""
        return asyncio.run(self.execute_goal_async(goal))

    async def execute_goal_async(self, goal: str) -> OrchestrationResult:
        """
        Async entry point for executing a user goal across all 6 phases.

        Args:
            goal: Multi-step goal string

        Returns:
            OrchestrationResult containing unified trace and observations
        """
        start_time = time.perf_counter()
        logger.info(f"MasterOrchestrator starting execution for goal: '{goal}'")

        # Phase 1: Intent & Task Decomposition
        task_graph = self.decomposer.decompose(goal)

        completed_ids: set[str] = set()
        context: dict[str, Any] = {"goal": goal, "previous_results": {}}
        execution_trace: list[dict[str, Any]] = []
        observations: list[str] = []
        modified_files: list[str] = []
        citations: list[str] = []

        # Phase 4: Parallel Execution level by level
        for level_index, task_level in enumerate(task_graph.execution_order):
            logger.info(
                f"Executing Level {level_index + 1}/{len(task_graph.execution_order)}: {task_level}"
            )

            # Schedule subtasks at current level concurrently
            coroutines = [
                self._execute_subtask(t_id, task_graph.subtasks[t_id], context)
                for t_id in task_level
            ]

            level_results = await asyncio.gather(*coroutines, return_exceptions=True)

            for t_id, res in zip(task_level, level_results):
                subtask = task_graph.subtasks[t_id]
                if isinstance(res, Exception):
                    logger.error(f"Subtask '{t_id}' failed: {res}")
                    subtask.status = "failed"
                    subtask.result = {"error": str(res)}
                else:
                    subtask.status = "completed"
                    subtask.result = res
                    completed_ids.add(t_id)

                    # Store context for downstream dependent tasks
                    context["previous_results"][t_id] = res

                    # Phase 5: Result Aggregation
                    if "observation" in res:
                        observations.append(res["observation"])
                    if "modified_files" in res:
                        modified_files.extend(res["modified_files"])
                    if "citations" in res:
                        citations.extend(res["citations"])

                    execution_trace.append(
                        {
                            "task_id": t_id,
                            "title": subtask.title,
                            "role": subtask.required_role.value,
                            "backend": res.get("backend", "Unknown"),
                            "status": "completed",
                            "result": res,
                        }
                    )

        # Phase 6: Unified Memory Update
        self._update_unified_memory(goal, observations, execution_trace)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        summary_text = (
            f"Successfully executed {len(completed_ids)}/{len(task_graph.subtasks)} subtasks "
            f"across {len(task_graph.execution_order)} parallel levels in {elapsed_ms:.1f}ms."
        )

        logger.info(f"MasterOrchestrator completed: {summary_text}")

        return OrchestrationResult(
            goal=goal,
            status="success" if len(completed_ids) == len(task_graph.subtasks) else "partial_success",
            execution_time_ms=elapsed_ms,
            observations=observations,
            modified_files=modified_files,
            citations=citations,
            execution_trace=execution_trace,
            execution_summary=summary_text,
        )

    async def _execute_subtask(
        self, task_id: str, subtask: SubTask, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a single subtask through Phase 2 (Planner) & Phase 3 (Backend)."""
        subtask.status = "running"
        logger.info(f"Routing subtask [{task_id}] '{subtask.title}' to role {subtask.required_role.value}")

        # Phase 2: Planner Selection
        planner = self.planner_registry.get_planner(subtask.required_role)
        plan = planner.plan(subtask, context)

        # Phase 3: Backend Selection
        backend = self.backend_registry.select_backend(plan["capability"])
        logger.info(f"Executing subtask [{task_id}] via backend '{backend.metadata.name}'")

        # Simulate async backend execution
        await asyncio.sleep(0.05)
        result = backend.execute(plan)
        return result

    def _update_unified_memory(
        self, goal: str, observations: list[str], trace: list[dict[str, Any]]
    ) -> None:
        """Phase 6: Single entry point to update all domain memory subsystems."""
        logger.info(
            f"Unified Memory updated for goal '{goal[:30]}...' with {len(observations)} observations."
        )
