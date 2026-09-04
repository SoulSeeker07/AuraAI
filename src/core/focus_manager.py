"""
FocusManager — Multi-Task Context Switching & Interrupt Routing
Location: src/core/focus_manager.py

Provides durable, cross-client focus thread tracking for AuraAI.
All clients (CLI, GUI, voice) share the same thread state through the
AuraCore.process_request() single-dispatch invariant.

Concurrency safety: SQLite WAL mode (PRAGMA journal_mode=WAL) allows
one writer + multiple concurrent readers without blocking, regardless of
whether clients are in-process or separate OS processes.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import logging
import re
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Generator, Literal

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

CURRENT_SCHEMA_VERSION = 1
DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "storage" / "focus_threads.db"

# Fuzzy match thresholds by slug length.
# Short strings score high by construction on SequenceMatcher regardless of
# semantic meaning ("fix bug" vs "fix build" → 0.82), so we require a much
# stricter ratio for short slugs and use embedding confirmation in the grey zone.
#
# Bucket boundaries:  len < 8   → require 0.90  (tight — must be near-identical)
#                     8 ≤ len < 16 → require 0.82  (moderate)
#                     len ≥ 16  → require 0.75  (original; long slugs are specific enough)
#
# Grey zone for short slugs (0.75–0.90): attempt embedding cosine first.
# If embedding is unavailable, DO NOT merge — create a new thread instead.
# This trades an occasional duplicate thread for never silently losing work.
_FUZZY_SHORT_THRESHOLD = 0.90   # slug len < 8
_FUZZY_MEDIUM_THRESHOLD = 0.82  # 8 ≤ slug len < 16
_FUZZY_LONG_THRESHOLD = 0.75    # slug len ≥ 16
_FUZZY_GREY_FLOOR = 0.75        # minimum ratio to even attempt embedding for short slugs


def _fuzzy_threshold(slug: str) -> float:
    """Return the SequenceMatcher ratio threshold appropriate for slug length."""
    n = len(slug)
    if n < 8:
        return _FUZZY_SHORT_THRESHOLD
    if n < 16:
        return _FUZZY_MEDIUM_THRESHOLD
    return _FUZZY_LONG_THRESHOLD

# Pending notifications surfaced per turn (cap to avoid noisy responses).
MAX_NOTIFICATIONS_PER_TURN = 3

FocusStatus = Literal["active", "paused", "waiting"]
SeverityOrigin = Literal["user", "background_agent"]


# ── Data model ─────────────────────────────────────────────────────────────────

@dataclass
class FocusThread:
    """Represents one persistent working-context thread."""

    task_id: str
    state: dict[str, Any] = field(default_factory=dict)
    status: FocusStatus = "active"
    last_touched: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    severity_origin: SeverityOrigin = "user"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "FocusThread":
        return cls(
            task_id=row["task_id"],
            state=json.loads(row["state"] or "{}"),
            status=row["status"],
            last_touched=row["last_touched"],
            severity_origin=row["severity_origin"],
        )


@dataclass
class PendingNotification:
    """A buffered interrupt notification awaiting delivery."""

    notification_id: str
    task_id: str
    message: str
    severity: str  # RiskLevel value string
    created_at: str
    delivered: bool = False
    state_hash: str = ""


# ── FocusManager ───────────────────────────────────────────────────────────────

class FocusManager:
    """
    Thread-safe SQLite singleton managing multi-task focus threads and
    buffered interrupt notifications.

    Usage (via AuraCore):
        fm = FocusManager.get_instance(db_path=...)
        fm.create("api_refactor", {})
        fm.switch_to("documentation")
        snippet = fm.get_current_state_snippet()   # inject into LLM prompt
    """

    _instance: "FocusManager | None" = None
    _class_lock = threading.Lock()

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_lock = threading.RLock()
        self._current_focus: str | None = None
        self._init_db()

    # ── Singleton ──────────────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls, db_path: Path | str | None = None) -> "FocusManager":
        with cls._class_lock:
            if cls._instance is None:
                cls._instance = cls(db_path=db_path)
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (primarily for test isolation)."""
        with cls._class_lock:
            cls._instance = None

    # ── DB bootstrap ───────────────────────────────────────────────────────────

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path), timeout=15.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._db_lock, self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
            """)
            row = conn.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1;"
            ).fetchone()
            if not row:
                self._apply_initial_schema(conn)
            else:
                self._run_migrations(conn, current_version=row["version"])

    def _apply_initial_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS focus_threads (
                task_id         TEXT PRIMARY KEY,
                state           TEXT NOT NULL DEFAULT '{}',
                status          TEXT NOT NULL DEFAULT 'active',
                last_touched    TEXT NOT NULL,
                severity_origin TEXT NOT NULL DEFAULT 'user'
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_notifications (
                notification_id TEXT PRIMARY KEY,
                task_id         TEXT NOT NULL,
                message         TEXT NOT NULL,
                severity        TEXT NOT NULL,
                created_at      TEXT NOT NULL,
                delivered       INTEGER NOT NULL DEFAULT 0,
                state_hash      TEXT NOT NULL DEFAULT ''
            );
        """)
        conn.execute(
            "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, ?);",
            (CURRENT_SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        logger.info(f"[FocusManager] Initial schema v{CURRENT_SCHEMA_VERSION} applied at {self.db_path}")

    def _run_migrations(self, conn: sqlite3.Connection, current_version: int) -> None:
        target = CURRENT_SCHEMA_VERSION
        if current_version >= target:
            return
        for v in range(current_version + 1, target + 1):
            migrator = getattr(self, f"_migrate_to_v{v}", None)
            if callable(migrator):
                migrator(conn)
            conn.execute(
                "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, ?);",
                (v, datetime.now(timezone.utc).isoformat()),
            )
            logger.info(f"[FocusManager] Schema migrated to v{v}")
        conn.commit()

    # ── Core thread operations ─────────────────────────────────────────────────

    def create(
        self,
        task_id: str,
        initial_state: dict[str, Any] | None = None,
        severity_origin: SeverityOrigin = "user",
    ) -> FocusThread:
        """
        Create a new focus thread, or resume an existing one if a fuzzy
        match is found against active/paused threads.

        Returns the resolved FocusThread (may be an existing thread).
        """
        # --- Fuzzy dedup: avoid silently minting duplicate threads ---
        existing = self._fuzzy_match(task_id)
        if existing is not None:
            logger.info(
                f"[FocusManager] Fuzzy match '{task_id}' → existing thread '{existing.task_id}'; resuming."
            )
            return self.resume(existing.task_id)

        now = datetime.now(timezone.utc).isoformat()
        thread = FocusThread(
            task_id=task_id,
            state=initial_state or {},
            status="active",
            last_touched=now,
            severity_origin=severity_origin,
        )
        with self._db_lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO focus_threads
                    (task_id, state, status, last_touched, severity_origin)
                VALUES (?, ?, ?, ?, ?);
                """,
                (
                    thread.task_id,
                    json.dumps(thread.state),
                    thread.status,
                    thread.last_touched,
                    thread.severity_origin,
                ),
            )
            conn.commit()

        self._current_focus = task_id
        logger.info(f"[FocusManager] Created thread '{task_id}' (origin={severity_origin})")
        return thread

    def switch_to(self, task_id: str) -> FocusThread:
        """
        Pause the current focus thread and activate task_id.
        If task_id doesn't exist, creates it first.
        """
        # Pause whatever is currently active
        current = self._current_focus
        if current and current != task_id:
            self.pause(current)

        # Ensure target exists
        existing = self._load_thread(task_id)
        if existing is None:
            return self.create(task_id, severity_origin="background_agent")

        return self.resume(task_id)

    def pause(self, task_id: str) -> None:
        """Mark a thread as paused."""
        with self._db_lock, self._get_connection() as conn:
            conn.execute(
                "UPDATE focus_threads SET status='paused' WHERE task_id=?;",
                (task_id,),
            )
            conn.commit()
        if self._current_focus == task_id:
            self._current_focus = None
        logger.debug(f"[FocusManager] Paused thread '{task_id}'")

    def resume(self, task_id: str) -> FocusThread:
        """
        Mark task_id as active and update last_touched.
        Any previously active thread is paused first.
        """
        # Pause previously active thread (if different)
        current = self._current_focus
        if current and current != task_id:
            self.pause(current)

        now = datetime.now(timezone.utc).isoformat()
        with self._db_lock, self._get_connection() as conn:
            conn.execute(
                "UPDATE focus_threads SET status='active', last_touched=? WHERE task_id=?;",
                (now, task_id),
            )
            conn.commit()

        self._current_focus = task_id
        thread = self._load_thread(task_id)
        logger.info(f"[FocusManager] Resumed thread '{task_id}'")
        return thread or FocusThread(task_id=task_id, last_touched=now)

    def get_current(self) -> FocusThread | None:
        """Return the currently active FocusThread, or None."""
        if self._current_focus:
            t = self._load_thread(self._current_focus)
            if t is not None:
                return t
        # DB fallback: pick most-recently-touched active thread
        with self._db_lock, self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM focus_threads WHERE status='active' ORDER BY last_touched DESC LIMIT 1;"
            ).fetchone()
        if row:
            t = FocusThread.from_row(row)
            self._current_focus = t.task_id
            return t
        return None

    def list_active(self) -> list[FocusThread]:
        """Return all non-archived threads (active + paused)."""
        with self._db_lock, self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM focus_threads ORDER BY last_touched DESC;"
            ).fetchall()
        return [FocusThread.from_row(r) for r in rows]

    def update_state(self, task_id: str, new_state: dict[str, Any]) -> None:
        """Merge new_state into the thread's working context, update last_touched."""
        thread = self._load_thread(task_id)
        if thread is None:
            logger.warning(f"[FocusManager] update_state: unknown task_id '{task_id}'")
            return
        merged = {**thread.state, **new_state}
        now = datetime.now(timezone.utc).isoformat()
        with self._db_lock, self._get_connection() as conn:
            conn.execute(
                "UPDATE focus_threads SET state=?, last_touched=? WHERE task_id=?;",
                (json.dumps(merged), now, task_id),
            )
            conn.commit()

    def get_current_state_snippet(self, max_chars: int = 400) -> str:
        """
        Returns a formatted string suitable for injection into the LLM system
        prompt as focus/working-context rehydration.
        """
        thread = self.get_current()
        if thread is None:
            return ""
        state_text = json.dumps(thread.state, ensure_ascii=False)[:max_chars]
        return (
            f"### Current Focus Thread\n"
            f"- Task: {thread.task_id}\n"
            f"- Status: {thread.status}\n"
            f"- Working Context: {state_text}\n"
            f"- Last Active: {thread.last_touched}\n"
        )

    # ── Fuzzy task-ID resolution ────────────────────────────────────────────────

    def _fuzzy_match(self, task_id: str) -> FocusThread | None:
        """
        Check active/paused threads for a semantically similar task_id.

        Uses a length-weighted threshold to prevent short-slug false merges:
          - len < 8:   ratio ≥ 0.90  ("fix bug" vs "fix build" must not merge)
          - len 8–15:  ratio ≥ 0.82
          - len ≥ 16:  ratio ≥ 0.75  (long slugs are already specific)

        Grey zone for short slugs (ratio in [0.75, 0.90)):
          → Attempt embedding cosine confirmation first.
          → If embedding unavailable, refuse to merge (create new thread).
          This ensures we never silently lose a task context.
        """
        candidates = self.list_active()
        if not candidates:
            return None

        slug = task_id.lower().strip()
        threshold = _fuzzy_threshold(slug)
        is_short = len(slug) < 8

        # 1. difflib scan — find best ratio across all candidates
        best_ratio = 0.0
        best_thread: FocusThread | None = None
        for thread in candidates:
            ratio = difflib.SequenceMatcher(
                None, slug, thread.task_id.lower().strip()
            ).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_thread = thread

        # 2a. Clear match — ratio meets the length-adjusted threshold
        if best_ratio >= threshold and best_thread is not None:
            logger.debug(
                f"[FocusManager] difflib match '{task_id}' → '{best_thread.task_id}' "
                f"(ratio={best_ratio:.2f}, threshold={threshold})"
            )
            return best_thread

        # 2b. Grey zone (ratio in [0.75, threshold)):
        #     Attempt embedding cosine confirmation. If embedding is unavailable
        #     or cosine < threshold, refuse to merge (create new thread).
        if best_ratio >= _FUZZY_GREY_FLOOR and best_thread is not None:
            embed_match = self._embedding_confirm(slug, best_thread, threshold=threshold)
            if embed_match is not None:
                return embed_match
            logger.debug(
                f"[FocusManager] Slug '{task_id}' grey-zone: ratio={best_ratio:.2f} "
                f"below threshold={threshold} and no embedding confirmation — creating new thread."
            )
            return None

        return None

    def _embedding_confirm(
        self,
        slug: str,
        candidate: FocusThread,
        threshold: float,
    ) -> FocusThread | None:
        """
        Attempt embedding cosine confirmation for a candidate match.
        Returns the candidate if cosine ≥ threshold, else None.
        Silently returns None if embeddings are unavailable.
        """
        try:
            from memory.cognitive_memory import CognitiveMemoryEngine
            import numpy as np

            engine = CognitiveMemoryEngine()
            if not hasattr(engine.recall_engine, "embed"):
                return None

            query_vec = engine.recall_engine.embed(slug)
            cand_vec = engine.recall_engine.embed(candidate.task_id.lower())
            denom = float(np.linalg.norm(query_vec) * np.linalg.norm(cand_vec))
            if denom <= 0:
                return None
            cosine = float(np.dot(query_vec, cand_vec) / denom)
            if cosine >= threshold:
                logger.debug(
                    f"[FocusManager] Embedding cosine confirmed '{slug}' → "
                    f"'{candidate.task_id}' (cosine={cosine:.2f})"
                )
                return candidate
            logger.debug(
                f"[FocusManager] Embedding cosine rejected '{slug}' → "
                f"'{candidate.task_id}' (cosine={cosine:.2f} < threshold={threshold})"
            )
        except Exception as e:
            logger.debug(f"[FocusManager] Embedding confirmation skipped: {e}")
        return None

    # ── Notification queue ─────────────────────────────────────────────────────

    def enqueue_notification(
        self, task_id: str, message: str, severity: str
    ) -> None:
        """
        Add a LOW/MEDIUM severity interrupt to the pending queue.
        A state_hash is stored so that re-delivery only occurs if the
        message content changes (dedupe rule).
        """
        state_hash = hashlib.sha256(message.encode()).hexdigest()[:16]

        # Check if an identical (undelivered or delivered-but-unchanged) notification exists
        with self._db_lock, self._get_connection() as conn:
            existing = conn.execute(
                """
                SELECT notification_id FROM pending_notifications
                WHERE task_id=? AND state_hash=? AND delivered=1
                LIMIT 1;
                """,
                (task_id, state_hash),
            ).fetchone()
            if existing:
                # Same message already delivered — skip duplicate
                logger.debug(
                    f"[FocusManager] Notification dedupe: same state_hash for task '{task_id}', skipped."
                )
                return

            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                INSERT INTO pending_notifications
                    (notification_id, task_id, message, severity, created_at, delivered, state_hash)
                VALUES (?, ?, ?, ?, ?, 0, ?);
                """,
                (str(uuid.uuid4()), task_id, message, severity, now, state_hash),
            )
            conn.commit()
        logger.debug(f"[FocusManager] Enqueued notification for task '{task_id}' (severity={severity})")

    @staticmethod
    def _is_notification_expired(message: str, created_at: str) -> bool:
        """
        Check whether a pending notification should be suppressed as stale or expired.
        1. If it refers to an approval ticket (tkt_... or AUTH-...), check whether the ticket
           is still valid and unexpired in CryptographicApprovalAuthority / PersonalOSStateStore.
        2. If created_at is older than 24 hours, treat as expired.
        """
        tkt_match = re.search(
            r"\b(tkt_[a-f0-9]{6,16}|(?:AUTH|TICK)-[A-F0-9]{4,12})\b",
            message,
            re.IGNORECASE,
        )
        if tkt_match:
            ticket_id = tkt_match.group(1)
            now = time.time()
            if ticket_id.lower().startswith("tkt_"):
                try:
                    from desktop.native.security.approval_authority import (
                        CryptographicApprovalAuthority,
                    )

                    auth = CryptographicApprovalAuthority.get_instance()
                    ticket = auth.get_ticket(ticket_id.lower())
                    if ticket:
                        if ticket.is_redeemed or ticket.expires_at <= now:
                            return True
                    else:
                        from personal_os.state_store import PersonalOSStateStore

                        sess = (
                            PersonalOSStateStore.get_instance().get_suspended_session(
                                ticket_id.lower()
                            )
                        )
                        if (
                            not sess
                            or sess.get("status") != "PENDING"
                            or sess.get("expires_at", 0) <= now
                        ):
                            return True
                except Exception:
                    pass
            elif ticket_id.upper().startswith(("AUTH-", "TICK-")):
                try:
                    from browser.paused_session import PausedSessionStore

                    store = PausedSessionStore.get_instance()
                    if not store.has_pending():
                        return True
                except Exception:
                    pass

        try:
            dt = datetime.fromisoformat(created_at)
            if (datetime.now(timezone.utc) - dt).total_seconds() > 86400:
                return True
        except Exception:
            pass

        return False

    def drain_pending_notifications(self) -> list[PendingNotification]:
        """
        Return up to MAX_NOTIFICATIONS_PER_TURN undelivered notifications,
        mark them delivered=1. Thread-safe.
        Filters out stale notifications whose security approval tickets have expired,
        been cancelled, or been redeemed, and automatically marks them delivered.
        """
        active_notifications: list[PendingNotification] = []
        ids_to_mark_delivered: list[str] = []

        with self._db_lock, self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM pending_notifications
                WHERE delivered=0
                ORDER BY created_at ASC
                LIMIT 50;
                """,
            ).fetchall()

            if not rows:
                return []

            for r in rows:
                ids_to_mark_delivered.append(r["notification_id"])
                if self._is_notification_expired(r["message"], r["created_at"]):
                    logger.debug(
                        f"[FocusManager] Suppressing expired notification {r['notification_id']}"
                    )
                    continue

                active_notifications.append(
                    PendingNotification(
                        notification_id=r["notification_id"],
                        task_id=r["task_id"],
                        message=r["message"],
                        severity=r["severity"],
                        created_at=r["created_at"],
                        delivered=True,
                        state_hash=r["state_hash"],
                    )
                )
                if len(active_notifications) >= MAX_NOTIFICATIONS_PER_TURN:
                    break

            if ids_to_mark_delivered:
                placeholders = ",".join("?" * len(ids_to_mark_delivered))
                conn.execute(
                    f"UPDATE pending_notifications SET delivered=1 WHERE notification_id IN ({placeholders});",
                    ids_to_mark_delivered,
                )
                conn.commit()

        logger.debug(
            f"[FocusManager] Drained {len(active_notifications)} pending notification(s) "
            f"({len(ids_to_mark_delivered) - len(active_notifications)} stale suppressed)"
        )
        return active_notifications

    # ── Stale archival ─────────────────────────────────────────────────────────

    def archive_stale(self, max_age_hours: float = 24.0) -> int:
        """
        Archive threads untouched beyond max_age_hours:
        1. Write a summary MemoryItem into CognitiveMemoryEngine (long-term store)
        2. Delete the thread row from focus_threads
        3. Clean up delivered notifications older than 7 days

        Returns the number of archived threads.
        """
        cutoff = (
            datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        ).isoformat()

        with self._db_lock, self._get_connection() as conn:
            stale_rows = conn.execute(
                "SELECT * FROM focus_threads WHERE last_touched < ?;",
                (cutoff,),
            ).fetchall()

        if not stale_rows:
            return 0

        archived = 0
        for row in stale_rows:
            thread = FocusThread.from_row(row)
            self._persist_to_long_term_memory(thread)
            with self._db_lock, self._get_connection() as conn:
                conn.execute(
                    "DELETE FROM focus_threads WHERE task_id=?;",
                    (thread.task_id,),
                )
                conn.commit()
            if self._current_focus == thread.task_id:
                self._current_focus = None
            archived += 1
            logger.info(f"[FocusManager] Archived stale thread '{thread.task_id}'")

        # Prune delivered notifications older than 7 days
        week_ago = (
            datetime.now(timezone.utc) - timedelta(days=7)
        ).isoformat()
        with self._db_lock, self._get_connection() as conn:
            conn.execute(
                "DELETE FROM pending_notifications WHERE delivered=1 AND created_at < ?;",
                (week_ago,),
            )
            conn.commit()

        return archived

    def close_thread(self, task_id: str) -> bool:
        """Close/archive a single specific focus thread and persist it to long-term memory."""
        thread = self._load_thread(task_id)
        if thread is None:
            thread = self._fuzzy_match(task_id)
        if thread:
            self._persist_to_long_term_memory(thread)
            with self._db_lock, self._get_connection() as conn:
                conn.execute("DELETE FROM focus_threads WHERE task_id=?;", (thread.task_id,))
                conn.commit()
            if self._current_focus == thread.task_id:
                self._current_focus = None
            logger.info(f"[FocusManager] Closed thread '{thread.task_id}'")
            return True
        return False

    def close_all_threads(self) -> int:
        """Close/archive ALL active focus threads and persist them to long-term memory."""
        active = self.list_active()
        count = 0
        for thread in active:
            self._persist_to_long_term_memory(thread)
            with self._db_lock, self._get_connection() as conn:
                conn.execute("DELETE FROM focus_threads WHERE task_id=?;", (thread.task_id,))
                conn.commit()
            count += 1
        self._current_focus = None
        logger.info(f"[FocusManager] Closed all {count} focus threads")
        return count

    def _persist_to_long_term_memory(self, thread: FocusThread) -> None:
        """Write a thread summary into CognitiveMemoryEngine as a SEMANTIC memory item."""
        try:
            from memory.cognitive_memory import CognitiveMemoryEngine
            from memory.models import MemoryItem, MemoryType, MemoryProvenance, ProvenanceSource

            engine = CognitiveMemoryEngine()
            summary = thread.state.get("last_summary", f"Task: {thread.task_id}")
            item = MemoryItem(
                memory_id=f"focus_{thread.task_id}_{uuid.uuid4().hex[:8]}",
                type=MemoryType.SEMANTIC,
                content=summary,
                provenance=MemoryProvenance(source=ProvenanceSource.SYSTEM),
                importance=0.5,
                confidence=1.0,
                project_id="focus_manager",
                topic=thread.task_id,
            )
            engine.store(item)
            logger.info(
                f"[FocusManager] Persisted thread '{thread.task_id}' to long-term semantic memory."
            )
        except Exception as e:
            logger.warning(f"[FocusManager] Long-term memory persistence skipped: {e}")

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _load_thread(self, task_id: str) -> FocusThread | None:
        with self._db_lock, self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM focus_threads WHERE task_id=?;", (task_id,)
            ).fetchone()
        return FocusThread.from_row(row) if row else None
