"""
Capability Usage Tracker
========================
Location: src/core/capabilities/capability_usage_tracker.py

Live instrumentation for the Universal Capability Registry.
Records which capabilities are dispatched, how often, and when --
powering the coverage dashboard and least-used analysis.

Design:
- WAL SQLite at {project_root}/storage/capability_usage.db
  (same storage/ convention as focus_threads.db, personal_os.db)
- One UPSERT per confirmed capability dispatch -- no polling writers
- Thread-safe: voice pipeline, triggers, GUI all fire concurrently
- Singleton via get_tracker() -- construct once, reuse everywhere
- Degrades silently: record_usage() never raises -- it's instrumentation

Hook point:
  _execute_level_task() in master_orchestrator.py, after policy check clears
  and backend is confirmed non-None, immediately before _dispatch_to_backend().
  This is the same chokepoint your AST governance guardrail already enforces,
  so anything that bypasses tracking also fails that test.

Denominator:
  Always len(CapabilityRegistry.list()) -- never hardcoded.
  Coverage % stays correct as capabilities are added/removed.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Optional

logger = logging.getLogger(__name__)

# Project root: src/core/capabilities/ -> parents[3] -> project root
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DB_PATH = _PROJECT_ROOT / "storage" / "capability_usage.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS capability_usage (
    capability_id   TEXT PRIMARY KEY,
    usage_count     INTEGER NOT NULL DEFAULT 0,
    first_used_at   REAL,
    last_used_at    REAL,
    last_risk_level TEXT,
    last_source     TEXT
);
CREATE INDEX IF NOT EXISTS idx_cap_last_used
    ON capability_usage(last_used_at DESC);
CREATE INDEX IF NOT EXISTS idx_cap_count
    ON capability_usage(usage_count);
"""


@dataclass
class CapabilityStat:
    capability_id: str
    usage_count: int
    first_used_at: Optional[float]
    last_used_at: Optional[float]
    last_risk_level: Optional[str]
    last_source: Optional[str]


