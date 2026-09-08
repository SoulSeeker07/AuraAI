"""
Procedural Failure Ledger
Location: src/memory/procedural_failure_ledger.py

Learns from tool-usage and execution failures without poisoning positive
procedural or episodic memory (which is guarded by ConsolidationEngine).

Two-Tier Architecture:
- Tier 1: Persistent SQLite knowledge base of normalized failure fingerprints,
  anti-patterns, occurrence counts, and verified countermeasures.
- Tier 2: Ephemeral session-scoped circuit breaker bound to effective_session_id
  that trips on 3 consecutive strikes of the same failure fingerprint and escalates.
"""

from __future__ import annotations

import dataclasses
import datetime
import hashlib
import logging
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("data/Memory.db")
DEFAULT_CIRCUIT_BREAKER_THRESHOLD = 3


@dataclasses.dataclass
class FailureRecord:
    """Represents a persistent procedural failure entry."""

    fingerprint: str
    tool_name: str
    error_type: str
    canonical_msg: str
    anti_pattern: str
    countermeasure: Optional[str] = None
    occurrence_count: int = 1
    last_seen_at: str = ""
    resolved_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class CircuitBreakerResult:
    """Status returned upon recording a failure, evaluating Tier 2 circuit breaker."""

    tripped: bool
    strikes: int
    threshold: int
    fingerprint: str
    tool_name: str
    error_type: str
    canonical_msg: str
    escalate_to_user: bool
    message: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


