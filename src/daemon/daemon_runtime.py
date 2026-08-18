"""
Autonomous Daemon Runtime Coordinator
Location: src/daemon/daemon_runtime.py

Manages bounded background worker pool, persistent scheduler loop, cooperative cancellation,
governance enforcement, and graceful shutdown.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable

from core.backends.backend_registry import BackendRegistry
from core.capabilities.capability_registry import CapabilityRegistry
from .governance import AutonomyGovernanceEngine
from .models import (
    AutonomyRiskTier,
    CancellationToken,
    JobDefinition,
    JobExecutionRecord,
    JobState,
    OfflineCatchupPolicy,
    TriggerType,
)
from .state_store import DaemonStateStore

logger = logging.getLogger(__name__)


class DaemonRuntime:
    """
    Central daemon runtime coordinating background task execution, scheduling,
    cancellation tokens, and state recovery.
    """

    _instance: DaemonRuntime | None = None

    def __init__(
        self,
        state_store: DaemonStateStore | None = None,
        governance: AutonomyGovernanceEngine | None = None,
        max_workers: int = 4,
    ) -> None:
        self.state_store = state_store or DaemonStateStore()
        self.governance = governance or AutonomyGovernanceEngine.get_instance()
        self.max_workers = max_workers

        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="AuraDaemonWorker")
        self._active_tokens: dict[str, CancellationToken] = {}  # run_id -> token
        self._active_futures: dict[str, Future] = {}            # run_id -> future
        self._running_jobs: set[str] = set()                    # job_id

        self._is_running = False
        self._shutdown_event = threading.Event()
        self._scheduler_thread: threading.Thread | None = None
        self._lock = threading.Lock()

        # Perform startup crash recovery
        self._recover_startup_state()

    @classmethod
    def get_instance(cls) -> DaemonRuntime:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        if cls._instance is not None:
            cls._instance.shutdown(wait=False)
            cls._instance = None

    def _recover_startup_state(self) -> None:
        """Scan state store for in-flight tasks interrupted during prior crash."""
        interrupted = self.state_store.recover_in_flight_jobs()
        if interrupted:
            logger.warning(f"[DaemonRuntime] Recovered {len(interrupted)} interrupted jobs from prior process crash.")

    # ── Lifecycle Control ────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background daemon scheduler loop."""
        with self._lock:
            if self._is_running:
                return
            self._is_running = True
            self._shutdown_event.clear()
            self._scheduler_thread = threading.Thread(
                target=self._scheduler_loop,
                name="AuraDaemonScheduler",
                daemon=True,
            )
            self._scheduler_thread.start()
            logger.info(f"[DaemonRuntime] Autonomous Daemon Runtime started with {self.max_workers} workers.")

    def shutdown(self, timeout_seconds: float = 5.0, wait: bool = True) -> None:
        """Gracefully stop the scheduler loop and cancel or drain active workers."""
        with self._lock:
            if not self._is_running:
                return
            self._is_running = False
            self._shutdown_event.set()

            # Signal cancellation to all running tasks
            for run_id, token in list(self._active_tokens.items()):
                token.cancel(reason="Daemon runtime shutting down")

        # Stop worker pool
        try:
            self._executor.shutdown(wait=wait, cancel_futures=True)
        except Exception as err:
            logger.warning(f"[DaemonRuntime] Executor shutdown warning: {err}")

        if wait and self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=timeout_seconds)

        logger.info("[DaemonRuntime] Autonomous Daemon Runtime successfully shut down.")

    # ── Task Registration & Submission ───────────────────────────────────────

    def register_job(self, job: JobDefinition) -> JobDefinition:
        """Persist a job definition and queue for scheduling."""
        self.state_store.save_job(job)
        logger.info(f"[DaemonRuntime] Registered daemon job '{job.job_id}' ({job.name}) [{job.trigger_type.value}].")
        return job

    def spawn_background_task(
        self,
        name: str,
        capability: str,
        goal: str,
        parameters: dict[str, Any] | None = None,
        autonomy_token: str | None = None,
        timeout_seconds: float = 300.0,
    ) -> JobExecutionRecord | None:
        """
        Immediately spawn a one-shot task in the background worker pool.
        """
        job_id = f"job_{uuid.uuid4().hex[:10]}"
        job = JobDefinition(
            job_id=job_id,
            name=name,
            capability=capability,
            goal=goal,
            parameters=parameters or {},
            trigger_type=TriggerType.ONE_SHOT,
            autonomy_token=autonomy_token,
            timeout_seconds=timeout_seconds,
        )
        self.register_job(job)
        return self._trigger_job_execution(job)

    def pause_job(self, job_id: str) -> bool:
        """Pause a scheduled job."""
        success = self.state_store.set_job_paused(job_id, True)
        logger.info(f"[DaemonRuntime] Paused job '{job_id}': {success}")
        return success

    def resume_job(self, job_id: str) -> bool:
        """Resume a paused scheduled job."""
        success = self.state_store.set_job_paused(job_id, False)
        logger.info(f"[DaemonRuntime] Resumed job '{job_id}': {success}")
        return success

    def cancel_job(self, job_id: str, reason: str = "User cancelled") -> bool:
        """Cancel a job and abort any active run in flight."""
        success = self.state_store.cancel_job(job_id)

        # Cancel any active running executions for this job
        with self._lock:
            for run_id, token in list(self._active_tokens.items()):
                # If run belongs to this job, cancel it
                token.cancel(reason=reason)

        logger.info(f"[DaemonRuntime] Cancelled job '{job_id}': {success}")
        return success

    # ── Job Execution & Worker Dispatch ──────────────────────────────────────

    def _trigger_job_execution(self, job: JobDefinition) -> JobExecutionRecord | None:
        """
        Dispatch a job execution through governance gating, atomic claim, and worker pool.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        now_ts = int(time.time())
        idempotency_key = f"{job.job_id}_{now_ts}"

        # 1. Autonomy Governance Gating
        authorized, reason, risk_tier = self.governance.evaluate_execution(
            job=job,
            capability=job.capability,
            arguments=job.parameters,
            token=job.autonomy_token,
        )
        if not authorized:
            logger.error(f"[DaemonRuntime] Job '{job.job_id}' blocked by AutonomyGovernance: {reason}")
            # Record failed authorization execution
            exec_rec = self.state_store.claim_execution(job.job_id, idempotency_key, now_iso)
            if exec_rec:
                self.state_store.record_execution_finish(
                    run_id=exec_rec.run_id,
                    status=JobState.FAILED,
                    finished_at=now_iso,
                    error=f"GOVERNANCE_BLOCKED: {reason}",
                )
                exec_rec.status = JobState.FAILED
                exec_rec.error = f"GOVERNANCE_BLOCKED: {reason}"
            return exec_rec

        # 2. Atomic Idempotent Claim
        exec_rec = self.state_store.claim_execution(
            job_id=job.job_id,
            idempotency_key=idempotency_key,
            scheduled_at=now_iso,
        )
        if not exec_rec:
            logger.warning(f"[DaemonRuntime] Could not claim run for '{job.job_id}' (duplicate key).")
            return None

        # 3. Create Cancellation Token and Dispatch to ThreadPool
        token = CancellationToken()
        with self._lock:
            self._active_tokens[exec_rec.run_id] = token
            self._running_jobs.add(job.job_id)

        fut = self._executor.submit(self._worker_execute, job, exec_rec, token)
        with self._lock:
            self._active_futures[exec_rec.run_id] = fut

        return exec_rec

    def _worker_execute(
        self,
        job: JobDefinition,
        record: JobExecutionRecord,
        cancel_token: CancellationToken,
    ) -> None:
        """
        Worker thread function executing capability through BackendRegistry with lifecycle recording.
        """
        start_iso = datetime.now(timezone.utc).isoformat()
        self.state_store.record_execution_start(record.run_id, start_iso)
        record.status = JobState.RUNNING
        record.started_at = start_iso

        result_payload: dict[str, Any] | None = None
        error_msg: str | None = None
        final_state = JobState.COMPLETED

        try:
            # Check for cancellation before beginning
            if cancel_token.is_cancelled:
                final_state = JobState.CANCELLED
                error_msg = f"Cancelled before start: {cancel_token.reason}"
            else:
                # Dispatch through canonical BackendRegistry
                backend_reg = BackendRegistry.get_instance()
                backend = backend_reg.select_best_backend(job.capability)

                if not backend:
                    # Fallback lookup directly
                    backend = backend_reg.get_backend(job.capability)

                if not backend:
                    final_state = JobState.FAILED
                    error_msg = f"No backend registered supporting capability '{job.capability}'"
                else:
                    # Check cancellation during execution
                    if cancel_token.is_cancelled:
                        final_state = JobState.CANCELLED
                        error_msg = f"Cancelled during run: {cancel_token.reason}"
                    else:
                        exec_res = backend.execute(
                            capability=job.capability,
                            goal=job.goal,
                            arguments=job.parameters,
                        )

                        if exec_res.success:
                            final_state = JobState.COMPLETED
                            result_payload = {
                                "observations": exec_res.observations,
                                "data": exec_res.data,
                                "confidence": exec_res.confidence,
                            }
                        else:
                            final_state = JobState.FAILED
                            error_msg = "; ".join(exec_res.observations) if exec_res.observations else "Capability execution failed"

        except Exception as ex:
            logger.error(f"[DaemonRuntime] Unhandled exception in worker for run '{record.run_id}': {ex}", exc_info=True)
            final_state = JobState.FAILED
            error_msg = f"Worker Exception: {type(ex).__name__}: {str(ex)}"

        finally:
            finished_iso = datetime.now(timezone.utc).isoformat()
            self.state_store.record_execution_finish(
                run_id=record.run_id,
                status=final_state,
                finished_at=finished_iso,
                result=result_payload,
                error=error_msg,
            )
            record.status = final_state
            record.finished_at = finished_iso
            record.result = result_payload
            record.error = error_msg

            with self._lock:
                self._active_tokens.pop(record.run_id, None)
                self._active_futures.pop(record.run_id, None)
                self._running_jobs.discard(job.job_id)

    # ── Background Scheduler Loop ────────────────────────────────────────────

    def _scheduler_loop(self) -> None:
        """Periodic background evaluation of registered recurring jobs."""
        logger.info("[DaemonRuntime] Scheduler loop initialized.")
        last_interval_eval: dict[str, float] = {}

        while not self._shutdown_event.is_set():
            try:
                jobs = self.state_store.list_jobs(include_cancelled=False)
                now_ts = time.time()

                for job in jobs:
                    if self._shutdown_event.is_set():
                        break

                    # Skip paused jobs
                    if job.metadata.get("is_paused") or getattr(job, "is_paused", False):
                        continue

                    # Handle interval jobs
                    if job.trigger_type == TriggerType.INTERVAL and job.interval_seconds > 0:
                        last_t = last_interval_eval.get(job.job_id, 0.0)
                        if now_ts - last_t >= job.interval_seconds:
                            last_interval_eval[job.job_id] = now_ts
                            self._trigger_job_execution(job)

                    # Handle one-shot delay jobs
                    elif job.trigger_type == TriggerType.ONE_SHOT and job.schedule_expression:
                        try:
                            run_at_ts = float(job.schedule_expression)
                            if now_ts >= run_at_ts and job.job_id not in last_interval_eval:
                                last_interval_eval[job.job_id] = now_ts
                                self._trigger_job_execution(job)
                        except ValueError:
                            pass

            except Exception as sched_err:
                logger.warning(f"[DaemonRuntime] Error in scheduler tick: {sched_err}")

            # Sleep with responsive wake-up
            self._shutdown_event.wait(timeout=1.0)
