"""
Scheduler Backend Adapter
Location: src/core/backends/adapters/scheduler_backend.py

Connects MasterOrchestrator to SchedulerManager for timers, interval loops, and cron tasks.
"""

from typing import Any

from ...planning.execution_result import ExecutionResult
from ..base_backend import BaseBackendAdapter


class SchedulerBackendAdapter(BaseBackendAdapter):
    """
    Backend adapter for task scheduling, timers, and cron routines.
    """

    @property
    def name(self) -> str:
        return "Scheduler Engine"

    @property
    def capabilities(self) -> list[str]:
        return [
            "scheduler",
            "scheduler.list",
            "scheduler.at",
            "scheduler.cron",
            "scheduler.interval",
            "scheduler.cancel",
            "scheduler.pause",
            "scheduler.resume",
            "scheduler.when",
            "scheduler.chain",
            "schedule",
            "cron",
            "timer",
        ]

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "capabilities": self.capabilities,
            "latency_ms": 20.0,
            "cost": 0.0,
            "is_local": True,
        }

    def health_check(self) -> bool:
        return True

    def execute(
        self, capability: str, goal: str, arguments: dict[str, Any] | None = None
    ) -> ExecutionResult:
        # Lazy import
        from desktop.native.managers.native_manager_registry import NativeManagerRegistry

        registry = NativeManagerRegistry.get_instance()
        sched_mgr = registry.get_manager("scheduler")

        if not sched_mgr:
            registry.discover()
            sched_mgr = registry.get_manager("scheduler")

        if not sched_mgr:
            return ExecutionResult(
                success=False,
                planner="scheduler",
                goal=goal,
                warnings=["SchedulerManager could not be loaded from native layer."],
            )

        res = sched_mgr.execute(capability=capability, goal=goal, arguments=arguments)

        return ExecutionResult(
            success=res.success,
            planner="scheduler",
            goal=goal,
            observations=[
                f"Scheduler operation: {capability}"
                if res.success
                else f"Scheduler error: {res.error}"
            ],
            warnings=[res.error] if (not res.success and res.error) else [],
            data=res.data,
        )

