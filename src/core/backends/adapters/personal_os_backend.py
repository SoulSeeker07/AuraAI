"""
Personal OS Backend Adapter
Location: src/core/backends/adapters/personal_os_backend.py

Connects MasterOrchestrator to the Personal OS subsystem:
- Daily context & agenda synthesis ('What do I need to do today?')
- Workspace fast indexing and search
- Persistent trigger routines and schedule management
"""

from __future__ import annotations

import logging
from typing import Any

from core.planning.execution_result import ExecutionResult
from personal_os.daily_context import DailyContextEngine
from personal_os.state_store import PersonalOSStateStore, PersonalOSTrigger
from ..base_backend import BaseBackendAdapter

logger = logging.getLogger(__name__)


class PersonalOSBackendAdapter(BaseBackendAdapter):
    """
    Backend adapter integrating Personal OS capabilities into cognitive orchestration.
    """

    def __init__(
        self,
        context_engine: DailyContextEngine | None = None,
        state_store: PersonalOSStateStore | None = None,
    ) -> None:
        self.state_store = state_store or PersonalOSStateStore.get_instance()
        self.context_engine = context_engine or DailyContextEngine(state_store=self.state_store)

    @property
    def name(self) -> str:
        return "Personal OS Engine"

    @property
    def capabilities(self) -> list[str]:
        return [
            "personal_os",
            "personal_os.daily_context",
            "personal_os.get_agenda",
            "personal_os.search",
            "personal_os.trigger.list",
            "personal_os.trigger.create",
            "personal_os.trigger.delete",
            "personal_os.trigger.run",
            "personal_os.task.add",
            "personal_os.task.list",
        ]

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "capabilities": self.capabilities,
            "latency_ms": 15.0,
            "cost": 0.0,
            "is_local": True,
            "version": "1.0.0",
        }

    def health_check(self) -> bool:
        return True

    def execute(
        self, capability: str, goal: str, arguments: dict[str, Any] | None = None
    ) -> ExecutionResult:
        """Route and execute personal_os capability calls."""
        args = arguments or {}
        cap = capability.lower().strip()

        try:
            if cap in ("personal_os", "personal_os.daily_context", "personal_os.get_agenda"):
                target_date = args.get("date")
                ctx = self.context_engine.get_daily_context(target_date=target_date)
                return ExecutionResult(
                    success=True,
                    planner="personal_os",
                    goal=goal,
                    observations=[ctx.summary],
                    data={"daily_context": ctx.to_dict()},
                )

            elif cap == "personal_os.search":
                from personal_os.workspace_search import WorkspaceSearchEngine

                search_engine = WorkspaceSearchEngine.get_instance()
                query = args.get("query") or goal
                results = search_engine.search(query=query, limit=args.get("limit", 10))
                obs_lines = [f"Found {len(results)} workspace match(es) for '{query}':"]
                for r in results[:5]:
                    snippet = f" (line {r.line_number}: {r.match_snippet})" if r.line_number else ""
                    obs_lines.append(f"- {r.path}{snippet}")
                return ExecutionResult(
                    success=True,
                    planner="personal_os",
                    goal=goal,
                    observations=obs_lines,
                    data={"results": [r.to_dict() for r in results]},
                )

            elif cap == "personal_os.trigger.list":
                triggers = self.state_store.list_triggers()
                obs = f"Registered triggers: {len(triggers)}"
                return ExecutionResult(
                    success=True,
                    planner="personal_os",
                    goal=goal,
                    observations=[obs],
                    data={"triggers": [t.to_dict() for t in triggers]},
                )

            elif cap == "personal_os.trigger.create":
                trig = PersonalOSTrigger(
                    trigger_id=args.get("trigger_id", f"trig_{args.get('name', 'custom')}"),
                    name=args["name"],
                    goal_text=args["goal_text"],
                    schedule=args.get("schedule", "0 9 * * 1-5"),
                    template_vars=args.get("template_vars", {}),
                    metadata=args.get("metadata", {}),
                )
                allowed_caps = args.get("allowed_capabilities")
                exec_map = args.get("execution_map")
                self.state_store.register_authorized_trigger(
                    trigger=trig,
                    allowed_capabilities=allowed_caps,
                    execution_map=exec_map,
                )
                auth_status = " (cryptographically pre-authorized)" if allowed_caps else ""
                return ExecutionResult(
                    success=True,
                    planner="personal_os",
                    goal=goal,
                    observations=[f"Created Personal OS trigger '{trig.name}' ({trig.schedule}){auth_status}"],
                    data={"trigger": trig.to_dict()},
                )

            elif cap == "personal_os.trigger.delete":
                identifier = args.get("trigger_id") or args.get("name")
                deleted = self.state_store.delete_trigger(identifier)
                return ExecutionResult(
                    success=deleted,
                    planner="personal_os",
                    goal=goal,
                    observations=[f"Trigger '{identifier}' deletion: {deleted}"],
                    data={"deleted": deleted},
                )

            elif cap == "personal_os.task.add":
                task_list = self.state_store.get_preference("tasks_list", [])
                new_task = {
                    "task_id": args.get("task_id", f"task_{len(task_list)+1}"),
                    "title": args.get("title", goal),
                    "priority": args.get("priority", "NORMAL"),
                    "status": "PENDING",
                    "due_date": args.get("due_date"),
                }
                task_list.append(new_task)
                self.state_store.set_preference("tasks_list", task_list)
                return ExecutionResult(
                    success=True,
                    planner="personal_os",
                    goal=goal,
                    observations=[f"Added task: {new_task['title']}"],
                    data={"task": new_task},
                )

            elif cap == "personal_os.task.list":
                task_list = self.state_store.get_preference("tasks_list", [])
                return ExecutionResult(
                    success=True,
                    planner="personal_os",
                    goal=goal,
                    observations=[f"Found {len(task_list)} task(s)"],
                    data={"tasks": task_list},
                )

            else:
                return ExecutionResult(
                    success=False,
                    planner="personal_os",
                    goal=goal,
                    observations=[f"Unknown personal_os capability: {capability}"],
                )

        except Exception as exc:
            logger.error(f"[PersonalOSBackendAdapter] Execution failed: {exc}", exc_info=True)
            return ExecutionResult(
                success=False,
                planner="personal_os",
                goal=goal,
                observations=[f"Personal OS execution error: {exc}"],
            )
