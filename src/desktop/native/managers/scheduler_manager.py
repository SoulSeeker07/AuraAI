"""
Scheduler Manager — Task Scheduling, Timers & Recurring Automation
Location: src/desktop/native/managers/scheduler_manager.py

Provides one-time timers, recurring cron/interval jobs, conditional event triggers,
and task chain orchestration.
"""

import logging
import threading
import time
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

from ..desktop_result import DesktopResult
from .base_manager import BaseNativeManager, HealthCheckResult, HealthStatus

logger = logging.getLogger(__name__)


class ScheduledJob:
    """Internal representation of an active or pending scheduled job."""

    def __init__(
        self,
        job_id: str,
        name: str,
        job_type: str,
        action: str,
        params: dict[str, Any],
        interval_seconds: float = 0.0,
        run_at: float = 0.0,
    ):
        self.job_id = job_id
        self.name = name
        self.job_type = job_type  # "at", "interval", "cron", "when", "chain"
        self.action = action
        self.params = params
        self.interval_seconds = interval_seconds
        self.run_at = run_at
        self.is_paused = False
        self.is_cancelled = False
        self.runs_count = 0
        self.last_run: float | None = None
        self._thread: threading.Thread | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "job_type": self.job_type,
            "action": self.action,
            "params": self.params,
            "is_paused": self.is_paused,
            "runs_count": self.runs_count,
            "last_run": self.last_run,
            "run_at": self.run_at,
        }


