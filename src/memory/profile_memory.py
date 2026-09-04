"""
ProfileMemory — Deterministic Identity & Structured Preferences Store (Tier 3)
==============================================================================
Location: src/memory/profile_memory.py

ACID SQLite store for deterministic, verified user identity, core preferences,
and system configuration. Completely isolated from fuzzy vector recall, decay
algorithms, and conversational drift.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ProfileMemory:
    """
    Tier 3 Memory Store: Deterministic User Profile & Identity.

    Guarantees:
    - ACID transactions with immediate WAL writes.
    - Zero vector fuzziness (exact key-value lookups).
    - Zero decay or loss across conversational turns.
    - Automatic type preservation (str, int, float, bool, list, dict).
    """

    _instance: Optional["ProfileMemory"] = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self, db_path: Optional[Path | str] = None):
        if db_path is None:
            data_dir = Path(__file__).resolve().parents[2] / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = data_dir / "profile.db"
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._local_lock = threading.Lock()
        self._init_db()

    @classmethod
    def get_instance(cls, db_path: Optional[Path | str] = None) -> "ProfileMemory":
        """Thread-safe process-wide singleton accessor."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(db_path)
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (primarily for testing)."""
        with cls._lock:
            cls._instance = None

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        with self._local_lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS profile_facts (
                        category TEXT NOT NULL,
                        key TEXT NOT NULL,
                        value TEXT NOT NULL,
                        value_type TEXT NOT NULL,
                        source TEXT NOT NULL,
                        confidence REAL DEFAULT 1.0,
                        updated_at TIMESTAMP NOT NULL,
                        PRIMARY KEY (category, key)
                    );
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_profile_cat ON profile_facts (category);"
                )
                conn.commit()

    def _serialize_value(self, value: Any) -> tuple[str, str]:
        if isinstance(value, bool):
            return str(value).lower(), "bool"
        elif isinstance(value, int):
            return str(value), "int"
        elif isinstance(value, float):
            return str(value), "float"
        elif isinstance(value, (dict, list)):
            return json.dumps(value), "json"
        elif value is None:
            return "", "none"
        else:
            return str(value), "str"

    def _deserialize_value(self, raw_value: str, value_type: str) -> Any:
        if value_type == "bool":
            return raw_value.lower() == "true"
        elif value_type == "int":
            try:
                return int(raw_value)
            except ValueError:
                return 0
        elif value_type == "float":
            try:
                return float(raw_value)
            except ValueError:
                return 0.0
        elif value_type == "json":
            try:
                return json.loads(raw_value)
            except Exception:
                return raw_value
        elif value_type == "none":
            return None
        return raw_value

    def set_fact(
        self,
        category: str,
        key: str,
        value: Any,
        source: str = "user",
        confidence: float = 1.0,
    ) -> None:
        """Store or update a deterministic profile fact."""
        cat_clean = category.strip().lower()
        key_clean = key.strip().lower()
        val_str, val_type = self._serialize_value(value)
        now = datetime.now().isoformat()

        with self._local_lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO profile_facts (category, key, value, value_type, source, confidence, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(category, key) DO UPDATE SET
                        value = excluded.value,
                        value_type = excluded.value_type,
                        source = excluded.source,
                        confidence = excluded.confidence,
                        updated_at = excluded.updated_at;
                    """,
                    (cat_clean, key_clean, val_str, val_type, source, confidence, now),
                )
                conn.commit()
        logger.debug(f"[ProfileMemory] Saved fact [{cat_clean}:{key_clean}] ({val_type})")

    def get_fact(self, category: str, key: str, default: Any = None) -> Any:
        """Retrieve a deterministic profile fact by category and key."""
        cat_clean = category.strip().lower()
        key_clean = key.strip().lower()

        with self._local_lock:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT value, value_type FROM profile_facts WHERE category = ? AND key = ? LIMIT 1;",
                    (cat_clean, key_clean),
                )
                row = cursor.fetchone()

        if row is None:
            return default

        raw_val, val_type = row
        return self._deserialize_value(raw_val, val_type)

    def delete_fact(self, category: str, key: str) -> bool:
        """Delete a profile fact. Returns True if deleted."""
        cat_clean = category.strip().lower()
        key_clean = key.strip().lower()

        with self._local_lock:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM profile_facts WHERE category = ? AND key = ?;",
                    (cat_clean, key_clean),
                )
                conn.commit()
                return cursor.rowcount > 0

    def list_facts(self, category: Optional[str] = None) -> dict[str, Any]:
        """List all facts, optionally filtered by category."""
        results: dict[str, Any] = {}
        with self._local_lock:
            with self._get_connection() as conn:
                if category:
                    cat_clean = category.strip().lower()
                    cursor = conn.execute(
                        "SELECT key, value, value_type FROM profile_facts WHERE category = ? ORDER BY key;",
                        (cat_clean,),
                    )
                    for key, val_str, val_type in cursor.fetchall():
                        results[key] = self._deserialize_value(val_str, val_type)
                else:
                    cursor = conn.execute(
                        "SELECT category, key, value, value_type FROM profile_facts ORDER BY category, key;"
                    )
                    for cat, key, val_str, val_type in cursor.fetchall():
                        if cat not in results:
                            results[cat] = {}
                        results[cat][key] = self._deserialize_value(val_str, val_type)
        return results

    def get_identity(self) -> dict[str, Any]:
        """Convenience method to retrieve all identity-related facts (name, email, role, etc.)."""
        return self.list_facts(category="identity")

    def get_preferences(self) -> dict[str, Any]:
        """Convenience method to retrieve user preferences (editor, theme, developer_mode, etc.)."""
        return self.list_facts(category="preferences")

    def export_profile(self) -> dict[str, dict[str, Any]]:
        """Export the full profile as a nested dictionary."""
        return self.list_facts()

    def import_profile(self, data: dict[str, dict[str, Any]], source: str = "import") -> None:
        """Import facts into ProfileMemory from an external dictionary."""
        for cat, facts in data.items():
            if isinstance(facts, dict):
                for key, val in facts.items():
                    self.set_fact(cat, key, val, source=source)

    def migrate_from_legacy(self, facts_db_path: "Path | str") -> int:
        """
        Non-destructive one-time migration of Tier 3 facts from the legacy SQLite
        ``facts`` table into ``profile_facts``.

        Rules
        -----
        - Reads only rows whose ``category`` matches TIER3_CATEGORIES.
        - Uses ``INSERT OR IGNORE`` so any row already present in ``profile_facts``
          (keyed on ``(category, key)``) is left untouched — profile_facts wins.
        - Does **not** DELETE, DROP, or mutate the legacy ``facts`` table.
        - After a successful pass, writes a sentinel row
          ``(_system, legacy_migration_v1_completed, true)`` so subsequent calls
          (and subsequent process restarts) detect completion without re-scanning.

        Returns
        -------
        int
            Number of rows actually inserted (0 on a repeat call after the
            sentinel is already present).
        """
        # Categories that belong exclusively to Tier 3 / ProfileMemory.
        # "person" handles legacy schema drift where the category was free-text.
        TIER3_CATEGORIES = ("profile", "preference", "important", "person")
        SENTINEL_CAT = "_system"
        SENTINEL_KEY = "legacy_migration_v1_completed"

        # Fast path: sentinel already written → nothing to do.
        if self.get_fact(SENTINEL_CAT, SENTINEL_KEY) == "true":
            logger.debug("[ProfileMemory] Legacy migration already completed (sentinel present). Skipping.")
            return 0

        facts_db_path = Path(facts_db_path)
        if not facts_db_path.exists():
            logger.warning(
                f"[ProfileMemory] migrate_from_legacy: legacy DB not found at {facts_db_path}. "
                "Writing sentinel and skipping."
            )
            self.set_fact(SENTINEL_CAT, SENTINEL_KEY, "true", source="migration")
            return 0

        inserted = 0
        now = datetime.now().isoformat()

        try:
            legacy_conn = sqlite3.connect(str(facts_db_path), timeout=10.0)
            placeholders = ",".join("?" * len(TIER3_CATEGORIES))
            rows = legacy_conn.execute(
                f"SELECT category, key, value FROM facts WHERE category IN ({placeholders})",
                TIER3_CATEGORIES,
            ).fetchall()
            legacy_conn.close()
        except Exception as exc:
            logger.error(
                f"[ProfileMemory] migrate_from_legacy: failed to read legacy DB: {exc}",
                exc_info=True,
            )
            return 0

        with self._local_lock:
            with self._get_connection() as conn:
                for cat, key, value in rows:
                    cat_clean = cat.strip().lower()
                    key_clean = key.strip().lower()
                    val_str, val_type = self._serialize_value(str(value))
                    cursor = conn.execute(
                        """
                        INSERT OR IGNORE INTO profile_facts
                            (category, key, value, value_type, source, confidence, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (cat_clean, key_clean, val_str, val_type, "legacy_migration", 1.0, now),
                    )
                    inserted += cursor.rowcount
                conn.commit()

        logger.info(
            f"[ProfileMemory] Legacy migration complete: {inserted} rows inserted "
            f"(of {len(rows)} legacy Tier 3 rows read). Conflicts preserved existing profile_facts values."
        )

        # Write sentinel so this never runs again across process restarts.
        self.set_fact(SENTINEL_CAT, SENTINEL_KEY, "true", source="migration")
        return inserted