class CapabilityUsageTracker:
    """
    Singleton usage tracker.  Obtain via get_tracker(), not direct instantiation.
    """

    _instance: Optional["CapabilityUsageTracker"] = None
    _instance_lock: threading.Lock = threading.Lock()

    def __init__(self, db_path: Path = _DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()
        self._init_db()

    @classmethod
    def get_instance(cls, db_path: Path = _DEFAULT_DB_PATH) -> "CapabilityUsageTracker":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls(db_path=db_path)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (test teardown only)."""
        with cls._instance_lock:
            cls._instance = None

    # -- DB helpers ----------------------------------------------------------

    def _init_db(self) -> None:
        try:
            with self._connect() as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA busy_timeout=3000;")
                conn.executescript(_SCHEMA)
        except Exception as exc:
            logger.warning(f"[CapabilityTracker] DB init failed: {exc}")

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path), timeout=5.0, check_same_thread=False)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # -- Write path ----------------------------------------------------------

    def record_usage(
        self,
        capability_id: str,
        risk_level: Optional[str] = None,
        source: Optional[str] = None,
    ) -> None:
        """
        Record one confirmed capability dispatch.

        Call this exactly once per dispatched capability -- at the single
        canonical chokepoint after all policy/auth checks have cleared.
        Never raises: instrumentation must not affect execution paths.
        """
        try:
            now = time.time()
            with self._write_lock, self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO capability_usage
                        (capability_id, usage_count, first_used_at, last_used_at,
                         last_risk_level, last_source)
                    VALUES (?, 1, ?, ?, ?, ?)
                    ON CONFLICT(capability_id) DO UPDATE SET
                        usage_count     = usage_count + 1,
                        last_used_at    = excluded.last_used_at,
                        last_risk_level = excluded.last_risk_level,
                        last_source     = excluded.last_source
                    """,
                    (capability_id, now, now, risk_level, source),
                )
            logger.debug(
                f"[CapabilityTracker] Recorded: {capability_id!r} "
                f"(risk={risk_level}, src={source})"
            )
        except Exception as exc:
            logger.debug(f"[CapabilityTracker] record_usage failed silently: {exc}")

    # -- Read path -----------------------------------------------------------

    def _get_all_stats(self) -> list[CapabilityStat]:
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT capability_id, usage_count, first_used_at, "
                    "last_used_at, last_risk_level, last_source "
                    "FROM capability_usage"
                ).fetchall()
            return [CapabilityStat(*row) for row in rows]
        except Exception as exc:
            logger.debug(f"[CapabilityTracker] _get_all_stats failed: {exc}")
            return []

    def get_coverage(self, total_registered: int) -> dict:
        """
        Compute coverage metrics.
        Pass len(CapabilityRegistry.get_instance().list()) as total_registered --
        never a hardcoded number.
        """
        try:
            with self._connect() as conn:
                used = conn.execute(
                    "SELECT COUNT(*) FROM capability_usage WHERE usage_count > 0"
                ).fetchone()[0]
            pct = (used / total_registered * 100.0) if total_registered else 0.0
            return {
                "total_registered": total_registered,
                "used_at_least_once": used,
                "never_used": max(0, total_registered - used),
                "coverage_pct": round(pct, 1),
            }
        except Exception as exc:
            logger.debug(f"[CapabilityTracker] get_coverage failed: {exc}")
            return {
                "total_registered": total_registered,
                "used_at_least_once": 0,
                "never_used": total_registered,
                "coverage_pct": 0.0,
            }

    def get_least_used(
        self, all_capability_ids: list[str], n: int = 15
    ) -> list[CapabilityStat]:
        """
        Return the N least-used capabilities.
        Includes never-used capabilities (usage_count=0) from the full registry --
        a capability with no rows in the DB is still "least used".
        """
        known = {s.capability_id: s for s in self._get_all_stats()}
        merged = [
            known.get(
                cid,
                CapabilityStat(
                    capability_id=cid,
                    usage_count=0,
                    first_used_at=None,
                    last_used_at=None,
                    last_risk_level=None,
                    last_source=None,
                ),
            )
            for cid in all_capability_ids
        ]
        merged.sort(key=lambda s: (s.usage_count, s.last_used_at or 0.0))
        return merged[:n]

    def get_most_recent(self, n: int = 15) -> list[CapabilityStat]:
        """Return the N most recently used capabilities, sorted descending by last_used_at."""
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT capability_id, usage_count, first_used_at, "
                    "last_used_at, last_risk_level, last_source "
                    "FROM capability_usage "
                    "WHERE last_used_at IS NOT NULL "
                    "ORDER BY last_used_at DESC LIMIT ?",
                    (n,),
                ).fetchall()
            return [CapabilityStat(*row) for row in rows]
        except Exception as exc:
            logger.debug(f"[CapabilityTracker] get_most_recent failed: {exc}")
            return []

    def export_dashboard_json(self, all_capability_ids: list[str]) -> dict:
        """
        Single call returning everything the dashboard widget needs.
        Cheap enough for a 3s poll tick: indexed COUNT + ORDER BY on a small table.
        """
        coverage = self.get_coverage(len(all_capability_ids))
        least = self.get_least_used(all_capability_ids, n=15)
        recent = self.get_most_recent(n=15)
        return {
            "generated_at": time.time(),
            "coverage": coverage,
            "least_used": [vars(s) for s in least],
            "most_recent": [vars(s) for s in recent],
        }

    def export_dashboard_file(
        self, all_capability_ids: list[str], out_path: Path
    ) -> None:
        """
        Write dashboard JSON to a file for JS file-polling.
        Atomic write (write to .tmp, rename) so the HTML page never reads a partial file.
        """
        try:
            data = self.export_dashboard_json(all_capability_ids)
            out_path = Path(out_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = out_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp.replace(out_path)
        except Exception as exc:
            logger.debug(f"[CapabilityTracker] export_dashboard_file failed: {exc}")


# Module-level singleton accessor
def get_tracker() -> CapabilityUsageTracker:
    """Return the process-wide CapabilityUsageTracker singleton."""
    return CapabilityUsageTracker.get_instance()