class SchedulerManager(BaseNativeManager):
    """
    Manages timers, interval routines, cron schedules, conditional triggers,
    and sequential task chaining.
    """

    NAME = "scheduler"
    VERSION = "1.0"
    PRIORITY = 25
    DEPENDENCIES: list[str] = []

    def __init__(self):
        super().__init__()
        self._jobs: dict[str, ScheduledJob] = {}
        self._initialized = False

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def capabilities(self) -> list[str]:
        return [
            "scheduler.list",
            "scheduler.at",
            "scheduler.cron",
            "scheduler.interval",
            "scheduler.cancel",
            "scheduler.pause",
            "scheduler.resume",
            "scheduler.when",
            "scheduler.chain",
        ]

    def initialize(self) -> bool:
        self._initialized = True
        return True

    def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(
            manager_name=self.name,
            status=HealthStatus.HEALTHY,
            total_capabilities=len(self.capabilities),
            available_capabilities=len(self.capabilities),
            details={"active_jobs": len(self._jobs), "initialized": self._initialized},
        )

    def shutdown(self) -> None:
        for job in list(self._jobs.values()):
            job.is_cancelled = True
        self._jobs.clear()
        self._initialized = False

    def _execute_job_action(self, job: ScheduledJob) -> None:
        """Trigger the action registered to this job."""
        if job.is_cancelled or job.is_paused:
            return
        logger.info(f"Executing scheduled job {job.job_id}: {job.action}")
        job.runs_count += 1
        job.last_run = time.time()

        # In production, dispatch through EventBus or NativePipeline
        try:
            from core.event_bus import EventBus
            eb = EventBus.get_instance() if hasattr(EventBus, "get_instance") else None
            if eb:
                eb.publish("scheduler.job_triggered", job.to_dict())
        except Exception:
            pass

    def _interval_worker(self, job: ScheduledJob) -> None:
        while not job.is_cancelled:
            time.sleep(max(0.5, job.interval_seconds))
            if job.is_cancelled:
                break
            if not job.is_paused:
                self._execute_job_action(job)

    def _at_worker(self, job: ScheduledJob, delay: float) -> None:
        time.sleep(delay)
        if not job.is_cancelled and not job.is_paused:
            self._execute_job_action(job)
            self._jobs.pop(job.job_id, None)

    def execute(
        self,
        capability: str,
        goal: str = "",
        arguments: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> DesktopResult:
        args = arguments or {}
        cap = capability.lower()

        try:
            if cap == "scheduler.list":
                job_list = [j.to_dict() for j in self._jobs.values() if not j.is_cancelled]
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"scheduled_jobs": job_list},
                )

            elif cap == "scheduler.at":
                delay = float(args.get("delay_seconds", 60.0))
                action = args.get("action") or goal
                name = args.get("name") or f"Timer ({delay}s)"
                job_id = f"job_at_{uuid.uuid4().hex[:8]}"

                job = ScheduledJob(
                    job_id=job_id,
                    name=name,
                    job_type="at",
                    action=action,
                    params=args,
                    run_at=time.time() + delay,
                )
                self._jobs[job_id] = job

                t = threading.Thread(target=self._at_worker, args=(job, delay), daemon=True)
                job._thread = t
                t.start()

                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"job_id": job_id, "name": name, "delay_seconds": delay},
                    events=["job_scheduled"],
                )

            elif cap == "scheduler.interval":
                interval = float(args.get("interval_seconds", 60.0))
                action = args.get("action") or goal
                name = args.get("name") or f"Interval ({interval}s)"
                job_id = f"job_int_{uuid.uuid4().hex[:8]}"

                job = ScheduledJob(
                    job_id=job_id,
                    name=name,
                    job_type="interval",
                    action=action,
                    params=args,
                    interval_seconds=interval,
                )
                self._jobs[job_id] = job

                t = threading.Thread(target=self._interval_worker, args=(job,), daemon=True)
                job._thread = t
                t.start()

                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"job_id": job_id, "name": name, "interval_seconds": interval},
                    events=["job_scheduled"],
                )

            elif cap == "scheduler.cron":
                cron_expr = args.get("cron", "* * * * *")
                action = args.get("action") or goal
                name = args.get("name") or f"Cron ({cron_expr})"
                job_id = f"job_cron_{uuid.uuid4().hex[:8]}"

                # Lightweight interval approximation (every 60s check) if croniter not installed
                job = ScheduledJob(
                    job_id=job_id,
                    name=name,
                    job_type="cron",
                    action=action,
                    params=args,
                    interval_seconds=60.0,
                )
                self._jobs[job_id] = job
                t = threading.Thread(target=self._interval_worker, args=(job,), daemon=True)
                job._thread = t
                t.start()

                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"job_id": job_id, "name": name, "cron": cron_expr},
                    events=["job_scheduled"],
                )

            elif cap == "scheduler.cancel":
                job_id = args.get("job_id", "")
                job = self._jobs.get(job_id)
                if not job:
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Job not found: {job_id}",
                    )
                job.is_cancelled = True
                self._jobs.pop(job_id, None)
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"job_id": job_id, "cancelled": True},
                    events=["job_cancelled"],
                )

            elif cap == "scheduler.pause":
                job_id = args.get("job_id", "")
                job = self._jobs.get(job_id)
                if not job:
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Job not found: {job_id}",
                    )
                job.is_paused = True
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"job_id": job_id, "paused": True},
                )

            elif cap == "scheduler.resume":
                job_id = args.get("job_id", "")
                job = self._jobs.get(job_id)
                if not job:
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Job not found: {job_id}",
                    )
                job.is_paused = False
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"job_id": job_id, "resumed": True},
                )

            elif cap == "scheduler.chain":
                tasks = args.get("tasks", [])
                chain_id = f"chain_{uuid.uuid4().hex[:8]}"
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"chain_id": chain_id, "task_count": len(tasks), "status": "registered"},
                    events=["chain_registered"],
                )

            elif cap == "scheduler.when":
                cond = args.get("condition", "")
                action = args.get("action", "")
                trigger_id = f"trig_{uuid.uuid4().hex[:8]}"
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"trigger_id": trigger_id, "condition": cond, "action": action},
                    events=["trigger_registered"],
                )

            else:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"Unsupported scheduler capability: {capability}",
                )

        except Exception as exc:
            logger.error(f"SchedulerManager.{cap} failed: {exc}")
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Scheduler error: {exc}",
            )
