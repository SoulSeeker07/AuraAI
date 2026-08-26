"""
M19.4 Runtime Checkpoint System (Hybrid In-Memory + SQLite Persistence)
========================================================================
Location: src/core/orchestration/runtime_checkpoint.py

Implements pre-action state capture, action reversibility classification, in-memory active rollback,
and SQLite persistence for crash resilience.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ActionReversibility(str, Enum):
    """Reversibility classification of state-modifying operations."""

    REVERSIBLE = "reversible"      # State can be restored automatically (e.g. file backup)
    RECOVERABLE = "recoverable"    # State cannot be undone directly, but alternative strategy can fix
    IRREVERSIBLE = "irreversible"  # Non-restorable external action (e.g. purchase, email send)


@dataclass
class RuntimeCheckpoint:
    """Snapshot of execution and environment state prior to action."""

    checkpoint_id: str
    session_id: str
    goal: str
    step_id: int
    reversibility: ActionReversibility = ActionReversibility.REVERSIBLE
    files_and_hashes: dict[str, str] = field(default_factory=dict)
    browser_url: str = ""
    window_process_ids: list[int] = field(default_factory=list)
    execution_state: str = "pending"
    verification_state: str = "unverified"
    recovery_state: str = "none"
    timestamp: str = field(default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "session_id": self.session_id,
            "goal": self.goal,
            "step_id": self.step_id,
            "reversibility": self.reversibility.value if isinstance(self.reversibility, ActionReversibility) else str(self.reversibility),
            "files_and_hashes": self.files_and_hashes,
            "browser_url": self.browser_url,
            "window_process_ids": self.window_process_ids,
            "execution_state": self.execution_state,
            "verification_state": self.verification_state,
            "recovery_state": self.recovery_state,
            "timestamp": self.timestamp,
        }


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = PROJECT_ROOT / "Memory.db"


class RuntimeCheckpointManager:
    """
    Manages active session checkpoints and persists state to SQLite.
    """

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            self.db_path = DEFAULT_DB_PATH
        else:
            p = Path(db_path)
            self.db_path = p if p.is_absolute() else (PROJECT_ROOT / p).resolve()
        self._active_checkpoints: dict[str, RuntimeCheckpoint] = {}
        self._init_db()

    def _init_db(self) -> None:
        """Initialize runtime_checkpoints table in SQLite database."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS runtime_checkpoints (
                        checkpoint_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        goal TEXT,
                        step_id INTEGER,
                        reversibility TEXT,
                        files_and_hashes TEXT,
                        browser_url TEXT,
                        window_process_ids TEXT,
                        execution_state TEXT,
                        verification_state TEXT,
                        recovery_state TEXT,
                        timestamp TEXT
                    )
                    """
                )
            conn.close()
        except Exception as e:
            logger.warning(f"RuntimeCheckpointManager SQLite init failed: {e}")

    def capture_file_hash(self, filepath: str | Path) -> str:
        """Compute SHA256 hash of a file for checkpoint state tracking."""
        p = Path(filepath)
        if not p.exists() or not p.is_file():
            return ""
        try:
            return hashlib.sha256(p.read_bytes()).hexdigest()
        except Exception:
            return ""

    def create_checkpoint(
        self,
        session_id: str,
        goal: str,
        step_id: int,
        files: list[str] | None = None,
        browser_url: str = "",
        window_pids: list[int] | None = None,
        reversibility: ActionReversibility = ActionReversibility.REVERSIBLE,
    ) -> RuntimeCheckpoint:
        """Create, cache, and persist a new RuntimeCheckpoint."""
        cid = str(uuid.uuid4())[:12]
        file_hashes: dict[str, str] = {}
        if files:
            for f in files:
                file_hashes[f] = self.capture_file_hash(f)

        cp = RuntimeCheckpoint(
            checkpoint_id=cid,
            session_id=session_id,
            goal=goal,
            step_id=step_id,
            reversibility=reversibility,
            files_and_hashes=file_hashes,
            browser_url=browser_url,
            window_process_ids=window_pids or [],
        )

        self._active_checkpoints[cid] = cp
        self.persist_checkpoint(cp)
        return cp

    def persist_checkpoint(self, checkpoint: RuntimeCheckpoint) -> bool:
        """Persist checkpoint metadata to SQLite table."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            with conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO runtime_checkpoints (
                        checkpoint_id, session_id, goal, step_id, reversibility,
                        files_and_hashes, browser_url, window_process_ids,
                        execution_state, verification_state, recovery_state, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        checkpoint.checkpoint_id,
                        checkpoint.session_id,
                        checkpoint.goal,
                        checkpoint.step_id,
                        checkpoint.reversibility.value if isinstance(checkpoint.reversibility, ActionReversibility) else str(checkpoint.reversibility),
                        json.dumps(checkpoint.files_and_hashes),
                        checkpoint.browser_url,
                        json.dumps(checkpoint.window_process_ids),
                        checkpoint.execution_state,
                        checkpoint.verification_state,
                        checkpoint.recovery_state,
                        checkpoint.timestamp,
                    ),
                )
            conn.close()
            return True
        except Exception as e:
            logger.warning(f"Failed to persist checkpoint {checkpoint.checkpoint_id}: {e}")
            return False

    def load_last_checkpoint(self, session_id: str) -> RuntimeCheckpoint | None:
        """Load the most recent persisted checkpoint for a given session."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM runtime_checkpoints
                WHERE session_id = ?
                ORDER BY timestamp DESC LIMIT 1
                """,
                (session_id,),
            )
            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            return RuntimeCheckpoint(
                checkpoint_id=row["checkpoint_id"],
                session_id=row["session_id"],
                goal=row["goal"],
                step_id=row["step_id"],
                reversibility=ActionReversibility(row["reversibility"]),
                files_and_hashes=json.loads(row["files_and_hashes"] or "{}"),
                browser_url=row["browser_url"] or "",
                window_process_ids=json.loads(row["window_process_ids"] or "[]"),
                execution_state=row["execution_state"],
                verification_state=row["verification_state"],
                recovery_state=row["recovery_state"],
                timestamp=row["timestamp"],
            )
        except Exception as e:
            logger.warning(f"Failed to load checkpoint for session {session_id}: {e}")
            return None


__all__ = ["ActionReversibility", "RuntimeCheckpoint", "RuntimeCheckpointManager"]
