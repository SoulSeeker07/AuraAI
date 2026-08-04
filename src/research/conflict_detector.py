"""
Conflict Detector

Detects and reports conflicts between evidence from different sources.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from .models import Evidence, SearchResult
from .evidence_merger import EvidenceMerger, EvidenceConflict

logger = logging.getLogger(__name__)


@dataclass
class SourceConflict:
    """Represents a conflict between sources."""
    conflict_type: str  # 'disagree', 'partial_overlap', 'confidence_loss'
    evidence1: str
    evidence1_source: str
    evidence1_url: str
    evidence2: str
    evidence2_source: str
    evidence2_url: str
    resolution: str  # 'use_evidence1', 'use_evidence2', 'need_human', 'merge'
    confidence: float  # 0-1, lower confidence indicates potential conflict


@dataclass
class ConflictReport:
    """Complete conflict report with all detected conflicts."""
    has_conflicts: bool
    conflicts: List[SourceConflict]
    resolution_strategy: str
    recommended_action: str
    confidence: float


class ConflictDetector:
    """
    Detects conflicts between evidence from different sources.
    
    When multiple sources provide information about the same topic,
    Aura should detect if they disagree and handle it appropriately.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize conflict detector.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.evidence_merger = EvidenceMerger(config)
        self.conflict_threshold = self.config.get('conflict_threshold', 0.3)

    def detect_conflicts(
        self,
        evidence_list: List[Evidence]
    ) -> List[SourceConflict]:
        """
        Detect conflicts between evidence sources.

        Args:
            evidence_list: List of evidence objects

        Returns:
            List of detected conflicts
        """
        conflicts = []

        if len(evidence_list) < 2:
            return conflicts

        logger.info(f"Detecting conflicts between {len(evidence_list)} evidence sources")

        # Detect conflicts using evidence merger
        detected_conflicts = self.evidence_merger.detect_conflicts(evidence_list)

        # Convert to SourceConflict objects
        for conflict in detected_conflicts:
            source_conflict = self._convert_to_source_conflict(conflict, evidence_list)
            if source_conflict:
                conflicts.append(source_conflict)

        logger.info(f"Detected {len(conflicts)} conflicts")

        return conflicts

    def _convert_to_source_conflict(
        self,
        conflict,
        evidence_list: List[Evidence]
    ) -> Optional[SourceConflict]:
        """
        Convert EvidenceConflict to SourceConflict.

        Args:
            conflict: EvidenceConflict object
            evidence_list: List of evidence objects

        Returns:
            SourceConflict object or None
        """
        # Find evidence objects by source name
        evidence1 = next((e for e in evidence_list if e.source == conflict.sources[0]), None)
        evidence2 = next((e for e in evidence_list if e.source == conflict.sources[1]), None)

        if not evidence1 or not evidence2:
            return None

        # Determine conflict type
        conflict_type = self._determine_conflict_type(conflict, evidence1, evidence2)

        # Determine resolution strategy
        resolution = self._determine_resolution(conflict, evidence1, evidence2)

        # Calculate confidence (lower for conflicts)
        confidence = 1.0 - (max(len(conflict.sources), 2) * 0.2)

        return SourceConflict(
            conflict_type=conflict_type,
            evidence1=conflict.fact,
            evidence1_source=conflict.sources[0],
            evidence1_url=conflict.source_urls[0],
            evidence2=conflict.fact,
            evidence2_source=conflict.sources[1],
            evidence2_url=conflict.source_urls[1],
            resolution=resolution,
            confidence=confidence
        )

    def _determine_conflict_type(
        self,
        conflict,
        evidence1: Evidence,
        evidence2: Evidence
    ) -> str:
        """
        Determine type of conflict.

        Args:
            conflict: Conflict object
            evidence1: First evidence object
            evidence2: Second evidence object

        Returns:
            Conflict type string
        """
        # Compare trust levels
        trust_levels = [evidence1.trust_level, evidence2.trust_level]
        high_trust = [t for t in trust_levels if t in ['official', 'government']]
        low_trust = [t for t in trust_levels if t not in ['official', 'government']]

        if high_trust and low_trust:
            return 'disagree'  # High-trust sources disagree

        if len(set(trust_levels)) > 1:
            return 'confidence_loss'  # Different trust levels

        return 'partial_overlap'  # Sources agree but slightly different

    def _determine_resolution(
        self,
        conflict,
        evidence1: Evidence,
        evidence2: Evidence
    ) -> str:
        """
        Determine resolution strategy for conflict.

        Args:
            conflict: Conflict object
            evidence1: First evidence object
            evidence2: Second evidence object

        Returns:
            Resolution strategy
        """
        trust_levels = [evidence1.trust_level, evidence2.trust_level]

        # Priority order: official > government > github > stackoverflow > wikipedia > reddit > blog
        trust_priority = {
            'official': 10,
            'government': 9,
            'github': 8,
            'stackoverflow': 7,
            'wikipedia': 6,
            'reddit': 5,
            'blog': 4,
            'unknown': 1
        }

        max_trust = max([trust_priority.get(t, 0) for t in trust_levels])
        max_sources = [t for t in trust_levels if trust_priority.get(t, 0) == max_trust]

        if len(max_sources) == 1:
            # Use the highest trust source
            return f'use_{max_sources[0]}'

        if len(max_sources) >= 2:
            # Multiple sources agree
            return 'merge'

        return 'need_human'

    def generate_report(
        self,
        conflicts: List[SourceConflict],
        query: str
    ) -> ConflictReport:
        """
        Generate a comprehensive conflict report.

        Args:
            conflicts: List of detected conflicts
            query: Original query

        Returns:
            Conflict report
        """
        if not conflicts:
            return ConflictReport(
                has_conflicts=False,
                conflicts=[],
                resolution_strategy='no_conflicts',
                recommended_action='Continue with normal response',
                confidence=1.0
            )

        # Determine overall resolution strategy
        resolution_strategy = self._determine_resolution_strategy(conflicts)
        recommended_action = self._determine_recommended_action(resolution_strategy)

        # Calculate overall confidence
        avg_confidence = sum(c.confidence for c in conflicts) / len(conflicts)

        return ConflictReport(
            has_conflicts=True,
            conflicts=conflicts,
            resolution_strategy=resolution_strategy,
            recommended_action=recommended_action,
            confidence=avg_confidence
        )

    def _determine_resolution_strategy(self, conflicts: List[SourceConflict]) -> str:
        """
        Determine overall resolution strategy.

        Args:
            conflicts: List of conflicts

        Returns:
            Resolution strategy string
        """
        # Count resolution types
        use_evidence1_count = sum(1 for c in conflicts if c.resolution.startswith('use_'))
        merge_count = sum(1 for c in conflicts if c.resolution == 'merge')
        need_human_count = sum(1 for c in conflicts if c.resolution == 'need_human')

        total = len(conflicts)

        if use_evidence1_count >= total * 0.7:
            return 'prefer_trusted_sources'
        elif merge_count >= total * 0.7:
            return 'merge_sources'
        elif need_human_count >= total * 0.5:
            return 'need_human_review'
        else:
            return 'weighted_merge'

    def _determine_recommended_action(self, resolution_strategy: str) -> str:
        """
        Determine recommended action based on resolution strategy.

        Args:
            resolution_strategy: Resolution strategy

        Returns:
            Recommended action string
        """
        strategies = {
            'prefer_trusted_sources': 'Use evidence from official/government sources. Note discrepancies in response.',
            'merge_sources': 'Combine information from all sources. Highlight where sources agree.',
            'need_human_review': 'Alert user to conflicting information. Recommend gathering more evidence.',
            'weighted_merge': 'Weight evidence by source trust. Note conflicts in confidence.'
        }

        return strategies.get(resolution_strategy, 'Continue with normal response')

    def get_confidence_adjustment(self, conflict_report: ConflictReport) -> float:
        """
        Get confidence adjustment factor based on conflicts.

        Args:
            conflict_report: Conflict report

        Returns:
            Confidence adjustment (0-1)
        """
        if not conflict_report.has_conflicts:
            return 1.0

        # Reduce confidence based on number of conflicts
        num_conflicts = len(conflict_report.conflicts)
        adjustment = max(0.3, 1.0 - (num_conflicts * 0.15))

        return adjustment

    def generate_conflict_message(self, conflict_report: ConflictReport, query: str) -> str:
        """
        Generate a human-readable conflict message.

        Args:
            conflict_report: Conflict report
            query: Original query

        Returns:
            Formatted conflict message
        """
        if not conflict_report.has_conflicts:
            return ""

        lines = [
            f"⚠️ **Conflict Detected** - Regarding '{query}'",
            "",
            f"**Resolution Strategy:** {conflict_report.resolution_strategy}",
            f"**Recommended Action:** {conflict_report.recommended_action}",
            f"**Overall Confidence:** {conflict_report.confidence * 100:.0f}%",
            ""
        ]

        if conflict_report.conflicts:
            lines.append("**Detected Conflicts:**")
            for i, conflict in enumerate(conflict_report.conflicts, 1):
                lines.append(f"\n{i}. **{conflict.conflict_type.upper()}**")
                lines.append(f"   - {conflict.evidence1[:100]}...")
                lines.append(f"   - Sources: {conflict.evidence1_source} and {conflict.evidence2_source}")
                lines.append(f"   - Suggested Resolution: {conflict.resolution}")

        lines.append("\n*Please review these conflicts when formulating your response.*")

        return "\n".join(lines)

    def should_research(
        self,
        conflict_report: ConflictReport,
        threshold: float = 0.6
    ) -> bool:
        """
        Determine if research should be performed based on conflicts.

        Args:
            conflict_report: Conflict report
            threshold: Confidence threshold

        Returns:
            True if research should be performed
        """
        if not conflict_report.has_conflicts:
            return False

        # If many conflicts, trigger deep research
        if len(conflict_report.conflicts) >= 2:
            return True

        # If confidence is low due to conflicts
        if conflict_report.confidence < threshold:
            return True

        return False
