"""
Research Engine Module

AuraAI's evidence collection and analysis system.
"""

from .models import (
    SearchQuery,
    SearchResult,
    Document,
    Citation,
    ResearchReport,
    ResearchConfig,
    SearchMode,
    SourceTrustLevel,
    ConflictResolution
)
from .research_engine import ResearchEngine
from .search_manager import SearchManager
from .provider_interface import ResearchProvider, BaseResearchProvider
from .content_fetcher import ContentFetcher
from .cache_manager import CacheManager
from .citation_builder import CitationBuilder

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
