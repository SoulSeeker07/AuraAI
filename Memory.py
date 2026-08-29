from __future__ import annotations

import datetime as dt
import json
import logging
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

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


class PendingQuestion:
    def __init__(
        self, slot: str, qtype: str = "memory_preference", expected: str = "text"
    ):
        self.type = qtype
        self.slot = slot
        self.expected = expected
        self.value = None
        self.slot_value = None

    def resolve(self, answer: str):
        self.value = answer
        self.slot_value = answer


class FavoriteEditorQuestion(PendingQuestion):
    def __init__(self):
        super().__init__(
            slot="favorite_editor", qtype="memory_preference", expected="text"
        )


class Memory:
    """
    Aura Core Conversational and Fact Memory System.

    Manages persistent SQLite memory facts, preferences, profiles,
    and conversational chat history with cognitive memory synchronization.
    """
    def __init__(
        self,
        db_path: Path | str = MEMORY_DB,
        chat_log_path: Path | str = CHAT_LOG_FILE,
        init_schema: bool = True,
        **kwargs,
    ):
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"[Memory] Initializing Memory with db_path: {db_path}")
        logger.info(f"[Memory] Memory module PROJECT_ROOT: {PROJECT_ROOT}")

        self.db_path = Path(db_path)
        self.chat_log_path = Path(chat_log_path)

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.chat_log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.chat_log_path.exists():
            self.chat_log_path.write_text("[]", encoding="utf-8")

        logger.info(f"[Memory] Database will be created at: {self.db_path}")
        logger.info(f"[Memory] Chat log will be written to: {self.chat_log_path}")

        self._init_db()
        try:
            from memory.cognitive_memory import CognitiveMemoryEngine
            self.cognitive = CognitiveMemoryEngine(db_path=self.db_path)
        except Exception as e:
            logger.warning(f"[Memory] CognitiveMemoryEngine init warning: {e}")
            self.cognitive = None

        try:
            from memory.vector_memory import VectorMemoryEngine
            self.vector_memory = VectorMemoryEngine.get_instance(db_path=self.db_path)
        except Exception as e:
            logger.warning(f"[Memory] VectorMemoryEngine init warning: {e}")
            self.vector_memory = None

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
            matching = conn.execute(
                """
                SELECT category, key FROM facts
                WHERE lower(category) LIKE ?
                   OR lower(key) LIKE ?
                   OR lower(value) LIKE ?
                """,
                (text_like, text_like, text_like),
            ).fetchall()

            cursor = conn.execute(
                """
                DELETE FROM facts
                WHERE lower(category) LIKE ?
                   OR lower(key) LIKE ?
                   OR lower(value) LIKE ?
                """,
                (text_like, text_like, text_like),
            )
            deleted_count = cursor.rowcount

        # Purge vector embeddings for forgotten facts
        if getattr(self, "vector_memory", None) is not None:
            try:
                for cat, k in matching:
                    self.vector_memory.delete_fact_embedding(cat, k)
            except Exception as e:
                logger.debug(f"[Memory] Vector deletion error in forget: {e}")

        # Purge from cognitive_memories store
        if getattr(self, "cognitive", None) is not None:
            try:
                self.cognitive.delete_by_text(text)
            except Exception as e:
                logger.debug(f"[Memory] Cognitive memory purge error in forget: {e}")

        return deleted_count

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
        self, user_input: str = "", current_topic: str = "", max_tokens: int = 2000
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

        # Add important facts relevant to the user input, or general user preference facts
        facts_to_include = []
        if user_input:
            facts_to_include.extend(self.search(user_input))

        for f in self.facts():
            if f.category in [
                "preference",
                "profile",
                "user_preference",
                "user_profile",
            ]:
                if not any(
                    x.category == f.category and x.key == f.key
                    for x in facts_to_include
                ):
                    facts_to_include.append(f)

        if facts_to_include:
            context_parts.append("Important Facts:")
            context_parts.append("-" * 60)
            for fact in facts_to_include[:15]:
                context_parts.append(f"{fact.category}: {fact.value}")
            context_parts.append("-" * 60)

        # Add memory summary
        if facts_to_include:
            summary = self.summarize()
            context_parts.append(f"Memory Summary: {summary}")

        context = "\n".join(context_parts)

        # Truncate if too long
        char_count = len(context)
        if char_count > max_tokens * 4:  # Approximate: 4 chars per token
            context = (
                context[: max_tokens * 4] + "\n\n... (truncated for context window)"
            )

        return context

    def _compute_lexical_fuzzy_score(self, query: str, target: str) -> float:
        """
        Compute lightweight lexical fuzzy similarity score between query and target string
        using subword n-gram overlap, token stem overlap, and substring matching.
        (Honest fallback when dense neural embedding engine is inactive).
        """
        q_clean = query.lower().strip()
        t_clean = target.lower().strip()

        if not q_clean or not t_clean:
            return 0.0

        if q_clean == t_clean:
            return 1.0

        if q_clean in t_clean or t_clean in q_clean:
            return 0.85

        q_words = re.findall(r"[a-z0-9]+", q_clean)
        t_words = re.findall(r"[a-z0-9]+", t_clean)

        if not q_words or not t_words:
            return 0.0

        # Token & stem overlap
        matches = 0
        for qw in q_words:
            qw_stem = qw[:4] if len(qw) > 4 else qw
            for tw in t_words:
                tw_stem = tw[:4] if len(tw) > 4 else tw
                if qw == tw or (len(qw_stem) >= 3 and (qw_stem in tw or tw_stem in qw)):
                    matches += 1
                    break

        overlap_score = matches / max(1, len(q_words))

        # Subword 3-gram character Dice coefficient
        def _get_ngrams(s: str, n: int = 3) -> set[str]:
            return {s[i : i + n] for i in range(len(s) - n + 1)} if len(s) >= n else {s}

        q_ngrams = _get_ngrams(q_clean)
        t_ngrams = _get_ngrams(t_clean)
        ngram_overlap = len(q_ngrams & t_ngrams)
        ngram_total = len(q_ngrams) + len(t_ngrams)
        ngram_sim = (2.0 * ngram_overlap) / ngram_total if ngram_total else 0.0

        return 0.6 * overlap_score + 0.4 * ngram_sim

    def search_semantic(
        self, query: str, limit: int = 5, min_score: float = 0.25
    ) -> list[MemoryFact]:
        """
        Search memory facts using real dense neural embeddings (all-MiniLM-L6-v2 on CPU)
        with cosine similarity, falling back to lexical fuzzy matching if vector engine is unavailable.

        Args:
            query: The natural language query or question (e.g., 'I work in AI')
            limit: Max results to return
            min_score: Minimum cosine similarity threshold (0.0 to 1.0)

        Returns:
            List of MemoryFact items ranked by semantic vector similarity
        """
        all_facts = self.facts()
        if not query.strip() or not all_facts:
            return all_facts[:limit]

        # 1. Real Dense Neural Embedding Search
        if getattr(self, "vector_memory", None) is not None:
            try:
                vector_results = self.vector_memory.search(
                    query=query, facts=all_facts, top_k=limit, min_similarity=min_score
                )
                if vector_results:
                    return [fact for _, fact in vector_results]
            except Exception as e:
                logger.debug(f"[Memory] Dense vector search error, falling back to lexical fuzzy matcher: {e}")

        # 2. Honest Lexical Fuzzy Fallback
        scored: list[tuple[float, MemoryFact]] = []
        for fact in all_facts:
            target_str = f"{fact.category} {fact.key} {fact.value}"
            score = self._compute_lexical_fuzzy_score(query, target_str)
            if score >= min_score:
                scored.append((score, fact))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:limit]]

    def get_relevant_facts(self, query: str, limit: int = 8) -> list[MemoryFact]:
        """
        Hybrid fact retrieval combining exact keyword matches and dense vector similarity.
        """
        if not query.strip():
            return self.facts()[:limit]

        exact_matches = self.search(query)
        semantic_matches = self.search_semantic(query, limit=limit)

        combined: list[MemoryFact] = []
        seen = set()

        for fact in exact_matches + semantic_matches:
            fact_id = (fact.category, fact.key, fact.value)
            if fact_id not in seen:
                seen.add(fact_id)
                combined.append(fact)

        return combined[:limit]

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
        now = dt.datetime.now().isoformat()
        messages.extend(
            [
                {"role": "user", "content": query, "topic": topic, "timestamp": now},
                {
                    "role": "assistant",
                    "content": answer,
                    "topic": topic,
                    "timestamp": now,
                },
            ]
        )
        self.chat_log_path.write_text(
            json.dumps(messages[-60:], indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def remember_exchange(self, query: str, answer: str, topic: str) -> None:
        compact_answer = self._format_answer(answer)
        if len(compact_answer) > 180:
            compact_answer = compact_answer[:177].rstrip() + "..."
        summary = f"User asked: {query.strip()} | Assistant answered: {compact_answer}"

        # Store the conversation in the chat log (including topic field)
        self.record_turn(query, answer, topic)

        # Store topic summary in the topics table
        self.upsert_topic(topic, summary)

    def recent_messages(self, limit: int = 10) -> list[dict[str, Any]]:
        return [
            {
                "role": item["role"],
                "content": item["content"],
                "topic": item.get("topic", ""),
            }
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
                if (
                    "do not know your name" in previous_text
                    or "nice to meet you" in next_text
                ):
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
        name_match = re.search(
            r"\b(?:my name is|call me|my full name is|i am called)\s+([A-Za-z0-9 _.-]{2,40})$",
            cleaned,
            re.IGNORECASE,
        )
        if not name_match:
            iam_match = re.search(
                r"\b(?:i am|i'm)\s+([A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20})?)$",
                cleaned,
            )
            if iam_match:
                candidate = iam_match.group(1).strip()
                cand_lower = candidate.lower()
                non_names = {
                    "good", "fine", "okay", "ok", "great", "happy", "sad", "tired", "hungry",
                    "at bed", "at home", "at work", "here", "there", "back", "doing", "going",
                    "trying", "sorry", "not", "feeling", "a developer", "an engineer", "ready",
                    "busy", "alive", "well", "sick", "bored", "late", "early", "sleeping", "learning"
                }
                if cand_lower not in non_names and not any(cand_lower.startswith(w) for w in ["a ", "an ", "the ", "at ", "in ", "on ", "to "]):
                    name_match = iam_match

        if name_match:
            facts.append(
                MemoryFact(
                    MemoryCategory.PROFILE.value, "name", name_match.group(1).strip()
                )
            )
        elif (
            self.looks_like_name(cleaned)
            and self.fact_value(MemoryCategory.PROFILE.value, "name") is None
        ):
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
                    facts.append(
                        MemoryFact(
                            MemoryCategory.SKILL.value,
                            self._key(value),
                            self._title_value(value),
                        )
                    )

        # 3. Extract projects
        for pattern in (
            r"\b(?:i am|i'm)\s+(?:building|working on|creating)\s+(.+)",
            r"\bmy projects? (?:are|include|is|at|path is|dir is|directory is|:)\s+(.+)",
            r"\bmy current project (?:is|at|path is|:)?\s*(.+)",
        ):
            match = re.search(pattern, lower)
            if match:
                for value in self._split_values(match.group(1)):
                    facts.append(
                        MemoryFact(
                            MemoryCategory.PROJECT.value,
                            self._key(value),
                            self._title_value(value),
                        )
                    )

        # 4. Extract goals
        goal_match = re.search(r"\bmy goal is to\s+(.+)", lower)
        if goal_match:
            value = goal_match.group(1).strip()
            facts.append(MemoryFact(MemoryCategory.GOAL.value, self._key(value), value))

        # 5. Extract preferences
        fav_match = re.search(
            r"\b(?:my favorite|my favourite)\s+(.+?)\s+is\s+(.+)$",
            cleaned,
            re.IGNORECASE,
        )
        if fav_match:
            subject = fav_match.group(1).strip()
            val = fav_match.group(2).strip()
            key_name = (
                f"favorite_{subject}" if not subject.startswith("favorite") else subject
            )
            facts.append(
                MemoryFact(
                    MemoryCategory.PREFERENCE.value,
                    self._key(key_name),
                    val,
                )
            )

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
                facts.append(
                    MemoryFact(MemoryCategory.PREFERENCE.value, self._key(value), value)
                )

        # 6. Extract important facts
        important_match = re.search(r"\bremember that\s+(.+)", cleaned, re.IGNORECASE)
        if important_match:
            value = important_match.group(1).strip()
            facts.append(
                MemoryFact(MemoryCategory.IMPORTANT.value, self._key(value), value)
            )

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
                    (str(category), key),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT category, key, value FROM facts "
                    "WHERE category = ? "
                    "ORDER BY updated_at DESC",
                    (str(category),),
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

    def set_preference(self, preference_type: str, value: str) -> None:
        """
        Store a specific preference by type.
        Example: set_preference("editor", "VS Code")

        Args:
            preference_type: Type/key of preference to store
            value: The preference value
        """
        self.upsert_fact(str(MemoryCategory.PREFERENCE.value), preference_type, str(value))

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
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            f"[Memory] upsert_fact called: category={category}, key={key}, value={value}"
        )

        # Log current memory count before insertion
        current_count = self.count_memories()
        logger.info(f"[Memory] Current memory count before insertion: {current_count}")

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO facts(category, key, value, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(category, key, value) DO UPDATE SET updated_at = excluded.updated_at
                """,
                (category, key, value, now, now),
            )
        logger.info("[Memory] Fact successfully inserted into database")

        # Sync with Cognitive Memory Engine
        if getattr(self, "cognitive", None) is not None:
            try:
                from memory.models import MemoryItem, MemoryType, MemoryProvenance, ProvenanceSource
                mem_type = MemoryType.PREFERENCE if category in ("preference", "profile") else MemoryType.LONG_TERM
                item = MemoryItem(
                    content=f"{category}: {key} = {value}",
                    type=mem_type,
                    importance=0.85 if category in ("preference", "profile", "important") else 0.6,
                    topic=category,
                    provenance=MemoryProvenance(
                        source_type=ProvenanceSource.USER_EXPLICIT,
                        verified=True,
                    ),
                    metadata={"category": category, "key": key, "value": value},
                )
                self.cognitive.store_memory(item)
            except Exception as e:
                logger.warning(f"[Memory] Cognitive memory sync error: {e}")

        # Index dense vector embedding
        if getattr(self, "vector_memory", None) is not None:
            try:
                self.vector_memory.index_fact(category, key, value)
            except Exception as e:
                logger.debug(f"[Memory] Vector indexing error: {e}")

        # Log memory count after insertion
        new_count = self.count_memories()
        logger.info(
            f"[Memory] Memory count after insertion: {new_count} (inserted 1 fact)"
        )

    def delete_fact(self, category: str, key: str) -> bool:
        """Delete a fact from SQLite, purge its vector embedding, and remove from cognitive_memories."""
        deleted = False
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM facts WHERE category = ? AND key = ?",
                (category, key),
            )
            deleted = cursor.rowcount > 0

        # Purge dense vector embedding
        if getattr(self, "vector_memory", None) is not None:
            try:
                self.vector_memory.delete_fact_embedding(category, key)
            except Exception as e:
                logger.debug(f"[Memory] Vector deletion error: {e}")

        # Purge from cognitive_memories store
        if getattr(self, "cognitive", None) is not None:
            try:
                self.cognitive.delete_by_category_key(category, key)
            except Exception as e:
                logger.debug(f"[Memory] Cognitive memory deletion error: {e}")

        logger.info(f"[Memory] Deleted fact [{category}] {key}: {deleted}")
        return deleted

    def delete_category(self, category: str) -> int:
        """Delete all facts in a category, purge vector embeddings, and remove from cognitive_memories."""
        deleted_count = 0
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM facts WHERE category = ?", (category,))
            deleted_count = cursor.rowcount

        # Purge dense vector embeddings
        if getattr(self, "vector_memory", None) is not None:
            try:
                self.vector_memory.delete_category_embeddings(category)
            except Exception as e:
                logger.debug(f"[Memory] Category vector deletion error: {e}")

        # Purge from cognitive_memories store
        if getattr(self, "cognitive", None) is not None:
            try:
                self.cognitive.delete_by_category(category)
            except Exception as e:
                logger.debug(f"[Memory] Cognitive memory category deletion error: {e}")

        logger.info(f"[Memory] Deleted {deleted_count} facts from category [{category}]")
        return deleted_count

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
        blocked = {
            "hello", "hi", "hey", "thanks", "ok", "okay", "yes", "no",
            "explain", "describe", "show", "tell", "what", "why", "how",
            "who", "when", "where", "search", "find", "open", "close",
            "start", "stop", "help", "play", "pause", "resume", "listen",
            "check", "test", "run", "make", "create", "build", "write"
        }
        if text.lower() in blocked or words[0].lower() in blocked:
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

    def get_pending_question(self) -> dict | None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pending_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    slot TEXT NOT NULL,
                    expected TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            row = conn.execute(
                "SELECT type, slot, expected FROM pending_questions ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row:
                return {"type": row[0], "slot": row[1], "expected": row[2]}
            return None

    def set_pending_question(self, qtype: str, slot: str, expected: str) -> None:
        now = dt.datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pending_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    slot TEXT NOT NULL,
                    expected TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("DELETE FROM pending_questions")
            conn.execute(
                "INSERT INTO pending_questions (type, slot, expected, created_at) VALUES (?, ?, ?, ?)",
                (qtype, slot, expected, now),
            )

    def clear_pending_question(self) -> None:
        with self._connect() as conn:
            conn.execute("DROP TABLE IF EXISTS pending_questions")

    def resolve_pending_question(self, answer: str, pending_question: Any) -> None:
        qtype = getattr(pending_question, "type", "memory_preference")
        slot = getattr(pending_question, "slot", "general")
        category = "preference"
        if qtype == "memory_profile":
            category = "profile"
        elif qtype == "memory_skill":
            category = "skill"
        self.upsert_fact(category, slot, answer)
        if hasattr(pending_question, "resolve"):
            pending_question.resolve(answer)
        else:
            setattr(pending_question, "value", answer)
            setattr(pending_question, "slot_value", answer)
        self.clear_pending_question()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(category, key, value)
                )
                """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS topics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL UNIQUE,
                    summary TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pending_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    slot TEXT NOT NULL,
                    expected TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """)

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
                (limit,),
            ).fetchall()
            return [(row[0], row[1]) for row in rows]

    def add_message(self, role: str, content: str) -> None:
        """Append a message turn to the chat log file."""
        messages = self.recent_messages(limit=1000)
        messages.append({
            "role": role,
            "content": content,
            "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        })
        try:
            self.chat_log_path.parent.mkdir(parents=True, exist_ok=True)
            self.chat_log_path.write_text(json.dumps(messages, indent=2), encoding="utf-8")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[Memory] Failed to write chat log: {e}")

    def _format_answer(self, text: str) -> str:
        return "\n".join(line.strip() for line in text.splitlines() if line.strip())
