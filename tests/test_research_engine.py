"""
Research Engine Tests

Test the Research Engine functionality.
"""

import pytest
import sys
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from research.models import (
    SearchQuery,
    ResearchReport,
    SearchMode,
    SourceTrustLevel,
    ResearchConfig
)
from research.research_engine import ResearchEngine


class TestResearchModels:
    """Test research data models."""

    def test_search_query_creation(self):
        """Test creating a search query."""
        query = SearchQuery(
            query_text="test query",
            mode=SearchMode.STANDARD,
            max_results=5
        )
        
        assert query.query_text == "test query"
        assert query.mode == SearchMode.STANDARD
        assert query.max_results == 5

    def test_search_report_creation(self):
        """Test creating a research report."""
        report = ResearchReport(
            query="test query",
            results=[],
            summary="Test summary"
        )
        
        assert report.query == "test query"
        assert len(report.results) == 0
        assert report.summary == "Test summary"

    def test_report_to_dict(self):
        """Test converting report to dictionary."""
        report = ResearchReport(
            query="test query",
            results=[],
            summary="Test summary"
        )
        
        data = report.to_dict()
        
        assert "query" in data
        assert "results" in data
        assert "summary" in data


class TestResearchEngine:
    """Test Research Engine functionality."""

    @pytest.fixture
    def research_engine(self):
        """Create a research engine instance for testing."""
        config = ResearchConfig(
            enabled=True,
            default_mode=SearchMode.STANDARD
        )
        return ResearchEngine(config)

    def test_engine_initialization(self, research_engine):
        """Test that engine initializes correctly."""
        assert research_engine is not None
        assert research_engine.config.enabled is True

    def test_is_research_needed_simple(self, research_engine):
        """Test simple research need detection."""
        assert research_engine.is_research_needed("latest news") is True
        assert research_engine.is_research_needed("current version") is True
        assert research_engine.is_research_needed("hello") is False

    def test_search_mode_enums(self):
        """Test search mode enum values."""
        assert SearchMode.QUICK.value == "quick"
        assert SearchMode.STANDARD.value == "standard"
        assert SearchMode.DEEP.value == "deep"

    def test_source_trust_levels(self):
        """Test source trust level enum values."""
        assert SourceTrustLevel.OFFICIAL.value == "official"
        assert SourceTrustLevel.GITHUB.value == "github"
        assert SourceTrustLevel.WIKIPEDIA.value == "wikipedia"

    def test_conflict_resolution(self):
        """Test conflict resolution enum values."""
        assert ConflictResolution.AUTO.value == "auto"
        assert ConflictResolution.PREFER_AUTHORITATIVE.value == "prefer_authoritative"


class TestResearchConfig:
    """Test research configuration."""

    def test_default_config(self):
        """Test default configuration."""
        config = ResearchConfig()
        
        assert config.enabled is True
        assert config.default_mode == SearchMode.STANDARD
        assert config.default_max_results == 10
        assert config.cache_ttl == 1800

    def test_custom_config(self):
        """Test custom configuration."""
        config = ResearchConfig(
            enabled=True,
            default_mode=SearchMode.QUICK,
            default_max_results=20,
            cache_ttl=3600
        )
        
        assert config.default_mode == SearchMode.QUICK
        assert config.default_max_results == 20
        assert config.cache_ttl == 3600

    def test_provider_config(self):
        """Test provider configuration."""
        config = ResearchConfig()
        
        assert "tavily" in config.providers
        assert "github" in config.providers
        assert "wikipedia" in config.providers

    def test_get_provider_config(self):
        """Test getting provider configuration."""
        config = ResearchConfig()
        tavily_config = config.get_provider_config("tavily")
        
        assert tavily_config is not None
        assert "enabled" in tavily_config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
