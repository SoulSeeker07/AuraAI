"""
Task Decomposer
Location: src/core/orchestration/task_decomposer.py

Decomposes goals into a Directed Acyclic Graph (DAG) of subtasks with capability tags.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class PlannerRole(str, Enum):
    """Role-based domain planner identifiers."""

    DESKTOP = "desktop"
    RESEARCH = "research"
    CODING = "coding"
    BROWSER = "browser"


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
    status: str = "pending"
    result: Any = None


@dataclass
class TaskGraph:
    """Directed Acyclic Graph (DAG) of subtasks representing a user goal."""

    goal: str
    subtasks: dict[str, SubTask] = field(default_factory=dict)
    execution_order: list[list[str]] = field(default_factory=list)

    def add_task(self, subtask: SubTask) -> None:
        self.subtasks[subtask.task_id] = subtask


class TaskDecomposer:
    """
    Decomposes user goals into structured subtasks with capability mappings.
    """

    def decompose(self, goal: str, decision: Any | None = None) -> TaskGraph:
        graph = TaskGraph(goal=goal)
        goal_lower = goal.lower()

        subtask_specs = self._analyze_goal_clauses(goal_lower, goal, decision)
        for spec in subtask_specs:
            graph.add_task(spec)

        self._compute_execution_levels(graph)
        logger.info(
            f"Decomposed goal into {len(graph.subtasks)} subtasks across {len(graph.execution_order)} levels."
        )
        return graph

    def _analyze_goal_clauses(
        self, goal_lower: str, raw_goal: str, decision: Any | None = None
    ) -> list[SubTask]:
        subtasks: list[SubTask] = []
        task_counter = 1

        intent_val = (
            getattr(decision, "intent_type", None).value
            if hasattr(getattr(decision, "intent_type", None), "value")
            else str(getattr(decision, "intent_type", ""))
        )

        if intent_val == "system_query":
            return [
                SubTask(
                    task_id="task_1",
                    title="Process System Query & Self Awareness",
                    required_role=PlannerRole.DESKTOP,
                    capability="system_info",
                    description=f"Provide system identity and capability response for: {raw_goal}",
                    dependencies=[],
                )
            ]

        if intent_val == "chat":
            return [
                SubTask(
                    task_id="task_1",
                    title="Process Conversational Chat",
                    required_role=PlannerRole.DESKTOP,
                    capability="chat",
                    description=f"Respond to chat message: {raw_goal}",
                    dependencies=[],
                )
            ]

        has_research = (intent_val == "research") or any(
            w in goal_lower
            for w in ["research", "search web", "look up", "find papers"]
        )
        has_coding = (intent_val == "coding") or any(
            w in goal_lower
            for w in [
                "update",
                "code",
                "modify",
                "implement",
                "refactor",
                "antigravity",
                "fix",
                "write report",
                "create report",
                "markdown",
            ]
        )
        has_browser = (intent_val == "browser") or any(
            w in goal_lower for w in ["browse", "web page", "navigate", "url", "site", "instagram", "github", "linkedin", "youtube"]
        )

        if has_browser and intent_val != "desktop_action":
            desktop_keywords = ["vs code", "vscode", "workspace", "notepad", "clipboard", "mute", "volume"]
            has_desktop = any(w in goal_lower for w in desktop_keywords)
        else:
            has_desktop = (intent_val == "desktop_action") or any(
                w in goal_lower
                for w in [
                    "open",
                    "launch",
                    "app",
                    "window",
                    "vs code",
                    "vscode",
                    "workspace",
                    "notepad",
                    "clipboard",
                    "mute",
                    "volume",
                ]
            )

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
                    description=f"Gather information for: {raw_goal}",
                    dependencies=[],
                )
            )
            prev_id = t_id

        if has_desktop:
            t_id = f"task_{task_counter}"
            task_counter += 1

            # Infer specific capability and app target from goal
            cap = "app_open"
            app_target = "application"
            title_text = f"Execute desktop action: {raw_goal}"

            import re
            m = re.search(r"\b(open|launch|start|run|close|minimize|restore|focus|activate|switch to)\s+([a-zA-Z0-9_\-\.\s]+)\b", goal_lower)
            if m:
                action_verb = m.group(1).lower()
                app_target = m.group(2).strip()

                if action_verb in ["open", "launch", "start", "run"]:
                    cap = "app_open"
                    title_text = f"Launch application: {app_target.title()}"
                elif action_verb in ["minimize"]:
                    cap = "window.minimize"
                    title_text = f"Minimize window for: {app_target.title()}"
                elif action_verb in ["close"]:
                    cap = "app_close"
                    title_text = f"Close application: {app_target.title()}"
                elif action_verb in ["restore", "focus", "activate", "switch to"]:
                    cap = "window.activate"
                    title_text = f"Focus window for: {app_target.title()}"

            subtasks.append(
                SubTask(
                    task_id=t_id,
                    title=title_text,
                    required_role=PlannerRole.DESKTOP,
                    capability=cap,
                    description=f"{title_text} ({raw_goal})",
                    parameters={"app_name": app_target, "goal": raw_goal},
                    dependencies=[],
                )
            )

        if has_browser and not has_research:
            # Multi-step goal-oriented browser decomposition
            t1_id = f"task_{task_counter}"
            task_counter += 1
            
            # Check if browser is already running from decision/world_state
            is_chrome_open = False
            if decision and hasattr(decision, "world_state") and isinstance(getattr(decision, "world_state"), dict):
                procs = decision.world_state.get("running_processes", [])
                is_chrome_open = any("chrome" in p for p in procs)

            subtasks.append(
                SubTask(
                    task_id=t1_id,
                    title="Ensure Browser Instance Active",
                    required_role=PlannerRole.BROWSER,
                    capability="browser.ensure_open",
                    description="Launch or verify browser instance",
                    dependencies=[],
                    status="skipped" if is_chrome_open else "pending",
                )
            )

            t2_id = f"task_{task_counter}"
            task_counter += 1
            subtasks.append(
                SubTask(
                    task_id=t2_id,
                    title="Navigate Target Site",
                    required_role=PlannerRole.BROWSER,
                    capability="browser.navigate",
                    description=f"Navigate to target URL for: {raw_goal}",
                    dependencies=[t1_id],
                )
            )

            t3_id = f"task_{task_counter}"
            task_counter += 1
            subtasks.append(
                SubTask(
                    task_id=t3_id,
                    title="Verify Authentication & Session",
                    required_role=PlannerRole.BROWSER,
                    capability="browser.check_auth",
                    description="Check login state and user session",
                    dependencies=[t2_id],
                )
            )

            t4_id = f"task_{task_counter}"
            task_counter += 1
            subtasks.append(
                SubTask(
                    task_id=t4_id,
                    title="Fulfill Page Goal",
                    required_role=PlannerRole.BROWSER,
                    capability="browser.navigate_goal",
                    description=f"Fulfill page goal for: {raw_goal}",
                    dependencies=[t3_id],
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
                    description="Implement code updates and generate artifacts",
                    dependencies=deps,
                )
            )

        return subtasks

    def _compute_execution_levels(self, graph: TaskGraph) -> None:
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
                current_level = list(remaining)

            levels.append(current_level)
            for t_id in current_level:
                completed.add(t_id)
                remaining.remove(t_id)

        graph.execution_order = levels
