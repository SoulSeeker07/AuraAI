"""
Memory Recall Engine
Location: src/memory/recall_engine.py

Multi-factor candidate scoring & ranking engine for cognitive memories.
Scores memories based on relevance, importance, recency, confidence,
project match, and memory type weights.
"""

import datetime as dt
import logging
from typing import Any

import numpy as np

from .models import MemoryItem, MemoryType

logger = logging.getLogger(__name__)

# Hybrid Recall Balance Constants
SEMANTIC_WEIGHT: float = 0.70
LEXICAL_WEIGHT: float = 0.30

ENGLISH_STOP_WORDS: frozenset[str] = frozenset({
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down",
    "during", "each", "few", "for", "from", "further", "had", "hadn't", "has",
    "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's",
    "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it",
    "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or",
    "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same",
    "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so",
    "some", "such", "than", "that", "that's", "the", "their", "theirs", "them",
    "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll",
    "they're", "they've", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're",
    "we've", "were", "weren't", "what", "what's", "when", "when's", "where",
    "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with",
    "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've",
    "your", "yours", "yourself", "yourselves", "tell", "show", "give", "please",
})


class RecallEngine:
    """Ranks and filters candidate memories for active context injection."""

    SEMANTIC_WEIGHT: float = SEMANTIC_WEIGHT
    LEXICAL_WEIGHT: float = LEXICAL_WEIGHT

    def __init__(
        self,
        weight_relevance: float = 0.35,
        weight_importance: float = 0.20,
        weight_recency: float = 0.15,
        weight_confidence: float = 0.15,
        weight_project: float = 0.10,
        weight_type: float = 0.05,
        semantic_weight: float = SEMANTIC_WEIGHT,
        lexical_weight: float = LEXICAL_WEIGHT,
    ):
        self.w_rel = weight_relevance
        self.w_imp = weight_importance
        self.w_rec = weight_recency
        self.w_conf = weight_confidence
        self.w_proj = weight_project
        self.w_type = weight_type
        self.semantic_weight = semantic_weight
        self.lexical_weight = lexical_weight

        # Type weight bonuses
        self.type_weights = {
            MemoryType.PREFERENCE: 1.0,
            MemoryType.WORKING: 0.9,
            MemoryType.PROJECT: 0.85,
            MemoryType.EPISODIC: 0.8,
            MemoryType.PROCEDURAL: 0.8,
            MemoryType.SEMANTIC: 0.75,
            MemoryType.LONG_TERM: 0.7,
            MemoryType.SHORT_TERM: 0.6,
            MemoryType.TASK: 0.5,
        }

    def score_and_rank(
        self,
        query: str,
        candidates: list[MemoryItem],
        active_project: str = "global",
        limit: int = 10,
    ) -> list[tuple[float, MemoryItem]]:
        """
        Score and rank a list of candidate MemoryItems against query and active project.

        Returns list of (score, MemoryItem) sorted descending by score.
        """
        if not candidates:
            return []

        import re
        query_terms = set(re.findall(r"\b\w+\b", query.lower())) if query else set()
        clean_terms = [t for t in query_terms if t not in ENGLISH_STOP_WORDS]

        # Hot-path single query embedding calculation (<10ms)
        query_vec: np.ndarray | None = None
        if clean_terms and query and query.strip():
            try:
                from memory.vector_memory import VectorMemoryEngine
                vec_eng = VectorMemoryEngine.get_instance()
                query_vec = vec_eng.encode(query)
            except Exception as e:
                logger.debug(f"[RecallEngine] Query encoding fallback to lexical: {e}")
                query_vec = None

        scored: list[tuple[float, MemoryItem]] = []
        now = dt.datetime.now()

        for mem in candidates:
            # 1. Relevance score (hybrid dense semantic cosine similarity + lexical overlap)
            lex_rel = self._compute_relevance(query_terms, mem)
            rel_score = lex_rel

            # Only evaluate vector similarity if query vector and pre-cached memory embedding both exist
            # Note: memory-side embeddings are NEVER computed inline during recall.
            if query_vec is not None and getattr(mem, "embedding", None) is not None:
                try:
                    mem_vec = np.frombuffer(mem.embedding, dtype=np.float32)
                    if mem_vec.shape == query_vec.shape:
                        cos_sim = float(np.dot(query_vec, mem_vec))
                        clamped_sim = max(0.0, min(1.0, cos_sim))
                        rel_score = (self.semantic_weight * clamped_sim) + (self.lexical_weight * lex_rel)
                except Exception as ve:
                    logger.debug(f"[RecallEngine] Cosine similarity fallback to lexical: {ve}")
                    rel_score = lex_rel

            setattr(mem, "_recall_relevance", round(rel_score, 4))

            # 2. Importance score (0.0 to 1.0)
            imp_score = mem.importance

            # 3. Recency score (decay over days)
            rec_score = self._compute_recency(now, mem.updated_at)

            # 4. Confidence score
            conf_score = mem.confidence

            # 5. Project match score
            proj_score = 1.0 if mem.project_id == active_project else (0.6 if mem.project_id == "global" else 0.1)

            # 6. Type weight score
            type_score = self.type_weights.get(mem.type, 0.5)

            # 7. Normalized Access Frequency Bonus (Capped logarithmic reinforcement)
            import math
            access_count = getattr(mem, "access_count", 0) or 0
            access_boost = min(0.15, 0.03 * math.log(1.0 + access_count))

            # Base weighted score
            base_score = (
                self.w_rel * rel_score
                + self.w_imp * imp_score
                + self.w_rec * rec_score
                + self.w_conf * conf_score
                + self.w_proj * proj_score
                + self.w_type * type_score
            )

            # Combined score with access boost
            total_score = base_score + access_boost

            # Anti-Popularity Floor/Ceiling: Ensure high-importance items (imp >= 0.9)
            # maintain a floor that prevents low-importance items (imp <= 0.3) from overtaking them
            if imp_score >= 0.90:
                total_score = max(total_score, 0.65)
            elif imp_score <= 0.30:
                total_score = min(total_score, 0.60)

            scored.append((round(total_score, 4), mem))

        # Sort descending by total_score
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:limit]

    def _compute_relevance(self, query_terms: set[str], mem: MemoryItem) -> float:
        """Compute keyword relevance between query terms and memory content, excluding stopwords."""
        effective_terms = {t for t in query_terms if len(t) > 2 and t not in ENGLISH_STOP_WORDS}
        if not effective_terms:
            return 0.0 if query_terms else 0.5

        content_lower = mem.content.lower()
        topic_lower = mem.topic.lower()
        metadata_str = str(mem.metadata).lower()

        matches = 0
        for term in effective_terms:
            if term in content_lower or term in topic_lower or term in metadata_str:
                matches += 1

        return min(1.0, matches / len(effective_terms))

    def _compute_recency(self, now: dt.datetime, timestamp_str: str) -> float:
        """Compute recency score based on hours elapsed since timestamp."""
        try:
            ts = dt.datetime.fromisoformat(timestamp_str)
            hours_old = (now - ts).total_seconds() / 3600.0
            if hours_old <= 1.0:
                return 1.0
            if hours_old <= 24.0:
                return 0.85
            if hours_old <= 168.0:  # 1 week
                return 0.65
            if hours_old <= 720.0:  # 1 month
                return 0.40
            return 0.20
        except Exception:
            return 0.5
