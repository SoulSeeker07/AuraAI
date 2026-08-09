"""
M19.5 Generic TaskWorker & Scoped Profiles
==========================================
Location: src/core/orchestration/task_worker.py

Defines a generic TaskWorker execution context with scoped context windows,
permission boundaries, profiles (Research, Test, Coding, Browser), and structured WorkerResult.

Architectural Rule:
    A TaskWorker may execute only within the scope, tools, permissions, and capabilities assigned by
    ExecutionCoordinator. A worker may not modify global policy, spawn another worker, bypass verification,
    bypass autonomy gates, or directly promote its own result to goal success.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class WorkerProfile:
    """Capability & permission configuration profile for TaskWorker."""

    profile_name: str
    allowed_tools: list[str] = field(default_factory=list)
    filesystem_scope: list[str] = field(default_factory=list)
    execution_permissions: list[str] = field(default_factory=list)
    can_write: bool = False
    can_execute: bool = False


# Pre-defined profiles
ResearchProfile = WorkerProfile(
    profile_name="ResearchProfile",
    allowed_tools=["web.search", "web.fetch", "doc.query"],
    filesystem_scope=[],
    execution_permissions=["read"],
    can_write=False,
    can_execute=False,
)

TestProfile = WorkerProfile(
    profile_name="TestProfile",
    allowed_tools=["pytest", "unittest", "code.inspect"],
    filesystem_scope=["tests/", "src/"],
    execution_permissions=["read", "execute_test"],
    can_write=False,
    can_execute=True,
)

CodingProfile = WorkerProfile(
    profile_name="CodingProfile",
    allowed_tools=["code.analyze", "code.edit", "ast.inspect"],
    filesystem_scope=["src/", "tests/"],
    execution_permissions=["read", "write", "test"],
    can_write=True,
    can_execute=True,
)

BrowserProfile = WorkerProfile(
    profile_name="BrowserProfile",
    allowed_tools=["browser.open", "browser.click", "browser.input", "browser.extract"],
    filesystem_scope=[],
    execution_permissions=["browser"],
    can_write=False,
    can_execute=False,
)


@dataclass
class WorkerResult:
    """Standardized structured output from a TaskWorker execution."""

    worker_name: str
    status: str  # "SUCCESS", "FAILED", "CANCELLED"
    task: str
    actions_taken: int = 0
    observations: list[str] = field(default_factory=list)
    verification: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    duration: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_name": self.worker_name,
            "status": self.status,
            "task": self.task,
            "actions_taken": self.actions_taken,
            "observations": self.observations,
            "verification": self.verification,
            "artifacts": self.artifacts,
            "errors": self.errors,
            "recommendations": self.recommendations,
            "duration": self.duration,
        }


class TaskWorker:
    """
    Generic scoped worker assigned bounded execution tasks by ExecutionCoordinator.
    """

    def __init__(
        self,
        worker_name: str,
        profile: WorkerProfile,
        time_budget_seconds: float = 60.0,
    ):
        self.worker_name = worker_name
        self.profile = profile
        self.time_budget_seconds = time_budget_seconds

    def execute_task(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        coordinator_callback: Any | None = None,
    ) -> WorkerResult:
        """
        Execute an assigned task within the profile's tool/permission boundaries.

        Args:
            task: Task description.
            context: Bounded input context dictionary.
            coordinator_callback: Optional callback to invoke engine actions via ExecutionCoordinator.

        Returns:
            Structured WorkerResult (no raw chain-of-thought).
        """
        start_time = time.time()
        context = context or {}
        observations: list[str] = []
        errors: list[str] = []
        actions_count = 0

        logger.info(f"[TaskWorker:{self.worker_name}] Starting task: '{task}' under {self.profile.profile_name}")

        # Check tool permission guardrail
        requested_tool = context.get("tool")
        if requested_tool and requested_tool not in self.profile.allowed_tools:
            err_msg = f"Tool '{requested_tool}' is forbidden for worker profile {self.profile.profile_name}"
            logger.warning(f"[TaskWorker:{self.worker_name}] {err_msg}")
            return WorkerResult(
                worker_name=self.worker_name,
                status="FAILED",
                task=task,
                errors=[err_msg],
                duration=time.time() - start_time,
            )

        # Execute bounded task logic
        if coordinator_callback and requested_tool:
            try:
                res = coordinator_callback(requested_tool, context.get("params", {}))
                actions_count += 1
                observations.append(f"Tool {requested_tool} returned: {res}")
            except Exception as e:
                errors.append(f"Execution failed: {e}")

        duration = time.time() - start_time
        success = len(errors) == 0

        return WorkerResult(
            worker_name=self.worker_name,
            status="SUCCESS" if success else "FAILED",
            task=task,
            actions_taken=actions_count,
            observations=observations,
            verification={"passed": success},
            artifacts=context.get("expected_artifacts", {}),
            errors=errors,
            duration=duration,
        )


__all__ = [
    "WorkerProfile",
    "ResearchProfile",
    "TestProfile",
    "CodingProfile",
    "BrowserProfile",
    "WorkerResult",
    "TaskWorker",
]
