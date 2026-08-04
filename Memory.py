from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Iterator


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "Data"
MEMORY_DB = PROJECT_ROOT / "Memory.db"
CHAT_LOG_FILE = DATA_DIR / "ChatLog.json"


class MemoryCategory(Enum):
    """Enum for memory fact categories to avoid string typos."""
    PROFILE = "profile"
    PREFERENCE = "preference"
    SKILL = "skill"
    PROJECT = "project"
    GOAL = "goal"
    TOOL = "tool"
    LANGUAGE = "language"
    IMPORTANT = "important"


@dataclass(frozen=True)
class MemoryFact:
    category: str
    key: str
    value: str


class Memory:
    def __init__(
        self,
        db_path: Path | str = MEMORY_DB,
        chat_log_path: Path | str = CHAT_LOG_FILE,
    ):
        self.db_path = Path(db_path)
        self.chat_log_path = Path(chat_log_path)

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.chat_log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.chat_log_path.exists():
            self.chat_log_path.write_text("[]", encoding="utf-8")

        self._init_db()
        self.recover_profile_from_chat_log()

    # ------------------------------------------------------------------
    # Connection handling
    # ------------------------------------------------------------------
    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """
        Context manager that yields a sqlite3 connection, commits on
        successful exit, and always closes the connection afterward.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def remember(self, text: str) -> list[MemoryFact]:
        facts = self.extract_facts(text)
        for fact in facts:
            self.upsert_fact(fact.category, fact.key, fact.value)
        return facts

    def forget(self, text: str) -> int:
        text_like = f"%{text.strip().lower()}%"
        with self._connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM facts
                WHERE lower(category) LIKE ?
                   OR lower(key) LIKE ?
                   OR lower(value) LIKE ?
                """,
                (text_like, text_like, text_like),
            )
            return cursor.rowcount

    def summarize(self) -> str:
        profile = self.get_context()
        topics = self.recent_topics(limit=5)
        if not profile and not topics:
            return "I do not have long-term memory saved yet."

        parts = []
        if profile:
            parts.append(profile)
        if topics:
            parts.append("Recent topics: " + ", ".join(topics))
        return "\n".join(parts)

    def get_context(self) -> str:
        facts = self.facts()
        if not facts:
            return ""

        grouped: dict[str, list[str]] = {}
        for fact in facts:
            grouped.setdefault(fact.category, []).append(fact.value)

        lines = []
        for category in sorted(grouped):
            values = sorted(set(grouped[category]))
            lines.append(f"{category.title()}: {', '.join(values)}")
        return "\n".join(lines)

    def build_context(
        self,
        user_input: str = "",
        current_topic: str = "",
        max_tokens: int = 2000
    ) -> str:
        """
        Build comprehensive context string for LLM.

        Combines:
        - Recent conversation messages
        - Important facts
        - Current topic context
        - Long-term facts
        - Memory summary

        Args:
            user_input: Current user input
            current_topic: Current topic of conversation
            max_tokens: Maximum tokens for context

        Returns:
            Formatted context string
        """
        context_parts = []

        # Add system context
        context_parts.append("=" * 60)
        context_parts.append("USER CONTEXT")
        context_parts.append("=" * 60)

        # Add current user input
        if user_input:
            context_parts.append(f"User Input: {user_input}")
            context_parts.append("-" * 60)

        # Add current topic
        if current_topic:
            context_parts.append(f"Current Topic: {current_topic}")
            context_parts.append("-" * 60)

        # Add recent messages
        recent_messages = self.recent_messages(limit=10)
        if recent_messages:
            context_parts.append("Recent Conversation:")
            context_parts.append("-" * 60)
            for msg in recent_messages:
                role = msg.get("role", "").upper()
                content = msg.get("content", "")[:300]
                context_parts.append(f"{role}: {content}")
            context_parts.append("-" * 60)

        # Add important facts
        important_facts = self.facts()
        if important_facts:
            context_parts.append("Important Facts:")
            context_parts.append("-" * 60)
            for fact in important_facts[:20]:  # Limit to first 20 facts
                context_parts.append(f"{fact.category}: {fact.value}")
            context_parts.append("-" * 60)

        # Add memory summary
        if important_facts:
            summary = self.summarize()
            context_parts.append(f"Memory Summary: {summary}")

        context = "\n".join(context_parts)

        # Truncate if too long
        char_count = len(context)
        if char_count > max_tokens * 4:  # Approximate: 4 chars per token
            context = context[:max_tokens * 4] + "\n\n... (truncated for context window)"

        return context

    def search(self, text: str = "") -> list[MemoryFact]:
        if not text.strip():
            return self.facts()

        pattern = f"%{text.strip().lower()}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT category, key, value
                FROM facts
                WHERE lower(category) LIKE ?
                   OR lower(key) LIKE ?
                   OR lower(value) LIKE ?
                ORDER BY category, key, value
                """,
                (pattern, pattern, pattern),
            ).fetchall()
        return [MemoryFact(*row) for row in rows]

    def record_turn(self, query: str, answer: str, topic: str) -> None:
        messages = self.load_chat_log()
        messages.extend(
            [
                {"role": "user", "content": query, "topic": topic},
                {"role": "assistant", "content": answer, "topic": topic},
            ]
        )
        self.chat_log_path.write_text(json.dumps(messages[-60:], indent=2, ensure_ascii=False), encoding="utf-8")

    def remember_exchange(self, query: str, answer: str, topic: str) -> None:
        compact_answer = self._format_answer(answer)
        if len(compact_answer) > 180:
            compact_answer = compact_answer[:177].rstrip() + "..."
        summary = f"User asked: {query.strip()} | Assistant answered: {compact_answer}"

        # Store the conversation in the chat log (including topic field)
        self.record_turn(query, answer, topic)

        # Store topic summary in the topics table
        self.upsert_topic(topic, summary)

    def recent_messages(self, limit: int) -> list[dict[str, str]]:
        return [
            {"role": item["role"], "content": item["content"], "topic": item.get("topic", "")}
            for item in self.load_chat_log()[-limit:]
            if item.get("role") in {"user", "assistant"} and item.get("content")
        ]

    def load_chat_log(self) -> list[dict[str, str]]:
        try:
            return json.loads(self.chat_log_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def recover_profile_from_chat_log(self) -> None:
        if self.fact_value("profile", "name") is not None:
            return

        messages = self.load_chat_log()
        for index, message in enumerate(messages):
            if message.get("role") != "user":
                continue

            text = str(message.get("content", "")).strip()
            if self.looks_like_name(text):
                previous = messages[index - 1] if index > 0 else {}
                next_message = messages[index + 1] if index + 1 < len(messages) else {}
                previous_text = str(previous.get("content", "")).lower()
                next_text = str(next_message.get("content", "")).lower()
                if "do not know your name" in previous_text or "nice to meet you" in next_text:
                    self.upsert_fact("profile", "name", text)
                    return

    def extract_facts(self, text: str) -> list[MemoryFact]:
        """
        Extract structured facts from user text using categorized patterns.
        """
        cleaned = text.strip().strip(".")
        lower = cleaned.lower()
        facts: list[MemoryFact] = []

        # 1. Extract profile/name facts
        name_match = re.search(r"\b(?:my name is|i am|i'm)\s+([A-Z][A-Za-z0-9 _.-]{1,40})$", cleaned)
        if name_match and not any(word in lower for word in ("learning", "studying", "building", "working")):
            facts.append(MemoryFact(MemoryCategory.PROFILE.value, "name", name_match.group(1).strip()))
        elif self.looks_like_name(cleaned) and self.fact_value(MemoryCategory.PROFILE.value, "name") is None:
            facts.append(MemoryFact(MemoryCategory.PROFILE.value, "name", cleaned))

        # 2. Extract skills
        for pattern in (
            r"\b(?:i am|i'm)\s+(?:learning|studying)\s+(.+)",
            r"\b(?:i am|i'm)\s+also\s+(?:learning|studying)\s+(.+)",
            r"\bmy skills? (?:are|include)\s+(.+)",
        ):
            match = re.search(pattern, lower)
            if match:
                for value in self._split_values(match.group(1)):
                    facts.append(MemoryFact(MemoryCategory.SKILL.value, self._key(value), self._title_value(value)))

        # 3. Extract projects
        for pattern in (
            r"\b(?:i am|i'm)\s+(?:building|working on|creating)\s+(.+)",
            r"\bmy projects? (?:are|include)\s+(.+)",
        ):
            match = re.search(pattern, lower)
            if match:
                for value in self._split_values(match.group(1)):
                    facts.append(MemoryFact(MemoryCategory.PROJECT.value, self._key(value), self._title_value(value)))

        # 4. Extract goals
        goal_match = re.search(r"\bmy goal is to\s+(.+)", lower)
        if goal_match:
            value = goal_match.group(1).strip()
            facts.append(MemoryFact(MemoryCategory.GOAL.value, self._key(value), value))

        # 5. Extract preferences
        for pattern in (
            r"\bi (?:like|prefer)\s+(.+)",
            r"\b(?:my favourite|my favorite|my preferred)\s+(.+?)(?:\s+(?:is|as|by)\s+.*$|\s*$)",
            r"\b(?:my editor is|my ide is|primary editor|primary ide)\s+(.+)",
            r"\b(?:my primary language|main language)\s+(.+)",
            r"\b(?:my primary framework|main framework)\s+(.+)",
            r"\b(?:i always use|i frequently use|i regularly use)\s+(.+)",
            r"\b(?:my tools? (?:are|include)\s+)(.+)",
        ):
            match = re.search(pattern, lower)
            if match:
                value = match.group(1).strip()
                facts.append(MemoryFact(MemoryCategory.PREFERENCE.value, self._key(value), value))

        # 6. Extract important facts
        important_match = re.search(r"\bremember that\s+(.+)", cleaned, re.IGNORECASE)
        if important_match:
            value = important_match.group(1).strip()
            facts.append(MemoryFact(MemoryCategory.IMPORTANT.value, self._key(value), value))

        return facts

    def facts(self) -> list[MemoryFact]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT category, key, value FROM facts ORDER BY category, key, value"
            ).fetchall()
        return [MemoryFact(*row) for row in rows]

    def find(
        self,
        category: MemoryCategory | str,
        key: str | None = None,
    ) -> list[MemoryFact]:
        """
        Retrieve facts with flexible matching.

        Args:
            category: Memory category to search in (uses enum for type safety)
            key: Optional key to filter by

        Returns:
            List of matching MemoryFact objects
        """
        with self._connect() as conn:
            if key:
                rows = conn.execute(
                    "SELECT category, key, value FROM facts "
                    "WHERE category = ? AND key = ? "
                    "ORDER BY updated_at DESC",
                    (str(category), key)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT category, key, value FROM facts "
                    "WHERE category = ? "
                    "ORDER BY updated_at DESC",
                    (str(category),)
                ).fetchall()
        return [MemoryFact(*row) for row in rows]

    def get_preference(self, preference_type: str) -> str | None:
        """
        Retrieve a specific preference by type.
        Example: get_preference("editor") returns "VS Code"

        Args:
            preference_type: Type of preference to retrieve

        Returns:
            The preference value, or None if not found
        """
        return self.fact_value(str(MemoryCategory.PREFERENCE.value), preference_type)

    def fact_value(self, category: str, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM facts WHERE category = ? AND key = ? ORDER BY updated_at DESC LIMIT 1",
                (category, key),
            ).fetchone()
        return str(row[0]) if row else None

    def values_for_category(self, category: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT value FROM facts WHERE category = ? ORDER BY value",
                (category,),
            ).fetchall()
        return [str(row[0]) for row in rows]

    def recent_topics(self, limit: int) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT topic FROM topics ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [str(row[0]) for row in rows]

    def upsert_fact(self, category: str, key: str, value: str) -> None:
        now = dt.datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO facts(category, key, value, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(category, key, value) DO UPDATE SET updated_at = excluded.updated_at
                """,
                (category, key, value, now, now),
            )

    def upsert_topic(self, topic: str, summary: str) -> None:
        now = dt.datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO topics(topic, summary, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(topic) DO UPDATE SET summary = excluded.summary, updated_at = excluded.updated_at
                """,
                (topic, summary, now),
            )

    def looks_like_name(self, text: str) -> bool:
        if text.endswith("?"):
            return False
        words = text.split()
        if not 1 <= len(words) <= 3:
            return False
        blocked = {"hello", "hi", "hey", "thanks", "ok", "okay", "yes", "no"}
        if text.lower() in blocked:
            return False
        return all(re.fullmatch(r"[A-Z][A-Za-z'.-]{1,30}", word) for word in words)

    # ------------------------------------------------------------------
    # Small text-normalization helpers used by extract_facts()
    # ------------------------------------------------------------------
    def _split_values(self, text: str) -> list[str]:
        """
        Split a raw matched phrase like "python, sql and docker" into
        individual cleaned values: ["python", "sql", "docker"].
        """
        text = text.strip().strip(".").strip()
        if not text:
            return []
        # Split on commas, "and", "&", and "/" while treating them as
        # equivalent separators.
        parts = re.split(r",|\band\b|&|/", text)
        values = [part.strip() for part in parts if part.strip()]
        return values

    def _key(self, value: str) -> str:
        """
        Normalize a value into a short, stable dictionary-style key,
        e.g. "Machine Learning" -> "machine_learning".
        """
        key = value.strip().lower()
        key = re.sub(r"[^a-z0-9]+", "_", key)
        key = key.strip("_")
        return key or "value"

    def _title_value(self, value: str) -> str:
        """
        Title-case a value for storage/display, e.g.
        "machine learning" -> "Machine Learning".
        Leaves already-cased acronyms (e.g. "AI", "SQL") untouched
        where possible by only title-casing lowercase words.
        """
        value = value.strip()
        words = value.split()
        titled = [word if not word.islower() else word.capitalize() for word in words]
        return " ".join(titled)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(category, key, value)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS topics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL UNIQUE,
                    summary TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def count_memories(self) -> int:
        """Count total number of facts stored."""
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM facts").fetchone()
            return row[0] if row else 0

    def count_categories(self) -> int:
        """Count number of unique categories."""
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(DISTINCT category) FROM facts").fetchone()
            return row[0] if row else 0

    def get_top_categories(self, limit: int = 5) -> list[tuple[str, int]]:
        """Get counts per category."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT category, COUNT(*) as count
                FROM facts
                GROUP BY category
                ORDER BY count DESC
                LIMIT ?
                """,
                (limit,)
            ).fetchall()
            return [(row[0], row[1]) for row in rows]

    def _format_answer(self, text: str) -> str:
        return "\n".join(line.strip() for line in text.splitlines() if line.strip())