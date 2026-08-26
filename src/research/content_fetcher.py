"""
Content Fetcher

Fetches and parses content from URLs.
"""

import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_src_root = Path(__file__).resolve().parent.parent
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

try:
    from desktop.native.security.network_policy import SafeSession
except (ModuleNotFoundError, ImportError):
    try:
        from src.desktop.native.security.network_policy import SafeSession
    except Exception:
        SafeSession = requests.Session

from .models import Document

logger = logging.getLogger(__name__)


class ContentFetcher:
    """
    Fetches and parses content from URLs.

    Handles HTML parsing, content extraction, and fact extraction.
    """

    def __init__(self, timeout: int = 10, max_retries: int = 3):
        """
        Initialize the content fetcher.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = self._create_session()

    def _create_session(self):
        """Create a safe requests session with retry logic and network policy enforcement."""
        session = SafeSession() if SafeSession is not None else requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set user agent
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )

        return session

    def fetch(self, url: str) -> Document | None:
        """
        Fetch content from a URL and parse it.

        Args:
            url: URL to fetch

        Returns:
            Parsed Document or None
        """
        try:
            logger.debug(f"Fetching content from: {url}")

            # Make request
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            # Parse HTML
            return self._parse_response(
                url, response.text, response.headers.get("Content-Type", "")
            )

        except (requests.RequestException, PermissionError) as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

    def fetch_text(self, url: str) -> str | None:
        """
        Fetch only text content from a URL.

        Args:
            url: URL to fetch

        Returns:
            Text content or None
        """
        document = self.fetch(url)
        return document.content if document else None

    def fetch_summary(self, url: str, max_length: int = 300) -> str | None:
        """
        Fetch a summary of content from a URL.

        Args:
            url: URL to fetch
            max_length: Maximum summary length

        Returns:
            Summary text or None
        """
        document = self.fetch(url)
        return document.summary if document else None

    def _parse_response(
        self, url: str, html: str, content_type: str
    ) -> Document | None:
        """
        Parse a response into a Document.

        Args:
            url: URL
            html: HTML content
            content_type: Content type header

        Returns:
            Parsed Document
        """
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Extract title
            title = self._extract_title(soup)

            # Extract content
            content = self._extract_content(soup)

            # Extract author
            author = self._extract_author(soup)

            # Extract date
            date = self._extract_date(soup, content_type)

            # Extract content type
            content_type = self._determine_content_type(url, content_type, soup)

            # Create document
            document = Document(
                url=url,
                title=title,
                content=content,
                author=author,
                date=date,
                content_type=content_type,
            )

            # Generate summary
            document.summary = self._generate_summary(content)

            return document

        except Exception as e:
            logger.error(f"Failed to parse {url}: {e}")
            return Document(url=url, title=url, content="")

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract title from HTML."""
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.string.strip()
        return ""

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """
        Extract main content from HTML.

        Args:
            soup: BeautifulSoup object

        Returns:
            Extracted content
        """
        # Try to find main content areas
        content_selectors = [
            "article",
            "main",
            '[role="main"]',
            "#content",
            ".content",
            ".article-content",
            ".post-content",
            ".entry-content",
            'div[itemprop="articleBody"]',
        ]

        for selector in content_selectors:
            element = soup.select_one(selector)
            if element:
                return self._clean_text(element.get_text(separator="\n"))

        # Fallback: get body text
        body = soup.find("body")
        if body:
            return self._clean_text(body.get_text(separator="\n"))

        # Last resort: get all text
        return self._clean_text(soup.get_text(separator="\n"))

    def _extract_author(self, soup: BeautifulSoup) -> str | None:
        """Extract author from HTML."""
        # Try meta tags
        author_meta = soup.find("meta", attrs={"name": "author"})
        if author_meta:
            return author_meta.get("content", "").strip()

        # Try itemprop
        author_div = soup.find("div", itemprop="author")
        if author_div:
            return author_div.get_text(strip=True)

        return None

    def _extract_date(self, soup: BeautifulSoup, content_type: str) -> datetime | None:
        """Extract publication date from HTML."""
        # Try meta tags
        date_meta = soup.find("meta", attrs={"property": "article:published_time"})
        if date_meta:
            date_str = date_meta.get("content", "")
            return self._parse_date(date_str)

        date_meta = soup.find("meta", attrs={"name": "date"})
        if date_meta:
            date_str = date_meta.get("content", "")
            return self._parse_date(date_str)

        # Try time elements
        time_tag = soup.find("time")
        if time_tag:
            date_str = time_tag.get("datetime", "")
            return self._parse_date(date_str)

        # For documentation, try finding "last updated" text
        if "documentation" in content_type.lower():
            text = soup.get_text()
            match = re.search(
                r"(updated|modified)\s+(?:on\s+)?(\w{3},?\s+\d{1,2},?\s+\d{4})",
                text,
                re.IGNORECASE,
            )
            if match:
                return self._parse_date(match.group(2))

        return None

    def _determine_content_type(
        self, url: str, content_type: str, soup: BeautifulSoup
    ) -> str:
        """
        Determine content type from URL and HTML.

        Args:
            url: URL
            content_type: Content type header
            soup: BeautifulSoup object

        Returns:
            Content type string
        """
        url_lower = url.lower()
        content_type_lower = content_type.lower()

        # Check URL patterns
        if any(ext in url_lower for ext in [".pdf", ".doc", ".docx"]):
            return "document"

        if "github" in url_lower or "gist" in url_lower:
            return "documentation"

        if "wikipedia" in url_lower:
            return "reference"

        if "stackoverflow" in url_lower:
            return "technical"

        if "reddit.com" in url_lower:
            return "social"

        if "news" in url_lower or "blog" in url_lower:
            return "news"

        # Check HTML structure
        if soup.find("div", class_="code") or soup.find("pre"):
            return "documentation"

        if soup.find("h1") and soup.find("p"):
            return "article"

        return "article"

    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize text.

        Args:
            text: Raw text

        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r"\s+", " ", text)

        # Remove special characters but keep basic punctuation
        text = re.sub(r"[^\w\s.,;:!?\-]", "", text)

        # Remove leading/trailing whitespace
        text = text.strip()

        return text

    def _generate_summary(self, text: str) -> str:
        """
        Generate a summary of text.

        Args:
            text: Text to summarize

        Returns:
            Summary text
        """
        if not text:
            return ""

        # Simple heuristic: first 300 characters
        if len(text) <= 300:
            return text

        return text[:300] + "..."

    def _parse_date(self, date_str: str) -> datetime | None:
        """
        Parse a date string.

        Args:
            date_str: Date string

        Returns:
            datetime object or None
        """
        if not date_str:
            return None

        # Try common date formats
        formats = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%d %B, %Y",
            "%B %d, %Y",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None

    def extract_facts(self, document: Document, query: str) -> list[dict[str, Any]]:
        """
        Extract relevant facts from a document.

        Args:
            document: Document to extract facts from
            query: Query for context

        Returns:
            List of extracted facts
        """
        facts = []

        if not document or not document.content:
            return facts

        content = document.content.lower()
        query_lower = query.lower()

        # Extract facts about specific entities
        entities = self._extract_entities(content)

        for entity in entities:
            entity_lower = entity.lower()

            # Check if entity is relevant to query
            if any(word in entity_lower for word in query_lower.split()):
                facts.append(
                    {
                        "type": "entity",
                        "text": entity,
                        "context": content,
                        "confidence": 0.8,
                    }
                )

        # Extract numbers and statistics
        numbers = re.findall(r"\b\d+(?:\.\d+)?\b", content)
        for num in numbers[:5]:  # Limit to top 5 numbers
            facts.append(
                {
                    "type": "statistic",
                    "text": num,
                    "context": content,
                    "confidence": 0.7,
                }
            )

        # Extract dates
        dates = self._extract_dates(content)
        for date_str in dates[:3]:
            facts.append(
                {
                    "type": "date",
                    "text": date_str,
                    "context": content,
                    "confidence": 0.8,
                }
            )

        return facts

    def _extract_entities(self, text: str) -> list[str]:
        """
        Extract named entities from text.

        Args:
            text: Text to extract entities from

        Returns:
            List of entities
        """
        # Simple entity extraction using capitalization and common patterns
        entities = []

        # Capitalized words (potential proper nouns)
        capitalized = re.findall(r"\b[A-Z][a-z]+\b", text)
        entities.extend(capitalized)

        # Extract version numbers (e.g., "v1.0", "version 2.5")
        versions = re.findall(r"(?:version\s+)?v?(\d+(?:\.\d+)*)", text, re.IGNORECASE)
        entities.extend([f"v{v}" for v in versions])

        return list(set(entities))  # Remove duplicates

    def _extract_dates(self, text: str) -> list[str]:
        """
        Extract dates from text.

        Args:
            text: Text to extract dates from

        Returns:
            List of dates
        """
        dates = []

        # Common date patterns
        patterns = [
            r"\b(\d{4})-(\d{2})-(\d{2})\b",  # YYYY-MM-DD
            r"\b(\d{2})/(\d{2})/(\d{4})\b",  # MM/DD/YYYY
            r"\b(\d{2})-(\d{2})-(\d{4})\b",  # DD-MM-YYYY
            r"\b(\w+ \d{1,2}, \d{4})\b",  # Month Day, Year
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if len(match) == 3:
                    if pattern.startswith(r"\b(\d{4})"):
                        dates.append(f"{match[0]}-{match[1]}-{match[2]}")
                    else:
                        dates.append(match[0])

        return dates[:5]  # Limit to top 5 dates

    def is_valid_url(self, url: str) -> bool:
        """
        Check if a URL is valid.

        Args:
            url: URL to validate

        Returns:
            True if valid
        """
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False
