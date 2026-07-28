from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Source authority weights (higher = more trusted)
SOURCE_AUTHORITY = {
    # Government/Official
    ".gov": 10.0,
    "who.int": 10.0,
    "cdc.gov": 9.5,
    "nih.gov": 9.0,
    "nasa.gov": 9.0,
    "fda.gov": 9.0,
    
    # Major Tech/Enterprise
    "microsoft.com": 8.5,
    "google.com": 8.0,
    "apple.com": 8.0,
    "amazon.com": 7.5,
    "github.com": 8.5,
    "stackoverflow.com": 8.0,
    "reactjs.org": 8.5,
    "python.org": 8.5,
    "nodejs.org": 8.0,
    "docs.python.org": 9.0,
    "developer.mozilla.org": 8.5,
    "learn.microsoft.com": 8.5,
    "devdocs.io": 8.0,
    
    # Tech Networks
    "cisco.com": 8.5,
    "juniper.net": 7.5,
    "paloaltonetworks.com": 7.5,
    "fortinet.com": 7.5,
    "f5.com": 7.5,
    
    # Educational/Academic
    "wikipedia.org": 6.0,  # Wikipedia is good for overview but not for factual claims
    "springer.com": 7.5,
    "sciencedirect.com": 7.0,
    "arxiv.org": 8.0,
    "ncbi.nlm.nih.gov": 9.0,
    "ieee.org": 8.0,
    
    # Major News
    "bbc.com": 7.5,
    "reuters.com": 8.0,
    "apnews.com": 7.5,
    "nytimes.com": 8.0,
    "washingtonpost.com": 8.0,
    
    # Healthcare
    "mayoclinic.org": 8.5,
    "healthline.com": 7.5,
    "verywellhealth.com": 7.0,
    "health.harvard.edu": 9.0,
    
    # Medium weight
    "medium.com": 5.0,
    "blog.some-blog.com": 3.0,
}


@dataclass
class RankedResult:
    """A ranked search result with score and confidence."""
    
    result: dict[str, Any]
    score: float
    confidence: float
    rank: int
    reasons: list[str]


