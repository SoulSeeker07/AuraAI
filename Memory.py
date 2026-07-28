from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "Data"
MEMORY_DB = PROJECT_ROOT / "Memory.db"
CHAT_LOG_FILE = DATA_DIR / "ChatLog.json"


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
        self.upsert_topic(topic, summary)

    def recent_messages(self, limit: int) -> list[dict[str, str]]:
        return [
            {"role": item["role"], "content": item["content"]}
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
        cleaned = text.strip().strip(".")
        lower = cleaned.lower()
        facts: list[MemoryFact] = []

        name_match = re.search(r"\b(?:my name is|i am|i'm)\s+([A-Z][A-Za-z0-9 _.-]{1,40})$", cleaned)
        if name_match and not any(word in lower for word in ("learning", "studying", "building", "working")):
            facts.append(MemoryFact("profile", "name", name_match.group(1).strip()))
        elif self.looks_like_name(cleaned) and self.fact_value("profile", "name") is None:
            facts.append(MemoryFact("profile", "name", cleaned))

        for pattern in (
            r"\b(?:i am|i'm)\s+(?:learning|studying)\s+(.+)",
            r"\b(?:i am|i'm)\s+also\s+(?:learning|studying)\s+(.+)",
            r"\bmy skills? (?:are|include)\s+(.+)",
        ):
            match = re.search(pattern, lower)
            if match:
                for value in self._split_values(match.group(1)):
                    facts.append(MemoryFact("skills", self._key(value), self._title_value(value)))

        for pattern in (
            r"\b(?:i am|i'm)\s+(?:building|working on|creating)\s+(.+)",
            r"\bmy projects? (?:are|include)\s+(.+)",
        ):
            match = re.search(pattern, lower)
            if match:
                for value in self._split_values(match.group(1)):
                    facts.append(MemoryFact("projects", self._key(value), self._title_value(value)))

        goal_match = re.search(r"\bmy goal is to\s+(.+)", lower)
        if goal_match:
            value = goal_match.group(1).strip()
            facts.append(MemoryFact("goals", self._key(value), value))

        preference_match = re.search(r"\bi (?:like|prefer)\s+(.+)", lower)
        if preference_match:
            value = preference_match.group(1).strip()
            facts.append(MemoryFact("preferences", self._key(value), value))

        important_match = re.search(r"\bremember that\s+(.+)", cleaned, re.IGNORECASE)
        if important_match:
            value = important_match.group(1).strip()
            facts.append(MemoryFact("important facts", self._key(value), value))

        return facts

    def facts(self) -> list[MemoryFact]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT category, key, value FROM facts ORDER BY category, key, value"
            ).fetchall()
        return [MemoryFact(*row) for row in rows]

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

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _split_values(self, text: str) -> Iterable[str]:
        text = re.sub(r"\b(?:and|also)\b", ",", text, flags=re.IGNORECASE)
        return [value.strip(" .") for value in text.split(",") if value.strip(" .")]

    def _key(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")

    def _title_value(self, value: str) -> str:
        known_upper = {"ai", "api", "bgp", "gui", "pdf", "tts", "stt"}
        words = []
        for word in value.strip().split():
            words.append(word.upper() if word.lower() in known_upper else word.capitalize())
        return " ".join(words)

    def _format_answer(self, text: str) -> str:
        return "\n".join(line.strip() for line in text.splitlines() if line.strip())
