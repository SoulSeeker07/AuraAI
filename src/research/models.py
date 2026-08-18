"""
Research Engine Data Models

Strongly-typed data structures for research operations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SearchMode(Enum):
    """Research search modes."""

    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class SourceTrustLevel(Enum):
    """Trust levels for search sources."""

    OFFICIAL = "official"
    GOVERNMENT = "government"
    GITHUB = "github"
    NEWS = "news"
    STACK_OVERFLOW = "stackoverflow"
    WIKIPEDIA = "wikipedia"
    REDDIT = "reddit"
    BLOG = "blog"
    UNKNOWN = "unknown"


def normalize_trust_level(level: Any) -> str:
    """Normalize a trust level to a lowercase string."""
    if isinstance(level, SourceTrustLevel):
        return level.value
    if level is None:
        return SourceTrustLevel.UNKNOWN.value
    return str(level).lower()


def parse_source_trust_level(level: Any) -> SourceTrustLevel:
    """Parse a value into a SourceTrustLevel enum."""
    if isinstance(level, SourceTrustLevel):
        return level
    try:
        return SourceTrustLevel(str(level).lower())
    except ValueError:
        return SourceTrustLevel.UNKNOWN


class ConflictResolution(Enum):
    """Conflict resolution strategies."""

    AUTO = "auto"
    PREFER_AUTHORITATIVE = "prefer_authoritative"
    PREFER_RECENT = "prefer_recent"
    INCLUDE_BOTH = "include_both"
    PROMPT_USER = "prompt_user"


# ── Canonical Quality & Gating Thresholds ────────────────────────────────────

# Minimum confidence required to synthesize search evidence into a factual report.
# Rationale: Rejects ungrounded hallucinations while accepting partially corroborated
# multi-source findings (at least one credible corroborated source).
MIN_SYNTHESIS_CONFIDENCE_THRESHOLD: float = 0.40



@dataclass
class Citation:
    """
    Citation for a specific source.

    Attributes:
        url: Source URL
        title: Source title
        trust_level: Trust level of the source
        score: int | float
        key: Citation key (e.g. '[1]', '[2]')
        domain: Extracted source domain (e.g. 'python.org')
        author: Author if available
        date: Publication date
        snippet: Relevant snippet
        evidence: The specific evidence or fact from this source
    """

    url: str
    title: str
    trust_level: SourceTrustLevel
    score: int | float = 80
    key: str = ""
    domain: str = ""
    author: str | None = None
    date: datetime | None = None
    snippet: str | None = None
    evidence: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "key": self.key,
            "url": self.url,
            "domain": self.domain,
            "title": self.title,
            "trust_level": self.trust_level.value if isinstance(self.trust_level, SourceTrustLevel) else str(self.trust_level),
            "score": self.score,
            "author": self.author,
            "date": self.date.isoformat() if self.date else None,
            "snippet": self.snippet,
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Citation":
        """Create from dictionary."""
        date_str = data.get("date")
        date = datetime.fromisoformat(date_str) if date_str else None
        trust = data.get("trust_level", "unknown")
        if isinstance(trust, str):
            try:
                trust_lvl = SourceTrustLevel(trust)
            except ValueError:
                trust_lvl = SourceTrustLevel.UNKNOWN
        else:
            trust_lvl = trust
        return cls(
            key=data.get("key", ""),
            url=data.get("url", ""),
            domain=data.get("domain", ""),
            title=data.get("title", ""),
            trust_level=trust_lvl,
            score=data.get("score", 80),
            author=data.get("author"),
            date=date,
            snippet=data.get("snippet"),
            evidence=data.get("evidence"),
        )


@dataclass
class Evidence:
    """
    A single piece of verified evidence extracted from search results.

    Evidence represents a fact or claim extracted from a source,
    ready for the LLM to reason over.

    Attributes:
        fact: The specific fact or claim (e.g., "Python 3.14 released")
        source: Source name (e.g., "python.org", "github.com")
        url: URL of the source page
        trust_level: Trust level of the source
        score: Trust score (0-5, or 0-100 for evidence score)
        confidence: Confidence in this evidence (0-100)
        citations: List of citation IDs supporting this evidence
        context: Brief context explaining the evidence
        tags: Tags for categorization (e.g., "feature", "bug", "release")
        is_verified: Whether evidence has been manually verified
        evidence_type: Type of evidence (fact, claim, statistic, quote)
        raw_snippet: Original source snippet if available
    """

    fact: str
    source: str
    trust_level: SourceTrustLevel
    score: int
    url: str = ""
    confidence: float = 85.0  # Default confidence
    citations: list[str] = field(default_factory=list)
    context: str | None = None
    tags: list[str] = field(default_factory=list)
    is_verified: bool = False
    evidence_type: str = "fact"
    raw_snippet: str | None = None
    # Freshness metadata (Milestone 14 requirement)
    retrieved_at: datetime | None = None
    published_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "url": self.url,
            "fact": self.fact,
            "source": self.source,
            "trust_level": self.trust_level.value,
            "score": self.score,
            "confidence": self.confidence,
            "citations": self.citations,
            "context": self.context,
            "tags": self.tags,
            "is_verified": self.is_verified,
            "evidence_type": self.evidence_type,
            "raw_snippet": self.raw_snippet,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Evidence":
        """Create from dictionary."""
        return cls(
            fact=data["fact"],
            source=data["source"],
            trust_level=SourceTrustLevel(data["trust_level"]),
            score=data["score"],
            confidence=data.get("confidence", 85.0),
            citations=data.get("citations", []),
            context=data.get("context"),
            tags=data.get("tags", []),
            is_verified=data.get("is_verified", False),
            evidence_type=data.get("evidence_type", "fact"),
            raw_snippet=data.get("raw_snippet"),
        )

    def __str__(self) -> str:
        """String representation."""
        source = f"[{self.source}]" if self.source else "[Unknown]"
        verified = "✓" if self.is_verified else ""
        return f"{verified}{source}: {self.fact}"


@dataclass
class Document:
    """
    Structured document from a URL.

    Attributes:
        url: Source URL
        title: Document title
        author: Author name
        date: Publication date
        content: Full content
        summary: Summary of the content
        content_type: Type of content (article, documentation, etc.)
        raw_html: Raw HTML if needed for further processing
        metadata: Additional metadata
    """

    url: str
    title: str
    content: str
    content_type: str = "article"
    author: str | None = None
    date: datetime | None = None
    summary: str | None = None
    raw_html: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "content_type": self.content_type,
            "author": self.author,
            "date": self.date.isoformat() if self.date else None,
            "summary": self.summary,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Document":
        """Create from dictionary."""
        date_str = data.get("date")
        date = datetime.fromisoformat(date_str) if date_str else None
        return cls(
            url=data["url"],
            title=data["title"],
            content=data["content"],
            content_type=data.get("content_type", "article"),
            author=data.get("author"),
            date=date,
            summary=data.get("summary"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class SearchResult:
    """
    A single search result.

    Attributes:
        url: Result URL
        title: Result title
        snippet: Short description
        source: Provider name
        score: Relevance score (0-100)
        trust_level: Trust level of the source
        document: Optional parsed document
        raw_data: Raw data from provider
    """

    url: str
    title: str
    snippet: str
    source: str
    score: int
    trust_level: SourceTrustLevel
    document: Document | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
            "source": self.source,
            "score": self.score,
            "trust_level": self.trust_level.value,
            "document": self.document.to_dict() if self.document else None,
            "raw_data": self.raw_data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SearchResult":
        """Create from dictionary."""
        doc_data = data.get("document")
        document = Document.from_dict(doc_data) if doc_data else None
        return cls(
            url=data["url"],
            title=data["title"],
            snippet=data["snippet"],
            source=data["source"],
            score=data["score"],
            trust_level=SourceTrustLevel(data["trust_level"]),
            document=document,
            raw_data=data.get("raw_data", {}),
        )


@dataclass
class SearchQuery:
    """
    A research query with all parameters.

    Attributes:
        query_text: The main query text
        mode: Search mode (quick, standard, deep)
        max_results: Maximum results per source
        sources: List of allowed source types (optional)
        min_trust_score: Minimum trust score (0-5)
        topics: Related topics to search for
        keywords: Additional keywords
        exclude_keywords: Words to exclude
        start_date: Start date for results
        end_date: End date for results
        language: Language code (e.g., 'en', 'es')
        time_range: Time range filter (e.g., 'week', 'month', 'year')
    """

    query_text: str
    mode: SearchMode = SearchMode.STANDARD
    max_results: int = 10
    sources: list[str] | None = None
    min_trust_score: int = 3
    topics: list[str] | None = None
    keywords: list[str] | None = None
    exclude_keywords: list[str] | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    language: str = "en"
    time_range: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "query_text": self.query_text,
            "mode": self.mode.value,
            "max_results": self.max_results,
            "sources": self.sources,
            "min_trust_score": self.min_trust_score,
            "topics": self.topics,
            "keywords": self.keywords,
            "exclude_keywords": self.exclude_keywords,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "language": self.language,
            "time_range": self.time_range,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SearchQuery":
        """Create from dictionary."""
        start_date_str = data.get("start_date")
        end_date_str = data.get("end_date")
        start_date = datetime.fromisoformat(start_date_str) if start_date_str else None
        end_date = datetime.fromisoformat(end_date_str) if end_date_str else None
        return cls(
            query_text=data["query_text"],
            mode=SearchMode(data["mode"]),
            max_results=data.get("max_results", 10),
            sources=data.get("sources"),
            min_trust_score=data.get("min_trust_score", 3),
            topics=data.get("topics"),
            keywords=data.get("keywords"),
            exclude_keywords=data.get("exclude_keywords"),
            start_date=start_date,
            end_date=end_date,
            language=data.get("language", "en"),
            time_range=data.get("time_range"),
        )


@dataclass
class ResearchReport:
    """
    Complete research report with merged findings.

    Attributes:
        query: The original search query
        results: All search results
        merged_evidence: Merged and ranked evidence
        citations: List of citations with confidence scores
        conflicts: Detected conflicts between sources
        primary_sources: Primary sources for the answer
        summary: Executive summary
        detailed_findings: Detailed findings organized by topic
        key_stats: Key statistics extracted
        timestamp: When the research was conducted
        duration: Research duration in seconds
        metadata: Additional metadata
    """

    query: str
    results: list[SearchResult] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    merged_evidence: list[dict[str, Any]] = field(default_factory=list)  # Legacy field
    citations: list[Citation] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    primary_sources: list[str] = field(default_factory=list)
    summary: str | None = None
    detailed_findings: dict[str, Any] = field(default_factory=dict)
    key_stats: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    duration: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_result(self, result: SearchResult) -> None:
        """Add a search result."""
        self.results.append(result)

    def add_citation(self, citation: Citation) -> None:
        """Add a citation."""
        self.citations.append(citation)

    def add_conflict(self, conflict: dict[str, Any]) -> None:
        """Add a detected conflict."""
        self.conflicts.append(conflict)

    def convert_results_to_evidence(self) -> None:
        """
        Convert search results to structured Evidence objects.

        Extracts facts and claims from search results and creates
        Evidence objects ready for LLM reasoning.
        """
        self.evidence = []

        for result in self.results:
            if result.document and result.document.content:
                # Extract key sentences as potential evidence
                sentences = self._extract_key_sentences(result.document.content)

                for sentence in sentences:
                    evidence = Evidence(
                        fact=sentence,
                        source=result.source,
                        trust_level=result.trust_level,
                        score=result.score,
                        confidence=self._calculate_evidence_confidence(result),
                        tags=self._categorize_evidence(sentence, result.trust_level),
                        raw_snippet=result.snippet,
                    )
                    self.evidence.append(evidence)
                    self.merged_evidence.append(evidence.to_dict())

        # Sort evidence by confidence and trust level
        self.evidence.sort(key=lambda e: e.confidence, reverse=True)

    def _extract_key_sentences(self, content: str, max_sentences: int = 5) -> list[str]:
        """
        Extract key sentences from content.

        Args:
            content: Text content
            max_sentences: Maximum number of sentences to extract

        Returns:
            List of key sentences
        """
        import re

        sentences = re.split(r"(?<=[.!?])\s+", content)
        return sentences[:max_sentences]

    def _calculate_evidence_confidence(self, result: SearchResult) -> float:
        """
        Calculate confidence score for evidence.

        Args:
            result: Search result

        Returns:
            Confidence score (0-100)
        """
        # Base confidence from relevance score
        base_confidence = result.score

        # Boost confidence from higher trust level
        trust_bonuses = {
            SourceTrustLevel.OFFICIAL: 10,
            SourceTrustLevel.GITHUB: 5,
            SourceTrustLevel.WIKIPEDIA: 3,
            SourceTrustLevel.STACK_OVERFLOW: 2,
        }
        base_confidence += trust_bonuses.get(result.trust_level, 0)

        # Cap at 100
        return min(base_confidence, 100.0)

    def _categorize_evidence(
        self, fact: str, trust_level: SourceTrustLevel
    ) -> list[str]:
        """
        Categorize evidence by type.

        Args:
            fact: Evidence fact
            trust_level: Trust level of source

        Returns:
            List of tags
        """
        tags = []

        # Categorize by trust level
        if trust_level in [SourceTrustLevel.OFFICIAL, SourceTrustLevel.GOVERNMENT]:
            tags.append("official")
        elif trust_level == SourceTrustLevel.GITHUB:
            tags.append("technical")
            tags.append("code")
        elif trust_level == SourceTrustLevel.WIKIPEDIA:
            tags.append("reference")
        elif trust_level == SourceTrustLevel.STACK_OVERFLOW:
            tags.append("solution")

        # Categorize by content
        fact_lower = fact.lower()
        if any(word in fact_lower for word in ["release", "version", "beta", "stable"]):
            tags.append("release")
        elif any(word in fact_lower for word in ["bug", "issue", "problem", "fix"]):
            tags.append("bug")
        elif any(word in fact_lower for word in ["deprecated", "removed"]):
            tags.append("breaking")

        return tags

    def get_confidence_score(self) -> float:
        """
        Calculate overall confidence score based on evidence.

        Returns:
            Confidence score (0-100)
        """
        if not self.evidence:
            return 0.0

        # Weighted average of evidence confidences
        avg_confidence = sum(e.confidence for e in self.evidence) / len(self.evidence)

        # Adjust by number of sources
        source_count = len(set(e.source for e in self.evidence))
        source_bonus = min(source_count * 5, 20)  # Max 20 bonus

        return min(avg_confidence + source_bonus, 100.0)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "query": self.query,
            "results": [r.to_dict() for r in self.results],
            "evidence": [e.to_dict() for e in self.evidence],
            "merged_evidence": self.merged_evidence,
            "citations": [c.to_dict() for c in self.citations],
            "conflicts": self.conflicts,
            "primary_sources": self.primary_sources,
            "summary": self.summary,
            "detailed_findings": self.detailed_findings,
            "key_stats": self.key_stats,
            "timestamp": self.timestamp.isoformat(),
            "duration": self.duration,
            "metadata": self.metadata,
            "confidence_score": self.get_confidence_score(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchReport":
        """Create from dictionary."""
        timestamp_str = data.get("timestamp")
        timestamp = (
            datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now()
        )

        # Handle legacy format
        if "search_results" in data:  # Old format
            results = [SearchResult.from_dict(r) for r in data["search_results"]]
        else:
            results = [SearchResult.from_dict(r) for r in data.get("results", [])]

        citations = [Citation.from_dict(c) for c in data.get("citations", [])]
        evidence_data = data.get("evidence", [])
        evidence = (
            [Evidence.from_dict(e) for e in evidence_data] if evidence_data else []
        )

        report = cls(
            query=data["query"],
            results=results,
            citations=citations,
            evidence=evidence,
            conflicts=data.get("conflicts", []),
            primary_sources=data.get("primary_sources", []),
            summary=data.get("summary"),
            detailed_findings=data.get("detailed_findings", {}),
            key_stats=data.get("key_stats", {}),
            timestamp=timestamp,
            duration=data.get("duration", 0.0),
            metadata=data.get("metadata", {}),
        )

        # Update merged_evidence from evidence if available
        if evidence:
            report.merged_evidence = [e.to_dict() for e in evidence]

        return report


class SourceRanking:
    """
    Rankings sources by trust level and score.

    Uses trust level scores to weight evidence from different sources.

    Attributes:
        ranking: Ordered list of (source_name, score) tuples
        max_score: Maximum possible score
    """

    OFFICIAL_WEIGHTS = {
        SourceTrustLevel.OFFICIAL: 5.0,
        SourceTrustLevel.GOVERNMENT: 4.5,
    }
    TECHNICAL_WEIGHTS = {
        SourceTrustLevel.GITHUB: 4.0,
        SourceTrustLevel.STACK_OVERFLOW: 3.5,
        SourceTrustLevel.WIKIPEDIA: 3.0,
    }
    NEWS_WEIGHTS = {
        SourceTrustLevel.NEWS: 2.5,
        SourceTrustLevel.REDDIT: 2.0,
        SourceTrustLevel.BLOG: 1.5,
    }
    UNKNOWN_WEIGHTS = {SourceTrustLevel.UNKNOWN: 0.5}

    ALL_WEIGHTS = {
        **OFFICIAL_WEIGHTS,
        **TECHNICAL_WEIGHTS,
        **NEWS_WEIGHTS,
        **UNKNOWN_WEIGHTS,
    }

    def __init__(self):
        self.ranking: list[tuple[str, float]] = []
        self.max_score = 0.0

    def rank_sources(self, results: list[SearchResult]) -> None:
        """
        Rank sources by trust level.

        Args:
            results: List of search results
        """
        source_scores: dict[str, float] = {}

        for result in results:
            source_name = result.source.lower()
            trust_level = result.trust_level

            # Get base score from weights
            weight = self.ALL_WEIGHTS.get(trust_level, 1.0)

            # Adjust score by relevance score (0-100)
            relevance_factor = result.score / 100.0

            # Combined score: weighted trust + relevance
            total_score = weight * (0.7 + 0.3 * relevance_factor)

            # Average multiple results from same source
            if source_name in source_scores:
                source_scores[source_name] = (
                    source_scores[source_name][0] + total_score,
                    source_scores[source_name][1] + 1,
                )
            else:
                source_scores[source_name] = (total_score, 1)

        # Convert to list and sort by score (descending)
        self.ranking = [
            (name, total_score) for name, (total_score, count) in source_scores.items()
        ]
        self.ranking.sort(key=lambda x: x[1], reverse=True)
        self.max_score = max((score for _, score in self.ranking), default=0.0)

    def get_weighted_evidence(
        self, evidence_list: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Return evidence weighted by source trust.

        Args:
            evidence_list: List of evidence dictionaries

        Returns:
            Evidence list with added weights
        """
        for evidence in evidence_list:
            if "source" in evidence:
                source_name = evidence["source"].lower()
                trust_level = evidence.get("trust_level", SourceTrustLevel.UNKNOWN)
                weight = self.ALL_WEIGHTS.get(trust_level, 1.0)
                evidence["weight"] = weight
                evidence["rank"] = next(
                    (
                        i
                        for i, (name, _) in enumerate(self.ranking)
                        if name == source_name
                    ),
                    -1,
                )

        return evidence_list

    def get_top_sources(self, top_n: int = 5) -> list[str]:
        """
        Get top N sources by trust.

        Args:
            top_n: Number of top sources to return

        Returns:
            List of top source names
        """
        return [name for name, _ in self.ranking[:top_n]]


