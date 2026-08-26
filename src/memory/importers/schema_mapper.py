"""
Schema Mapper — Fact Classification & Conflict Detection
Location: src/memory/importers/schema_mapper.py

Classifies RawMemoryFact → MemoryType and topic tag using keyword heuristics.
Also provides conflict detection against existing memories in CognitiveMemoryEngine.

Design decisions:
- Keyword-only classification — no embedding fallback this milestone.
- Fallback type is LONG_TERM (safe catch-all for unclassifiable facts).
- Conflict detection uses tokenized Jaccard similarity, not embeddings,
  since it queries via CognitiveMemoryEngine.search_memories() which
  returns MemoryItem objects with text content, not vectors.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memory.cognitive_memory import CognitiveMemoryEngine

from memory.models import MemoryType

from .base_importer import RawMemoryFact

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword classification rules
# ---------------------------------------------------------------------------

# Each rule: (frozenset of trigger keywords, target MemoryType)
# Checked in order; first match wins.
_CLASSIFICATION_RULES: list[tuple[frozenset[str], MemoryType]] = [
    (
        frozenset({"prefer", "prefers", "preference", "favorite", "favourite",
                   "always use", "likes", "dislikes", "hates", "loves"}),
        MemoryType.PREFERENCE,
    ),
    (
        frozenset({"workflow", "procedure", "step-by-step", "recipe", "routine",
                   "process", "how to", "howto", "steps to"}),
        MemoryType.PROCEDURAL,
    ),
    (
        frozenset({"task", "todo", "deadline", "due date", "assigned",
                   "action item", "ticket", "issue", "bug"}),
        MemoryType.TASK,
    ),
    (
        frozenset({"project", "repository", "repo", "codebase", "workspace",
                   "milestone", "sprint"}),
        MemoryType.PROJECT,
    ),
    (
        frozenset({"learned", "discovered", "research", "finding", "fact",
                   "definition", "means", "refers to", "is defined as"}),
        MemoryType.SEMANTIC,
    ),
    (
        frozenset({"happened", "event", "session", "conversation", "meeting",
                   "discussed", "talked about", "mentioned"}),
        MemoryType.EPISODIC,
    ),
]

# Topic keyword mapping: keyword → topic tag
_TOPIC_KEYWORDS: dict[str, str] = {
    "editor": "tools:editor",
    "ide": "tools:ide",
    "browser": "tools:browser",
    "terminal": "tools:terminal",
    "language": "programming:language",
    "python": "programming:python",
    "javascript": "programming:javascript",
    "typescript": "programming:typescript",
    "rust": "programming:rust",
    "gpu": "hardware:gpu",
    "cpu": "hardware:cpu",
    "ram": "hardware:ram",
    "monitor": "hardware:display",
    "os": "system:os",
    "windows": "system:windows",
    "linux": "system:linux",
    "music": "personal:music",
    "food": "personal:food",
    "hobby": "personal:hobby",
    "name": "profile:name",
    "age": "profile:age",
    "location": "profile:location",
    "job": "profile:occupation",
    "work": "profile:occupation",
}

# Conflict detection threshold
_CONFLICT_SIMILARITY_THRESHOLD: float = 0.55
"""Jaccard similarity threshold for flagging a fact as conflicting with an existing memory."""


class SchemaMapper:
    """
    Maps RawMemoryFact to MemoryType, topic tag, and detects conflicts
    against existing CognitiveMemoryEngine memories.
    """

    def classify_store(self, fact: RawMemoryFact) -> MemoryType:
        """
        Classify a raw fact into one of the 9 MemoryType values.

        Uses the category_hint from the vendor parser first (if it maps
        directly), then falls back to keyword matching on the fact text.
        Returns LONG_TERM as the safe default if nothing matches.
        """
        # Try category_hint first (vendor-provided classification)
        hint_lower = fact.category_hint.lower().strip()
        hint_map = {
            "preference": MemoryType.PREFERENCE,
            "preferences": MemoryType.PREFERENCE,
            "project": MemoryType.PROJECT,
            "procedural": MemoryType.PROCEDURAL,
            "procedure": MemoryType.PROCEDURAL,
            "semantic": MemoryType.SEMANTIC,
            "knowledge": MemoryType.SEMANTIC,
            "episodic": MemoryType.EPISODIC,
            "event": MemoryType.EPISODIC,
            "task": MemoryType.TASK,
        }
        if hint_lower in hint_map:
            return hint_map[hint_lower]

        # Keyword matching on fact text
        text_lower = fact.text.lower()
        for keywords, mem_type in _CLASSIFICATION_RULES:
            for kw in keywords:
                if kw in text_lower:
                    return mem_type

        return MemoryType.LONG_TERM

    def classify_topic(self, fact: RawMemoryFact) -> str:
        """
        Generate a topic tag for a raw fact.

        Checks category_hint first, then scans the fact text for known
        topic keywords. Returns 'imported:general' if nothing matches.
        """
        if fact.category_hint:
            return f"imported:{fact.category_hint.lower().strip()}"

        text_lower = fact.text.lower()
        for keyword, topic in _TOPIC_KEYWORDS.items():
            if keyword in text_lower:
                return f"imported:{topic}"

        return "imported:general"

    def check_conflict(
        self,
        fact: RawMemoryFact,
        cognitive_engine: CognitiveMemoryEngine,
    ) -> bool:
        """
        Check if a semantically similar fact already exists in the target store.

        Uses tokenized Jaccard similarity on the text content of existing
        memories returned by search_memories(). Returns True if any existing
        memory exceeds the similarity threshold, indicating a potential conflict
        that should be flagged as PendingConfirmation.

        Args:
            fact: The raw fact to check.
            cognitive_engine: CognitiveMemoryEngine to search against.

        Returns:
            True if a conflicting fact exists, False otherwise.
        """
        try:
            # Extract significant words from the fact for search
            words = [w for w in fact.text.lower().split() if len(w) > 2]
            if not words:
                return False

            # Use first few significant words as search query
            search_query = " ".join(words[:6])
            existing = cognitive_engine.search_memories(
                query=search_query, limit=5
            )

            fact_tokens = _tokenize(fact.text)
            if not fact_tokens:
                return False

            for mem in existing:
                mem_tokens = _tokenize(mem.content)
                if not mem_tokens:
                    continue

                similarity = _jaccard_similarity(fact_tokens, mem_tokens)
                if similarity >= _CONFLICT_SIMILARITY_THRESHOLD:
                    logger.debug(
                        f"Conflict detected: {fact.text[:40]!r} ↔ {mem.content[:40]!r} "
                        f"(similarity={similarity:.3f})"
                    )
                    return True

        except Exception as exc:
            # Fail-open on conflict detection: if we can't check, don't flag.
            # A false negative (missing a conflict) is safer than a false positive
            # (blocking a valid import) since PendingConfirmation requires manual review.
            logger.warning(f"Conflict detection failed, proceeding without flag: {exc}")

        return False


def _tokenize(text: str) -> set[str]:
    """Tokenize text into a set of lowercase words (length > 2)."""
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2}


def _jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    """Compute Jaccard similarity between two token sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)
