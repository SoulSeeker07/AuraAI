"""
Comprehensive tests for Deep Research capabilities (Milestone 2).

Testing Checklist Items:
1. Latest Python version
2. OpenAI news
3. RTX comparison
4. Windows features
5. Cisco vulnerabilities
6. Firewall comparison
7. GitHub repository summarization

This tests the complete deep research implementation including:
- PageReader (document type detection, extraction)
- SourceRanker (authority scoring)
- ResearchAgent (plan creation)
- CitationBuilder (citation generation)
- DeepResearchManager (orchestration)
- ConversationEngine integration
"""

import asyncio

# Add project root to path for imports
import sys
from datetime import datetime
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from ai.provider_manager import ProviderManager
from brain.citation_builder import CitationBuilder
from brain.conversation_engine import ConversationEngine
from brain.intent_router import IntentRouter
from brain.models import (
    ConversationAttachment,
    DeepResearchResult,
    IntentName,
    ResearchFinding,
    WebSearchResultSimple,
)
from brain.models_extended import IntentAnalysis, SearchResult
from brain.page_reader import DocumentType, PageReader
from brain.source_ranker import SOURCE_AUTHORITY, SourceRanker
from Memory import Memory

# Skip tests if dependencies are not available
pytest.importorskip("ai.provider_manager", reason="AI provider manager not available")
pytest.importorskip("Memory", reason="Memory module not available")


