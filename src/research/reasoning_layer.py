"""
Research Reasoning Layer

This module provides the reasoning layer that evaluates evidence quality,
detects conflicts, calculates confidence, and identifies unanswered questions.

The reasoning layer sits between evidence extraction and the LLM.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime

from .metrics import MetricsCollector
from .models import Evidence, normalize_trust_level

logger = logging.getLogger(__name__)


@dataclass
class ReasoningResult:
    """
    Result of the research reasoning process.

    Attributes:
        strong_evidence: High-quality evidence with strong supporting claims
        weak_evidence: Lower-quality evidence that may be marginally useful
        conflicts: List of conflicting evidence or claims
        missing_information: Questions or aspects that couldn't be answered
        confidence: Overall confidence score (0.0-1.0)
        recommendations: Actionable recommendations for further research
        evidence_score_distribution: Distribution of evidence scores
    """

    strong_evidence: list[Evidence] = field(default_factory=list)
    weak_evidence: list[Evidence] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    confidence: float = 0.5
    recommendations: list[str] = field(default_factory=list)
    evidence_score_distribution: dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        """Post-initialization setup."""
        if not self.evidence_score_distribution:
            self.evidence_score_distribution = {}

    def add_strong_evidence(self, evidence: Evidence):
        """Add strong evidence."""
        self.strong_evidence.append(evidence)

    def add_weak_evidence(self, evidence: Evidence):
        """Add weak evidence."""
        self.weak_evidence.append(evidence)

    def add_conflict(self, conflict: str):
        """Add a conflict."""
        self.conflicts.append(conflict)

    def add_missing_information(self, question: str):
        """Add unanswered question."""
        self.missing_information.append(question)

    def add_recommendation(self, recommendation: str):
        """Add a recommendation."""
        self.recommendations.append(recommendation)


class ResearchReasoner:
    """
    Research Reasoning Layer

    Responsibilities:
    - Rank evidence quality (strong vs weak)
    - Detect unsupported claims
    - Detect conflicts between evidence
    - Calculate overall confidence
    - Identify unanswered questions
    - Recommend additional searches

    The reasoner evaluates all evidence and categorizes it into:
    - Strong evidence: High-quality, well-supported claims
    - Weak evidence: Lower-quality but potentially useful information
    - Conflicts: Contradictory information
    - Missing information: Aspects not covered
    """

    # Evidence quality indicators
    STRONG_QUALITY_KEYWORDS = [
        "confirmed",
        "verified",
        "validated",
        "researched",
        "evidence-based",
        "studies show",
        "data indicates",
        "official documentation",
        "reliable source",
    ]

    WEAK_QUALITY_KEYWORDS = [
        "likely",
        "probably",
        "seems",
        "appears",
        "potentially",
        "may be",
        "could be",
        "suggests",
        "indicates",
    ]

    UNCERTAINTY_KEYWORDS = [
        "unclear",
        "uncertain",
        "ambiguous",
        "conflicting",
        "debatable",
        "disputed",
        "inconsistent",
    ]

    # Confidence thresholds
    STRONG_CONFIDENCE_THRESHOLD = 0.70  # Temporarily lowered to 0.70 for testing
    MODERATE_CONFIDENCE_THRESHOLD = 0.5
    WEAK_CONFIDENCE_THRESHOLD = 0.3

    def __init__(
        self,
        min_evidence_count: int = 3,
        confidence_update_threshold: float = 0.1,
        debug: bool = False,
    ):
        """
        Initialize the research reasoner.

        Args:
            min_evidence_count: Minimum number of evidence items required
            confidence_update_threshold: Minimum change to update confidence
            debug: Enable detailed runtime diagnostics
        """
        self.min_evidence_count = min_evidence_count
        self.confidence_update_threshold = confidence_update_threshold
        self.total_evaluations = 0
        self.debug = debug

    def reason(self, evidence_list: list[Evidence], query: str) -> ReasoningResult:
        """
        Evaluate all evidence and produce a reasoned result.

        Args:
            evidence_list: List of Evidence objects
            query: Original research query

        Returns:
            ReasoningResult with categorized evidence and confidence
        """
        logger.info(f"Starting reasoning on {len(evidence_list)} evidence items")
        self.total_evaluations += len(evidence_list)

        # Collect metrics
        metrics_collector = MetricsCollector(query=query)

        result = ReasoningResult()

        # Start timing
        metrics_collector.start_timer("reasoning")

        # Analyze each evidence item
        for evidence in evidence_list:
            self._analyze_evidence(evidence, query, result)

        # Rank evidence quality
        self._rank_evidence(result)

        # Detect conflicts
        self._detect_conflicts(result)

        # Identify missing information
        self._identify_missing_information(result, query)

        # Calculate confidence
        metrics_collector.start_timer("confidence")
        self._calculate_confidence(result)
        metrics_collector.record_confidence(result.confidence)
        metrics_collector.stop_timer("confidence")

        # Generate recommendations
        # TODO (Milestone 14): Replace fallback with full recommendation engine.
        # Currently using logic from _calculate_confidence. Should refactor
        # recommendation logic into a separate recommendation engine module.
        if hasattr(self, "_generate_recommendations"):
            self._generate_recommendations(result)
        else:
            # Stub for when recommendations aren't fully implemented
            logger.debug("Recommendation generation not yet implemented")

        # Record metrics
        metrics_collector.evidence_count = len(evidence_list)
        metrics_collector.strong_count = len(result.strong_evidence)
        metrics_collector.weak_count = len(result.weak_evidence)
        metrics_collector.conflicts = len(result.conflicts)
        metrics_collector.missing_information = result.missing_information

        metrics_collector.stop_timer("reasoning")

        logger.info(
            f"Reasoning complete: {len(result.strong_evidence)} strong, "
            f"{len(result.weak_evidence)} weak, "
            f"confidence: {result.confidence:.2f}"
        )

        return result

    def _analyze_evidence(
        self, evidence: Evidence, query: str, result: ReasoningResult
    ):
        """
        Analyze a single evidence item.

        Args:
            evidence: Evidence to analyze
            query: Original query
            result: ReasoningResult to update
        """
        # Evaluate quality score with all components
        quality_score, components = self._evaluate_quality_detailed(evidence)

        # Categorize as strong or weak
        if quality_score >= self.STRONG_CONFIDENCE_THRESHOLD:
            result.add_strong_evidence(evidence)
        else:
            result.add_weak_evidence(evidence)

        # Track score distribution
        score_category = self._score_to_category(quality_score)
        result.evidence_score_distribution[score_category] = (
            result.evidence_score_distribution.get(score_category, 0) + 1
        )

        # Log detailed evaluation if debug mode is enabled
        if self.debug:
            self._log_evidence_evaluation(evidence, quality_score, components)

    def _evaluate_quality(self, evidence: Evidence) -> float:
        """
        Evaluate the quality of evidence.

        Quality is determined by:
        - Source reliability
        - Content certainty
        - Relevance to query
        - Recency

        Args:
            evidence: Evidence to evaluate

        Returns:
            Quality score (0.0-1.0)
        """
        quality_score = 0.5  # Base score

        # Check for strong indicators
        content_lower = evidence.fact.lower()

        if any(keyword in content_lower for keyword in self.STRONG_QUALITY_KEYWORDS):
            quality_score += 0.25

        # Check for uncertainty indicators
        if any(keyword in content_lower for keyword in self.UNCERTAINTY_KEYWORDS):
            quality_score -= 0.2

        # Check for weak indicators
        if any(keyword in content_lower for keyword in self.WEAK_QUALITY_KEYWORDS):
            quality_score -= 0.1

        # Adjust based on source trust level first
        trust_level = normalize_trust_level(evidence.trust_level)
        trust_score = self._score_source(trust_level, evidence.source)
        trust_bonus = {
            "official": 0.3,
            "government": 0.28,
            "github": 0.22,
            "stackoverflow": 0.18,
            "wikipedia": 0.15,
            "reddit": 0.1,
            "blog": 0.08,
            "unknown": 0.0,
        }.get(trust_level, 0.0)
        quality_score = min(1.0, quality_score + trust_bonus)

        # Combine with normalized trust score
        quality_score = (quality_score * 0.6) + (trust_score * 0.4)

        return max(0.0, min(1.0, quality_score))

    def _score_source(self, trust_level: str, source: str) -> float:
        """
        Score a source based on trust level and reliability.

        Args:
            trust_level: Normalized trust level string
            source: Source URL or identifier

        Returns:
            Source score (0.0-1.0)
        """
        # Trust-based score has primary weight
        trust_scores = {
            "official": 1.0,
            "government": 0.95,
            "github": 0.85,
            "stackoverflow": 0.8,
            "wikipedia": 0.75,
            "news": 0.65,
            "reddit": 0.6,
            "blog": 0.55,
            "unknown": 0.5,
        }
        if trust_level in trust_scores:
            return trust_scores[trust_level]

        source_lower = source.lower()

        # Fallback reliability scoring based on source string
        reliable_sources = [
            "gov",
            "edu",
            "org",
            "academic",
            "journal",
            "research",
            "documentation",
            "official",
            "white paper",
            "case study",
        ]

        for pattern in reliable_sources:
            if pattern in source_lower:
                return 0.9

        # Medium reliability
        if any(pattern in source_lower for pattern in ["news", "blog", "article"]):
            return 0.7

        # Low reliability
        return 0.5

    def _score_freshness(
        self, retrieved_at: datetime | None, published_at: datetime | None
    ) -> float:
        """
        Score evidence freshness based on timestamps.

        Args:
            retrieved_at: When the evidence was retrieved
            published_at: When the source content was published

        Returns:
            Freshness score (0.0-1.0), where 1.0 is most recent
        """
        # If no timestamps available, return neutral score
        if retrieved_at is None and published_at is None:
            return 0.5  # Neutral

        # Use retrieved_at as primary metric
        if retrieved_at is not None:
            now = (
                datetime.now(retrieved_at.tzinfo)
                if retrieved_at.tzinfo
                else datetime.now()
            )
            time_diff = (now - retrieved_at).total_seconds()

            # Score: 1.0 for very recent (< 1 hour), decays over 24 hours
            if time_diff < 3600:  # Less than 1 hour
                return 1.0
            elif time_diff < 86400:  # Less than 24 hours
                return 1.0 - (time_diff - 3600) / (86400 - 3600) * 0.5
            elif time_diff < 604800:  # Less than 7 days
                return 0.5 - (time_diff - 86400) / (604800 - 86400) * 0.4
            else:  # Older than 7 days
                return 0.1

        # Fallback to published_at if retrieved_at is None
        if published_at is not None:
            now = (
                datetime.now(published_at.tzinfo)
                if published_at.tzinfo
                else datetime.now()
            )
            time_diff = (now - published_at).total_seconds()

            # Use published_at as secondary metric (slower decay)
            if time_diff < 86400:  # Less than 24 hours
                return 1.0
            elif time_diff < 604800:  # Less than 7 days
                return 0.8
            elif time_diff < 2592000:  # Less than 30 days
                return 0.6
            else:  # Older than 30 days
                return 0.3

        return 0.5

    def _evaluate_quality_detailed(self, evidence: Evidence) -> tuple[float, dict]:
        """
        Evaluate evidence quality with detailed component breakdown.

        Returns:
            Tuple of (quality_score, components_dict)
        """
        components = {
            "base_score": 0.5,
            "trust_bonus": 0.0,
            "keyword_bonus": 0.0,
            "freshness_bonus": 0.0,
            "agreement_bonus": 0.0,
            "final_score": 0.0,
        }

        # Base score
        base_score = 0.5
        components["base_score"] = base_score

        # Check for strong indicators
        content_lower = evidence.fact.lower()
        strong_keyword_bonus = 0.0
        weak_keyword_penalty = 0.0
        uncertainty_penalty = 0.0

        if any(keyword in content_lower for keyword in self.STRONG_QUALITY_KEYWORDS):
            strong_keyword_bonus = 0.25

        if any(keyword in content_lower for keyword in self.UNCERTAINTY_KEYWORDS):
            uncertainty_penalty = 0.2

        if any(keyword in content_lower for keyword in self.WEAK_QUALITY_KEYWORDS):
            weak_keyword_penalty = 0.1

        components["keyword_bonus"] = strong_keyword_bonus
        components["uncertainty_penalty"] = uncertainty_penalty
        components["weak_penalty"] = weak_keyword_penalty

        # Adjust based on source trust level
        trust_level = normalize_trust_level(evidence.trust_level)
        trust_bonus = {
            "official": 0.3,
            "government": 0.28,
            "github": 0.22,
            "stackoverflow": 0.18,
            "wikipedia": 0.15,
            "reddit": 0.1,
            "blog": 0.08,
            "unknown": 0.0,
        }.get(trust_level, 0.0)

        components["trust_bonus"] = trust_bonus

        # Calculate normalized trust score
        trust_score = self._score_source(trust_level, evidence.source)
        components["trust_score"] = trust_score

        # Calculate freshness bonus using timestamp metadata (Milestone 14 requirement)
        # TODO (Milestone 14): Eventually use published_at when available
        freshness_bonus = (
            self._score_freshness(evidence.retrieved_at, evidence.published_at) * 0.1
        )
        components["freshness_bonus"] = freshness_bonus

        # Calculate final score
        final_score = max(
            0.0,
            min(1.0, base_score + trust_bonus + strong_keyword_bonus + freshness_bonus),
        )
        components["final_score"] = final_score

        return final_score, components

    def _log_evidence_evaluation(
        self, evidence: Evidence, quality_score: float, components: dict
    ):
        """
        Log detailed evidence evaluation.

        Args:
            evidence: Evidence that was evaluated
            quality_score: Final quality score
            components: Dictionary of scoring components
        """

        lines = [
            "========== Evidence Evaluation ==========",
            f"Source          : {evidence.source}",
            f"Trust           : {evidence.trust_level.value if hasattr(evidence.trust_level, 'value') else evidence.trust_level}",
            f"Trust Bonus     : +{components['trust_bonus']:.2f}",
            f"Keyword Bonus   : +{components['keyword_bonus']:.2f}",
            f"Uncertainty Pen : {components['uncertainty_penalty']:.2f}",
            f"Weak Penalty    : {components['weak_penalty']:.2f}",
            f"Freshness Bonus : +{components['freshness_bonus']:.2f}",
            f"Final Score     : {components['final_score']:.2f}",
            f"Classification  : {'STRONG' if quality_score >= self.STRONG_CONFIDENCE_THRESHOLD else 'WEAK'}",
            "=========================================",
        ]

        logger.info("\n" + "\n".join(lines))

    def _score_recency(self, timestamp) -> float:
        """
        Score evidence based on recency.

        Args:
            timestamp: Evidence timestamp

        Returns:
            Recency score (0.0-1.0)
        """
        if timestamp is None:
            return 0.5  # No timestamp = neutral

        from datetime import datetime

        # If timestamp is a datetime object
        if isinstance(timestamp, datetime):
            age = datetime.now() - timestamp
        else:
            # Assume it's a timestamp (could be seconds since epoch)
            age_seconds = datetime.now().timestamp() - float(timestamp)
            age = age_seconds

        # Age in days
        age_days = age.total_seconds() / (24 * 60 * 60)

        # Prefer recent evidence (within last year)
        if age_days < 30:  # Within a month
            return 0.9
        elif age_days < 365:  # Within a year
            return 0.7
        elif age_days < 730:  # Within 2 years
            return 0.5
        else:  # Older than 2 years
            return 0.3

    def _score_to_category(self, score: float) -> str:
        """Convert score to category name."""
        if score >= self.STRONG_CONFIDENCE_THRESHOLD:
            return "strong"
        elif score >= self.MODERATE_CONFIDENCE_THRESHOLD:
            return "moderate"
        else:
            return "weak"

    def _rank_evidence(self, result: ReasoningResult):
        """
        Rank evidence within categories.

        Args:
            result: ReasoningResult to update
        """
        # Sort strong evidence by quality using detailed evaluation
        result.strong_evidence.sort(
            key=lambda e: self._evaluate_quality_detailed(e)[0], reverse=True
        )

        # Sort weak evidence by quality using detailed evaluation
        result.weak_evidence.sort(
            key=lambda e: self._evaluate_quality_detailed(e)[0], reverse=True
        )

    def _detect_conflicts(self, result: ReasoningResult):
        """
        Detect conflicts in evidence.

        A conflict occurs when:
        - Two sources make contradictory claims about the same fact
        - Evidence contains explicit uncertainty or debate indicators

        Args:
            result: ReasoningResult to update
        """
        # Combine all evidence text
        all_text = ""
        for evidence in result.strong_evidence + result.weak_evidence:
            all_text += evidence.fact.lower() + " "

        # Look for explicit conflict keywords
        conflict_patterns = [
            r"contradict",
            "conflict",
            "oppose",
            "debate",
            "disagree",
            r"(\w+)\s+vs\s+(\w+)",  # Company vs Company
            r"(\w+)\s+versus\s+(\w+)",
            r"(\w+)\s+vs\.?\s+(\w+)",
        ]

        for pattern in conflict_patterns:
            matches = re.findall(pattern, all_text, re.IGNORECASE)
            for match in matches:
                if len(match) >= 2:
                    result.add_conflict(
                        f"Potential conflict between {match[0]} and {match[1]}"
                    )

    def _identify_missing_information(self, result: ReasoningResult, query: str):
        """
        Identify missing information.

        Args:
            result: ReasoningResult to update
            query: Original query
        """
        # Extract key entities and concepts from query
        query_lower = query.lower()

        # Simple heuristics for missing information
        missing_patterns = [
            ("recent", "current", "latest", "2026"),
            ("price", "cost", "price tag"),
            ("performance", "benchmark", "test results"),
            ("comparison", "vs", "versus"),
            ("customer", "user", "feedback", "reviews"),
        ]

        # Check if certain information types are mentioned
        for pattern_tuple in missing_patterns:
            # pattern_tuple contains multiple keywords that could indicate missing information
            for pattern in pattern_tuple:
                if pattern not in query_lower:
                    # Don't add if query doesn't ask for it
                    continue

            # Check if evidence mentions this type
            has_mention = False
            for evidence in result.strong_evidence + result.weak_evidence:
                if pattern in evidence.fact.lower():
                    has_mention = True
                    break

            if not has_mention:
                result.add_missing_information(f"Information about {pattern}")

    def _calculate_confidence(self, result: ReasoningResult):
        """
        Calculate overall confidence score.

        Confidence is based on:
        - Number of strong evidence items
        - Quality of sources
        - Absence of conflicts
        - Completeness of information

        Args:
            result: ReasoningResult to update
        """
        if not result.strong_evidence and not result.weak_evidence:
            result.confidence = 0.0

            # Log empty result
            if self.debug:
                logger.info(
                    "\n"
                    "========== Confidence ==========\n"
                    "Strong Evidence : 0\n"
                    "Weak Evidence   : 0\n"
                    "Conflicts       : 0\n"
                    "Base Score      : 0.00\n"
                    "Final Confidence: 0.00\n"
                    "================================"
                )
            return

        # Weighted score based on evidence categories
        strong_weight = len(result.strong_evidence) / max(
            1, len(result.strong_evidence) + len(result.weak_evidence)
        )
        weak_weight = len(result.weak_evidence) / max(
            1, len(result.strong_evidence) + len(result.weak_evidence)
        )

        base_confidence = (
            strong_weight * 0.8  # Strong evidence = 0.8 confidence
            + weak_weight * 0.5  # Weak evidence = 0.5 confidence
        )

        # Adjust based on conflicts
        conflict_penalty = 0.0
        if result.conflicts:
            conflict_penalty = 0.1 * len(result.conflicts)
            base_confidence -= conflict_penalty

        # Minimum confidence
        final_confidence = max(0.0, min(1.0, base_confidence))
        result.confidence = final_confidence

        # Log detailed confidence calculation if debug mode is enabled
        if self.debug:
            logger.info(
                "\n"
                "========== Confidence ==========\n"
                f"Strong Evidence : {len(result.strong_evidence)}\n"
                f"Weak Evidence   : {len(result.weak_evidence)}\n"
                f"Conflicts       : {len(result.conflicts)}\n"
                f"Base Score      : {base_confidence:.2f}\n"
                f"Conflict Penalty: -{conflict_penalty:.2f}\n"
                f"Final Confidence: {final_confidence:.2f}\n"
                f"Threshold       : {self.STRONG_CONFIDENCE_THRESHOLD:.2f}\n"
                "================================"
            )
        if result.missing_information:
            result.add_recommendation(
                "Research missing information to improve completeness"
            )

        # Add recommendation for conflicting evidence
        if result.conflicts:
            result.add_recommendation(
                "Resolve conflicting evidence by finding primary sources"
            )

        # Add recommendation if insufficient evidence
        total_evidence = len(result.strong_evidence) + len(result.weak_evidence)
        if total_evidence < self.min_evidence_count:
            result.add_recommendation(
                f"Need at least {self.min_evidence_count} evidence items for reliable results"
            )

        # Add recommendation for verification
        if result.confidence < self.MODERATE_CONFIDENCE_THRESHOLD:
            result.add_recommendation(
                "Verify findings through multiple reliable sources"
            )
