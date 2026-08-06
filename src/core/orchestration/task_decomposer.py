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
    MEMORY = "memory"


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
    input_artifacts: list[str] = field(default_factory=list)
    output_artifacts: list[str] = field(default_factory=list)
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
        # Check if this is a multi-stage research + persistence + launch task, which shouldn't be split
        is_multi_stage = (
            any(w in goal_lower for w in ["research", "search web", "look up", "find papers"])
            and any(w in goal_lower for w in ["save", "create", "write", "summary"])
            and any(w in goal_lower for w in ["open", "launch", "in vs code", "in notepad", "in code"])
        )

        # Check if the goal contains multiple sequential clauses separated by "and" or ";"
        # Example: "open notepad and type hello world"
        if not is_multi_stage and (" and " in goal_lower or "; " in goal_lower):
            import re
            parts = re.split(r'\band\b|;', raw_goal, flags=re.IGNORECASE)
            valid_clauses = []
            for p in parts:
                p_clean = p.strip()
                if any(v in p_clean.lower() for v in ["open", "launch", "start", "run", "close", "minimize", "type", "write", "search", "navigate", "focus", "activate", "bring"]):
                    valid_clauses.append(p_clean)
            
            if len(valid_clauses) > 1:
                decomposed_tasks = []
                prev_task_id = None
                task_counter = 1
                for idx, clause in enumerate(valid_clauses):
                    clause_lower = clause.lower()
                    clause_tasks = self._analyze_goal_clauses_single(clause_lower, clause, decision)
                    for t in clause_tasks:
                        t.task_id = f"task_{task_counter}"
                        task_counter += 1
                        if prev_task_id:
                            t.dependencies = [prev_task_id]
                        prev_task_id = t.task_id
                        decomposed_tasks.append(t)
                return decomposed_tasks

        return self._analyze_goal_clauses_single(goal_lower, raw_goal, decision)

    def _analyze_goal_clauses_single(
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

        if intent_val in ["memory", "memory_write", "memory_recall"]:
            cap = getattr(decision, "capability", "memory_write") if decision else "memory_write"
            # Fallback if capability not set cleanly
            if cap == "memory" or not cap:
                cap = "memory_read" if any(w in goal_lower for w in ["recall", "what is", "retrieve", "tell me", "do you"]) else "memory_write"
            title = "Recall Facts from Memory" if cap == "memory_read" else "Remember Facts in Memory"
            return [
                SubTask(
                    task_id="task_1",
                    title=title,
                    required_role=PlannerRole.MEMORY,
                    capability=cap,
                    description=raw_goal,
                    dependencies=[],
                )
            ]

        has_research = (intent_val == "research") or any(
            w in goal_lower
            for w in ["research", "search web", "look up", "find papers"]
        )
        has_coding = (intent_val == "coding") or (
            intent_val not in ["desktop_action", "browser", "system_query", "chat"]
            and any(
                w in goal_lower
                for w in [
                    "refactor",
                    "antigravity",
                    "fix bug",
                    "write code",
                    "modify code",
                    "implement feature",
                    "unit test",
                    "git commit",
                ]
            )
        )
        has_browser = (intent_val == "browser") or any(
            w in goal_lower
            for w in [
                "browse",
                "web page",
                "navigate",
                "url",
                "site",
                "instagram",
                "github",
                "linkedin",
                "youtube",
            ]
        )

        if has_browser and intent_val != "desktop_action":
            desktop_keywords = [
                "vs code",
                "vscode",
                "workspace",
                "notepad",
                "clipboard",
                "mute",
                "volume",
            ]
            has_desktop = any(w in goal_lower for w in desktop_keywords)
        else:
            import re
            desktop_patterns = [
                r"\bopen\b",
                r"\blaunch\b",
                r"\bapp\b",
                r"\bwindow\b",
                r"\btype\b",
                r"\bwrite\b",
                r"\bvs\s*code\b",
                r"\bvscode\b",
                r"\bworkspace\b",
                r"\bnotepad\b",
                r"\bclipboard\b",
                r"\bmute\b",
                r"\bvolume\b",
            ]
            has_desktop = (intent_val == "desktop_action") or any(
                re.search(pat, goal_lower) for pat in desktop_patterns
            )

        # Check for multi-stage research -> document -> persist -> open DAG
        if (
            has_research
            and any(w in goal_lower for w in ["save", "create", "write", "summary"])
            and any(w in goal_lower for w in ["open", "launch", "in vs code", "in notepad", "in code"])
        ):
            import re

            m_file = re.search(
                r"['\"]([a-zA-Z]:[\\/][^'\"]+\.[a-zA-Z0-9]+|[^'\"]+\.[a-zA-Z0-9]+)['\"]",
                raw_goal,
            )
            target_file_name = (
                m_file.group(1) if m_file else "python_release_summary.md"
            )

            target_app = "code"
            if "notepad" in goal_lower:
                target_app = "notepad"
            elif "vs code" in goal_lower or "vscode" in goal_lower or "code" in goal_lower:
                target_app = "code"

            t1_id = f"task_{task_counter}"
            task_counter += 1
            t2_id = f"task_{task_counter}"
            task_counter += 1
            t3_id = f"task_{task_counter}"
            task_counter += 1
            t4_id = f"task_{task_counter}"
            task_counter += 1

            # Stage 1: Research — produces raw structured research data
            t1 = SubTask(
                task_id=t1_id,
                title="Conduct Research & Synthesize Knowledge",
                required_role=PlannerRole.RESEARCH,
                capability="research",
                description=f"Gather information for: {raw_goal}",
                output_artifacts=["art_research_data"],
            )
            # Stage 2: Document Generation — transforms research into markdown
            t2 = SubTask(
                task_id=t2_id,
                title="Generate Markdown Document from Research",
                required_role=PlannerRole.DESKTOP,
                capability="document.generate",
                description=f"Transform research data into formatted markdown document: {target_file_name}",
                input_artifacts=["art_research_data"],
                output_artifacts=["art_markdown_doc"],
                parameters={"format": "markdown", "target_filename": target_file_name},
                dependencies=[t1_id],
            )
            # Stage 3: File Persistence — writes markdown content to disk
            t3 = SubTask(
                task_id=t3_id,
                title=f"Persist Artifact: {target_file_name}",
                required_role=PlannerRole.DESKTOP,
                capability="file.create",
                description=f"Save markdown document as '{target_file_name}'",
                input_artifacts=["art_markdown_doc"],
                output_artifacts=["art_saved_file"],
                parameters={"file_path": target_file_name, "goal": raw_goal},
                dependencies=[t2_id],
            )
            # Stage 4: Open in Application — launches the saved file
            t4 = SubTask(
                task_id=t4_id,
                title=f"Open Artifact in {target_app.title()}: {target_file_name}",
                required_role=PlannerRole.DESKTOP,
                capability="app_open",
                description=f"Open artifact '{target_file_name}' using {target_app.title()}",
                input_artifacts=["art_saved_file"],
                parameters={
                    "app_name": target_app,
                    "file_path": target_file_name,
                    "target_file": target_file_name,
                    "goal": raw_goal,
                },
                dependencies=[t3_id],
            )
            return [t1, t2, t3, t4]

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

            params = {"app_name": app_target, "goal": raw_goal}
            if any(k in goal_lower for k in ["type ", "type", "write text"]):
                cap = "keyboard.type"
                app_target = "keyboard"
                text_to_type = raw_goal
                for prefix in ["type ", "type", "write text "]:
                    if text_to_type.lower().startswith(prefix):
                        text_to_type = text_to_type[len(prefix):]
                text_to_type = text_to_type.strip("'\" ")
                params = {"app_name": "keyboard", "goal": raw_goal, "text": text_to_type}
                title_text = f"Type text: '{text_to_type}'"
            elif any(k in goal_lower for k in ["create file", "write file", "save file", "make file", "create a file"]):
                cap = "file.create"
                title_text = f"Create and write file: {raw_goal}"
            else:
                import re

                m = re.search(
                    r"\b(open|launch|start|run|close|minimize|restore|focus|activate|switch to)\s+([a-zA-Z0-9_\-\.\s]+)\b",
                    goal_lower,
                )
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
                else:
                    # Fallback: if no verb matches but a known app name is present, treat as open
                    known_apps = ["notepad", "calc", "calculator", "chrome", "cmd", "powershell", "spotify", "code", "vscode", "vs code", "visual studio code"]
                    for app in known_apps:
                        if app in goal_lower:
                            app_target = app
                            cap = "app_open"
                            title_text = f"Launch application: {app_target.title()}"
                            break
                params = {"app_name": app_target, "goal": raw_goal}

            subtasks.append(
                SubTask(
                    task_id=t_id,
                    title=title_text,
                    required_role=PlannerRole.DESKTOP,
                    capability=cap,
                    description=f"{title_text} ({raw_goal})",
                    parameters=params,
                    dependencies=[],
                )
            )

        if has_browser and not has_research:
            # Multi-step goal-oriented browser decomposition
            t1_id = f"task_{task_counter}"
            task_counter += 1

            # Check if browser is already running from decision/world_state
            is_chrome_open = False
            if (
                decision
                and hasattr(decision, "world_state")
                and isinstance(getattr(decision, "world_state"), dict)
            ):
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

        if has_coding or (not subtasks and intent_val == "coding"):
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
        elif not subtasks:
            # Fallback for unrecognized action goals — default to DESKTOP action
            t_id = f"task_{task_counter}"
            subtasks.append(
                SubTask(
                    task_id=t_id,
                    title=f"Execute desktop action: {raw_goal}",
                    required_role=PlannerRole.DESKTOP,
                    capability="app_open",
                    description=raw_goal,
                    dependencies=[],
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
