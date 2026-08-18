"""
Durable SQLite State Store for Autonomous Daemon
Location: src/daemon/state_store.py

Manages persistence of job specifications, execution history, checkpointing,
and crash recovery with zero silent ambiguous replay.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from .models import (
    AutonomyRiskTier,
    JobDefinition,
    JobExecutionRecord,
    JobState,
    OfflineCatchupPolicy,
    TriggerType,
)

logger = logging.getLogger(__name__)


class DaemonStateStore:
    """Thread-safe SQLite persistent store for daemon jobs and execution records."""

    def __init__(self, db_path: str = "daemon_state.db") -> None:
        self.db_path = os.path.abspath(db_path)
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS daemon_jobs (
                            job_id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            capability TEXT NOT NULL,
                            goal TEXT NOT NULL,
                            parameters_json TEXT NOT NULL,
                            trigger_type TEXT NOT NULL,
                            schedule_expression TEXT NOT NULL,
                            interval_seconds REAL NOT NULL,
                            timezone_name TEXT NOT NULL,
                            offline_policy TEXT NOT NULL,
                            risk_tier TEXT NOT NULL,
                            autonomy_token TEXT,
                            max_retries INTEGER NOT NULL,
                            timeout_seconds REAL NOT NULL,
                            is_paused INTEGER DEFAULT 0,
                            is_cancelled INTEGER DEFAULT 0,
                            created_at TEXT NOT NULL,
                            created_by TEXT NOT NULL,
                            metadata_json TEXT NOT NULL
                        );
                    """)
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS daemon_executions (
                            run_id TEXT PRIMARY KEY,
                            job_id TEXT NOT NULL,
                            idempotency_key TEXT UNIQUE NOT NULL,
                            attempt INTEGER NOT NULL,
                            status TEXT NOT NULL,
                            scheduled_at TEXT NOT NULL,
                            started_at TEXT,
                            finished_at TEXT,
                            result_json TEXT,
                            error TEXT,
                            checkpoint_json TEXT,
                            node_id TEXT NOT NULL,
                            FOREIGN KEY(job_id) REFERENCES daemon_jobs(job_id)
                        );
                    """)
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_exec_job_id ON daemon_executions(job_id);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_exec_status ON daemon_executions(status);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_exec_idempotency ON daemon_executions(idempotency_key);")
            finally:
                conn.close()

    # ── Job Specification Management ─────────────────────────────────────────

    def save_job(self, job: JobDefinition) -> None:
        """Persist or update a job definition."""
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO daemon_jobs (
                            job_id, name, capability, goal, parameters_json,
                            trigger_type, schedule_expression, interval_seconds,
                            timezone_name, offline_policy, risk_tier, autonomy_token,
                            max_retries, timeout_seconds, created_at, created_by, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        job.job_id,
                        job.name,
                        job.capability,
                        job.goal,
                        json.dumps(job.parameters),
                        job.trigger_type.value,
                        job.schedule_expression,
                        job.interval_seconds,
                        job.timezone_name,
                        job.offline_policy.value,
                        job.risk_tier.value,
                        job.autonomy_token,
                        job.max_retries,
                        job.timeout_seconds,
                        job.created_at,
                        job.created_by,
                        json.dumps(job.metadata),
                    ))
            finally:
                conn.close()

    def get_job(self, job_id: str) -> JobDefinition | None:
        """Retrieve a job definition by ID."""
        with self._lock:
            conn = self._get_connection()
            try:
                row = conn.execute("SELECT * FROM daemon_jobs WHERE job_id = ?;", (job_id,)).fetchone()
                if not row:
                    return None
                return self._row_to_job(row)
            finally:
                conn.close()

    def list_jobs(self, include_cancelled: bool = False) -> list[JobDefinition]:
        """List registered jobs."""
        with self._lock:
            conn = self._get_connection()
            try:
                if include_cancelled:
                    rows = conn.execute("SELECT * FROM daemon_jobs;").fetchall()
                else:
                    rows = conn.execute("SELECT * FROM daemon_jobs WHERE is_cancelled = 0;").fetchall()
                return [self._row_to_job(r) for r in rows]
            finally:
                conn.close()

    def set_job_paused(self, job_id: str, is_paused: bool) -> bool:
        """Pause or resume a job."""
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    cur = conn.execute("UPDATE daemon_jobs SET is_paused = ? WHERE job_id = ?;", (1 if is_paused else 0, job_id))
                    return cur.rowcount > 0
            finally:
                conn.close()

    def cancel_job(self, job_id: str) -> bool:
        """Mark a job as cancelled."""
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    cur = conn.execute("UPDATE daemon_jobs SET is_cancelled = 1 WHERE job_id = ?;", (job_id,))
                    return cur.rowcount > 0
            finally:
                conn.close()

    # ── Execution History & Idempotent Claim ─────────────────────────────────

    def claim_execution(
        self,
        job_id: str,
        idempotency_key: str,
        scheduled_at: str,
        attempt: int = 1,
        node_id: str = "local_node",
    ) -> JobExecutionRecord | None:
        """
        Atomically claim a job run for execution. Returns None if already claimed.
        """
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute("""
                        INSERT INTO daemon_executions (
                            run_id, job_id, idempotency_key, attempt,
                            status, scheduled_at, node_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?);
                    """, (
                        run_id,
                        job_id,
                        idempotency_key,
                        attempt,
                        JobState.CLAIMED.value,
                        scheduled_at,
                        node_id,
                    ))
                    return JobExecutionRecord(
                        run_id=run_id,
                        job_id=job_id,
                        idempotency_key=idempotency_key,
                        attempt=attempt,
                        status=JobState.CLAIMED,
                        scheduled_at=scheduled_at,
                        node_id=node_id,
                    )
            except sqlite3.IntegrityError:
                # Duplicate idempotency key — already claimed or executed
                logger.warning(f"[DaemonStateStore] Idempotency key '{idempotency_key}' already claimed — rejecting duplicate run.")
                return None
            finally:
                conn.close()

    def record_execution_start(self, run_id: str, started_at: str) -> None:
        """Mark run as RUNNING."""
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute("""
                        UPDATE daemon_executions
                        SET status = ?, started_at = ?
                        WHERE run_id = ?;
                    """, (JobState.RUNNING.value, started_at, run_id))
            finally:
                conn.close()

    def record_execution_checkpoint(self, run_id: str, checkpoint_data: dict[str, Any]) -> None:
        """Update intermediate checkpoint data."""
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute("""
                        UPDATE daemon_executions
                        SET checkpoint_json = ?
                        WHERE run_id = ?;
                    """, (json.dumps(checkpoint_data), run_id))
            finally:
                conn.close()

    def record_execution_finish(
        self,
        run_id: str,
        status: JobState,
        finished_at: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Finalize execution status and result."""
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute("""
                        UPDATE daemon_executions
                        SET status = ?, finished_at = ?, result_json = ?, error = ?
                        WHERE run_id = ?;
                    """, (
                        status.value,
                        finished_at,
                        json.dumps(result) if result else None,
                        error,
                        run_id,
                    ))
            finally:
                conn.close()

    def get_execution(self, run_id: str) -> JobExecutionRecord | None:
        """Retrieve execution record by run_id."""
        with self._lock:
            conn = self._get_connection()
            try:
                row = conn.execute("SELECT * FROM daemon_executions WHERE run_id = ?;", (run_id,)).fetchone()
                if not row:
                    return None
                return self._row_to_execution(row)
            finally:
                conn.close()

    def list_executions_for_job(self, job_id: str) -> list[JobExecutionRecord]:
        """Retrieve execution history for a job."""
        with self._lock:
            conn = self._get_connection()
            try:
                rows = conn.execute("SELECT * FROM daemon_executions WHERE job_id = ? ORDER BY scheduled_at DESC;", (job_id,)).fetchall()
                return [self._row_to_execution(r) for r in rows]
            finally:
                conn.close()

    # ── Crash Recovery ───────────────────────────────────────────────────────

    def recover_in_flight_jobs(self) -> list[JobExecutionRecord]:
        """
        CRASH RECOVERY:
        Scan for runs that were left in 'claimed' or 'running' status when the process died.
        Transition them to 'recovery_required' with 'INTERRUPTED_BY_CRASH' error.
        Guarantees no uncommitted side effect is silently replayed.
        """
        interrupted_runs: list[JobExecutionRecord] = []
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    rows = conn.execute("""
                        SELECT * FROM daemon_executions
                        WHERE status IN ('claimed', 'running');
                    """).fetchall()

                    for r in rows:
                        rec = self._row_to_execution(r)
                        rec.status = JobState.RECOVERY_REQUIRED
                        rec.error = "INTERRUPTED_BY_CRASH"
                        interrupted_runs.append(rec)

                    conn.execute("""
                        UPDATE daemon_executions
                        SET status = ?, error = 'INTERRUPTED_BY_CRASH'
                        WHERE status IN ('claimed', 'running');
                    """, (JobState.RECOVERY_REQUIRED.value,))
            finally:
                conn.close()

        if interrupted_runs:
            logger.warning(f"[DaemonStateStore] Recovered {len(interrupted_runs)} in-flight runs to RECOVERY_REQUIRED status.")
        return interrupted_runs

    # ── Helper Mappers ───────────────────────────────────────────────────────

    def _row_to_job(self, row: sqlite3.Row) -> JobDefinition:
        return JobDefinition(
            job_id=row["job_id"],
            name=row["name"],
            capability=row["capability"],
            goal=row["goal"],
            parameters=json.loads(row["parameters_json"]),
            trigger_type=TriggerType(row["trigger_type"]),
            schedule_expression=row["schedule_expression"],
            interval_seconds=float(row["interval_seconds"]),
            timezone_name=row["timezone_name"],
            offline_policy=OfflineCatchupPolicy(row["offline_policy"]),
            risk_tier=AutonomyRiskTier(row["risk_tier"]),
            autonomy_token=row["autonomy_token"],
            max_retries=int(row["max_retries"]),
            timeout_seconds=float(row["timeout_seconds"]),
            created_at=row["created_at"],
            created_by=row["created_by"],
            metadata=json.loads(row["metadata_json"]),
        )

    def _row_to_execution(self, row: sqlite3.Row) -> JobExecutionRecord:
        return JobExecutionRecord(
            run_id=row["run_id"],
            job_id=row["job_id"],
            idempotency_key=row["idempotency_key"],
            attempt=int(row["attempt"]),
            status=JobState(row["status"]),
            scheduled_at=row["scheduled_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            error=row["error"],
            checkpoint_data=json.loads(row["checkpoint_json"]) if row["checkpoint_json"] else {},
            node_id=row["node_id"],
        )