@dataclass
class ResearchConfig:
    """
    Configuration for the Research Engine.

    Attributes:
        enabled: Whether research is enabled
        default_mode: Default search mode
        default_max_results: Default max results per source
        cache_ttl: Cache time-to-live in seconds
        conflict_resolution: Default conflict resolution strategy
        enable_auto_expansion: Automatically expand search with related topics
        enable_fact_checking: Enable fact extraction and validation
        citation_required: Require citations for all answers
        debug: Enable detailed runtime diagnostics and logging
    """

    enabled: bool = True
    default_mode: SearchMode = SearchMode.STANDARD
    default_max_results: int = 10
    cache_ttl: int = 1800  # 30 minutes
    conflict_resolution: ConflictResolution = ConflictResolution.AUTO
    enable_auto_expansion: bool = True
    enable_fact_checking: bool = True
    citation_required: bool = False
    debug: bool = False

    # Provider configurations
    providers: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {
            "tavily": {"enabled": True, "api_key": None},
            "brave": {"enabled": True, "api_key": None},
            "github": {"enabled": True, "api_key": None},
            "wikipedia": {"enabled": True},
            "stackoverflow": {"enabled": True},
            "documentation": {"enabled": True},
            "news": {"enabled": True},
        }
    )

    def get_provider_config(self, provider_name: str) -> dict[str, Any]:
        """Get configuration for a specific provider."""
        return self.providers.get(provider_name, {})

    def set_provider_config(self, provider_name: str, config: dict[str, Any]) -> None:
        """Set configuration for a specific provider."""
        if provider_name in self.providers:
            self.providers[provider_name].update(config)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "default_mode": self.default_mode.value,
            "default_max_results": self.default_max_results,
            "cache_ttl": self.cache_ttl,
            "conflict_resolution": self.conflict_resolution.value,
            "enable_auto_expansion": self.enable_auto_expansion,
            "enable_fact_checking": self.enable_fact_checking,
            "citation_required": self.citation_required,
            "debug": self.debug,
            "providers": self.providers,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchConfig":
        """Create from dictionary."""
        default_mode = SearchMode(data.get("default_mode", "standard"))
        conflict_resolution = ConflictResolution(
            data.get("conflict_resolution", "auto")
        )

        config = cls(
            enabled=data.get("enabled", True),
            default_mode=default_mode,
            default_max_results=data.get("default_max_results", 10),
            cache_ttl=data.get("cache_ttl", 1800),
            conflict_resolution=conflict_resolution,
            enable_auto_expansion=data.get("enable_auto_expansion", True),
            enable_fact_checking=data.get("enable_fact_checking", True),
            citation_required=data.get("citation_required", False),
            debug=data.get("debug", False),
        )

        if "providers" in data:
            config.providers = data["providers"]

        return config
