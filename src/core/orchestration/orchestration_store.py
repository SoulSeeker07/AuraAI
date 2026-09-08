"""
Orchestration Store - SQLite-backed durable task graph and session persistence.
Location: src/core/orchestration/orchestration_store.py

Provides persistent lifecycle tracking for AgentSession and TaskGraph nodes,
enabling crash recovery, resume-time idempotency protection, and fail-safe
interrupted task handling.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Iterable

from .task_decomposer import SubTask, TaskGraph, PlannerRole

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = PROJECT_ROOT / "Memory.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OrchestrationStore:
    """
    Thread-safe SQLite store for durable execution of AgentSessions and SubTasks.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            self.db_path = DEFAULT_DB_PATH
        else:
            p = Path(db_path)
            self.db_path = p if p.is_absolute() else (PROJECT_ROOT / p).resolve()

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=20.0,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Create tables and indices if they do not exist."""
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS orchestration_sessions (
                    session_id TEXT PRIMARY KEY,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL,
                    budget_json TEXT DEFAULT '{}',
                    metadata_json TEXT DEFAULT '{}',
                    error TEXT DEFAULT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT DEFAULT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS orchestration_tasks (
                    session_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    required_role TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    risk_tier TEXT NOT NULL,
                    status TEXT NOT NULL,
                    dependencies_json TEXT DEFAULT '[]',
                    parameters_json TEXT DEFAULT '{}',
                    result_json TEXT DEFAULT NULL,
                    error TEXT DEFAULT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT DEFAULT NULL,
                    PRIMARY KEY (session_id, task_id),
                    FOREIGN KEY (session_id) REFERENCES orchestration_sessions(session_id) ON DELETE CASCADE
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_orchestration_tasks_session_status
                ON orchestration_tasks(session_id, status);
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS goals (
                    goal_id         TEXT PRIMARY KEY,
                    session_id      TEXT NOT NULL,
                    user_prompt     TEXT NOT NULL,
                    status          TEXT NOT NULL,
                    max_steps       INTEGER NOT NULL DEFAULT 8,
                    created_at      TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS goal_steps (
                    step_id         TEXT PRIMARY KEY,
                    goal_id         TEXT NOT NULL REFERENCES goals(goal_id) ON DELETE CASCADE,
                    tool_name       TEXT,
                    tool_args       TEXT NOT NULL,
                    status          TEXT NOT NULL,
                    observation     TEXT,
                    verify_reason   TEXT,
                    created_at      TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_goal_steps_goal_id ON goal_steps(goal_id);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_goals_session_id ON goals(session_id);
                """
            )
            conn.commit()

    def register_session(
        self,
        session_id: str,
        goal: str,
        budget: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Register a new active session."""
        now = _now_iso()
        budget_dict = (
            budget.to_dict()
            if hasattr(budget, "to_dict")
            else (dict(budget) if isinstance(budget, dict) else {})
        )
        metadata_dict = dict(metadata or {})
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO orchestration_sessions (
                    session_id, goal, status, budget_json, metadata_json, created_at, updated_at
                ) VALUES (?, ?, 'running', ?, ?, ?, ?);
                """,
                (
                    session_id,
                    goal,
                    json.dumps(budget_dict),
                    json.dumps(metadata_dict),
                    now,
                    now,
                ),
            )
            conn.commit()

    def register_initial_tasks(
        self, session_id: str, subtasks: Iterable[SubTask]
    ) -> None:
        """Bulk insert the initial set of subtasks decomposed for the session."""
        now = _now_iso()
        with self._lock, self._get_connection() as conn:
            for st in subtasks:
                role_str = (
                    st.required_role.value
                    if hasattr(st.required_role, "value")
                    else str(st.required_role)
                )
                risk_tier = (
                    st.risk_tier.upper()
                    if getattr(st, "risk_tier", None)
                    else "LOW"
                )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO orchestration_tasks (
                        session_id, task_id, title, required_role, capability,
                        risk_tier, status, dependencies_json, parameters_json,
                        attempt_count, max_retries, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        session_id,
                        st.task_id,
                        st.title or st.task_id,
                        role_str,
                        st.capability,
                        risk_tier,
                        st.status or "pending",
                        json.dumps(getattr(st, "dependencies", []) or []),
                        json.dumps(getattr(st, "parameters", {}) or {}),
                        getattr(st, "attempt_count", 0),
                        getattr(st, "max_retries", 0),
                        now,
                        now,
                    ),
                )
            conn.commit()

    def add_task(self, session_id: str, subtask: SubTask) -> None:
        """Dynamically add a single subtask during execution (supports ReAct / replanning)."""
        now = _now_iso()
        role_str = (
            subtask.required_role.value
            if hasattr(subtask.required_role, "value")
            else str(subtask.required_role)
        )
        risk_tier = (
            subtask.risk_tier.upper()
            if getattr(subtask, "risk_tier", None)
            else "LOW"
        )
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO orchestration_tasks (
                    session_id, task_id, title, required_role, capability,
                    risk_tier, status, dependencies_json, parameters_json,
                    attempt_count, max_retries, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    session_id,
                    subtask.task_id,
                    subtask.title or subtask.task_id,
                    role_str,
                    subtask.capability,
                    risk_tier,
                    subtask.status or "pending",
                    json.dumps(getattr(subtask, "dependencies", []) or []),
                    json.dumps(getattr(subtask, "parameters", {}) or {}),
                    getattr(subtask, "attempt_count", 0),
                    getattr(subtask, "max_retries", 0),
                    now,
                    now,
                ),
            )
            conn.commit()

    def update_task_status(
        self,
        session_id: str,
        task_id: str,
        status: str,
        result: Any = None,
        error: str | None = None,
        increment_attempt: bool = False,
    ) -> None:
        """Update the status, attempt count, and outcome of a subtask."""
        now = _now_iso()
        result_json = json.dumps(result) if result is not None else None
        completed_at = now if status in ("completed", "failed", "cancelled") else None

        with self._lock, self._get_connection() as conn:
            if increment_attempt:
                conn.execute(
                    """
                    UPDATE orchestration_tasks
                    SET status = ?,
                        attempt_count = attempt_count + 1,
                        result_json = COALESCE(?, result_json),
                        error = COALESCE(?, error),
                        updated_at = ?,
                        completed_at = COALESCE(?, completed_at)
                    WHERE session_id = ? AND task_id = ?;
                    """,
                    (status, result_json, error, now, completed_at, session_id, task_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE orchestration_tasks
                    SET status = ?,
                        result_json = COALESCE(?, result_json),
                        error = COALESCE(?, error),
                        updated_at = ?,
                        completed_at = COALESCE(?, completed_at)
                    WHERE session_id = ? AND task_id = ?;
                    """,
                    (status, result_json, error, now, completed_at, session_id, task_id),
                )
            conn.commit()

    def update_session_status(
        self, session_id: str, status: str, error: str | None = None
    ) -> None:
        """Update top-level session status."""
        now = _now_iso()
        completed_at = now if status in ("completed", "failed", "cancelled") else None
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                UPDATE orchestration_sessions
                SET status = ?,
                    error = COALESCE(?, error),
                    updated_at = ?,
                    completed_at = COALESCE(?, completed_at)
                WHERE session_id = ?;
                """,
                (status, error, now, completed_at, session_id),
            )
            conn.commit()

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve a session row by ID."""
        with self._lock, self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM orchestration_sessions WHERE session_id = ?;",
                (session_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_tasks(self, session_id: str) -> list[dict[str, Any]]:
        """Retrieve all task rows for a session."""
        with self._lock, self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM orchestration_tasks WHERE session_id = ? ORDER BY created_at ASC;",
                (session_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def prepare_session_for_resume(
        self, session_id: str
    ) -> tuple[dict[str, Any], list[SubTask], list[str], list[SubTask]]:
        """
        Loads session from disk and inspects tasks across risk tiers to enforce fail-safe crash-resume:

        Returns:
            (session_dict, all_subtasks, completed_ids, interrupted_high_risk_tasks)

        Idempotency / Fail-Safe Gating Rules:
        - completed: restored into completed_ids.
        - pending / dispatched: re-queued as pending.
        - executing + risk_tier == 'LOW': safe read-only/idempotent task; reset to 'pending' for re-dispatch.
        - executing + risk_tier in ('MEDIUM', 'HIGH', 'CRITICAL'):
            FAIL CLOSED: set to 'interrupted', session set to 'suspended',
            and returned in interrupted_high_risk_tasks so orchestrator halts and prompts.
        """
        now = _now_iso()
        session_row = self.get_session(session_id)
        if not session_row:
            raise ValueError(f"Orchestration session '{session_id}' not found in store.")

        task_rows = self.get_tasks(session_id)
        all_subtasks: list[SubTask] = []
        completed_ids: list[str] = []
        interrupted_high_risk: list[SubTask] = []

        with self._lock, self._get_connection() as conn:
            for row in task_rows:
                t_id = row["task_id"]
                raw_status = row["status"]
                risk_tier = (row["risk_tier"] or "LOW").upper()

                role_val = row["required_role"]
                try:
                    role_enum = PlannerRole(role_val)
                except Exception:
                    role_enum = PlannerRole.DESKTOP

                params = json.loads(row["parameters_json"] or "{}")
                deps = json.loads(row["dependencies_json"] or "[]")
                res = json.loads(row["result_json"]) if row["result_json"] else None

                subtask = SubTask(
                    task_id=t_id,
                    title=row["title"],
                    required_role=role_enum,
                    capability=row["capability"],
                    description="",
                    dependencies=deps,
                    parameters=params,
                    status=raw_status,
                    result=res,
                    max_retries=row["max_retries"],
                    attempt_count=row["attempt_count"],
                    risk_tier=risk_tier,
                )

                if raw_status == "completed":
                    completed_ids.append(t_id)
                elif raw_status in ("pending", "dispatched"):
                    # Safe to run/retry
                    subtask.status = "pending"
                    if raw_status == "dispatched":
                        conn.execute(
                            "UPDATE orchestration_tasks SET status = 'pending', updated_at = ? WHERE session_id = ? AND task_id = ?;",
                            (now, session_id, t_id),
                        )
                elif raw_status == "executing":
                    if risk_tier == "LOW":
                        # Low risk: idempotent / read-only -> safely reset to pending
                        logger.info(
                            f"[OrchestrationStore] Session [{session_id}] resuming interrupted LOW-risk task '{t_id}' -> reset to 'pending'."
                        )
                        subtask.status = "pending"
                        conn.execute(
                            "UPDATE orchestration_tasks SET status = 'pending', updated_at = ? WHERE session_id = ? AND task_id = ?;",
                            (now, session_id, t_id),
                        )
                    else:
                        # MEDIUM, HIGH, CRITICAL: Fail closed -> mark interrupted and suspend
                        logger.warning(
                            f"[OrchestrationStore] Session [{session_id}] detected interrupted {risk_tier}-risk task '{t_id}'. Failing closed -> mark 'interrupted'."
                        )
                        subtask.status = "interrupted"
                        conn.execute(
                            "UPDATE orchestration_tasks SET status = 'interrupted', updated_at = ? WHERE session_id = ? AND task_id = ?;",
                            (now, session_id, t_id),
                        )
                        interrupted_high_risk.append(subtask)

                all_subtasks.append(subtask)

            if interrupted_high_risk:
                conn.execute(
                    "UPDATE orchestration_sessions SET status = 'suspended', updated_at = ? WHERE session_id = ?;",
                    (now, session_id),
                )
                session_row["status"] = "suspended"

            conn.commit()

        return session_row, all_subtasks, completed_ids, interrupted_high_risk
