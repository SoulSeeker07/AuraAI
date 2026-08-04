"""
Evidence Extractor

Extracts verifiable facts from research results into structured Evidence objects.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .models import SearchResult, Evidence

logger = logging.getLogger(__name__)


@dataclass
class ExtractedFact:
    """A single fact extracted from source text."""
    text: str
    confidence: float  # 0-1, based on relevance and source quality
    source: str  # Provider name
    source_url: str
    trust_level: str


class EvidenceExtractor:
    """
    Extracts evidence (verified facts) from research results.
    
    Converts raw search results into structured Evidence objects with
    verifiable facts, confidence scores, and citations.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize evidence extractor.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.max_facts_per_source = self.config.get('max_facts_per_source', 10)
        self.min_fact_length = self.config.get('min_fact_length', 20)
        self.max_fact_length = self.config.get('max_fact_length', 200)

    def extract_evidence(self, results: List[SearchResult], query: str) -> List[Evidence]:
        """
        Extract evidence from search results.

        Args:
            results: List of search results
            query: Original query for context

        Returns:
            List of Evidence objects
        """
        if not results:
            return []

        evidence_list = []

        for result in results:
            try:
                evidence = self._extract_from_source(result, query)
                if evidence:
                    evidence_list.append(evidence)
            except Exception as e:
                logger.warning(f"Failed to extract evidence from {result.url}: {e}")

        logger.info(f"Extracted {len(evidence_list)} evidence objects from {len(results)} sources")
        return evidence_list

    def _extract_from_source(self, result: SearchResult, query: str) -> Optional[Evidence]:
        """
        Extract evidence from a single search result.

        Args:
            result: Search result to extract from
            query: Query for context

        Returns:
            Evidence object or None
        """
        # Get content from document or snippet
        content = self._get_content(result)

        if not content:
            return None

        # Extract facts
        facts = self._extract_facts(content, result, query)

        if not facts:
            return None

        # Create evidence object
        evidence = Evidence(
            query=query,
            source=result.source,
            url=result.url,
            facts=facts,
            trust_level=result.trust_level,
            tags=self._extract_tags(result, query),
            timestamp=None
        )

        return evidence

    def _get_content(self, result: SearchResult) -> Optional[str]:
        """
        Get content from search result.

        Args:
            result: Search result

        Returns:
            Content text or None
        """
        # Try to get full document content if available
        if hasattr(result, 'document') and result.document:
            doc = result.document
            if hasattr(doc, 'content') and doc.content:
                return doc.content
            if hasattr(doc, 'snippet') and doc.snippet:
                return doc.snippet

        # Fall back to snippet
        if hasattr(result, 'snippet') and result.snippet:
            return result.snippet

        return None

    def _extract_facts(self, content: str, result: SearchResult, query: str) -> List[ExtractedFact]:
        """
        Extract facts from content.

        Args:
            content: Content text
            result: Search result
            query: Query for context

        Returns:
            List of extracted facts
        """
        facts = []

        # Use a combination of fact extraction strategies
        facts.extend(self._extract_facts_by_sentences(content, query, result))
        facts.extend(self._extract_facts_by_keywords(content, query, result))

        # Remove duplicates based on text similarity
        unique_facts = self._remove_duplicate_facts(facts)

        # Score and rank facts
        scored_facts = self._score_facts(unique_facts, query, result)

        return scored_facts[:self.max_facts_per_source]

    def _extract_facts_by_sentences(self, content: str, result: SearchResult, query: str) -> List[ExtractedFact]:
        """
        Extract facts by analyzing sentences.

        Args:
            content: Content text
            result: Search result
            query: Query

        Returns:
            List of extracted facts
        """
        facts = []

        # Split content into sentences
        sentences = re.split(r'[.!?]', content)

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < self.min_fact_length:
                continue
            if len(sentence) > self.max_fact_length:
                continue

            # Skip if sentence doesn't seem informative
            if self._is_boring_sentence(sentence):
                continue

            # Calculate relevance score
            score = self._calculate_relevance_score(sentence, query, result)

            if score > 0.3:  # Minimum relevance threshold
                facts.append(ExtractedFact(
                    text=sentence,
                    confidence=score,
                    source=result.source,
                    source_url=result.url,
                    trust_level=result.trust_level
                ))

        return facts

    def _extract_facts_by_keywords(self, content: str, result: SearchResult, query: str) -> List[ExtractedFact]:
        """
        Extract facts by matching keywords.

        Args:
            content: Content text
            result: Search result
            query: Query

        Returns:
            List of extracted facts
        """
        facts = []

        # Extract noun phrases or key information
        query_terms = query.lower().split()

        # Look for important content
        important_words = {
            'version', 'release', 'bug', 'issue', 'fix', 'change',
            'added', 'removed', 'deprecated', 'supported', 'recommended'
        }

        sentences = re.split(r'[.!?]', content)

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < self.min_fact_length:
                continue

            # Check if sentence contains important words
            sentence_lower = sentence.lower()
            if any(word in important_words for word in sentence_lower.split()):
                score = 0.5  # High confidence for important words

                facts.append(ExtractedFact(
                    text=sentence,
                    confidence=score,
                    source=result.source,
                    source_url=result.url,
                    trust_level=result.trust_level
                ))

        return facts

    def _calculate_relevance_score(self, sentence: str, query: str, result: SearchResult) -> float:
        """
        Calculate relevance score for a sentence.

        Args:
            sentence: Sentence to score
            query: Query for context
            result: Search result

        Returns:
            Relevance score (0-1)
        """
        score = 0.0

        # Token overlap with query
        query_terms = set(query.lower().split())
        sentence_terms = set(sentence.lower().split())

        # Jaccard similarity
        if query_terms and sentence_terms:
            intersection = len(query_terms & sentence_terms)
            union = len(query_terms | sentence_terms)
            score += intersection / union if union > 0 else 0

        # Boost for trusted sources
        trust_scores = {
            'official': 0.1,
            'government': 0.1,
            'github': 0.05,
            'stackoverflow': 0.05,
            'wikipedia': 0.03
        }

        score += trust_scores.get(result.trust_level, 0)

        # Maximum score is 1.0
        return min(score, 1.0)

    def _is_boring_sentence(self, sentence: str) -> bool:
        """
        Check if sentence is likely to be uninformative.

        Args:
            sentence: Sentence to check

        Returns:
            True if sentence is boring
        """
        # Common boring phrases
        boring_phrases = [
            'for example', 'in particular', 'in general',
            'moreover', 'furthermore', 'additionally',
            'however', 'therefore', 'consequently',
            'it is important', 'note that', 'it should be noted'
        ]

        sentence_lower = sentence.lower()
        return any(phrase in sentence_lower for phrase in boring_phrases)

    def _remove_duplicate_facts(self, facts: List[ExtractedFact]) -> List[ExtractedFact]:
        """
        Remove duplicate facts based on text similarity.

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

    def _are_facts_similar(self, fact1: ExtractedFact, fact2: ExtractedFact) -> bool:
        """
        Check if two facts are similar.

        Args:
            fact1: First fact
            fact2: Second fact

        Returns:
            True if facts are similar
        """
        # Simple string similarity
        text1 = fact1.text.lower()
        text2 = fact2.text.lower()

        # Check for overlapping terms
        terms1 = set(text1.split())
        terms2 = set(text2.split())

        overlap = len(terms1 & terms2)
        total = len(terms1 | terms2)

        # Similarity threshold
        return overlap / total > 0.7 if total > 0 else False

    def _score_facts(self, facts: List[ExtractedFact], query: str, result: SearchResult) -> List[ExtractedFact]:
        """
        Score and rank facts.

        Args:
            facts: List of facts to score
            query: Query for context
            result: Search result

        Returns:
            List of scored and sorted facts
        """
        # Score each fact
        for fact in facts:
            # Base score from relevance
            score = fact.confidence

            # Boost for important words
            important_words = {
                'version', 'release', 'bug', 'issue', 'fix', 'change',
                'security', 'vulnerability', 'cve', 'latest', 'new'
            }

            if any(word in fact.text.lower() for word in important_words):
                score += 0.2

            fact.confidence = min(score, 1.0)

        # Sort by confidence (descending)
        facts.sort(key=lambda x: x.confidence, reverse=True)

        return facts

    def _extract_tags(self, result: SearchResult, query: str) -> List[str]:
        """
        Extract tags for evidence.

        Args:
            result: Search result
            query: Query

        Returns:
            List of tags
        """
        tags = []

        # Source-based tags
        if result.trust_level == 'official':
            tags.append('official')
        elif result.trust_level == 'github':
            tags.append('github')
        elif result.trust_level == 'stackoverflow':
            tags.append('documentation')

        # Content-based tags
        content_lower = result.snippet.lower() if result.snippet else ''

        # Version-related
        if re.search(r'version\s+\d+(\.\d+)*', content_lower):
            tags.append('version')

        # Bug/issue related
        if any(word in content_lower for word in ['bug', 'issue', 'error', 'fix']):
            tags.append('issue')

        # Documentation related
        if any(word in content_lower for word in ['guide', 'tutorial', 'documentation', 'tutorial']):
            tags.append('documentation')

        return tags
