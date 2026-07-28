"""
Extended models for the new Aura AI web search system.
These are separate from the core conversation models to avoid conflicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Re-export for convenience
from brain.models import (
    ConversationAttachment,
    ConversationContext,
    ConversationResult,
    Intent,
)


@dataclass(frozen=True)
class WebSearchResult:
    """Result from a web search."""
    title: str
    url: str
    snippet: str
    content: str | None = None  # Full content if available
    score: float = 0.0  # Relevance score
    source_rank: int = 0  # Source ranking position


# Alias for backward compatibility
SearchResult = WebSearchResult


@dataclass(frozen=True)
class IntentAnalysis:
    """Result of intent analysis with confidence scores."""
    intent: str  # e.g., "LIVE_INFORMATION", "KNOWLEDGE_REQUEST", "PROGRAMMING"
    confidence: float  # 0.0 to 1.0
    subintent: str | None = None  # More specific category
    category: str | None = None  # Mapped domain category
    metadata: dict[str, Any] = field(default_factory=dict)
    needs_web_search: bool = False  # Should this query use web search?
    needs_deep_research: bool = False  # Should this query read multiple pages?
    specialized_sources: list[str] = field(default_factory=list)  # Domains to prioritize
    data: dict[str, Any] = field(default_factory=dict)  # Additional extracted data


@dataclass(frozen=True)
class PageContent:
    """Extracted content from a webpage."""
    title: str
    url: str
    main_text: str
    headings: list[tuple[int, str]]
    code_blocks: list[str]
    tables: list[dict[str, Any]]
    metadata: dict[str, Any]
