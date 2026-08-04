"""
Research Context

Represents the complete research result including summary, evidence, citations,
confidence, conflicts, unanswered questions, and recommendations.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import logging

from .models import Evidence, SearchMode
from .citation_builder import Citation, CitationBuilder

logger = logging.getLogger(__name__)


class ResearchMode(Enum):
    """Research modes for determining search depth."""
    QUICK = "quick"  # 3 sources
    STANDARD = "standard"  # 5-8 sources
    DEEP = "deep"  # 10-15 sources
    EXPERT = "expert"  # 20-40 sources + recursive research
    
    @classmethod
    def from_search_mode(cls, mode) -> 'ResearchMode':
        """
        Convert SearchMode to ResearchMode.
        
        Args:
            mode: SearchMode enum value
            
        Returns:
            Corresponding ResearchMode enum value
        """
        if mode is None:
            return cls.STANDARD
        
        # Map SearchMode to ResearchMode
        if mode == SearchMode.QUICK:
            return cls.QUICK
        elif mode == SearchMode.STANDARD:
            return cls.STANDARD
        elif mode == SearchMode.DEEP:
            return cls.DEEP
        else:
            # Map other modes to STANDARD for now
            return cls.STANDARD


@dataclass
class ResearchContext:
    """
    Complete research context to be sent to the LLM.
    
    This replaces raw evidence in the research pipeline.
    The LLM receives a structured ResearchContext instead of individual evidence items.
    
    Attributes:
        query: Original research query
        mode: Research mode used
        summary: High-level summary of findings
        evidence: List of Evidence objects
        citations: List of Citation objects
        confidence: Overall confidence score (0.0-1.0)
        conflicts: List of conflicting evidence
        unanswered_questions: List of questions that couldn't be answered
        recommendations: List of actionable recommendations
        metadata: Additional metadata
    """
    query: str
    mode: ResearchMode
    summary: str = ""
    evidence: List[Evidence] = field(default_factory=list)
    citations: List[Citation] = field(default_factory=list)
    confidence: float = 0.5
    conflicts: List[str] = field(default_factory=list)
    unanswered_questions: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Post-initialization setup."""
        if not self.conflicts:
            self.conflicts = []
        if not self.unanswered_questions:
            self.unanswered_questions = []
        if not self.recommendations:
            self.recommendations = []
        if not self.metadata:
            self.metadata = {}
    
    def to_llm_prompt(self) -> str:
        """
        Convert ResearchContext to LLM-friendly prompt format.
        
        Returns:
            Formatted prompt string for LLM
        """
        prompt = f"# RESEARCH QUERY\n{self.query}\n\n"
        prompt += f"# RESEARCH MODE\n{self.mode.name}\n\n"
        
        if self.summary:
            prompt += f"# SUMMARY\n{self.summary}\n\n"
        
        if self.confidence > 0:
            prompt += f"# CONFIDENCE: {self.confidence:.2f}\n\n"
        
        if self.conflicts:
            prompt += f"# CONFLICTS DETECTED\n"
            for conflict in self.conflicts:
                prompt += f"- {conflict}\n"
            prompt += "\n"
        
        if self.unanswered_questions:
            prompt += f"# UNANSWERED QUESTIONS\n"
            for question in self.unanswered_questions:
                prompt += f"- {question}\n"
            prompt += "\n"
        
        if self.recommendations:
            prompt += f"# RECOMMENDATIONS\n"
            for rec in self.recommendations:
                prompt += f"- {rec}\n"
            prompt += "\n"
        
        prompt += "# EVIDENCE\n"
        for i, evidence in enumerate(self.evidence, 1):
            citation = self.citations[i-1] if self.citations else None
            prompt += f"{i}. {evidence.fact}\n"
            if evidence.score:
                prompt += f"   Score: {evidence.score}/5\n"
            if citation and citation.url:
                prompt += f"   Source: {citation.url}\n"
            if evidence.source:
                prompt += f"   Source: {evidence.source}\n"
            if citation and citation.confidence:
                prompt += f"   Confidence: {citation.confidence:.2f}\n"
            prompt += "\n"
        
        return prompt
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'query': self.query,
            'mode': self.mode.value,
            'summary': self.summary,
            'evidence': [evidence.to_dict() for evidence in self.evidence],
            'citations': [citation.__dict__ for citation in self.citations],
            'confidence': self.confidence,
            'conflicts': self.conflicts,
            'unanswered_questions': self.unanswered_questions,
            'recommendations': self.recommendations,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_evidence_and_citations(
        cls,
        evidence: List[Evidence],
        citations: List[Citation],
        query: str,
        mode: ResearchMode = ResearchMode.STANDARD,
        summary: str = "",
        confidence: float = 0.5
    ) -> 'ResearchContext':
        """
        Create ResearchContext from evidence and citations.
        
        Args:
            evidence: List of evidence objects
            citations: List of citation objects
            query: Research query
            mode: Research mode used
            summary: Summary of findings
            confidence: Overall confidence score
            
        Returns:
            ResearchContext instance
        """
        ctx = cls(
            query=query,
            mode=mode,
            summary=summary,
            confidence=confidence
        )
        ctx.evidence = evidence
        ctx.citations = citations
        
        return ctx
    
    def get_confidence_by_source(self) -> Dict[str, float]:
        """
        Calculate average confidence per source type.
        
        Returns:
            Dictionary mapping source types to average confidence
        """
        source_confidence = {}
        
        for citation in self.citations:
            source = citation.url.split('/')[2] if len(citation.url.split('/')) > 2 else citation.url
            if source not in source_confidence:
                source_confidence[source] = []
            source_confidence[source].append(citation.confidence)
        
        return {
            source: sum(confidences) / len(confidences)
            for source, confidences in source_confidence.items()
        }