"""
Personal OS Persistent State Store
Location: src/personal_os/state_store.py

Provides durable SQLite-backed storage for Personal OS triggers,
user routines, schedule history, and preference state across Aura restarts.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger(__name__)

CURRENT_SCHEMA_VERSION = 1
DEFAULT_DB_PATH = Path.home() / ".aura" / "personal_os" / "state.db"


@dataclass
class PersonalOSTrigger:
    """Represents a persistent user automation trigger/routine."""

    trigger_id: str
    name: str
    goal_text: str
    schedule: str  # Cron expression, interval (e.g. 'every 1h'), or 'on_event'
    enabled: bool = True
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_fired_at: str | None = None
    run_count: int = 0
    last_result_summary: str | None = None
    template_vars: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PersonalOSTrigger:
        return cls(
            trigger_id=data["trigger_id"],
            name=data["name"],
            goal_text=data["goal_text"],
            schedule=data.get("schedule", "0 9 * * 1-5"),
            enabled=bool(data.get("enabled", True)),
            created_at=data.get(
                "created_at", datetime.now(timezone.utc).isoformat()
            ),
            last_fired_at=data.get("last_fired_at"),
            run_count=int(data.get("run_count", 0)),
            last_result_summary=data.get("last_result_summary"),
            template_vars=data.get("template_vars") or {},
            metadata=data.get("metadata") or {},
        )


class PersonalOSStateStore:
    """
    Thread-safe SQLite store managing persistent routines and configuration.
    """

    CURRENT_SCHEMA_VERSION: int = CURRENT_SCHEMA_VERSION
    _instance: PersonalOSStateStore | None = None
    _lock = threading.Lock()

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_lock = threading.RLock()
        self._init_db()

    @classmethod
    def get_instance(
        cls, db_path: Path | str | None = None
    ) -> PersonalOSStateStore:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(db_path=db_path)
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=15.0,
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
        with self._db_lock, self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS personal_os_suspended_sessions (
                    ticket_id TEXT PRIMARY KEY,
                    trigger_id TEXT,
                    session_id TEXT NOT NULL,
                    task_graph_json TEXT NOT NULL,
                    subtask_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING'
                );
                """
            )
            row = conn.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1;"
            ).fetchone()
            if not row:
                self._apply_initial_schema(conn)
            else:
                self._run_migrations(conn, current_version=row["version"])

    def _apply_initial_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS personal_os_triggers (
                trigger_id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                goal_text TEXT NOT NULL,
                schedule TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                last_fired_at TEXT,
                run_count INTEGER NOT NULL DEFAULT 0,
                last_result_summary TEXT,
                template_vars TEXT NOT NULL,
                metadata TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS personal_os_preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS personal_os_suspended_sessions (
                ticket_id TEXT PRIMARY KEY,
                trigger_id TEXT,
                session_id TEXT NOT NULL,
                task_graph_json TEXT NOT NULL,
                subtask_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING'
            );
            """
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO schema_version (version, applied_at)
            VALUES (?, ?);
            """,
            (self.CURRENT_SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        logger.info(
            f"[PersonalOSStateStore] Initial schema v{self.CURRENT_SCHEMA_VERSION} applied at {self.db_path}"
        )

    def _run_migrations(
        self, conn: sqlite3.Connection, current_version: int
    ) -> None:
        target_version = self.CURRENT_SCHEMA_VERSION
        if current_version >= target_version:
            return

        for target_ver in range(current_version + 1, target_version + 1):
            migrator = getattr(self, f"_migrate_to_v{target_ver}", None)
            if callable(migrator):
                migrator(conn)
            conn.execute(
                "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, ?);",
                (target_ver, datetime.now(timezone.utc).isoformat()),
            )
            logger.info(
                f"[PersonalOSStateStore] Successfully migrated schema to v{target_ver}"
            )
        conn.commit()

    # ── Trigger Operations ──────────────────────────────────────────────────

    def save_trigger(self, trigger: PersonalOSTrigger) -> None:
        """Insert or replace a trigger record in the SQLite database."""
        with self._db_lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO personal_os_triggers (
                    trigger_id, name, goal_text, schedule, enabled,
                    created_at, last_fired_at, run_count, last_result_summary,
                    template_vars, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trigger_id) DO UPDATE SET
                    name=excluded.name,
                    goal_text=excluded.goal_text,
                    schedule=excluded.schedule,
                    enabled=excluded.enabled,
                    template_vars=excluded.template_vars,
                    metadata=excluded.metadata;
                """,
                (
                    trigger.trigger_id,
                    trigger.name,
                    trigger.goal_text,
                    trigger.schedule,
                    1 if trigger.enabled else 0,
                    trigger.created_at,
                    trigger.last_fired_at,
                    trigger.run_count,
                    trigger.last_result_summary,
                    json.dumps(trigger.template_vars),
                    json.dumps(trigger.metadata),
                ),
            )
            conn.commit()

    def register_authorized_trigger(
        self,
        trigger: PersonalOSTrigger,
        allowed_capabilities: list[str] | None = None,
        execution_map: dict[str, Any] | None = None,
    ) -> PersonalOSTrigger:
        """
        Register a trigger and bind its cryptographic HMAC authorization signature
        for standing execution of whitelisted capabilities.
        """
        if allowed_capabilities:
            from desktop.native.security.approval_authority import CryptographicApprovalAuthority

            auth = CryptographicApprovalAuthority.get_instance()
            sig = auth.sign_trigger(
                trigger_id=trigger.trigger_id,
                action_goal=trigger.goal_text,
                allowed_capabilities=allowed_capabilities,
                execution_map=execution_map or {},
            )
            trigger.metadata["allowed_capabilities"] = allowed_capabilities
            trigger.metadata["auth_signature"] = sig
            if execution_map:
                trigger.metadata["execution_map"] = execution_map

        self.save_trigger(trigger)
        return trigger

    def get_trigger(self, identifier: str) -> PersonalOSTrigger | None:
        """Retrieve a trigger by trigger_id or exact name."""
        with self._db_lock, self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM personal_os_triggers
                WHERE trigger_id = ? OR name = ?
                LIMIT 1;
                """,
                (identifier, identifier),
            ).fetchone()
            if not row:
                return None
            return self._row_to_trigger(row)

    def list_triggers(
        self, enabled_only: bool = False
    ) -> list[PersonalOSTrigger]:
        """List stored triggers."""
        with self._db_lock, self._get_connection() as conn:
            query = "SELECT * FROM personal_os_triggers"
            if enabled_only:
                query += " WHERE enabled = 1"
            query += " ORDER BY name ASC;"
            rows = conn.execute(query).fetchall()
            return [self._row_to_trigger(r) for r in rows]

    def delete_trigger(self, identifier: str) -> bool:
        """Delete a trigger by trigger_id or name."""
        with self._db_lock, self._get_connection() as conn:
            cur = conn.execute(
                "DELETE FROM personal_os_triggers WHERE trigger_id = ? OR name = ?;",
                (identifier, identifier),
            )
            conn.commit()
            return cur.rowcount > 0

    def update_trigger_run(
        self,
        trigger_id: str,
        fired_at: str | None = None,
        result_summary: str | None = None,
    ) -> bool:
        """Record a successful or completed run of a trigger."""
        timestamp = fired_at or datetime.now(timezone.utc).isoformat()
        with self._db_lock, self._get_connection() as conn:
            cur = conn.execute(
                """
                UPDATE personal_os_triggers
                SET last_fired_at = ?,
                    run_count = run_count + 1,
                    last_result_summary = ?
                WHERE trigger_id = ?;
                """,
                (timestamp, result_summary, trigger_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def _row_to_trigger(self, row: sqlite3.Row) -> PersonalOSTrigger:
        template_vars: dict[str, Any] = {}
        metadata: dict[str, Any] = {}
        raw_tv = row["template_vars"]
        if raw_tv:
            try:
                template_vars = json.loads(raw_tv)
            except Exception as e:
                logger.warning(
                    f"[PersonalOSStateStore] Failed to deserialize template_vars for {row['trigger_id']}: {e}"
                )
        raw_meta = row["metadata"]
        if raw_meta:
            try:
                metadata = json.loads(raw_meta)
            except Exception as e:
                logger.warning(
                    f"[PersonalOSStateStore] Failed to deserialize metadata for {row['trigger_id']}: {e}"
                )

        return PersonalOSTrigger(
            trigger_id=row["trigger_id"],
            name=row["name"],
            goal_text=row["goal_text"],
            schedule=row["schedule"],
            enabled=bool(row["enabled"]),
            created_at=row["created_at"],
            last_fired_at=row["last_fired_at"],
            run_count=row["run_count"],
            last_result_summary=row["last_result_summary"],
            template_vars=template_vars,
            metadata=metadata,
        )

    # ── Preferences Operations ──────────────────────────────────────────────

    def set_preference(self, key: str, value: Any) -> None:
        """Save a user preference (JSON serializable)."""
        now = datetime.now(timezone.utc).isoformat()
        with self._db_lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO personal_os_preferences (key, value, updated_at)
                VALUES (?, ?, ?);
                """,
                (key, json.dumps(value), now),
            )
            conn.commit()

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Retrieve a stored preference or default."""
        with self._db_lock, self._get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM personal_os_preferences WHERE key = ? LIMIT 1;",
                (key,),
            ).fetchone()
            if not row:
                return default
            try:
                return json.loads(row["value"])
            except Exception:
                return default

    def get_all_preferences(self) -> dict[str, Any]:
        """Retrieve all stored preferences as a dictionary."""
        with self._db_lock, self._get_connection() as conn:
            rows = conn.execute(
                "SELECT key, value FROM personal_os_preferences;"
            ).fetchall()
            result = {}
            for r in rows:
                try:
                    result[r["key"]] = json.loads(r["value"])
                except Exception:
                    result[r["key"]] = r["value"]
            return result

    # ── Suspended Session Operations (Resumable Approvals) ───────────────────

    def save_suspended_session(
        self,
        ticket_id: str,
        trigger_id: str | None,
        session_id: str,
        task_graph_json: str,
        subtask_id: str,
        expires_at: float,
    ) -> None:
        """Persist a suspended DAG session awaiting cryptographic human approval."""
        now = datetime.now(timezone.utc).isoformat()
        with self._db_lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO personal_os_suspended_sessions
                (ticket_id, trigger_id, session_id, task_graph_json, subtask_id, created_at, expires_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING');
                """,
                (ticket_id, trigger_id, session_id, task_graph_json, subtask_id, now, expires_at),
            )
            conn.commit()

    def get_suspended_session(self, ticket_id: str) -> dict[str, Any] | None:
        """Retrieve suspended session details by ticket ID."""
        with self._db_lock, self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM personal_os_suspended_sessions WHERE ticket_id = ? LIMIT 1;",
                (ticket_id,),
            ).fetchone()
            if not row:
                return None
            return dict(row)

    def get_active_suspended_for_trigger(self, trigger_id: str) -> dict[str, Any] | None:
        """
        Check if a trigger already has an active, unexpired pending approval ticket.
        Used to prevent duplicate approval ticket pile-ups on recurring triggers.
        """
        now = time.time()
        with self._db_lock, self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM personal_os_suspended_sessions
                WHERE trigger_id = ? AND status = 'PENDING' AND expires_at > ?
                ORDER BY expires_at DESC LIMIT 1;
                """,
                (trigger_id, now),
            ).fetchone()
            if not row:
                return None
            return dict(row)

    def mark_suspended_session_status(self, ticket_id: str, status: str) -> None:
        """Update status of a suspended session (e.g. 'REDEEMED', 'EXPIRED_ABORTED', 'CANCELLED')."""
        with self._db_lock, self._get_connection() as conn:
            conn.execute(
                "UPDATE personal_os_suspended_sessions SET status = ? WHERE ticket_id = ?;",
                (status, ticket_id),
            )
            conn.commit()

    def cleanup_expired_suspended_sessions(self) -> int:
        """Clean up expired suspended sessions."""
        now = time.time()
        with self._db_lock, self._get_connection() as conn:
            cur = conn.execute(
                "UPDATE personal_os_suspended_sessions SET status = 'EXPIRED_ABORTED' WHERE status = 'PENDING' AND expires_at <= ?;",
                (now,),
            )
            conn.commit()
            return cur.rowcount
