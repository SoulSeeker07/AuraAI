"""
Research Engine Module

AuraAI's evidence collection and analysis system.
"""

from .cache_manager import CacheManager
from .citation_builder import CitationBuilder
from .content_fetcher import ContentFetcher
from .models import (
    Citation,
    ConflictResolution,
    Document,
    ResearchConfig,
    ResearchReport,
    SearchMode,
    SearchQuery,
    SearchResult,
    SourceTrustLevel,
)
from .provider_interface import BaseResearchProvider, ResearchProvider
from .research_engine import ResearchEngine
from .search_manager import SearchManager

__all__ = [
    # Models
    "SearchQuery",
    "SearchResult",
    "Document",
    "Citation",
    "ResearchReport",
    "ResearchConfig",
    "SearchMode",
    "SourceTrustLevel",
    "ConflictResolution",
    # Core components
    "ResearchEngine",
    "SearchManager",
    "ResearchProvider",
    "BaseResearchProvider",
    "ContentFetcher",
    "CacheManager",
    "CitationBuilder",
]
