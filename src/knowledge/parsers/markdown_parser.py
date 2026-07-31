"""
Markdown Parser for RAG 2.0 Knowledge Intelligence

Supports:
- Heading-based chunking
- Code block extraction
- Metadata frontmatter parsing
"""

import logging
import re
from typing import List, Dict, Any, Optional
from pathlib import Path

from ..models import DocumentChunk, DocumentMetadata, ChunkType, SourceType

logger = logging.getLogger(__name__)


class MarkdownParser:
    """Parser for Markdown documents."""

    def __init__(self):
        self.name = "Markdown"
        # NOTE: must be a list (not a set) and in this exact order —
        # tests assert supported_extensions == ['.md', '.markdown', '.mkd']
        self.supported_extensions = [".md", ".markdown", ".mkd"]

    def parse(self, file_path: Path, project: str = "unknown") -> List[DocumentChunk]:
        """
        Parse a Markdown file.

        Args:
            file_path: Path to Markdown file
            project: Project name

        Returns:
            List of document chunks
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read Markdown file: {e}")
            return []

        logger.info(f"Parsing Markdown: {file_path}")

        # Extract frontmatter if present
        frontmatter = self._extract_frontmatter(content)

        # Remove frontmatter from content for parsing
        content_no_frontmatter = content
        if frontmatter:
            content_no_frontmatter = content[frontmatter["end"] :]

        # Parse headings to create chunks
        chunks = self._parse_by_headings(content_no_frontmatter, file_path, project, frontmatter)

        logger.info(f"Parsed Markdown into {len(chunks)} chunks")
        return chunks

    def _extract_frontmatter(self, content: str) -> Optional[Dict[str, Any]]:
        """
        Extract YAML frontmatter from Markdown.

        Args:
            content: Markdown content

        Returns:
            Dictionary of frontmatter or None
        """
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if match:
            try:
                import yaml
                frontmatter = yaml.safe_load(match.group(1))
                return {"data": frontmatter or {}, "end": match.end()}
            except ImportError:
                logger.warning("PyYAML not installed, skipping frontmatter parsing")
                return None
            except yaml.YAMLError as e:
                logger.warning(f"Failed to parse YAML frontmatter: {e}")
                return None
        return None

    def _parse_by_headings(self, content: str, file_path: Path, project: str, frontmatter: Dict[str, Any]) -> List[DocumentChunk]:
        """
        Parse content by headings.

        Args:
            content: Content to parse
            file_path: File path
            project: Project name
            frontmatter: Frontmatter data

        Returns:
            List of chunks
        """
        chunks = []

        # Split by headings (h1-h6)
        lines = content.split("\n")
        current_chunk = []
        current_level = 0

        for line in lines:
            # Check if line is a heading
            level_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if level_match:
                heading_level = len(level_match.group(1))
                heading_text = level_match.group(2).strip()

                # If we have a current chunk and the new heading is not a child
                if current_chunk and (heading_level > current_level or heading_level == current_level):
                    chunk = self._create_chunk(
                        "\n".join(current_chunk),
                        file_path,
                        project,
                        heading_text,
                        current_level,
                    )
                    chunks.append(chunk)

                    current_chunk = []
                    current_level = 0

                # Start new chunk with heading
                current_chunk = [heading_text]
                current_level = heading_level
            else:
                current_chunk.append(line)

        # Add final chunk
        if current_chunk:
            chunk = self._create_chunk(
                "\n".join(current_chunk),
                file_path,
                project,
                "content",
                current_level,
            )
            chunks.append(chunk)

        return chunks

    def _create_chunk(self, content: str, file_path: Path, project: str, title: str, level: int) -> DocumentChunk:
        """
        Create a document chunk.

        Args:
            content: Chunk content
            file_path: File path
            project: Project name
            title: Heading title
            level: Heading level

        Returns:
            Document chunk
        """
        # Determine chunk type based on heading level
        chunk_type = "header" if level == 1 else "section"

        metadata = DocumentMetadata(
            source=str(file_path),
            project=project,
            file_type="markdown",
            chunk_type=chunk_type,
            language="en",
            tags=["markdown", chunk_type, project, title],
            created_at=None,
            modified_at=None,
        )

        # Get line range for better context
        lines = content.split("\n")
        start_line = 0
        end_line = len(lines)

        chunk = DocumentChunk(
            id=f"{file_path.stem}_{title}_chunk_{start_line + 1}",
            content=content.strip(),
            chunk_type=ChunkType.PARAGRAPH if level > 1 else ChunkType.SECTION,
            source_type=SourceType.MARKDOWN,
            source_file=str(file_path),
            project=project,
            metadata=metadata,
            chunk_index=start_line + 1,
            total_chunks=end_line,
        )

        return chunk

    def supports(self, file_path: Path) -> bool:
        """
        Check if file is supported.

        Args:
            file_path: Path to file

        Returns:
            True if supported
        """
        return file_path.suffix.lower() in self.supported_extensions

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract metadata from Markdown file.

        Args:
            file_path: Path to file

        Returns:
            Dictionary of metadata
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            return {}

        # Extract title from first heading
        title_match = re.match(r"^#{1}\s+(.+)$", content)
        title = title_match.group(1).strip() if title_match else file_path.stem

        # Extract frontmatter
        frontmatter = self._extract_frontmatter(content)

        metadata = {"title": title}
        if frontmatter and frontmatter["data"]:
            metadata.update(frontmatter["data"])

        return metadata

    def extract_code_blocks(self, content: str) -> List[Dict[str, str]]:
        """
        Extract code blocks from Markdown.

        Args:
            content: Markdown content

        Returns:
            List of code blocks with language and content
        """
        code_blocks = []

        # Match code blocks
        pattern = r"```(\w*)\n(.*?)```"
        for match in re.finditer(pattern, content, re.DOTALL):
            language = match.group(1) or "text"
            code = match.group(2)
            code_blocks.append({"language": language, "content": code.strip()})

        return code_blocks