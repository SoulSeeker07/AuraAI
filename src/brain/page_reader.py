from __future__ import annotations

import asyncio
import datetime
import logging
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Comment

logger = logging.getLogger(__name__)


class DocumentType(str, Enum):
    """Document types for page reader."""

    HTML = "html"
    GITHUB = "github"
    GITLAB = "gitlab"
    DOCUMENTATION = "documentation"
    PDF = "pdf"
    MARKDOWN = "markdown"
    GOV = "gov"
    ACADEMIC = "academic"


@dataclass
class PageContent:
    """Extracted content from a webpage with Deep Research support."""

    title: str
    url: str
    content_type: str = "html"
    main_text: str = ""
    headings: list[tuple[int, str]] = field(default_factory=list)
    code_blocks: list[str] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_authority: float = 0.0
    processing_time: float = 0.0
    raw_content: str = ""


class PageReader:
    """
    Enhanced Page Reader with Deep Research capabilities.

    Features:
    - Document type detection (GitHub, docs, PDF, Markdown)
    - Specialized extraction strategies
    - Parallel page reading
    - Progress tracking
    - Content cleaning and formatting
    """

    # Non-content element patterns to remove
    AD_PATTERNS = [
        r"ad[ _]?[0-9]*",  # Ad words
        r"google.*[ _]?[ad|banner]",
        r"sponsored",
        r"advertisement",
        r"promoted",
        r"marketplace",
        r"affiliate",
        r"partner",
    ]

    # Navigation patterns to remove
    NAVIGATION_PATTERNS = [
        r"nav[ _]?[a-z]*",
        r"menu[ _]?[a-z]*",
        r"sidebar[ _]?[a-z]*",
        r"footer[ _]?[a-z]*",
        r"header[ _]?[a-z]*",
        r"breadcrumb[ _]?[a-z]*",
    ]

    # Cookie banner patterns
    COOKIE_PATTERNS = [
        r"cookie[ _]?[b|B]anner",
        r"consent[ _]?[popup|modal]",
        r"accept[ _]?[cookies]",
    ]

    # Document type detection patterns
    DOCUMENT_PATTERNS = {
        "github": [
            "github.com",
            "raw.githubusercontent.com",
        ],
        "gitlab": [
            "gitlab.com",
        ],
        "readthedocs": [
            "readthedocs.io",
            "docs.python.org",
            "docs.microsoft.com",
            "learn.microsoft.com",
            "developer.mozilla.org",
            "cisco.com/c/en/us/support",
            "paloaltonetworks.com/documentation",
            "fortinet.com/documentation",
            "juniper.net/documentation",
        ],
        "pdf": [
            ".pdf",
            "file.pdf",
        ],
        "markdown": [
            ".md",
            "README.md",
        ],
        "gov": [
            ".gov",
        ],
        "academic": [
            "acm.org",
            "springer.com",
            "sciencedirect.com",
            "arxiv.org",
            "ieee.org",
            "ncbi.nlm.nih.gov",
        ],
    }

    # Document type extraction strategies
    DOCUMENT_STRATEGIES = {
        "github": "github",
        "gitlab": "markdown",
        "readthedocs": "documentation",
        "pdf": "pdf",
        "markdown": "markdown",
        "gov": "formal",
        "academic": "academic",
    }

    def __init__(self, timeout_seconds: float = 15.0, max_workers: int = 3):
        """
        Initialize the enhanced page reader with Deep Research capabilities.

        Args:
            timeout_seconds: Timeout for fetching pages
            max_workers: Maximum number of parallel readers
        """
        self.timeout_seconds = timeout_seconds
        self.max_workers = max_workers
        self._lock = threading.Lock()
        self._progress = {"total": 0, "completed": 0, "current": None}

    def read_page(self, url: str, timeout_seconds: float | None = None) -> PageContent:
        """
        Read and extract content from a webpage with document type detection.

        Args:
            url: URL of the webpage to read
            timeout_seconds: Optional timeout override

        Returns:
            PageContent object with extracted data

        Supports:
        - HTML pages with content cleaning
        - GitHub README files
        - Documentation sites (Microsoft Learn, Cisco, etc.)
        - PDF files (with PyPDF2)
        - Markdown files
        """
        timeout = timeout_seconds or self.timeout_seconds
        from urllib.error import HTTPError, URLError
        from urllib.request import Request, build_opener
        from src.desktop.native.security.network_policy import (
            EgressDecision,
            NetworkPolicyEngine,
            SafeHTTPRedirectHandler,
        )

        try:
            # Enforce NetworkPolicy on initial destination
            decision, reason, _ = NetworkPolicyEngine.get_instance().evaluate_destination(url)
            if decision == EgressDecision.HARD_BLOCKED:
                logger.warning(f"Blocked URL fetch for '{url}': {reason}")
                return PageContent(
                    url=url,
                    title="Access Denied",
                    main_text=f"Security Error: Network policy hard-block: {reason}",
                )

            # Detect document type
            content_type = self.detect_document_type(url)

            # Fetch content based on type with per-hop redirect validation
            headers = {
                "User-Agent": "Mozilla/5.0 AuraAI/0.3 (compatible; bot)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }

            request = Request(url, headers=headers)
            opener = build_opener(SafeHTTPRedirectHandler())

            with opener.open(request, timeout=timeout) as response:
                if content_type == "pdf":
                    raw_content = response.read()
                else:
                    raw_content = response.read().decode("utf-8", errors="replace")

            # Apply specialized extraction strategy
            if content_type == "github":
                text, code_blocks = self._extract_github_readme(raw_content, url)
                metadata = {"type": "github"}
            elif content_type == "pdf":
                text = self._extract_pdf(raw_content, url)
                code_blocks = []
                metadata = {"type": "pdf", "raw_size": len(raw_content)}
            elif content_type == "markdown":
                text = self._extract_markdown(raw_content, url)
                code_blocks = []
                metadata = {"type": "markdown"}
            else:
                # Default HTML extraction
                content = self._extract_content(url, raw_content)
                text = content.main_text
                code_blocks = content.code_blocks
                metadata = {"type": content_type, "headings": len(content.headings)}

            # Create PageContent
            from bs4 import BeautifulSoup

            if content_type == "html":
                soup = BeautifulSoup(raw_content, "html.parser")
                title = (
                    soup.find("title").get_text(strip=True)
                    if soup.find("title")
                    else ""
                )
            else:
                title = url.split("/")[-1] or "Untitled"

            return PageContent(
                title=title,
                url=url,
                content_type=content_type,
                main_text=text,
                code_blocks=code_blocks,
                metadata=metadata,
                processing_time=timeout,
            )

        except URLError as exc:
            raise ValueError(f"Network error: {exc}")
        except HTTPError as exc:
            raise ValueError(f"HTTP error {exc.code}: {exc.reason}")
        except Exception as exc:
            raise ValueError(f"Failed to read page: {exc}")

    def _extract_content(self, url: str, html_content: str) -> PageContent:
        """
        Extract meaningful content from HTML.

        Args:
            url: URL of the page
            html_content: HTML content as string

        Returns:
            PageContent object
        """
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove unwanted elements
        self._remove_elements(soup)

        # Extract page metadata
        metadata = self._extract_metadata(soup, url)

        # Extract main content
        title = self._extract_title(soup)
        main_text = self._extract_main_text(soup)
        headings = self._extract_headings(soup)
        code_blocks = self._extract_code_blocks(soup)
        tables = self._extract_tables(soup)

        return PageContent(
            title=title,
            url=url,
            content_type="html",
            main_text=main_text,
            headings=headings,
            code_blocks=code_blocks,
            tables=tables,
            metadata=metadata,
            source_authority=0.0,
            processing_time=0.0,
            raw_content=html_content,
        )

    def _remove_elements(self, soup: BeautifulSoup) -> None:
        """
        Remove non-content elements from HTML.

        Args:
            soup: BeautifulSoup object
        """
        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # Remove script and style tags and their content
        for element in soup(["script", "style", "iframe", "noscript"]):
            element.decompose()

        # Remove elements with common class names (ads, navigation, etc.)
        ad_pattern = re.compile("|".join(self.AD_PATTERNS), re.IGNORECASE)
        nav_pattern = re.compile("|".join(self.NAVIGATION_PATTERNS), re.IGNORECASE)
        cookie_pattern = re.compile("|".join(self.COOKIE_PATTERNS), re.IGNORECASE)

        for element in soup.find_all(True):
            # Check class names
            class_names = " ".join(element.get("class", []))
            if (
                ad_pattern.search(class_names)
                or nav_pattern.search(class_names)
                or cookie_pattern.search(class_names)
            ):
                element.decompose()
                continue

            # Check for ad/affiliate tags
            if (
                element.name in ["ins", "iframe"]
                and "data-ad" in element.attrs
                or "adsbygoogle" in element.get("class", [])
            ):
                element.decompose()
                continue

            # Remove empty elements
            if not element.get_text(strip=True):
                element.decompose()

    def _extract_metadata(self, soup: BeautifulSoup, url: str) -> dict[str, Any]:
        """
        Extract page metadata.

        Args:
            soup: BeautifulSoup object
            url: Page URL

        Returns:
            Metadata dictionary
        """
        metadata = {
            "url": url,
            "encoding": soup.original_encoding,
        }

        # Check for meta tags
        meta_tags = {
            "description": soup.find("meta", attrs={"name": "description"}),
            "keywords": soup.find("meta", attrs={"name": "keywords"}),
            "author": soup.find("meta", attrs={"name": "author"}),
            "og:title": soup.find("meta", attrs={"property": "og:title"}),
            "og:description": soup.find("meta", attrs={"property": "og:description"}),
            "og:image": soup.find("meta", attrs={"property": "og:image"}),
        }

        for key, tag in meta_tags.items():
            if tag and tag.get("content"):
                metadata[key] = tag["content"]

        # Extract canonical URL
        canonical = soup.find("link", attrs={"rel": "canonical"})
        if canonical and canonical.get("href"):
            metadata["canonical_url"] = urljoin(url, canonical["href"])

        # Extract language
        lang = soup.get("lang") or soup.get("xml:lang")
        if lang:
            metadata["language"] = lang

        return metadata

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """
        Extract page title.

        Args:
            soup: BeautifulSoup object

        Returns:
            Page title
        """
        title_tag = soup.find("title")
        return title_tag.get_text(strip=True) if title_tag else ""

    def _extract_main_text(self, soup: BeautifulSoup) -> str:
        """
        Extract main text content.

        Args:
            soup: BeautifulSoup object

        Returns:
            Main text as string
        """
        # Try to find the main content area
        main_content = (
            soup.find("article")
            or soup.find("main")
            or soup.find(
                "div", class_=re.compile(r"content|main|article", re.IGNORECASE)
            )
            or soup.find("body")
        )

        if not main_content:
            main_content = soup

        # Extract text, but skip headings and code blocks
        for tag in main_content.find_all(["h1", "h2", "h3", "pre", "code"]):
            tag.extract()

        # Get text and clean it up
        text = main_content.get_text(separator="\n", strip=True)

        # Clean up multiple newlines and spaces
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)

        return text

    def _extract_headings(self, soup: BeautifulSoup) -> list[tuple[int, str]]:
        """
        Extract all headings with their levels.

        Args:
            soup: BeautifulSoup object

        Returns:
            List of (level, text) tuples
        """
        headings = []

        for level in range(1, 5):  # h1 to h4
            for heading in soup.find_all(f"h{level}"):
                text = heading.get_text(strip=True)
                if text:
                    headings.append((level, text))

        return headings

    def _extract_code_blocks(self, soup: BeautifulSoup) -> list[str]:
        """
        Extract code blocks.

        Args:
            soup: BeautifulSoup object

        Returns:
            List of code block contents
        """
        code_blocks = []

        for code in soup.find_all(["pre", "code"]):
            code_text = code.get_text(separator="\n", strip=True)
            if code_text:
                code_blocks.append(code_text)

        return code_blocks

    def _extract_tables(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """
        Extract tables from the page.

        Args:
            soup: BeautifulSoup object

        Returns:
            List of tables with headers and rows
        """
        tables = []

        for table in soup.find_all("table"):
            rows = []
            headers = []

            # Extract headers
            header_row = table.find("tr")
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all("th")]

            # Extract data rows
            for row in table.find_all("tr")[1:] if header_row else table.find_all("tr"):
                cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
                if cells:
                    rows.append(cells)

            if headers or rows:
                tables.append(
                    {
                        "headers": headers,
                        "rows": rows,
                    }
                )

        return tables

    def clean_text(self, text: str) -> str:
        """
        Clean extracted text.

        Args:
            text: Raw text

        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r"\s+", " ", text)
        text = text.strip()

        # Limit length
        max_length = 10000
        if len(text) > max_length:
            text = text[:max_length] + "... (truncated)"

        return text

    def detect_document_type(self, url: str) -> str:
        """
        Detect the type of document at a URL.

        Args:
            url: URL to analyze

        Returns:
            Document type: "html", "github", "pdf", "markdown", etc.
        """
        url_lower = url.lower()

        # Check for PDF
        if any(ext in url_lower for ext in [".pdf", ".pdf?"]):
            return "pdf"

        # Check for Markdown
        if any(ext in url_lower for ext in [".md", ".markdown"]):
            return "markdown"

        # Check for GitHub
        if any(domain in url_lower for domain in DOCUMENT_PATTERNS["github"]):
            return "github"

        # Check for GitLab
        if any(domain in url_lower for domain in DOCUMENT_PATTERNS["gitlab"]):
            return "gitlab"

        # Check for documentation sites
        for doc_type, domains in DOCUMENT_PATTERNS["readthedocs"].items():
            if any(domain in url_lower for domain in domains):
                return "documentation"

        # Check for academic sites
        if any(domain in url_lower for domain in DOCUMENT_PATTERNS["academic"]):
            return "academic"

        # Check for government sites
        if any(domain in url_lower for domain in DOCUMENT_PATTERNS["gov"]):
            return "gov"

        # Default to HTML
        return "html"

    def get_extraction_strategy(self, content_type: str) -> str:
        """
        Get extraction strategy for a document type.

        Args:
            content_type: Document type

        Returns:
            Extraction strategy name
        """
        return DOCUMENT_STRATEGIES.get(content_type, "html")

    def _mark_progress(self, current: str, total: int = None):
        """Mark progress update (thread-safe)."""
        with self._lock:
            self._progress["current"] = current
            if total is not None:
                self._progress["total"] = total
            self._progress["completed"] += 1

    def _extract_github_readme(self, content: str, url: str) -> tuple[str, list[str]]:
        """
        Extract GitHub README content with code blocks.

        Args:
            content: Raw content from GitHub
            url: URL (should be a GitHub repo URL)

        Returns:
            Tuple of (text, code_blocks)
        """
        # Try to parse as markdown
        import re

        import markdown

        # Clean content
        content = re.sub(r"\r\n", "\n", content)
        content = re.sub(r"\n{3,}", "\n\n", content)

        # Parse markdown
        md = markdown.Markdown(
            extensions=["codehilite", "fenced_code", "tables"],
            extension_configs={"codehilite": {"linenums": True, "guess_lang": False}},
        )

        try:
            html = md.convert(content)
            # Extract code blocks
            code_blocks = []
            for match in re.finditer(
                r'<pre><code(?: class="language-(\w+)")?>(.*?)</code></pre>',
                html,
                re.DOTALL,
            ):
                lang = match.group(1) or "text"
                code = match.group(2)
                code_blocks.append(
                    {"language": lang, "content": code, "lines": code.count("\n") + 1}
                )
            return md.convert(content), code_blocks
        except Exception:
            # Fallback: basic markdown parsing
            text = content
            # Extract code blocks using simple regex
            code_blocks = []
            for match in re.finditer(r"```\s*(\w+)?\s*\n(.*?)```", content, re.DOTALL):
                lang = match.group(1) or "text"
                code = match.group(2).rstrip("\n")
                code_blocks.append(
                    {"language": lang, "content": code, "lines": code.count("\n") + 1}
                )
            return text, code_blocks

    def _extract_pdf(self, content: str, url: str) -> str:
        """
        Extract basic text from PDF.

        Args:
            content: PDF binary content
            url: PDF URL

        Returns:
            Extracted text
        """
        try:
            import pypdf

            pdf_reader = pypdf.PdfReader(content)
            text = ""

            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

            return text

        except ImportError:
            # Fallback: try to extract basic text
            try:
                return content.decode("utf-8", errors="ignore")
            except:
                return ""
        except Exception:
            return ""

    def _extract_markdown(self, content: str, url: str) -> str:
        """
        Extract Markdown content.

        Args:
            content: Markdown content
            url: URL

        Returns:
            Cleaned markdown
        """
        # Basic Markdown cleaning
        content = re.sub(r"\n{3,}", "\n\n", content)  # Normalize line breaks
        content = content.strip()

        # Remove comments
        content = re.sub(r"^\s*<!--.*?-->", "", content, flags=re.MULTILINE)

        return content

    async def read_pages_parallel(
        self,
        urls: list[str],
        timeout_seconds: float | None = None,
        max_workers: int = 5,
    ) -> list[PageContent]:
        """
        Read multiple pages concurrently with thread pool execution.

        Args:
            urls: List of URLs to read
            timeout_seconds: Optional timeout override
            max_workers: Maximum number of concurrent readers

        Returns:
            List of PageContent objects (in original URL order)
        """

        semaphore = asyncio.Semaphore(max_workers)

        async def read_single(url: str) -> tuple[int, PageContent]:
            async with semaphore:
                try:
                    content = self.read_page(url, timeout_seconds)
                    return urls.index(url), content  # Return original index
                except Exception as exc:
                    print(f"Failed to read {url}: {exc}")
                    return urls.index(url), None

        # Create tasks
        tasks = [read_single(url) for url in urls]

        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Sort by original index
        results.sort(key=lambda x: x[0] if isinstance(x, tuple) else 0)

        return [content for _, content in results if content is not None]

    # Progress callback type
    ResearchProgressCallback = Callable[[str, int, int], None]

    async def research_with_streaming(
        self,
        query: str,
        urls: list[str],
        callback: ResearchProgressCallback | None = None,
        timeout_seconds: float | None = None,
        max_workers: int = 5,
    ) -> tuple[list[PageContent], dict[str, str]]:
        """
        Read multiple pages with streaming progress updates.

        Args:
            query: Research query
            urls: List of URLs to read
            callback: Progress callback function(current_stage, completed, total)
            timeout_seconds: Optional timeout override
            max_workers: Maximum concurrent readers

        Yields:
            Progress updates: (current_stage, completed, total)

        Returns:
            Tuple of (pages, summary)
        """
        stages = ["Searching pages", "Reading content", "Processing text"]

        def update(stage: int, current: int, total: int):
            if callback:
                callback(stages[stage], current, total)

        # Search pages (simulated - actual search happens in research_agent)
        update(0, 0, len(urls))

        # Read pages
        pages = await self.read_pages_parallel(urls, timeout_seconds, max_workers)
        update(1, len(pages), len(urls))

        # Process text
        summaries = {}
        for i, page in enumerate(pages):
            update(2, i + 1, len(pages))
            summaries[page.url] = f"From {page.title}:\n{page.main_text[:200]}..."

        return pages, summaries
