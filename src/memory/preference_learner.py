"""
Adaptive Preference Learning & Extraction Engine
Location: src/memory/preference_learner.py

Extracts, categorizes, tiers (PROVISIONAL vs CONFIRMED), and resolves conflicts
for user preferences and standing instructions across sessions.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from .models import MemoryItem, MemoryProvenance, MemoryType, ProvenanceSource

logger = logging.getLogger(__name__)

# Patterns signaling an explicit, durable standing preference (direct subject-predicate binding)
EXPLICIT_PREFERENCE_PATTERNS = [
    r"\b(?:always|never)\s+(?:use|run|prefer|do|apply|include|create|output|format|write)\b",
    r"\b(?:i\s+prefer|my\s+preference\s+is|i\s+like\s+to\s+use|i\s+favor|favor\s+\w+\s+over)\b",
    r"\b(?:from\s+now\s+on|going\s+forward|as\s+a\s+rule)\s+(?:let's\s+)?(?:use|stick\s+with|run\s+with|prefer)\b",
    r"\b(?:let's\s+(?:just\s+)?(?:go|stick)\s+with\s+[a-zA-Z0-9_\-\.\+]+(?:\s+going\s+forward)?)\b",
    r"\b(?:by\s+default\s+(?:use|run|prefer)|(?:use|run|prefer)\s+[a-zA-Z0-9_\-\.\+]+\s+by\s+default)\b",
    r"\b(?:make\s+sure\s+to\s+always|remember\s+to\s+always)\s+(?:use|write|run|create)\b",
    r"\b(?:keep\s+everything\s+(?:concise|verbose|brief))\b",
]

# Patterns signaling a bug report, diagnostics, or question (suppress false positive preference extraction)
NEGATIVE_OR_BUG_PATTERNS = [
    r"\b(?:bug|broken|crash|failure|fails|failing|error|exception|issue|problem|warning|traceback)\b",
    r"\b(?:why\s+is|how\s+to|what\s+is|is\s+there|help\s+with|debug|fixing|diagnose)\b",
    r"\b(?:reproduce|reproducing|investigate|inspect|audit)\b",
]

# Patterns signaling third-person/passive descriptions (should use, could use, to use)
MODAL_OR_PASSIVE_PATTERNS = [
    r"\b(?:should|could|would|might|must|to|of)\s+(?:use|run|try|test|install|build|format)\b",
]

# Patterns signaling a direct one-off / imperative command
IMPERATIVE_COMMAND_PATTERNS = [
    r"\b(?:use|run(?:\s+\w+)?\s+with|try(?:\s+\w+)?\s+with|switch\s+to|change\s+to|test(?:\s+\w+)?\s+with|install(?:\s+\w+)?\s+with|build(?:\s+\w+)?\s+with|format(?:\s+\w+)?\s+with)\b",
    r"\b(?:run|try|test|install|build|format)\s+(?:tests|suite|code|files|package|project)?\s*(?:with|using)\b",
    r"^(?:please\s+)?(?:use|run|try|test|install|build|format)\s+[a-zA-Z0-9_\-\.\+]+",
    r"\b(?:let's\s+)(?:use|run|try|test|install|build|format|stick\s+with)\b",
    r"\b(?:can\s+you\s+)(?:use|run|try|test|install|build|format)\b",
]

# Domain categories for preference classification (specific, unambiguous identifiers)
PREFERENCE_CATEGORIES = {
    "tooling": ["pytest", "npm", "pnpm", "yarn", "uv", "pip", "ruff", "black", "mypy", "docker", "poetry", "bun"],
    "runtime_lang": ["python", "python3", "nodejs", "node.js", "node runtime", "rust", "golang", "go", "java", "c++", "c#"],
    "llm_provider": ["groq", "openai", "anthropic", "gemini", "ollama", "claude", "gpt-4", "local llm"],
    "editor_env": ["vscode", "vs code", "pycharm", "sublime", "vim", "neovim", "cursor", "emacs"],
    "style_code": ["async", "sync", "camelcase", "snake_case", "typescript", "type annotations", "docstrings", "pep8", "tabs", "spaces"],
    "ui_theme": ["dark mode", "light mode", "dark theme", "light theme", "high contrast", "minimal"],
    "communication": ["concise", "verbose", "brief", "detailed", "bullet points", "step by step"],
}

_EXPLICIT_RE = re.compile("|".join(EXPLICIT_PREFERENCE_PATTERNS), re.IGNORECASE)
_IMPERATIVE_RE = re.compile("|".join(IMPERATIVE_COMMAND_PATTERNS), re.IGNORECASE)
_NEGATIVE_RE = re.compile("|".join(NEGATIVE_OR_BUG_PATTERNS), re.IGNORECASE)
_MODAL_RE = re.compile("|".join(MODAL_OR_PASSIVE_PATTERNS), re.IGNORECASE)


class PreferenceLearner:
    """
    Learns and tracks durable user preferences with strict provenance
    and provisional-vs-confirmed lifecycle tiers.
    """

    def __init__(self, promotion_threshold: int = 2):
        self.promotion_threshold = promotion_threshold

    def extract_preference_candidates(
        self,
        text: str,
        session_id: str = "session_unknown",
        project_id: str = "global",
    ) -> List[MemoryItem]:
        """
        Analyze user conversational turn and extract candidate preference items.
        Classifies as CONFIRMED if explicitly phrased, or PROVISIONAL if imperative one-off.
        Suppresses false positives from quotes, bug reports, and passive noun mentions.
        """
        if not text or len(text.strip()) < 5:
            return []

        # 1. Strip XML wrapper tags like <USER_REQUEST> if present
        raw_text = re.sub(r"<[^>]+>", " ", text)

        # 2. Strip paired quoted text across full message to avoid citation leaks
        raw_unquoted = re.sub(r'"[^"]*"', ' ', raw_text)
        raw_unquoted = re.sub(r'“[^”]*”', ' ', raw_unquoted)
        raw_unquoted = re.sub(r'`[^`]*`', ' ', raw_unquoted)
        raw_unquoted = re.sub(r'«[^»]*»', ' ', raw_unquoted)

        # 3. Split text into sentences/clauses
        sentences = [s.strip() for s in re.split(r"[\n\.\?!;]+", raw_unquoted) if s.strip()]
        candidates: List[MemoryItem] = []

        for sent in sentences:
            unquoted = sent.strip()
            if len(unquoted) < 5:
                continue

            # Check if sentence is a bug report or diagnostic question
            if bool(_NEGATIVE_RE.search(unquoted)):
                continue

            # Check for third-person modal expressions (e.g. "should use")
            if not bool(_EXPLICIT_RE.search(unquoted)) and bool(_MODAL_RE.search(unquoted)):
                continue

            # Check for explicit standing preference vs imperative command
            is_explicit = bool(_EXPLICIT_RE.search(unquoted))
            is_imperative = bool(_IMPERATIVE_RE.search(unquoted))

            if not (is_explicit or is_imperative):
                # Passive noun mention (e.g. "TypeScript provider" without a preference predicate) -> skip
                continue

            # Detect category keyword inside this specific sentence
            detected_category, matched_kw = self._detect_category(unquoted)
            if not matched_kw:
                continue

            topic = f"pref:{detected_category}:{matched_kw.replace(' ', '_').lower()}"
            confidence = 0.95 if is_explicit else 0.50
            importance = 0.90 if is_explicit else 0.40
            status = "CONFIRMED" if is_explicit else "PROVISIONAL"

            content = self._format_preference_statement(unquoted, detected_category, matched_kw, is_explicit)

            item = MemoryItem(
                type=MemoryType.PREFERENCE,
                content=content,
                importance=importance,
                confidence=confidence,
                project_id=project_id,
                topic=topic,
                provenance=MemoryProvenance(
                    source_type=ProvenanceSource.USER_EXPLICIT if is_explicit else ProvenanceSource.RUNTIME_SESSION,
                    source_id=session_id,
                    confidence=confidence,
                    verified=is_explicit,
                ),
                metadata={
                    "category": detected_category,
                    "keyword": matched_kw,
                    "status": status,
                    "hit_count": 1,
                    "is_explicit": is_explicit,
                    "raw_statement": unquoted[:200],
                },
            )
            candidates.append(item)
            # One preference per sentence is sufficient
            break

        return candidates

    def resolve_conflicts_and_merge(
        self,
        new_item: MemoryItem,
        existing_items: List[MemoryItem],
    ) -> Tuple[List[MemoryItem], List[str]]:
        """
        Evaluate a new candidate preference against existing memory items.
        Returns:
            (items_to_save_or_update, memory_ids_to_deprecate_or_supersede)
        """
        items_to_save = []
        superseded_ids = []

        new_cat = new_item.metadata.get("category")
        new_kw = new_item.metadata.get("keyword")

        matching_existing = [
            m for m in existing_items
            if m.type == MemoryType.PREFERENCE and m.metadata.get("category") == new_cat
        ]

        if not matching_existing:
            items_to_save.append(new_item)
            return items_to_save, superseded_ids

        # Check if identical preference keyword
        exact_match = next((m for m in matching_existing if m.metadata.get("keyword") == new_kw), None)

        if exact_match:
            # Reinforce hit count & promote if provisional threshold met
            hit_count = int(exact_match.metadata.get("hit_count", 1)) + 1
            exact_match.metadata["hit_count"] = hit_count

            if hit_count >= self.promotion_threshold and exact_match.metadata.get("status") == "PROVISIONAL":
                exact_match.metadata["status"] = "CONFIRMED"
                exact_match.confidence = 0.90
                exact_match.importance = 0.85
                exact_match.provenance.verified = True
                logger.info(f"[PreferenceLearner] Promoted provisional preference '{new_kw}' to CONFIRMED (Hits: {hit_count})")

            exact_match.updated_at = new_item.updated_at
            items_to_save.append(exact_match)
            return items_to_save, superseded_ids

        # Conflicting preference in the same category (e.g. package_manager: npm vs pnpm)
        # If new item is explicit or higher confidence, supersede older preference
        for old in matching_existing:
            if old.metadata.get("status") != "SUPERSEDED":
                old.metadata["status"] = "SUPERSEDED"
                old.metadata["superseded_by"] = new_item.memory_id
                old.importance = 0.10
                old.confidence = 0.20
                superseded_ids.append(old.memory_id)
                items_to_save.append(old)
                logger.info(
                    f"[PreferenceLearner] Superseded older preference '{old.metadata.get('keyword')}' with '{new_kw}'"
                )

        items_to_save.append(new_item)
        return items_to_save, superseded_ids

    def _detect_category(self, text: str) -> Tuple[str, str]:
        """Match text against known preference taxonomies."""
        text_lower = text.lower()
        for cat, keywords in PREFERENCE_CATEGORIES.items():
            for kw in keywords:
                pattern = r"\b" + re.escape(kw) + r"\b"
                if re.search(pattern, text_lower):
                    return cat, kw
        return "general", ""

    def _format_preference_statement(self, raw: str, category: str, keyword: str, is_explicit: bool) -> str:
        if is_explicit:
            return f"User preference ({category}): {raw}"
        return f"User observed practice ({category}): prefers {keyword}"
