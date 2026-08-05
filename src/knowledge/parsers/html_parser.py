"""
HTML Parser for RAG 2.0 Knowledge Intelligence

Supports:
- Section-level chunking
- Title/Heading extraction
- Paragraph extraction
"""

import logging
from pathlib import Path

from bs4 import BeautifulSoup

from ..models import DocumentChunk, DocumentMetadata

logger = logging.getLogger(__name__)


class HTMLParser:
    """Parse HTML files into structured chunks."""

    def __init__(self):
        self.supported_extensions = [".html", ".htm"]

    def supports(self, file_path: Path) -> bool:
        """Check if file type is supported."""
        return file_path.suffix.lower() in self.supported_extensions

    def parse(self, file_path: Path) -> list[DocumentChunk]:
        """Parse HTML file into document chunks."""
        chunks = []
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            soup = BeautifulSoup(content, "html.parser")

            # Get main content area
            main_content = self._get_main_content(soup)

            # Chunk by sections (headings)
            for heading in main_content.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
                section_title = heading.text.strip()

                # Get all elements after this heading until next heading
                section = heading.find_next_sibling()
                section_content = []

                while section and section.name not in [
                    "h1",
                    "h2",
                    "h3",
                    "h4",
                    "h5",
                    "h6",
                ]:
                    if section.name in ["p", "div", "section", "article", "main"]:
                        section_content.append(
                            section.get_text(separator="\n", strip=True)
                        )
                    section = section.find_next_sibling()

                # Skip empty sections
                if section_content:
                    full_content = f"## {section_title}\n\n" + "\n".join(
                        section_content
                    )
                    chunk = DocumentChunk(
                        id=f"{file_path.stem}_{section_title.replace(' ', '_')}",
                        content=full_content,
                        metadata=DocumentMetadata(
                            source=str(file_path),
                            file_type="html",
                            chunk_type="section",
                            chunk_id=section_title,
                            line_start=(
                                heading.start_line
                                if hasattr(heading, "start_line")
                                else 0
                            ),
                            line_end=(
                                heading.end_line if hasattr(heading, "end_line") else 0
                            ),
                            section_title=section_title,
                            heading_level=heading.name,
                            word_count=len(full_content.split()),
                        ),
                        embeddings=None,
                    )
                    chunks.append(chunk)

            # Add page content as fallback
            if not chunks:
                page_text = main_content.get_text(separator="\n", strip=True)
                if page_text.strip():
                    chunks.append(
                        DocumentChunk(
                            id=f"{file_path.stem}_page_1",
                            content=page_text,
                            metadata=DocumentMetadata(
                                source=str(file_path),
                                file_type="html",
                                chunk_type="page",
                                chunk_id="page",
                                line_start=1,
                                line_end=0,
                                word_count=len(page_text.split()),
                            ),
                            embeddings=None,
                        )
                    )

        except Exception as e:
            logger.error(f"Error parsing HTML file {file_path}: {e}")
            # Fall back to simple text extraction
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()
                chunks.append(
                    DocumentChunk(
                        id=f"{file_path.stem}_fallback",
                        content=content,
                        metadata=DocumentMetadata(
                            source=str(file_path),
                            file_type="html",
                            chunk_type="fallback",
                            chunk_id="fallback",
                            line_start=1,
                            line_end=len(content.split("\n")),
                        ),
                        embeddings=None,
                    )
                )
            except Exception:
                pass

        return chunks

    def extract_metadata(self, file_path: Path) -> DocumentMetadata:
        """Extract metadata from HTML file."""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            soup = BeautifulSoup(content, "html.parser")
            main_content = self._get_main_content(soup)

            # Count heading levels
            heading_counts = {}
            for h in main_content.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
                heading_counts[h.name] = heading_counts.get(h.name, 0) + 1

            # Get links and images
            link_count = len(main_content.find_all("a"))
            img_count = len(main_content.find_all("img"))

            return DocumentMetadata(
                source=str(file_path),
                file_type="html",
                chunk_type="file",
                chunk_id=file_path.stem,
                line_start=1,
                line_end=len(content.split("\n")),
                heading_levels=heading_counts,
                link_count=link_count,
                image_count=img_count,
            )
        except Exception as e:
            logger.error(f"Error extracting metadata from HTML file {file_path}: {e}")
            return DocumentMetadata(
                source=str(file_path),
                file_type="html",
                chunk_type="file",
                chunk_id=file_path.stem,
                line_start=1,
                line_end=0,
            )

    def _get_main_content(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Get main content area from HTML."""
        # Try to find main semantic elements
        for tag in ["main", "article", "content", "article"]:
            main = soup.find(tag)
            if main:
                return main

        # Try to find the body
        return soup.body or soup
