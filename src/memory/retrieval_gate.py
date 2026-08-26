"""
Memory Retrieval Gate
Location: src/memory/retrieval_gate.py

Two-stage relevance-and-confidence gated memory injection for AuraAI.

Placement in the agent loop:
    User Goal (goal_text)
        → MemoryRetrievalGate.get_context(goal_text)
        → MasterOrchestrator receives MemoryContext
        → to_prompt_fragment() injected into LLM prompt if non-empty

Stage 1 — Domain pre-filter (DomainClassifier):
    Cheap keyword-based check. Most queries need zero personalization;
    this must be fast. If no domain clears DOMAIN_PREFILTER_MIN_SCORE,
    return MemoryContext.empty() immediately.

Stage 2 — Retrieve, discount, gate:
    Queries CognitiveMemoryEngine.recall_ranked() for candidates,
    applies confidence discount for imported facts, applies elevated
    threshold for sensitive domains, excludes PendingConfirmation facts,
    caps at MAX_INJECTED_FACTS.

Fail-closed: any exception returns MemoryContext.empty(). Personalization
is an enhancement the agent loop must survive without.

Design decisions:
- Single scorer: wraps RecallEngine's existing multi-factor scoring,
  does NOT introduce a second embedding-based scorer.
- No meta-narration: to_prompt_fragment() renders bare fact statements.
- Sensitive domains (health, relationships, finance) require a stricter
  threshold to prevent irrelevant personalization bleeding.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memory.cognitive_memory import CognitiveMemoryEngine

from memory.models import MemoryItem, ProvenanceSource

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

MIN_MEMORY_RELEVANCE_THRESHOLD: float = 0.25
"""Minimum RecallEngine score for a fact to be considered for injection."""

IMPORTED_FACT_CONFIDENCE_DISCOUNT: float = 0.70
"""Multiplicative discount applied to imported facts' confidence before thresholding."""

MAX_INJECTED_FACTS: int = 5
"""Maximum number of facts injected into a single prompt."""

DOMAIN_PREFILTER_MIN_SCORE: float = 0.40
"""Minimum domain match score to proceed with retrieval (below = skip entirely)."""

SENSITIVE_DOMAIN_THRESHOLD: float = 0.55
"""Elevated threshold for sensitive domains — facts must be more clearly relevant."""

SENSITIVE_DOMAINS: frozenset[str] = frozenset({"health", "relationships", "finance"})

# Imported provenance sources that get the confidence discount
_IMPORTED_SOURCES: frozenset[str] = frozenset({
    ProvenanceSource.IMPORTED.value,
    ProvenanceSource.CLAUDE_IMPORT.value,
    ProvenanceSource.CHATGPT_IMPORT.value,
})


# ---------------------------------------------------------------------------
# Domain classifier — keyword heuristic, no embedding fallback
# ---------------------------------------------------------------------------

# Mapping: domain tag → set of trigger keywords
_DOMAIN_KEYWORDS: dict[str, frozenset[str]] = {
    "preferences": frozenset({
        "prefer", "favorite", "favourite", "like", "dislike", "always",
        "default", "choice", "chosen",
    }),
    "projects": frozenset({
        "project", "repo", "repository", "codebase", "milestone", "sprint",
        "deploy", "branch", "workspace",
    }),
    "procedures": frozenset({
        "how to", "workflow", "step", "procedure", "process", "routine",
        "recipe", "guide",
    }),
    "tech": frozenset({
        "gpu", "cpu", "ram", "monitor", "driver", "hardware", "software",
        "version", "install", "update", "os", "windows", "linux",
    }),
    "personal": frozenset({
        "name", "age", "birthday", "location", "city", "country", "hobby",
        "pet", "family",
    }),
    "health": frozenset({
        "health", "medical", "doctor", "medication", "diagnosis", "symptom",
        "therapy", "exercise", "diet",
    }),
    "relationships": frozenset({
        "partner", "spouse", "friend", "family", "relationship", "dating",
        "married", "children",
    }),
    "finance": frozenset({
        "salary", "income", "savings", "investment", "budget", "expense",
        "bank", "tax", "debt",
    }),
}


class DomainClassifier:
    """
    Cheap keyword-based domain pre-filter.

    Checks if goal_text plausibly touches any domain the memory system
    tracks. A generic question ("what's the capital of France") should
    return an empty dict, skipping retrieval entirely.
    """

    def classify(self, goal_text: str) -> dict[str, float]:
        """
        Returns {domain_tag: score} for domains above noise floor.

        Score is the fraction of domain keywords found in the goal text.
        Only domains with at least one keyword hit are returned.
        """
        text_lower = goal_text.lower()
        scores: dict[str, float] = {}

        for domain, keywords in _DOMAIN_KEYWORDS.items():
            hits = sum(1 for kw in keywords if kw in text_lower)
            if hits > 0:
                score = hits / len(keywords)
                scores[domain] = round(score, 3)

        return scores


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class FactSource(Enum):
    """Origin classification for a surfaced fact."""

    OBSERVED = auto()
    DEVICE_POLLED = auto()
    IMPORTED = auto()


@dataclass(frozen=True)
class InjectedFact:
    """A single fact that has cleared the retrieval gate for prompt injection."""

    text: str
    effective_confidence: float
    recall_score: float
    source: FactSource
    topic: str


