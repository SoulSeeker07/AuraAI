"""
Research Reasoning Layer

This module provides the reasoning layer that evaluates evidence quality,
detects conflicts, calculates confidence, and identifies unanswered questions.

The reasoning layer sits between evidence extraction and the LLM.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import logging
import re
from .models import Evidence
from .citation_builder import Citation

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
    strong_evidence: List[Evidence] = field(default_factory=list)
    weak_evidence: List[Evidence] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    missing_information: List[str] = field(default_factory=list)
    confidence: float = 0.5
    recommendations: List[str] = field(default_factory=list)
    evidence_score_distribution: Dict[str, int] = field(default_factory=dict)
    
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
        "confirmed", "verified", "validated", "researched", 
        "evidence-based", "studies show", "data indicates",
        "official documentation", "reliable source"
    ]
    
    WEAK_QUALITY_KEYWORDS = [
        "likely", "probably", "seems", "appears", "potentially",
        "may be", "could be", "suggests", "indicates"
    ]
    
    UNCERTAINTY_KEYWORDS = [
        "unclear", "uncertain", "ambiguous", "conflicting",
        "debatable", "disputed", "inconsistent"
    ]
    
    # Confidence thresholds
    STRONG_CONFIDENCE_THRESHOLD = 0.85
    MODERATE_CONFIDENCE_THRESHOLD = 0.6
    WEAK_CONFIDENCE_THRESHOLD = 0.4
    
    def __init__(
        self,
        min_evidence_count: int = 3,
        confidence_update_threshold: float = 0.1
    ):
        """
        Initialize the research reasoner.
        
        Args:
            min_evidence_count: Minimum number of evidence items required
            confidence_update_threshold: Minimum change to update confidence
        """
        self.min_evidence_count = min_evidence_count
        self.confidence_update_threshold = confidence_update_threshold
        self.total_evaluations = 0
    
    def reason(self, evidence_list: List[Evidence], query: str) -> ReasoningResult:
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
        
        result = ReasoningResult()
        
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
        self._calculate_confidence(result)
        
        # Generate recommendations
        self._generate_recommendations(result)
        
        logger.info(
            f"Reasoning complete: {len(result.strong_evidence)} strong, "
            f"{len(result.weak_evidence)} weak, "
            f"confidence: {result.confidence:.2f}"
        )
        
        return result
    
    def _analyze_evidence(
        self,
        evidence: Evidence,
        query: str,
        result: ReasoningResult
    ):
        """
        Analyze a single evidence item.
        
        Args:
            evidence: Evidence to analyze
            query: Original query
            result: ReasoningResult to update
        """
        # Evaluate quality score
        quality_score = self._evaluate_quality(evidence)
        
        # Categorize as strong or weak
        if quality_score >= self.STRONG_CONFIDENCE_THRESHOLD:
            result.add_strong_evidence(evidence)
        else:
            result.add_weak_evidence(evidence)
        
        # Track score distribution
        score_category = self._score_to_category(quality_score)
        result.evidence_score_distribution[score_category] = \
            result.evidence_score_distribution.get(score_category, 0) + 1
    
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
            quality_score += 0.3
        
        # Check for uncertainty indicators
        if any(keyword in content_lower for keyword in self.UNCERTAINTY_KEYWORDS):
            quality_score -= 0.2
        
        # Check for weak indicators
        if any(keyword in content_lower for keyword in self.WEAK_QUALITY_KEYWORDS):
            quality_score -= 0.1
        
        # Adjust based on source type
        source_score = self._score_source(evidence.source)
        quality_score = (quality_score * 0.5) + (source_score * 0.5)
        
        return max(0.0, min(1.0, quality_score))
    
    def _score_source(self, source: str) -> float:
        """
        Score a source based on its reliability.
        
        Args:
            source: Source URL or identifier
            
        Returns:
            Source score (0.0-1.0)
        """
        source_lower = source.lower()
        
        # Highly reliable sources
        reliable_sources = [
            "gov", "edu", "org", "academic", "journal", "research",
            "documentation", "official", "white paper", "case study"
        ]
        
        for pattern in reliable_sources:
            if pattern in source_lower:
                return 1.0
        
        # Medium reliability
        if any(pattern in source_lower for pattern in ["news", "blog", "article"]):
            return 0.7
        
        # Low reliability
        return 0.5
    
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
        # Sort strong evidence by quality
        result.strong_evidence.sort(
            key=lambda e: self._evaluate_quality(e),
            reverse=True
        )
        
        # Sort weak evidence by quality
        result.weak_evidence.sort(
            key=lambda e: self._evaluate_quality(e),
            reverse=True
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
            r"contradict", "conflict", "oppose", "debate", "disagree",
            r"(\w+)\s+vs\s+(\w+)",  # Company vs Company
            r"(\w+)\s+versus\s+(\w+)",
            r"(\w+)\s+vs\.?\s+(\w+)"
        ]
        
        for pattern in conflict_patterns:
            matches = re.findall(pattern, all_text, re.IGNORECASE)
            for match in matches:
                if len(match) >= 2:
                    result.add_conflict(f"Potential conflict between {match[0]} and {match[1]}")
    
    def _identify_missing_information(
        self,
        result: ReasoningResult,
        query: str
    ):
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
            ("customer", "user", "feedback", "reviews")
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
            return
        
        # Weighted score based on evidence categories
        strong_weight = len(result.strong_evidence) / max(1, len(result.strong_evidence) + len(result.weak_evidence))
        weak_weight = len(result.weak_evidence) / max(1, len(result.strong_evidence) + len(result.weak_evidence))
        
        base_confidence = (
            strong_weight * 0.8 +  # Strong evidence = 0.8 confidence
            weak_weight * 0.5      # Weak evidence = 0.5 confidence
        )
        
        # Adjust based on conflicts
        if result.conflicts:
            base_confidence -= 0.1 * len(result.conflicts)
        
        # Minimum confidence
        result.confidence = max(0.0, min(1.0, base_confidence))
    
    def _generate_recommendations(self, result: ReasoningResult):
        """
        Generate actionable recommendations.
        
        Args:
            result: ReasoningResult to update
        """
        # Add recommendation if low confidence
        if result.confidence < self.STRONG_CONFIDENCE_THRESHOLD:
            result.add_recommendation(
                "Consider additional research to increase confidence above 85%"
            )
        
        # Add recommendation for missing information
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