class SourceRanker:
    """
    Ranks search results based on source authority and relevance.
    This helps Aura determine which sources to trust more.
    """

    def __init__(self, authority_weights: dict[str, float] | None = None):
        """
        Initialize the source ranker.
        
        Args:
            authority_weights: Custom authority weights
        """
        self.authority_weights = authority_weights or SOURCE_AUTHORITY.copy()
    
    def rank_results(
        self,
        results: list[dict[str, Any]],
        query: str,
        specialized_domains: list[str] | None = None,
        context_sources: list[str] | None = None,
    ) -> list[RankedResult]:
        """
        Rank search results by authority and relevance.
        
        Args:
            results: List of search results (with url and title fields)
            query: Original search query
            specialized_domains: User-specified special domains to prioritize
            context_sources: Source URLs to consider as context
            
        Returns:
            List of RankedResult objects in descending score order
        """
        ranked_results = []
        
        for rank, result in enumerate(results):
            url = result.get("url", "")
            title = result.get("title", "")
            
            # Skip results without URLs
            if not url:
                continue
            
            # Calculate base score from authority
            base_score = self._get_authority_score(url)
            
            # Calculate relevance score
            relevance_score = self._calculate_relevance(url, title, query)
            
            # Combine scores (40% authority, 60% relevance)
            score = base_score * 0.4 + relevance_score * 0.6
            
            # Boost score for specialized domains
            if specialized_domains and url:
                for domain in specialized_domains:
                    if domain in url:
                        score += 2.0
                        break
            
            # Boost score if result appears in context sources
            if context_sources and url in context_sources:
                score += 1.0
            
            # Calculate confidence (based on how strong the signals are)
            confidence = self._calculate_confidence(base_score, relevance_score, url)
            
            # Generate reasoning
            reasons = self._generate_reasoning(url, score, base_score)
            
            ranked_results.append(RankedResult(
                result=result,
                score=score,
                confidence=confidence,
                rank=rank + 1,
                reasons=reasons
            ))
        
        # Sort by score descending
        ranked_results.sort(key=lambda x: x.score, reverse=True)
        
        return ranked_results
    
    def _get_authority_score(self, url: str) -> float:
        """
        Get authority score for a URL.
        
        Args:
            url: URL to score
            
        Returns:
            Authority score (0-10)
        """
        if not url:
            return 0.0
        
        # Check for exact domain match
        domain = url.lower().replace("https://", "").replace("http://", "").split("/")[0]
        
        if domain in self.authority_weights:
            return self.authority_weights[domain]
        
        # Check for .gov domains
        if ".gov" in url:
            return 10.0
        
        # Check for .edu domains
        if ".edu" in url:
            return 8.5
        
        # Check for common patterns
        if "github.com" in url:
            return 8.5
        if "stackoverflow.com" in url:
            return 8.0
        if "wikipedia.org" in url:
            return 6.0
        
        # Default score
        return 5.0
    
    def _calculate_relevance(self, url: str, title: str, query: str) -> float:
        """
        Calculate relevance score based on query matching.
        
        Args:
            url: URL to score
            title: Title to score
            query: Search query
            
        Returns:
            Relevance score (0-10)
        """
        relevance = 0.0
        
        # Combine URL and title for matching
        text = f"{url} {title}".lower()
        query_lower = query.lower()
        
        # Exact match of query terms
        query_terms = query_lower.split()
        matching_terms = sum(1 for term in query_terms if term in text)
        
        if matching_terms > 0:
            relevance += matching_terms * 2.0
        
        # Phrase matching (exact words in order)
        if query_lower in text:
            relevance += 3.0
        
        # Partial match
        words_in_url = set(url.lower().split())
        words_in_title = set(title.lower().split())
        common_words = words_in_url.intersection(words_in_title)
        
        if common_words:
            relevance += len(common_words) * 0.5
        
        # Bonus for having query in URL
        if query_lower in url.lower():
            relevance += 2.0
        
        return min(relevance, 10.0)
    
    def _calculate_confidence(self, authority_score: float, relevance_score: float, url: str) -> float:
        """
        Calculate overall confidence in the result.
        
        Args:
            authority_score: Authority score (0-10)
            relevance_score: Relevance score (0-10)
            url: URL of the result
            
        Returns:
            Confidence score (0-1)
        """
        # High authority + high relevance = high confidence
        combined = (authority_score + relevance_score) / 20.0  # Normalize to 0-1
        
        # Boost for well-known domains
        if url and ("gov" in url or "edu" in url):
            combined = min(combined + 0.1, 1.0)
        
        return combined
    
    def _generate_reasoning(self, url: str, score: float, authority_score: float) -> list[str]:
        """
        Generate reasoning for the ranking.
        
        Args:
            url: URL
            score: Total score
            authority_score: Authority score
            
        Returns:
            List of reasoning strings
        """
        reasons = []
        
        # Check authority
        if authority_score >= 8.0:
            reasons.append("high_authority")
        elif authority_score >= 5.0:
            reasons.append("medium_authority")
        
        # Check for government
        if ".gov" in url:
            reasons.append("government_source")
        
        # Check for academic
        if ".edu" in url:
            reasons.append("academic_source")
        
        # Check for tech
        if "github.com" in url:
            reasons.append("technical_source")
        
        # Check for news
        if "news" in url.lower():
            reasons.append("news_source")
        
        return reasons

    def select_top_sources(
        self,
        ranked_results: list[RankedResult],
        count: int = 3
    ) -> list[RankedResult]:
        """
        Select top N sources for research.
        
        Args:
            ranked_results: Ranked results
            count: Number of sources to select
            
        Returns:
            Top N ranked results
        """
        return ranked_results[:count]