class ProceduralFailureLedger:
    """
    Two-Tier Failure Ledger for autonomous tool learning & anti-pattern protection.

    - Tier 1: Persistent SQLite store for failure fingerprints & countermeasures.
    - Tier 2: In-memory session-scoped circuit breaker tracking consecutive strikes.
    """

    def __init__(
        self,
        db_path: Path | str = DEFAULT_DB_PATH,
        circuit_breaker_threshold: int = DEFAULT_CIRCUIT_BREAKER_THRESHOLD,
    ):
        self.db_path = Path(db_path)
        self.threshold = circuit_breaker_threshold
        # Ephemeral session strikes: {session_id: {fingerprint: count}}
        self._session_strikes: dict[str, dict[str, int]] = {}

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize SQLite database tables for procedural failures."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS procedural_failures (
                    fingerprint TEXT PRIMARY KEY,
                    tool_name TEXT NOT NULL,
                    error_type TEXT NOT NULL,
                    canonical_msg TEXT NOT NULL,
                    anti_pattern TEXT NOT NULL,
                    countermeasure TEXT,
                    occurrence_count INTEGER DEFAULT 1,
                    last_seen_at TEXT NOT NULL,
                    resolved_at TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pf_tool_name ON procedural_failures(tool_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pf_resolved ON procedural_failures(resolved_at)")

    @staticmethod
    def normalize_error(tool_name: str, error: Any) -> Tuple[str, str, str]:
        """
        Extract error type, normalize volatile tokens (memory addresses, file paths, line numbers,
        UUIDs, timestamps), and compute a deterministic fingerprint hash.

        Returns: (error_type, canonical_msg, fingerprint)
        """
        # 1. Extract error type and initial string representation
        if isinstance(error, Exception):
            err_type = type(error).__name__
            raw_msg = str(error)
        else:
            raw_msg = str(error or "Unknown error")
            # Try to match patterns like "FileNotFoundError: [Errno 2]..." or "PermissionError: ..."
            match = re.match(r"^([A-Za-z0-9_]+(?:Error|Exception)):\s*(.*)$", raw_msg, re.DOTALL)
            if match:
                err_type = match.group(1).strip()
                raw_msg = match.group(2).strip()
            else:
                err_type = "ExecutionError"

        clean_tool = (tool_name or "unknown_tool").strip().lower()

        # 2. Scrub volatile dynamic tokens from canonical message
        msg = raw_msg

        # ISO Timestamps / Dates (scrub BEFORE line/colon numbers)
        msg = re.sub(
            r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?\b",
            "<TIMESTAMP>",
            msg,
        )
        msg = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "<DATE>", msg)

        # UUIDs / GUIDs
        msg = re.sub(
            r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
            "<UUID>",
            msg,
        )

        # Memory addresses (e.g. 0x7ffe42a1, 0x000001B42)
        msg = re.sub(r"0x[0-9a-fA-F]+", "<HEX_ADDR>", msg)

        # Windows paths (e.g. C:\Users\..., d:\project\sub\file.ext)
        msg = re.sub(
            r"[a-zA-Z]:\\(?:[^\\/:*?\"<>|\r\n\s',;)]+\\)*[^\\/:*?\"<>|\r\n\s',;)]*",
            "<PATH>",
            msg,
        )

        # Unix / POSIX paths (e.g. /home/user/..., /tmp/file.py)
        msg = re.sub(
            r"(?:/(?:[a-zA-Z0-9_\.\-]+))+/?",
            "<PATH>",
            msg,
        )

        # Line and column numbers (e.g. line 42, :10:5, :123)
        msg = re.sub(r"\bline\s+\d+\b", "line <NUM>", msg, flags=re.IGNORECASE)
        msg = re.sub(r":\d+:\d+", ":<NUM>:<NUM>", msg)
        msg = re.sub(r":\d+\b", ":<NUM>", msg)

        # Whitespace normalization
        msg = re.sub(r"\s+", " ", msg).strip()
        if not msg:
            msg = "<EMPTY_ERROR_MSG>"

        # 3. Compute deterministic hash (SHA256 slice)
        norm_key = f"{clean_tool}:{err_type}:{msg}"
        fingerprint = hashlib.sha256(norm_key.encode("utf-8")).hexdigest()[:16]

        return err_type, msg, fingerprint

    def record_failure(
        self,
        tool_name: str,
        error: Any,
        anti_pattern: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> CircuitBreakerResult:
        """
        Record a failure event in persistent storage (Tier 1) and advance
        the session's consecutive strike counter (Tier 2).

        If strikes >= threshold, trips circuit breaker and signals escalation.
        """
        error_type, canonical_msg, fingerprint = self.normalize_error(tool_name, error)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        synthesized_anti_pattern = (
            anti_pattern
            if anti_pattern
            else f"Tool '{tool_name}' failed with {error_type}: {canonical_msg}"
        )

        # Tier 1: Persist to SQLite
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO procedural_failures (
                        fingerprint, tool_name, error_type, canonical_msg, anti_pattern,
                        countermeasure, occurrence_count, last_seen_at, resolved_at
                    ) VALUES (?, ?, ?, ?, ?, NULL, 1, ?, NULL)
                    ON CONFLICT(fingerprint) DO UPDATE SET
                        occurrence_count = occurrence_count + 1,
                        last_seen_at = excluded.last_seen_at,
                        resolved_at = NULL,
                        anti_pattern = COALESCE(excluded.anti_pattern, anti_pattern)
                    """,
                    (fingerprint, tool_name, error_type, canonical_msg, synthesized_anti_pattern, now_iso),
                )
        except Exception as db_err:
            logger.warning(f"[ProceduralFailureLedger] Failed to persist failure to DB: {db_err}")

        # Tier 2: Ephemeral Circuit Breaker tracking
        strikes = 1
        if session_id:
            session_dict = self._session_strikes.setdefault(session_id, {})
            strikes = session_dict.get(fingerprint, 0) + 1
            session_dict[fingerprint] = strikes

        tripped = strikes >= self.threshold
        escalate = tripped

        if tripped:
            msg = (
                f"🚨 Circuit breaker TRIPPED for tool '{tool_name}' "
                f"(fingerprint: {fingerprint}, strikes: {strikes}/{self.threshold}). "
                f"Consecutive repeated failure detected in session '{session_id or 'unknown'}'. "
                f"Error: {error_type} - {canonical_msg}. Escalating to user to prevent execution loop."
            )
            logger.error(f"[ProceduralFailureLedger] {msg}")
        else:
            msg = (
                f"Failure recorded for tool '{tool_name}' "
                f"(fingerprint: {fingerprint}, strike {strikes}/{self.threshold})."
            )
            logger.info(f"[ProceduralFailureLedger] {msg}")

        return CircuitBreakerResult(
            tripped=tripped,
            strikes=strikes,
            threshold=self.threshold,
            fingerprint=fingerprint,
            tool_name=tool_name,
            error_type=error_type,
            canonical_msg=canonical_msg,
            escalate_to_user=escalate,
            message=msg,
        )

    def record_resolution(
        self,
        tool_name: str,
        countermeasure: str,
        fingerprint: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> int:
        """
        Record a verified countermeasure and mark the failure fingerprint(s) as resolved.
        Resets Tier 2 ephemeral strikes for the resolved failure.
        """
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        rows_affected = 0

        try:
            with self._connect() as conn:
                if fingerprint:
                    cursor = conn.execute(
                        """
                        UPDATE procedural_failures
                        SET resolved_at = ?, countermeasure = ?
                        WHERE fingerprint = ?
                        """,
                        (now_iso, countermeasure, fingerprint),
                    )
                    rows_affected = cursor.rowcount
                else:
                    cursor = conn.execute(
                        """
                        UPDATE procedural_failures
                        SET resolved_at = ?, countermeasure = ?
                        WHERE tool_name = ? AND resolved_at IS NULL
                        """,
                        (now_iso, countermeasure, tool_name),
                    )
                    rows_affected = cursor.rowcount
        except Exception as db_err:
            logger.warning(f"[ProceduralFailureLedger] Failed to record resolution: {db_err}")

        # Reset Tier 2 strikes
        if session_id and session_id in self._session_strikes:
            if fingerprint:
                self._session_strikes[session_id].pop(fingerprint, None)
            else:
                # Clear all strikes for this tool if no fingerprint specified
                try:
                    with self._connect() as conn:
                        fps = [r["fingerprint"] for r in conn.execute(
                            "SELECT fingerprint FROM procedural_failures WHERE tool_name = ?", (tool_name,)
                        ).fetchall()]
                        for fp in fps:
                            self._session_strikes[session_id].pop(fp, None)
                except Exception:
                    pass

        logger.info(
            f"[ProceduralFailureLedger] Resolved failure for tool '{tool_name}' "
            f"(fp={fingerprint}, affected={rows_affected}). Countermeasure: {countermeasure[:60]}"
        )
        return rows_affected

    def is_circuit_breaker_tripped(
        self,
        session_id: str,
        fingerprint: Optional[str] = None,
    ) -> bool:
        """Check if the circuit breaker is tripped in the given session."""
        if not session_id or session_id not in self._session_strikes:
            return False
        if fingerprint:
            return self._session_strikes[session_id].get(fingerprint, 0) >= self.threshold
        # Any fingerprint tripped in this session
        return any(count >= self.threshold for count in self._session_strikes[session_id].values())

    def get_strikes(self, session_id: str, fingerprint: str) -> int:
        """Get current consecutive strike count for a fingerprint in a session."""
        return self._session_strikes.get(session_id, {}).get(fingerprint, 0)

    def reset_session(self, session_id: str) -> None:
        """Reset ephemeral circuit breaker strikes for a session."""
        if session_id in self._session_strikes:
            del self._session_strikes[session_id]

    def get_anti_patterns(
        self,
        tool_name: Optional[str] = None,
        limit: int = 5,
        include_resolved: bool = False,
    ) -> List[FailureRecord]:
        """
        Retrieve recorded anti-patterns sorted by occurrence frequency.
        """
        query = "SELECT * FROM procedural_failures WHERE 1=1"
        params: list[Any] = []

        if tool_name:
            query += " AND tool_name = ?"
            params.append(tool_name)

        if not include_resolved:
            query += " AND resolved_at IS NULL"

        query += " ORDER BY occurrence_count DESC, last_seen_at DESC LIMIT ?"
        params.append(limit)

        results: List[FailureRecord] = []
        try:
            with self._connect() as conn:
                for row in conn.execute(query, params).fetchall():
                    results.append(
                        FailureRecord(
                            fingerprint=row["fingerprint"],
                            tool_name=row["tool_name"],
                            error_type=row["error_type"],
                            canonical_msg=row["canonical_msg"],
                            anti_pattern=row["anti_pattern"],
                            countermeasure=row["countermeasure"],
                            occurrence_count=row["occurrence_count"],
                            last_seen_at=row["last_seen_at"],
                            resolved_at=row["resolved_at"],
                        )
                    )
        except Exception as db_err:
            logger.warning(f"[ProceduralFailureLedger] Failed to fetch anti-patterns: {db_err}")

        return results

    def format_anti_patterns_prompt(
        self,
        tool_name: Optional[str] = None,
        limit: int = 5,
    ) -> str:
        """
        Format anti-patterns into a negative-constraint prompt block for LLM planners.
        """
        records = self.get_anti_patterns(tool_name=tool_name, limit=limit, include_resolved=False)
        if not records:
            return ""

        lines = ["<procedural_anti_patterns>"]
        lines.append("The following tool execution patterns have repeatedly failed. AVOID repeating them:")
        for rec in records:
            lines.append(
                f"- [AVOID] Tool '{rec.tool_name}': {rec.anti_pattern} "
                f"(Failed {rec.occurrence_count} time{'s' if rec.occurrence_count != 1 else ''})"
            )
        lines.append("</procedural_anti_patterns>")
        return "\n".join(lines)