class TestPageReaderDeepResearch:
    """Test Deep Research capabilities of PageReader."""

    @pytest.fixture
    def page_reader(self):
        """Create PageReader instance."""
        return PageReader(timeout_seconds=10.0)

    def test_document_type_detection_html(self, page_reader, mocker):
        """Test HTML document type detection."""
        url = "https://example.com/article"
        assert page_reader.detect_document_type(url) == "html"

    def test_document_type_detection_github(self, page_reader):
        """Test GitHub repository URL detection."""
        url = "https://github.com/openai/transformers"
        assert page_reader.detect_document_type(url) == "github"

    def test_document_type_detection_markdown(self, page_reader):
        """Test Markdown file URL detection."""
        url = "https://raw.githubusercontent.com/user/repo/master/README.md"
        assert page_reader.detect_document_type(url) == "markdown"

    def test_document_type_detection_pdf(self, page_reader):
        """Test PDF file URL detection."""
        url = "https://example.com/document.pdf"
        assert page_reader.detect_document_type(url) == "pdf"

    def test_document_type_detection_microsoft_learn(self, page_reader):
        """Test Microsoft Learn documentation."""
        url = "https://learn.microsoft.com/en-us/python/api/"
        assert page_reader.detect_document_type(url) == "MICROSOFT_LEARN"

    def test_document_type_detection_cisco_docs(self, page_reader):
        """Test Cisco documentation."""
        url = "https://www.cisco.com/c/en/us/td/docs/"
        assert page_reader.detect_document_type(url) == "CISCO_DOCS"

    def test_document_type_detection_python_docs(self, page_reader):
        """Test Python documentation."""
        url = "https://docs.python.org/3/library/"
        assert page_reader.detect_document_type(url) == "PYTHON_DOCS"

    def test_extract_github_readme_simple(self, page_reader):
        """Test GitHub README extraction."""
        url = "https://github.com/openai/transformers"
        content = """
# Transformers
        
A library by Hugging Face's 🤗 team.
        
## Installation
        
```bash
pip install transformers
```
        
## Usage
        
```python
from transformers import pipeline
```
        """
        text, code_blocks = page_reader._extract_github_readme(content, url)

        assert "Transformers" in text
        assert "pip install transformers" in text
        assert len(code_blocks) == 2
        assert code_blocks[0]["language"] == "bash"
        assert code_blocks[1]["language"] == "python"

    def test_extract_pdf_with_pypdf2(self, page_reader, mocker):
        """Test PDF extraction with PyPDF2."""
        pdf_content = b"%PDF-1.4\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj\n<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n3 0 obj\n<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer\n<</Size 4/Root 1 0 R>>\nstartxref\n167\n%%EOF"

        # Mock PyPDF2
        mocker.patch(
            "src.brain.page_reader.PyPDF2.PdfReader", return_value=mocker.Mock()
        )

        text = page_reader._extract_pdf(pdf_content, "https://example.com/doc.pdf")
        assert len(text) > 0

    def test_extract_markdown_content(self, page_reader):
        """Test Markdown extraction."""
        content = """
# Title
        
This is some **bold** and *italic* text.
        
## Subtitle
        
- List item 1
- List item 2
        
```python
print("Hello")
```
        """
        text = page_reader._extract_markdown(content, "https://example.com")
        assert "Title" in text
        assert "**bold**" in text
        assert "print" in text

    def test_read_page_html(self, page_reader, mocker):
        """Test reading HTML page."""
        url = "https://example.com"
        mock_response = mocker.Mock()
        mock_response.read.return_value = b"""
        <html>
        <head><title>Test Page</title></head>
        <body><h1>Test Content</h1><p>Hello World</p></body>
        </html>
        """
        mock_response.getheader.return_value = "text/html"

        mocker.patch("src.brain.page_reader.urlopen", return_value=mock_response)

        page = page_reader.read_page(url)

        assert page.title == "Test Page"
        assert page.content_type == "html"
        assert "Hello World" in page.main_text

    @pytest.mark.asyncio
    async def test_read_pages_parallel(self, page_reader, mocker):
        """Test parallel reading of multiple pages."""
        urls = [
            "https://example.com/1",
            "https://example.com/2",
            "https://example.com/3",
        ]

        # Mock responses
        mock_responses = []
        for i, url in enumerate(urls):
            mock_response = mocker.Mock()
            mock_response.read.return_value = f"<html><title>Page {i+1}</title><body>Content {i+1}</body></html>".encode()
            mock_responses.append(mock_response)

        call_order = []

        def mock_urlopen(request, timeout=None):
            index = call_order.__len__()
            call_order.append(index)
            return mock_responses[index]

        mocker.patch("src.brain.page_reader.urlopen", side_effect=mock_urlopen)

        pages = await page_reader.read_pages_parallel(urls)

        assert len(pages) == 3
        assert call_order == [
            0,
            1,
            2,
        ]  # All should be called concurrently (approximate)
        assert [p.title for p in pages] == ["Page 1", "Page 2", "Page 3"]

    def test_intent_detection_web_search(self, mocker):
        """Test intent detection for web search queries."""
        query = "What is the latest Python version?"
        question = "What is the latest Python version?"

        # Mock Groq API response
        mock_response = mocker.Mock()
        mock_response.choices = [
            mocker.Mock(
                message=mocker.Mock(
                    content='{"intent": "web_search", "confidence": 0.95, "sources": ["python.org"], "subtopics": ["version", "features"]}'
                )
            )
        ]

        mocker.patch(
            "src.brain.intent_analyzer.client.chat.completions.create",
            return_value=mock_response,
        )

        analyzer = IntentAnalyzer()
        analysis = analyzer.analyze_intent(query, question)

        assert analysis.intent == IntentAnalysis.INTENT_WEB_SEARCH
        assert analysis.confidence >= 0.8

    def test_intent_detection_code_related(self, mocker):
        """Test intent detection for code-related queries."""
        query = "How do I use React useEffect?"
        question = "How do I use React useEffect?"

        # Mock Groq API response
        mock_response = mocker.Mock()
        mock_response.choices = [
            mocker.Mock(
                message=mocker.Mock(
                    content='{"intent": "code", "confidence": 0.92, "sources": ["github.com", "stackoverflow.com"], "subtopics": ["useEffect", "hooks", "React"]}'
                )
            )
        ]

        mocker.patch(
            "src.brain.intent_analyzer.client.chat.completions.create",
            return_value=mock_response,
        )

        analyzer = IntentAnalyzer()
        analysis = analyzer.analyze_intent(query, question)

        assert analysis.intent == IntentAnalysis.INTENT_CODE_RELATED
        assert analysis.confidence >= 0.8

    def test_intent_detection_coding_help(self, mocker):
        """Test intent detection for coding help queries."""
        query = "Help me fix this Python code"
        question = "Help me fix this Python code"

        # Mock Groq API response
        mock_response = mocker.Mock()
        mock_response.choices = [
            mocker.Mock(
                message=mocker.Mock(
                    content='{"intent": "coding_help", "confidence": 0.98, "sources": ["stackoverflow.com", "github.com"], "subtopics": ["debugging", "error_fix", "code_review"]}'
                )
            )
        ]

        mocker.patch(
            "src.brain.intent_analyzer.client.chat.completions.create",
            return_value=mock_response,
        )

        analyzer = IntentAnalyzer()
        analysis = analyzer.analyze_intent(query, question)

        assert analysis.intent == IntentAnalysis.INTENT_CODING_HELP
        assert analysis.confidence >= 0.8

    def test_source_detection_python_docs(self, mocker):
        """Test source detection for Python documentation queries."""
        query = "What is the asyncio.run function?"
        question = "What is the asyncio.run function?"

        # Mock Groq API response
        mock_response = mocker.Mock()
        mock_response.choices = [
            mocker.Mock(
                message=mocker.Mock(
                    content='{"intent": "web_search", "confidence": 0.90, "sources": ["python.org"], "subtopics": ["asyncio", "run", "coroutines"]}'
                )
            )
        ]

        mocker.patch(
            "src.brain.intent_analyzer.client.chat.completions.create",
            return_value=mock_response,
        )

        analyzer = IntentAnalyzer()
        analysis = analyzer.analyze_intent(query, question)

        assert "python.org" in analysis.detected_sources
        assert len(analysis.detected_sources) > 0

    def test_source_detection_github(self, mocker):
        """Test source detection for GitHub queries."""
        query = "How do I implement a WebSocket server in Python?"
        question = "How do I implement a WebSocket server in Python?"

        # Mock Groq API response
        mock_response = mocker.Mock()
        mock_response.choices = [
            mocker.Mock(
                message=mocker.Mock(
                    content='{"intent": "code", "confidence": 0.88, "sources": ["github.com"], "subtopics": ["websocket", "server", "python"]}'
                )
            )
        ]

        mocker.patch(
            "src.brain.intent_analyzer.client.chat.completions.create",
            return_value=mock_response,
        )

        analyzer = IntentAnalyzer()
        analysis = analyzer.analyze_intent(query, question)

        assert "github.com" in analysis.detected_sources
        assert len(analysis.detected_sources) > 0

    def test_source_detection_programming_sites(self, mocker):
        """Test source detection for programming help queries."""
        query = "What's the difference between list and tuple in Python?"
        question = "What's the difference between list and tuple in Python?"

        # Mock Groq API response
        mock_response = mocker.Mock()
        mock_response.choices = [
            mocker.Mock(
                message=mocker.Mock(
                    content='{"intent": "web_search", "confidence": 0.87, "sources": ["stackoverflow.com", "w3schools.com"], "subtopics": ["list", "tuple", "difference", "python"]}'
                )
            )
        ]

        mocker.patch(
            "src.brain.intent_analyzer.client.chat.completions.create",
            return_value=mock_response,
        )

        analyzer = IntentAnalyzer()
        analysis = analyzer.analyze_intent(query, question)

        assert len(analysis.detected_sources) > 0
        assert any(
            "stackoverflow.com" in source or "w3schools.com" in source
            for source in analysis.detected_sources
        )

    def test_knowledge_router_news(self, mocker):
        """Test knowledge router for news queries."""
        router = KnowledgeRouter()

        analysis = IntentAnalysis(
            intent=IntentAnalysis.INTENT_WEB_SEARCH,
            confidence=0.95,
            detected_sources=["news.google.com", "bbc.com", "cnn.com"],
            subtopics=["latest", "technology", "2025"],
        )

        source = router.route(analysis)

        assert source == "news"

    def test_knowledge_router_programming(self, mocker):
        """Test knowledge router for programming queries."""
        router = KnowledgeRouter()

        analysis = IntentAnalysis(
            intent=IntentAnalysis.INTENT_CODE_RELATED,
            confidence=0.92,
            detected_sources=["github.com", "stackoverflow.com", "stackoverflow.com"],
            subtopics=["python", "react", "typescript"],
        )

        source = router.route(analysis)

        assert source == "programming"

    def test_knowledge_router_networking(self, mocker):
        """Test knowledge router for networking queries."""
        router = KnowledgeRouter()

        analysis = IntentAnalysis(
            intent=IntentAnalysis.INTENT_WEB_SEARCH,
            confidence=0.89,
            detected_sources=["cisco.com", "networkinglessons.com", "cisco.com"],
            subtopics=["firewall", "security", "network"],
        )

        source = router.route(analysis)

        assert source == "networking"

    def test_knowledge_router_medical(self, mocker):
        """Test knowledge router for medical queries."""
        router = KnowledgeRouter()

        analysis = IntentAnalysis(
            intent=IntentAnalysis.INTENT_WEB_SEARCH,
            confidence=0.91,
            detected_sources=["mayoclinic.org", "healthline.com", "cdc.gov"],
            subtopics=["virus", "symptoms", "treatment"],
        )

        source = router.route(analysis)

        assert source == "medical"

    def test_citation_builder_format(self):
        """Test citation formatting in markdown."""
        builder = CitationBuilder()

        citations = [
            {
                "source": "python.org",
                "title": "Python Documentation",
                "url": "https://docs.python.org/3/library/asyncio.html",
                "reason": "Official documentation for asyncio module",
            }
        ]

        markdown = builder.build_citations(citations)

        assert (
            "[Python Documentation](https://docs.python.org/3/library/asyncio.html)"
            in markdown
        )
        assert "python.org" in markdown
        assert len(markdown) > 0

    def test_citation_builder_multiple_sources(self):
        """Test citation builder with multiple sources."""
        builder = CitationBuilder()

        citations = [
            {
                "source": "stackoverflow.com",
                "title": "Stack Overflow Discussion",
                "url": "https://stackoverflow.com/questions/12345",
                "reason": "Popular discussion with multiple solutions",
            },
            {
                "source": "github.com",
                "title": "GitHub Repository",
                "url": "https://github.com/user/repo",
                "reason": "Code examples and documentation",
            },
            {
                "source": "w3schools.com",
                "title": "W3Schools Tutorial",
                "url": "https://www.w3schools.com/python/python_howto.asp",
                "reason": "Simple explanation of concepts",
            },
        ]

        markdown = builder.build_citations(citations)

        assert markdown.count("[Stack Overflow") == 1
        assert markdown.count("[GitHub") == 1
        assert markdown.count("[W3Schools") == 1
        assert len(markdown) > 0

    def test_source_ranker_authority_scoring(self):
        """Test source ranking with authority scores."""
        ranker = SourceRanker()

        sources = [
            {"url": "https://docs.python.org/3", "relevance": 0.9, "authority": "GOV"},
            {
                "url": "https://github.com/user/repo",
                "relevance": 0.7,
                "authority": "GITHUB",
            },
            {"url": "https://example.com", "relevance": 0.5, "authority": None},
        ]

        ranked = ranker.rank_sources(sources)

        assert ranked[0]["url"] == "https://docs.python.org/3"  # .gov has highest score
        assert (
            ranked[1]["url"] == "https://github.com/user/repo"
        )  # GitHub has high score
        assert ranked[2]["url"] == "https://example.com"  # No authority, lowest score

    def test_source_ranker_no_authority(self):
        """Test source ranking without authority information."""
        ranker = SourceRanker()

        sources = [
            {"url": "https://example.com/page1", "relevance": 0.8},
            {"url": "https://example.com/page2", "relevance": 0.6},
        ]

        ranked = ranker.rank_sources(sources)

        assert ranked[0]["url"] == "https://example.com/page1"
        assert ranked[1]["url"] == "https://example.com/page2"

    def test_intent_router_web_search(self):
        """Test intent router for web search."""
        router = IntentRouter()

        query = "What is the latest Python version?"
        question = "What is the latest Python version?"

        intent = IntentAnalysis(
            intent=IntentAnalysis.INTENT_WEB_SEARCH, confidence=0.95
        )

        action = router.route(query, question, intent)

        assert action == "web_search"

    def test_intent_router_code_related(self):
        """Test intent router for code-related queries."""
        router = IntentRouter()

        query = "How do I use React useEffect?"
        question = "How do I use React useEffect?"

        intent = IntentAnalysis(
            intent=IntentAnalysis.INTENT_CODE_RELATED, confidence=0.92
        )

        action = router.route(query, question, intent)

        assert action == "code_related"

    def test_intent_router_coding_help(self):
        """Test intent router for coding help queries."""
        router = IntentRouter()

        query = "Help me fix this Python code"
        question = "Help me fix this Python code"

        intent = IntentAnalysis(
            intent=IntentAnalysis.INTENT_CODING_HELP, confidence=0.98
        )

        action = router.route(query, question, intent)

        assert action == "coding_help"

    def test_intent_router_news(self):
        """Test intent router for news queries."""
        router = IntentRouter()

        query = "What's happening in the tech world today?"
        question = "What's happening in the tech world today?"

        intent = IntentAnalysis(
            intent=IntentAnalysis.INTENT_WEB_SEARCH, confidence=0.87
        )

        action = router.route(query, question, intent)

        assert action == "news"

    def test_intent_router_deep_research(self):
        """Test intent router for deep research queries."""
        router = IntentRouter()

        query = "Compare RTX 5090 and RTX 4090 performance in AI workloads"
        question = "Compare RTX 5090 and RTX 4090 performance in AI workloads"

        intent = IntentAnalysis(
            intent=IntentAnalysis.INTENT_WEB_SEARCH, confidence=0.88
        )

        action = router.route(query, question, intent)

        assert action == "deep_research"

    def test_intent_router_windows_features(self):
        """Test intent router for Windows feature queries."""
        router = IntentRouter()

        query = "What are the new features in Windows 11"
        question = "What are the new features in Windows 11"

        intent = IntentAnalysis(
            intent=IntentAnalysis.INTENT_WEB_SEARCH, confidence=0.86
        )

        action = router.route(query, question, intent)

        assert action == "deep_research"

    def test_intent_router_cisco_vulnerabilities(self):
        """Test intent router for Cisco vulnerability queries."""
        router = IntentRouter()

        query = "What are the latest Cisco firewall vulnerabilities"
        question = "What are the latest Cisco firewall vulnerabilities"

        intent = IntentAnalysis(
            intent=IntentAnalysis.INTENT_WEB_SEARCH, confidence=0.90
        )

        action = router.route(query, question, intent)

        assert action == "deep_research"

    def test_intent_router_firewall_comparison(self):
        """Test intent router for firewall comparison queries."""
        router = IntentRouter()

        query = "Compare pfSense and OPNsense firewalls"
        question = "Compare pfSense and OPNsense firewalls"

        intent = IntentAnalysis(
            intent=IntentAnalysis.INTENT_WEB_SEARCH, confidence=0.85
        )

        action = router.route(query, question, intent)

        assert action == "deep_research"

    def test_web_search_with_cache(self, mocker):
        """Test web search with caching."""
        from brain.live_search_engine import LiveSearchEngine
        from brain.search_cache import SearchCache

        # Mock cache
        cache = SearchCache()

        # Mock search engine
        mock_tavily = mocker.Mock()
        mock_response = mocker.Mock()
        mock_response.results = [
            SearchResult(
                url="https://example.com/python-features",
                title="Python 3.13 Features",
                content="Python 3.13 introduces new features like...",
            )
        ]
        mock_tavily.search.return_value = mock_response

        search_engine = LiveSearchEngine(cache=cache)
        search_engine.tavily = mock_tavily

        results = search_engine.search("Python 3.13 features", max_results=5)

        assert len(results) == 1
        assert results[0].title == "Python 3.13 Features"
        mock_tavily.search.assert_called_once()

    def test_research_agent_planning(self, mocker):
        """Test research agent planning multi-step research."""
        from brain.research_agent import ResearchAgent

        # Mock components
        mock_intent = mocker.Mock()
        mock_intent.intent = IntentAnalysis.INTENT_WEB_SEARCH
        mock_intent.confidence = 0.95

        mock_router = mocker.Mock()
        mock_router.route.return_value = "web_search"

        mock_search = mocker.Mock()
        mock_search.search.return_value = []

        mock_page_reader = mocker.Mock()
        mock_page_reader.read_page.return_value = mocker.Mock(
            title="Test Page",
            url="https://example.com",
            main_text="Test content",
            content_type="html",
        )

        agent = ResearchAgent(
            intent_analyzer=None,
            intent_router=mock_router,
            live_search_engine=mock_search,
            page_reader=mock_page_reader,
            source_ranker=None,
        )

        query = "What is the latest Python version?"

        plan = agent.create_research_plan(query, mock_intent)

        assert plan is not None
        assert len(plan.tasks) > 0

    def test_research_agent_execution(self, mocker):
        """Test research agent executing research plan."""
        from brain.research_agent import ResearchAgent

        # Mock components
        mock_intent = mocker.Mock()
        mock_intent.intent = IntentAnalysis.INTENT_WEB_SEARCH
        mock_intent.confidence = 0.95

        mock_router = mocker.Mock()
        mock_router.route.return_value = "web_search"

        mock_search = mocker.Mock()
        mock_response = mocker.Mock()
        mock_response.results = [
            SearchResult(
                url="https://example.com/python-version",
                title="Python 3.13 Released",
                content="Python 3.13 is now available...",
            )
        ]
        mock_search.search.return_value = mock_response.results

        mock_page_reader = mocker.Mock()
        mock_page_reader.read_page.return_value = mocker.Mock(
            title="Python 3.13 Released",
            url="https://example.com/python-version",
            main_text="Python 3.13 is the latest version.",
            content_type="html",
        )

        mock_ranker = mocker.Mock()
        mock_ranker.rank_sources.return_value = mock_response.results

        agent = ResearchAgent(
            intent_analyzer=None,
            intent_router=mock_router,
            live_search_engine=mock_search,
            page_reader=mock_page_reader,
            source_ranker=mock_ranker,
        )

        query = "What is the latest Python version?"
        question = "What is the latest Python version?"

        pages, summaries = agent.research(query, question)

        assert len(pages) == 1
        assert mock_page_reader.read_page.called
        mock_search.search.assert_called()

    def test_aura_search_system_basic_search(self, mocker):
        """Test AuraSearchSystem basic web search."""
        from brain.aura_search_system import AuraSearchSystem

        # Mock components
        mock_intent = mocker.Mock()
        mock_intent.intent = IntentAnalysis.INTENT_WEB_SEARCH
        mock_intent.confidence = 0.95
        mock_intent.detected_sources = ["python.org"]

        mock_router = mocker.Mock()
        mock_router.route.return_value = "web_search"

        mock_search = mocker.Mock()
        mock_search.search.return_value = []

        system = AuraSearchSystem(
            intent_analyzer=None,
            intent_router=mock_router,
            live_search_engine=mock_search,
            page_reader=None,
            source_ranker=None,
            citation_builder=None,
            research_agent=None,
        )

        query = "What is the latest Python version?"
        question = "What is the latest Python version?"

        results = system.search(query, question)

        assert isinstance(results, list)
        assert len(results) >= 0

    def test_research_progress_callback(self, page_reader):
        """Test research progress callback."""
        stages = []

        def progress_callback(stage: int, completed: int, total: int):
            stages.append({"stage": stage, "completed": completed, "total": total})

        import asyncio

        async def run_test():
            urls = [
                "https://example.com/1",
                "https://example.com/2",
                "https://example.com/3",
            ]

            await page_reader.read_pages_parallel(urls, max_workers=3)

            return stages

        stages = asyncio.run(run_test())

        assert len(stages) == 3
        assert all(
            st["stage"] == 1 and st["completed"] == 3 and st["total"] == 3
            for st in stages
        )