@dataclass(frozen=True)
class MemoryContext:
    """
    Container for gated memory facts ready for prompt injection.

    Immutable after construction. to_prompt_fragment() renders facts as
    bare statements — no "based on memory" or "I recall" framing.
    """

    facts: tuple[InjectedFact, ...] = ()
    domains_considered: frozenset[str] = frozenset()
    retrieval_skipped: bool = False
    skip_reason: str | None = None

    @classmethod
    def empty(cls, reason: str | None = None) -> MemoryContext:
        return cls(retrieval_skipped=True, skip_reason=reason)

    def to_prompt_fragment(self) -> str:
        """
        Render facts as bare statements for prompt injection.

        No "based on memory", "I recall", or similar framing — that's an
        application-layer concern. The LLM uses the facts directly.
        """
        if not self.facts:
            return ""
        lines = [f"- {f.text}" for f in self.facts]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------

class MemoryRetrievalGate:
    """
    Two-stage relevance-and-confidence gated memory injection.

    Wraps CognitiveMemoryEngine.recall_ranked() and adds:
    - Domain pre-filtering (skip retrieval for generic queries)
    - Confidence discount for imported facts
    - Elevated threshold for sensitive domains
    - PendingConfirmation exclusion
    - Fact count cap

    Fail-closed: any exception returns MemoryContext.empty().
    """

    def __init__(
        self,
        cognitive_engine: CognitiveMemoryEngine,
        *,
        min_relevance: float = MIN_MEMORY_RELEVANCE_THRESHOLD,
        imported_discount: float = IMPORTED_FACT_CONFIDENCE_DISCOUNT,
        max_facts: int = MAX_INJECTED_FACTS,
        domain_prefilter_min: float = DOMAIN_PREFILTER_MIN_SCORE,
        sensitive_threshold: float = SENSITIVE_DOMAIN_THRESHOLD,
    ) -> None:
        self._engine = cognitive_engine
        self._classifier = DomainClassifier()
        self._min_relevance = min_relevance
        self._imported_discount = imported_discount
        self._max_facts = max_facts
        self._prefilter_min = domain_prefilter_min
        self._sensitive_threshold = sensitive_threshold

    def get_context(
        self,
        goal_text: str,
        active_project: str = "global",
    ) -> MemoryContext:
        """
        Fail-closed entry point. Any exception returns MemoryContext.empty().

        Args:
            goal_text: The user's goal/query text.
            active_project: Active project ID for scoped retrieval.

        Returns:
            MemoryContext with relevant facts, or empty context.
        """
        try:
            return self._get_context_unsafe(goal_text, active_project)
        except Exception:
            logger.exception(
                "MemoryRetrievalGate failed; proceeding with empty context",
                extra={"goal_text_len": len(goal_text)},
            )
            return MemoryContext.empty(reason="retrieval_error")

    def _get_context_unsafe(
        self, goal_text: str, active_project: str
    ) -> MemoryContext:
        # Stage 1: Domain pre-filter
        domain_scores = self._classifier.classify(goal_text)
        relevant_domains = {
            d: s for d, s in domain_scores.items() if s >= self._prefilter_min
        }
        if not relevant_domains:
            logger.debug("No domain match above prefilter; skipping memory retrieval.")
            return MemoryContext.empty(reason="no_domain_match")

        # Check if any matched domains are sensitive
        has_sensitive = bool(set(relevant_domains.keys()) & SENSITIVE_DOMAINS)

        # Stage 2: Retrieve candidates via RecallEngine
        candidates = self._engine.recall_ranked(
            query=goal_text, active_project=active_project, limit=20
        )
        if not candidates:
            return MemoryContext.empty(reason="no_candidates")

        # Filter out PendingConfirmation facts
        candidates = [
            c for c in candidates
            if not c.metadata.get("pending_confirmation")
        ]
        if not candidates:
            return MemoryContext.empty(reason="all_pending_confirmation")

        # Score and gate each candidate
        injected: list[InjectedFact] = []

        # We need the RecallEngine scores — re-score to get (score, mem) pairs
        scored_pairs = self._engine.recall_engine.score_and_rank(
            goal_text, candidates, active_project=active_project, limit=20
        )

        for recall_score, mem in scored_pairs:
            # Apply confidence discount for imported facts
            effective_confidence = mem.confidence
            prov_source = ""
            if hasattr(mem.provenance, "source_type"):
                prov_source = (
                    mem.provenance.source_type.value
                    if hasattr(mem.provenance.source_type, "value")
                    else str(mem.provenance.source_type)
                )

            is_imported = prov_source in _IMPORTED_SOURCES
            if is_imported:
                effective_confidence *= self._imported_discount

            # Determine threshold
            threshold = self._min_relevance
            if has_sensitive:
                threshold = max(threshold, self._sensitive_threshold)

            # Gate: recall_score discounted by imported factor must clear threshold
            discount_factor = self._imported_discount if is_imported else 1.0
            combined = recall_score * discount_factor
            if combined < threshold:
                continue

            source = FactSource.IMPORTED if is_imported else FactSource.OBSERVED
            injected.append(
                InjectedFact(
                    text=mem.content,
                    effective_confidence=round(effective_confidence, 4),
                    recall_score=round(recall_score, 4),
                    source=source,
                    topic=mem.topic,
                )
            )

        # Sort by combined score descending, cap at max
        injected.sort(
            key=lambda f: f.recall_score * f.effective_confidence, reverse=True
        )
        injected = injected[: self._max_facts]

        return MemoryContext(
            facts=tuple(injected),
            domains_considered=frozenset(relevant_domains.keys()),
        )
