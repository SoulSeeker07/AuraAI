"""
Evidence Merger

Merges similar facts from different evidence sources into unified evidence.
"""

import logging
from typing import List, Dict, Any, Set, Tuple, Optional
from dataclasses import dataclass

from .models import Evidence

logger = logging.getLogger(__name__)


@dataclass
class EvidenceConflict:
    """Represents a conflict between evidence from different sources."""
    fact: str
    sources: List[str]
    source_urls: List[str]
    confidence: float
    trust_levels: List[str]


class EvidenceMerger:
    """
    Merges similar facts from different evidence sources.
    
    Instead of treating Provider A, Provider B, Provider C as separate
    evidence objects, they merge into one evidence object with multiple
    supporting sources.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize evidence merger.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.merge_threshold = self.config.get('merge_threshold', 0.75)  # 75% similarity
        self.max_evidence_objects = self.config.get('max_evidence_objects', 10)
        self.conflict_threshold = self.config.get('conflict_threshold', 0.3)  # Low confidence indicates potential conflict

    def merge_evidence(self, evidence_list: List[Evidence]) -> List[Evidence]:
        """
        Merge evidence from multiple sources.

        Args:
            evidence_list: List of evidence objects

        Returns:
            List of merged evidence objects
        """
        if not evidence_list:
            return []

        logger.info(f"Merging {len(evidence_list)} evidence objects into {self.max_evidence_objects} or fewer")

        # Group similar facts within same evidence objects
        groups = self._group_similar_facts(evidence_list)

        # Merge facts within each group
        merged_evidence = self._merge_fact_groups(groups)

        # Reduce to max_evidence_objects
        merged_evidence = merged_evidence[:self.max_evidence_objects]

        logger.info(f"Merged to {len(merged_evidence)} evidence objects")
        return merged_evidence

    def _group_similar_facts(self, evidence_list: List[Evidence]) -> List[List[Evidence]]:
        """
        Group evidence objects with similar facts.

        Args:
            evidence_list: List of evidence objects

        Returns:
            List of groups (each group is a list of evidence objects)
        """
        # Find pairs of evidence with overlapping facts
        overlapping_groups = []

        for i, evidence1 in enumerate(evidence_list):
            group = [evidence1]

            for evidence2 in evidence_list[i+1:]:
                if self._evidence_overlap(evidence1, evidence2):
                    group.append(evidence2)

            if len(group) > 1:
                overlapping_groups.append(group)

        return overlapping_groups

    def _evidence_overlap(self, evidence1: Evidence, evidence2: Evidence) -> bool:
        """
        Check if two evidence objects have overlapping facts.

        Args:
            evidence1: First evidence object
            evidence2: Second evidence object

        Returns:
            True if they overlap
        """
        if not evidence1.facts or not evidence2.facts:
            return False

        # Check if any fact from evidence1 appears in evidence2
        facts1_lower = {fact.lower() for fact in evidence1.facts}
        facts2_lower = {fact.lower() for fact in evidence2.facts}

        # Check for overlapping text
        for fact1 in facts1_lower:
            for fact2 in facts2_lower:
                if self._are_facts_similar(fact1, fact2):
                    return True

        return False

    def _are_facts_similar(self, fact1: str, fact2: str) -> bool:
        """
        Check if two facts are similar.

        Args:
            fact1: First fact
            fact2: Second fact

        Returns:
            True if facts are similar
        """
        # Simple string similarity
        text1 = fact1.lower()
        text2 = fact2.lower()

        # Check for overlapping terms
        terms1 = set(text1.split())
        terms2 = set(text2.split())

        overlap = len(terms1 & terms2)
        total = len(terms1 | terms2)

        # Similarity threshold
        return overlap / total > self.merge_threshold if total > 0 else False

    def _merge_fact_groups(self, groups: List[List[Evidence]]) -> List[Evidence]:
        """
        Merge facts within each group into a single evidence object.

        Args:
            groups: List of groups of evidence objects

        Returns:
            List of merged evidence objects
        """
        merged = []

        for group in groups:
            # Merge all facts from group into one evidence object
            merged_evidence = self._merge_evidence_group(group)

            if merged_evidence:
                merged.append(merged_evidence)

        return merged

    def _merge_evidence_group(self, group: List[Evidence]) -> Evidence:
        """
        Merge a group of evidence objects into one.

        Args:
            group: List of evidence objects to merge

        Returns:
            Merged evidence object
        """
        if not group:
            return None

        # Get all facts from all evidence objects
        all_facts = []
        all_sources = []
        all_urls = []
        all_trust_levels = []

        for evidence in group:
            all_facts.extend(evidence.facts)
            all_sources.extend([evidence.source] * len(evidence.facts))
            all_urls.extend([evidence.url] * len(evidence.facts))
            all_trust_levels.extend([evidence.trust_level] * len(evidence.facts))

        # Remove duplicates
        unique_facts = self._remove_duplicate_facts(all_facts)

        # Score facts and rank
        scored_facts = self._score_and_rank_facts(unique_facts, group)

        # Calculate overall confidence
        confidence = self._calculate_group_confidence(scored_facts, all_trust_levels)

        # Determine merged source
        primary_source = self._determine_primary_source(all_trust_levels)

        # Determine merged trust level
        merged_trust_level = self._determine_merged_trust_level(all_trust_levels)

        # Create merged evidence
        merged_evidence = Evidence(
            query=group[0].query,
            source=primary_source,
            url=group[0].url,
            facts=[fact.text for fact in scored_facts],
            trust_level=merged_trust_level,
            tags=group[0].tags,
            timestamp=None
        )

        return merged_evidence

    def _remove_duplicate_facts(self, facts: List[str]) -> List[str]:
        """
        Remove duplicate facts.

        Args:
            facts: List of facts

        Returns:
            List of unique facts
        """
        unique_facts = []

        for fact in facts:
            # Check if similar fact already exists
            is_duplicate = False
            for existing in unique_facts:
                if self._are_facts_similar(fact, existing):
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_facts.append(fact)

        return unique_facts

    def _score_and_rank_facts(self, facts: List[str], group: List[Evidence]) -> List[Any]:
        """
        Score and rank facts within a group.

        Args:
            facts: List of facts to score
            group: Evidence group context

        Returns:
            List of scored facts (with confidence scores)
        """
        scored_facts = []

        for fact in facts:
            # Calculate score based on source quality and content
            score = self._calculate_fact_score(fact, group)

            # Check for conflicts
            is_conflicting = self._check_for_conflicts(fact, group)

            if is_conflicting:
                score = max(score - 0.3, 0)  # Reduce confidence for conflicts

            scored_facts.append({
                'text': fact,
                'confidence': score,
                'is_conflicting': is_conflicting
            })

        # Sort by confidence (descending)
        scored_facts.sort(key=lambda x: x['confidence'], reverse=True)

        return scored_facts

    def _calculate_fact_score(self, fact: str, group: List[Evidence]) -> float:
        """
        Calculate score for a fact.

        Args:
            fact: Fact to score
            group: Evidence group

        Returns:
            Score (0-1)
        """
        score = 0.5  # Base score

        # Count trust levels
        trust_counts = {}
        for evidence in group:
            trust_counts[evidence.trust_level] = trust_counts.get(evidence.trust_level, 0) + 1

        # Boost for multiple sources
        if len(group) > 1:
            score += 0.15

        # Boost for multiple trusted sources
        trusted_count = 0
        for trust_level, count in trust_counts.items():
            if trust_level in ['official', 'government', 'github']:
                trusted_count += count

        if trusted_count > 1:
            score += 0.15

        # Boost for high-trust sources
        max_trust_score = max(trust_counts.values()) if trust_counts else 0
        score += max_trust_score / len(group) * 0.1

        return min(score, 1.0)

    def _check_for_conflicts(self, fact: str, group: List[Evidence]) -> bool:
        """
        Check if fact might be in conflict with other sources.

        Args:
            fact: Fact to check
            group: Evidence group

        Returns:
            True if conflict detected
        """
        if not group:
            return False

        # Get trust levels of all sources
        trust_levels = [evidence.trust_level for evidence in group]

        # If we have sources with very different trust levels
        trusted = [level for level in trust_levels if level in ['official', 'government']]
        non_trusted = [level for level in trust_levels if level not in ['official', 'government']]

        if trusted and non_trusted:
            # Potential conflict between high-trust and low-trust sources
            return True

        return False

    def _calculate_group_confidence(self, scored_facts: List[Any], trust_levels: List[str]) -> float:
        """
        Calculate overall confidence for a merged evidence group.

        Args:
            scored_facts: Scored facts
            trust_levels: Trust levels of all sources

        Returns:
            Confidence score (0-1)
        """
        if not scored_facts:
            return 0.0

        # Average of top facts
        top_facts = scored_facts[:5]
        avg_confidence = sum(fact['confidence'] for fact in top_facts) / len(top_facts)

        # Adjust based on trust level diversity
        if len(set(trust_levels)) > 3:
            avg_confidence *= 0.9  # Less confidence with diverse sources

        return avg_confidence

    def _determine_primary_source(self, trust_levels: List[str]) -> str:
        """
        Determine primary source for merged evidence.

        Args:
            trust_levels: List of trust levels

        Returns:
            Primary source name
        """
        # Count by trust level
        counts = {}
        for level in trust_levels:
            counts[level] = counts.get(level, 0) + 1

        # Return most frequent high-trust level
        for level in ['official', 'government', 'github']:
            if level in counts and counts[level] >= 2:
                return level

        # Fall back to most frequent
        return max(counts, key=counts.get) if counts else 'unknown'

    def _determine_merged_trust_level(self, trust_levels: List[str]) -> str:
        """
        Determine merged trust level for evidence.

        Args:
            trust_levels: List of trust levels

        Returns:
            Merged trust level
        """
        if not trust_levels:
            return 'unknown'

        # Count by trust level
        counts = {}
        for level in trust_levels:
            counts[level] = counts.get(level, 0) + 1

        # Return highest trust level
        for level in ['official', 'government', 'github', 'stackoverflow', 'wikipedia']:
            if level in counts:
                return level

        # Fall back to most frequent
        return max(counts, key=counts.get)

    def detect_conflicts(self, evidence_list: List[Evidence]) -> List[EvidenceConflict]:
        """
        Detect conflicts between evidence from different sources.

        Args:
            evidence_list: List of evidence objects

        Returns:
            List of detected conflicts
        """
        conflicts = []

        # Find pairs of evidence with conflicting facts
        for i in range(len(evidence_list)):
            for j in range(i + 1, len(evidence_list)):
                conflict = self._detect_conflict_between_evidence(
                    evidence_list[i],
                    evidence_list[j]
                )

                if conflict:
                    conflicts.append(conflict)

        return conflicts

    def _detect_conflict_between_evidence(
        self,
        evidence1: Evidence,
        evidence2: Evidence
    ) -> Optional[EvidenceConflict]:
        """
        Detect conflict between two evidence objects.

        Args:
            evidence1: First evidence object
            evidence2: Second evidence object

        Returns:
            Conflict object or None
        """
        if not evidence1.facts or not evidence2.facts:
            return None

        # Get unique facts from each
        facts1 = set(fact.lower() for fact in evidence1.facts)
        facts2 = set(fact.lower() for fact in evidence2.facts)

        # Find overlapping facts
        overlaps = []
        for fact1 in facts1:
            for fact2 in facts2:
                if self._are_facts_similar(fact1, fact2):
                    overlaps.append((fact1, fact2))

        if not overlaps:
            return None

        # Get actual fact texts with case preserved
        fact_texts = []
        for fact1, fact2 in overlaps:
            # Find matching fact in evidence1
            for fact in evidence1.facts:
                if fact.lower() == fact1:
                    fact_texts.append(fact)
                    break

        # Get unique fact texts
        unique_facts = list(set(fact_texts))

        if len(unique_facts) < 2:
            return None

        # Create conflict object
        return EvidenceConflict(
            fact=", ".join(unique_facts[:3]),  # Max 3 facts per conflict
            sources=[evidence1.source, evidence2.source],
            source_urls=[evidence1.url, evidence2.url],
            confidence=0.5,  # Default confidence
            trust_levels=[evidence1.trust_level, evidence2.trust_level]
        )
