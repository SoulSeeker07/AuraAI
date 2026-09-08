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

DOMAIN_PREFILTER_MIN_SCORE: float = 0.10
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

import re

# Mapping: domain tag → set of trigger keywords (whole-word boundary matched)
_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "preferences": (
        "prefer", "preference", "preferences", "favorite", "favourite",
        "dislike", "always", "default", "choice", "chosen",
    ),
    "projects": (
        "project", "repo", "repository", "codebase", "milestone", "sprint",
        "deploy", "branch", "workspace",
    ),
    "procedures": (
        "how to", "workflow", "procedure", "process", "routine",
        "recipe", "guide",
    ),
    "tech": (
        "gpu", "cpu", "ram", "monitor", "driver", "hardware", "software",
        "version", "install", "update", "os", "windows", "linux", "python",
        "editor", "terminal", "docker", "ide",
    ),
    "personal": (
        "name", "birthday", "location", "city", "country", "hobby",
        "pet", "family", "residence", "me", "myself", "about me",
        "who am i", "profile", "identity", "user", "my info", "detailed",
        "what do you know", "remember about me", "stored about me", "tell me about myself",
    ),
    "health": (
        "health", "medical", "doctor", "medication", "diagnosis", "symptom",
        "therapy", "exercise", "diet",
    ),
    "relationships": (
        "partner", "spouse", "friend", "family", "relationship", "dating",
        "married", "children",
    ),
    "finance": (
        "salary", "income", "savings", "investment", "budget", "expense",
        "bank", "tax", "debt",
    ),
}


class DomainClassifier:
    """
    Cheap keyword-based domain pre-filter using word boundaries.

    Checks if goal_text plausibly touches any domain the memory system
    tracks. A generic question ("what's the capital of France") should
    return an empty dict, skipping retrieval entirely.
    """

    def __init__(self) -> None:
        self._patterns: dict[str, list[re.Pattern]] = {
            domain: [
                re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE)
                for kw in keywords
            ]
            for domain, keywords in _DOMAIN_KEYWORDS.items()
        }

    def classify(self, goal_text: str) -> dict[str, float]:
        """
        Returns {domain_tag: score} for domains above noise floor.

        Score is the fraction of domain keywords found in the goal text.
        Guarantees score >= 0.10 for any single distinct keyword hit so
        legitimate queries with 1 hit pass DOMAIN_PREFILTER_MIN_SCORE.
        """
        scores: dict[str, float] = {}

        for domain, patterns in self._patterns.items():
            hits = sum(1 for pat in patterns if pat.search(goal_text))
            if hits > 0:
                raw_score = hits / len(patterns)
                score = max(0.10, round(raw_score, 3))
                scores[domain] = score

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

            # Gate: raw relevance score discounted by imported factor must clear threshold
            raw_rel = getattr(mem, "_recall_relevance", None)
            if raw_rel is None and hasattr(mem, "metadata") and isinstance(mem.metadata, dict):
                raw_rel = mem.metadata.get("_recall_relevance")
            if raw_rel is None:
                if hasattr(self._engine, "recall_engine"):
                    import re
                    q_terms = set(re.findall(r"\b\w+\b", goal_text.lower()))
                    raw_rel = self._engine.recall_engine._compute_relevance(q_terms, mem)
                else:
                    raw_rel = recall_score

            discount_factor = self._imported_discount if is_imported else 1.0
            combined = raw_rel * discount_factor
            gate_pass = combined >= threshold

            # Privacy-safe, zero-overhead telemetry gated strictly behind DEBUG verbosity
            if logger.isEnabledFor(logging.DEBUG):
                import hashlib
                q_hash = hashlib.sha256(goal_text.encode("utf-8")).hexdigest()[:8]
                mem_id = getattr(mem, "memory_id", "") or hashlib.sha256(mem.content.encode("utf-8")).hexdigest()[:8]
                mem_topic = getattr(mem, "topic", "unknown")
                mem_type = mem.type.value if hasattr(mem.type, "value") else str(mem.type)
                logger.debug(
                    f"[RetrievalGateTelemetry] q_hash={q_hash} q_len={len(goal_text)} "
                    f"mem_id={mem_id} topic={mem_topic} type={mem_type} "
                    f"rel={raw_rel:.4f} threshold={threshold:.2f} gate_pass={gate_pass}"
                )

            if not gate_pass:
                continue

            source = FactSource.IMPORTED if is_imported else FactSource.OBSERVED
            injected.append(
                InjectedFact(
                    text=mem.content,
                    effective_confidence=round(effective_confidence, 4),
                    recall_score=round(raw_rel, 4),
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
