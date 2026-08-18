"""
Daemon Backend Adapter
Location: src/core/backends/adapters/daemon_backend.py

Connects MasterOrchestrator to DaemonRuntime for asynchronous background execution,
scheduling, cancellation, and job lifecycle queries.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from core.planning.execution_result import ExecutionResult
from daemon.daemon_runtime import DaemonRuntime
from daemon.models import JobDefinition, JobState, TriggerType
from ..base_backend import BaseBackendAdapter

logger = logging.getLogger(__name__)


class DaemonEngineBackend(BaseBackendAdapter):
    """Backend adapter connecting orchestrator to autonomous daemon runtime."""

    def __init__(self, runtime: DaemonRuntime | None = None) -> None:
        self._runtime = runtime

    def _get_runtime(self) -> DaemonRuntime:
        if self._runtime is None:
            self._runtime = DaemonRuntime.get_instance()
        return self._runtime

    @property
    def name(self) -> str:
        return "daemon_engine"

    @property
    def capabilities(self) -> list[str]:
        return [
            "daemon",
            "daemon.spawn",
            "daemon.status",
            "daemon.list",
            "daemon.pause",
            "daemon.resume",
            "daemon.cancel",
            "background.execute",
            "background.run",
        ]

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "capabilities": self.capabilities,
            "latency_ms": 10.0,
            "cost": 0.0,
            "is_local": True,
            "version": "1.0.0",
        }

    def health_check(self) -> bool:
        return True

    def execute(
        self, capability: str, goal: str, arguments: dict[str, Any] | None = None
    ) -> ExecutionResult:
        """Execute daemon operation with structured execution result."""
        runtime = self._get_runtime()
        args = arguments or {}
        cap_clean = capability.lower().strip()
        start_t = datetime.now().timestamp()

        try:
            # ── 1. Spawn Background Task ─────────────────────────────────────
            if cap_clean in ("daemon.spawn", "background.execute", "background.run", "daemon"):
                task_cap = args.get("capability") or "system_info"
                task_goal = args.get("goal") or goal
                task_name = args.get("name") or f"Task for: {task_goal[:30]}"
                task_params = args.get("parameters") or {}
                autonomy_token = args.get("autonomy_token")

                rec = runtime.spawn_background_task(
                    name=task_name,
                    capability=task_cap,
                    goal=task_goal,
                    parameters=task_params,
                    autonomy_token=autonomy_token,
                )

                if not rec:
                    return ExecutionResult(
                        success=False,
                        planner="daemon",
                        goal=goal,
                        observations=["❌ Failed to spawn background task (duplicate or rejected claim)."],
                        data={"error": "SPAWN_FAILED"},
                    )

                dur = datetime.now().timestamp() - start_t
                obs_text = f"✓ Spawned background task '{task_name}' [Job: {rec.job_id}, Run: {rec.run_id}, Status: {rec.status.value}]"
                return ExecutionResult(
                    success=True,
                    planner="daemon",
                    goal=goal,
                    confidence=0.98,
                    execution_time_seconds=dur,
                    observations=[obs_text],
                    data={
                        "backend": self.name,
                        "capability": cap_clean,
                        "job_id": rec.job_id,
                        "run_id": rec.run_id,
                        "status": rec.status.value,
                        "scheduled_at": rec.scheduled_at,
                    },
                )

            # ── 2. Job Status Query ──────────────────────────────────────────
            elif cap_clean == "daemon.status":
                job_id = args.get("job_id", "")
                run_id = args.get("run_id", "")
                job = runtime.state_store.get_job(job_id) if job_id else None
                exec_rec = runtime.state_store.get_execution(run_id) if run_id else None

                if not job and not exec_rec:
                    return ExecutionResult(
                        success=False,
                        planner="daemon",
                        goal=goal,
                        observations=[f"❌ Job or run '{job_id or run_id}' not found."],
                        data={"error": "NOT_FOUND"},
                    )

                dur = datetime.now().timestamp() - start_t
                status_val = exec_rec.status.value if exec_rec else ("active" if not job.metadata.get("is_paused") else "paused")
                obs_text = f"✓ Daemon task status for '{job_id or run_id}': {status_val}"
                return ExecutionResult(
                    success=True,
                    planner="daemon",
                    goal=goal,
                    confidence=1.0,
                    execution_time_seconds=dur,
                    observations=[obs_text],
                    data={
                        "backend": self.name,
                        "capability": cap_clean,
                        "job_id": job_id or (exec_rec.job_id if exec_rec else ""),
                        "run_id": run_id,
                        "status": status_val,
                        "result": exec_rec.result if exec_rec else None,
                        "error": exec_rec.error if exec_rec else None,
                    },
                )

            # ── 3. List Jobs ─────────────────────────────────────────────────
            elif cap_clean == "daemon.list":
                inc_cancelled = args.get("include_cancelled", False)
                jobs = runtime.state_store.list_jobs(include_cancelled=inc_cancelled)
                dur = datetime.now().timestamp() - start_t
                jobs_data = [j.to_dict() for j in jobs]
                obs_text = f"✓ Daemon active jobs list: {len(jobs)} jobs registered."
                return ExecutionResult(
                    success=True,
                    planner="daemon",
                    goal=goal,
                    confidence=1.0,
                    execution_time_seconds=dur,
                    observations=[obs_text],
                    data={
                        "backend": self.name,
                        "capability": cap_clean,
                        "jobs": jobs_data,
                        "count": len(jobs),
                    },
                )

            # ── 4. Pause / Resume / Cancel ───────────────────────────────────
            elif cap_clean == "daemon.pause":
                job_id = args.get("job_id", "")
                ok = runtime.pause_job(job_id)
                return ExecutionResult(
                    success=ok,
                    planner="daemon",
                    goal=goal,
                    observations=[f"✓ Paused daemon job '{job_id}'" if ok else f"❌ Failed to pause job '{job_id}'"],
                    data={"backend": self.name, "job_id": job_id, "is_paused": True},
                )

            elif cap_clean == "daemon.resume":
                job_id = args.get("job_id", "")
                ok = runtime.resume_job(job_id)
                return ExecutionResult(
                    success=ok,
                    planner="daemon",
                    goal=goal,
                    observations=[f"✓ Resumed daemon job '{job_id}'" if ok else f"❌ Failed to resume job '{job_id}'"],
                    data={"backend": self.name, "job_id": job_id, "is_paused": False},
                )

            elif cap_clean == "daemon.cancel":
                job_id = args.get("job_id", "")
                reason = args.get("reason", "Cancelled by user")
                ok = runtime.cancel_job(job_id, reason=reason)
                return ExecutionResult(
                    success=ok,
                    planner="daemon",
                    goal=goal,
                    observations=[f"✓ Cancelled daemon job '{job_id}' ({reason})" if ok else f"❌ Failed to cancel job '{job_id}'"],
                    data={"backend": self.name, "job_id": job_id, "is_cancelled": True},
                )

            else:
                return ExecutionResult(
                    success=False,
                    planner="daemon",
                    goal=goal,
                    observations=[f"❌ Unknown daemon capability '{capability}'"],
                    data={"error": f"Unknown capability: {capability}"},
                )

        except Exception as ex:
            logger.error(f"[DaemonEngineBackend] Execution error: {ex}", exc_info=True)
            return ExecutionResult(
                success=False,
                planner="daemon",
                goal=goal,
                observations=[f"❌ Daemon backend error: {ex}"],
                data={"error": str(ex)},
            )
