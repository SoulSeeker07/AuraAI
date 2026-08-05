"""
Task Decomposer (Milestone 16 - Phase 1)

Decomposes complex, multi-intent user goals into a Directed Acyclic Graph (DAG)
of subtasks with explicit dependency links and required capability tags.
"""

from dataclasses import dataclass, field
from enum import Enum
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class PlannerRole(str, Enum):
    """Role-based domain planner identifiers."""

    DESKTOP = "desktop_planner"
    RESEARCH = "research_planner"
    CODING = "coding_planner"
    BROWSER = "browser_planner"


@dataclass
class SubTask:
    """Represents a single node in a Task Graph."""

    task_id: str
    title: str
    required_role: PlannerRole
    capability: str
    description: str = ""
    dependencies: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending, running, completed, failed
    result: Any = None


@dataclass
class TaskGraph:
    """Directed Acyclic Graph (DAG) of subtasks representing a user goal."""

    goal: str
    subtasks: dict[str, SubTask] = field(default_factory=dict)
    execution_order: list[list[str]] = field(default_factory=list)

    def add_task(self, subtask: SubTask) -> None:
        """Add a subtask to the graph."""
        self.subtasks[subtask.task_id] = subtask

    def get_ready_tasks(self, completed_ids: set[str]) -> list[SubTask]:
        """Get subtasks whose dependencies have all been completed."""
        ready = []
        for task in self.subtasks.values():
            if task.status == "pending":
                if all(dep in completed_ids for dep in task.dependencies):
                    ready.append(task)
        return ready


class TaskDecomposer:
    """
    Decomposes user goals into structured subtasks with capability mappings.
    Combines rule-based decomposition patterns with fallback logic.
    """

    def decompose(self, goal: str) -> TaskGraph:
        """
        Decompose a goal into a TaskGraph.

        Args:
            goal: User request string

        Returns:
            TaskGraph containing subtasks and dependency links
        """
        graph = TaskGraph(goal=goal)
        goal_lower = goal.lower()

        # Complex multi-step pattern detection (e.g. "Research Python 3.14, summarize, open VS Code, update files")
        subtask_specs = self._analyze_goal_clauses(goal_lower, goal)

        for spec in subtask_specs:
            graph.add_task(spec)

        self._compute_execution_levels(graph)
        logger.info(
            f"Decomposed goal into {len(graph.subtasks)} subtasks across {len(graph.execution_order)} execution levels."
        )
        return graph

    def _analyze_goal_clauses(self, goal_lower: str, raw_goal: str) -> list[SubTask]:
        """Parse clauses and detect required planner roles and dependencies."""
        subtasks: list[SubTask] = []
        task_counter = 1

        has_research = any(w in goal_lower for w in ["research", "search", "summarize", "find out", "look up"])
        has_desktop = any(w in goal_lower for w in ["open", "launch", "app", "window", "vs code", "vscode", "workspace"])
        has_coding = any(w in goal_lower for w in ["update", "code", "modify", "implement", "refactor", "antigravity", "fix", "write report", "create report", "markdown"])
        has_browser = any(w in goal_lower for w in ["browse", "web page", "navigate", "url", "site"])

        prev_id: str | None = None

        if has_research:
            t_id = f"task_{task_counter}"
            task_counter += 1
            subtasks.append(
                SubTask(
                    task_id=t_id,
                    title="Conduct Research & Gather Knowledge",
                    required_role=PlannerRole.RESEARCH,
                    capability="research",
                    description=f"Gather and summarize information for: {raw_goal}",
                    dependencies=[],
                )
            )
            prev_id = t_id

        if has_desktop:
            t_id = f"task_{task_counter}"
            task_counter += 1
            subtasks.append(
                SubTask(
                    task_id=t_id,
                    title="Prepare Desktop Environment",
                    required_role=PlannerRole.DESKTOP,
                    capability="desktop",
                    description="Open specified applications or workspace",
                    dependencies=[],  # Independent of research; can run in parallel!
                )
            )

        if has_browser and not has_research:
            t_id = f"task_{task_counter}"
            task_counter += 1
            subtasks.append(
                SubTask(
                    task_id=t_id,
                    title="Browse Web Context",
                    required_role=PlannerRole.BROWSER,
                    capability="browser",
                    description="Navigate and extract web information",
                    dependencies=[],
                )
            )

        if has_coding or (not subtasks):
            t_id = f"task_{task_counter}"
            task_counter += 1
            deps = [prev_id] if prev_id else []
            subtasks.append(
                SubTask(
                    task_id=t_id,
                    title="Execute Code Changes & Synthesis",
                    required_role=PlannerRole.CODING,
                    capability="coding",
                    description="Implement code updates and generate final artifacts",
                    dependencies=deps,
                )
            )

        return subtasks

    def _compute_execution_levels(self, graph: TaskGraph) -> None:
        """Partition subtasks into parallel execution levels (topological sort)."""
        completed: set[str] = set()
        remaining = set(graph.subtasks.keys())
        levels: list[list[str]] = []

        while remaining:
            current_level = []
            for t_id in list(remaining):
                subtask = graph.subtasks[t_id]
                if all(dep in completed for dep in subtask.dependencies):
                    current_level.append(t_id)

            if not current_level:
                # Cycle or unresolvable dependency fallback
                current_level = list(remaining)

            levels.append(current_level)
            for t_id in current_level:
                completed.add(t_id)
                remaining.remove(t_id)

        graph.execution_order = levels
