"""
Knowledge Chunker

Splits documents into chunks with appropriate strategies.
"""

import logging
import re
from typing import Any

from .models import ChunkType, DocumentChunk, SourceType

logger = logging.getLogger(__name__)


class Chunker:
    """
    Splits documents into chunks.
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 100):
        """
        Initialize chunker.

        Args:
            chunk_size: Maximum size of each chunk (characters)
            chunk_overlap: Overlap between chunks (characters)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.logger = logger

    def chunk(
        self,
        content: str,
        file_path: str,
        file_type: SourceType,
        metadata: dict[str, Any],
    ) -> list[DocumentChunk]:
        """
        Chunk document based on type and content.

        Args:
            content: Document content
            file_path: Source file path
            file_type: File type
            metadata: Existing metadata

        Returns:
            List of chunks
        """
        if not content or not content.strip():
            return []

        if file_type == SourceType.PYTHON:
            return self._chunk_python(content, file_path, metadata)
        elif file_type == SourceType.MARKDOWN:
            return self._chunk_markdown(content, file_path, metadata)
        elif file_type == SourceType.HTML:
            return self._chunk_html(content, file_path, metadata)
        elif file_type == SourceType.PDF:
            return self._chunk_pdf(content, file_path, metadata)
        elif file_type == SourceType.JSON:
            return self._chunk_json(content, file_path, metadata)
        elif file_type == SourceType.YAML:
            return self._chunk_yaml(content, file_path, metadata)
        elif file_type == SourceType.CSV:
            return self._chunk_csv(content, file_path, metadata)
        else:
            return self._chunk_text(content, file_path, metadata)

    def _chunk_text(
        self, content: str, file_path: str, metadata: dict[str, Any]
    ) -> list[DocumentChunk]:
        """
        Chunk plain text by paragraphs.

        Args:
            content: Text content
            file_path: File path
            metadata: Metadata

        Returns:
            List of chunks
        """
        chunks = []
        # Split into paragraphs
        paragraphs = content.split("\n\n")
        current_chunk = []
        current_content = ""
        chunk_id = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Check if adding this paragraph exceeds chunk size
            test_content = (current_content + "\n\n" + para).strip()
            if len(test_content) <= self.chunk_size and current_chunk:
                current_chunk.append(para)
                current_content = test_content
            else:
                # Save current chunk
                if current_chunk:
                    chunks.append(
                        self._create_chunk(
                            current_content,
                            file_path,
                            ChunkType.PARAGRAPH,
                            chunk_id,
                            metadata,
                        )
                    )
                    chunk_id += 1

                # Start new chunk with this paragraph
                current_chunk = [para]
                current_content = para

        # Save last chunk
        if current_chunk:
            chunks.append(
                self._create_chunk(
                    current_content, file_path, ChunkType.PARAGRAPH, chunk_id, metadata
                )
            )

        return chunks

    def _chunk_markdown(
        self, content: str, file_path: str, metadata: dict[str, Any]
    ) -> list[DocumentChunk]:
        """
        Chunk markdown by headings.

        Args:
            content: Markdown content
            file_path: File path
            metadata: Metadata

        Returns:
            List of chunks
        """
        chunks = []
        lines = content.split("\n")
        current_chunk_lines = []
        current_chunk = ""
        chunk_id = 0

        current_section = "Document"
        current_level = 0

        for line in lines:
            # Check for heading
            heading_match = re.match(r"^(#{1,6})\s+(.*)$", line)

            if heading_match:
                # Save previous chunk
                if current_chunk_lines:
                    chunks.append(
                        self._create_chunk(
                            current_chunk,
                            file_path,
                            ChunkType.SECTION,
                            chunk_id,
                            metadata,
                            current_section,
                            current_level,
                        )
                    )
                    chunk_id += 1

                # Start new section
                current_level = len(heading_match.group(1))
                current_section = heading_match.group(2).strip()
                current_chunk_lines = [line]
                current_chunk = line
            else:
                current_chunk_lines.append(line)
                current_chunk = "\n".join(current_chunk_lines)

        # Save last chunk
        if current_chunk_lines:
            chunks.append(
                self._create_chunk(
                    current_chunk,
                    file_path,
                    ChunkType.SECTION,
                    chunk_id,
                    metadata,
                    current_section,
                    current_level,
                )
            )

        return chunks

    def _chunk_python(
        self, content: str, file_path: str, metadata: dict[str, Any]
    ) -> list[DocumentChunk]:
        """
        Chunk Python code by functions and classes.

        Args:
            content: Python code
            file_path: File path
            metadata: Metadata

        Returns:
            List of chunks
        """
        chunks = []

        # Find all functions and classes
        class_pattern = re.compile(r"^class\s+(\w+)")
        function_pattern = re.compile(r"^def\s+(\w+)[\(\:]")

        current_block = []
        current_block_type = ChunkType.PARAGRAPH
        current_block_name = ""

        for line in content.split("\n"):
            line_stripped = line.strip()

            # Check for class definition
            class_match = class_pattern.match(line_stripped)
            if class_match:
                # Save previous block
                if current_block:
                    chunk = self._create_chunk(
                        "\n".join(current_block),
                        file_path,
                        current_block_type,
                        len(chunks),
                        metadata,
                        current_block_name,
                    )
                    chunks.append(chunk)

                # Start new block
                current_block_type = ChunkType.CLASS
                current_block_name = f"Class: {class_match.group(1)}"
                current_block = [line]
                continue

            # Check for function definition
            func_match = function_pattern.match(line_stripped)
            if func_match:
                # Save previous block
                if current_block:
                    chunk = self._create_chunk(
                        "\n".join(current_block),
                        file_path,
                        current_block_type,
                        len(chunks),
                        metadata,
                        current_block_name,
                    )
                    chunks.append(chunk)

                # Start new block
                current_block_type = ChunkType.FUNCTION
                current_block_name = f"Function: {func_match.group(1)}"
                current_block = [line]
                continue

            # Add line to current block
            if current_block:
                current_block.append(line)

        # Save last block
        if current_block:
            chunks.append(
                self._create_chunk(
                    "\n".join(current_block),
                    file_path,
                    current_block_type,
                    len(chunks),
                    metadata,
                    current_block_name,
                )
            )

        return chunks

    def _chunk_html(
        self, content: str, file_path: str, metadata: dict[str, Any]
    ) -> list[DocumentChunk]:
        """
        Chunk HTML by sections.

        Args:
            content: HTML content
            file_path: File path
            metadata: Metadata

        Returns:
            List of chunks
        """
        chunks = []
        lines = content.split("\n")

        current_chunk_lines = []
        current_chunk = ""
        chunk_id = 0

        for line in lines:
            # Check for section tags
            section_match = re.match(
                r"^\s*<(h[1-6]|section|article|div)[^>]*>(.*)$", line
            )

            if section_match:
                # Save previous chunk
                if current_chunk_lines:
                    title = section_match.group(2).strip()[:100]
                    chunks.append(
                        self._create_chunk(
                            current_chunk,
                            file_path,
                            ChunkType.SECTION,
                            chunk_id,
                            metadata,
                            title,
                        )
                    )
                    chunk_id += 1

                # Start new chunk with this line
                current_chunk_lines = [line]
                current_chunk = line
            else:
                current_chunk_lines.append(line)
                current_chunk = "\n".join(current_chunk_lines)

        # Save last chunk
        if current_chunk_lines:
            chunks.append(
                self._create_chunk(
                    current_chunk,
                    file_path,
                    ChunkType.SECTION,
                    chunk_id,
                    metadata,
                    "HTML Section",
                )
            )

        return chunks

    def _chunk_pdf(
        self, content: str, file_path: str, metadata: dict[str, Any]
    ) -> list[DocumentChunk]:
        """
        Chunk PDF by pages.

        Args:
            content: PDF content (usually text)
            file_path: File path
            metadata: Metadata

        Returns:
            List of chunks
        """
        chunks = []

        # PDF text is often already paginated, split by double newlines
        pages = content.split("\n\n")
        chunk_id = 0

        for i, page in enumerate(pages):
            page = page.strip()
            if not page:
                continue

            chunks.append(
                self._create_chunk(
                    page, file_path, ChunkType.PAGE, chunk_id, metadata, f"Page {i + 1}"
                )
            )
            chunk_id += 1

        return chunks

    def _chunk_json(
        self, content: str, file_path: str, metadata: dict[str, Any]
    ) -> list[DocumentChunk]:
        """
        Chunk JSON by structure.

        Args:
            content: JSON content
            file_path: File path
            metadata: Metadata

        Returns:
            List of chunks
        """
        chunks = []

        try:
            data = json.loads(content)

            # Try to structure by keys
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, (str, int, float, bool)):
                        chunk = self._create_chunk(
                            f"Key: {key}\nValue: {value}",
                            file_path,
                            ChunkType.SECTION,
                            len(chunks),
                            metadata,
                            f"JSON: {key}",
                        )
                        chunks.append(chunk)
                    elif isinstance(value, (list, dict)):
                        chunk = self._create_chunk(
                            json.dumps(value, indent=2),
                            file_path,
                            ChunkType.SECTION,
                            len(chunks),
                            metadata,
                            f"JSON: {key}",
                        )
                        chunks.append(chunk)
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    chunk = self._create_chunk(
                        json.dumps(item, indent=2),
                        file_path,
                        ChunkType.SECTION,
                        len(chunks),
                        metadata,
                        f"JSON Item {i + 1}",
                    )
                    chunks.append(chunk)
        except json.JSONDecodeError:
            # Fallback to text chunking
            chunks = self._chunk_text(content, file_path, metadata)

        return chunks

    def _chunk_yaml(
        self, content: str, file_path: str, metadata: dict[str, Any]
    ) -> list[DocumentChunk]:
        """
        Chunk YAML by sections.

        Args:
            content: YAML content
            file_path: File path
            metadata: Metadata

        Returns:
            List of chunks
        """
        chunks = []
        lines = content.split("\n")
        current_chunk_lines = []
        current_chunk = ""
        chunk_id = 0

        for line in lines:
            # Check for section headers
            if line.strip().startswith("#") or line.strip().startswith("-"):
                # Save previous chunk
                if current_chunk_lines:
                    chunks.append(
                        self._create_chunk(
                            current_chunk,
                            file_path,
                            ChunkType.SECTION,
                            chunk_id,
                            metadata,
                        )
                    )
                    chunk_id += 1

                # Start new chunk
                current_chunk_lines = [line]
                current_chunk = line
            else:
                current_chunk_lines.append(line)
                current_chunk = "\n".join(current_chunk_lines)

        # Save last chunk
        if current_chunk_lines:
            chunks.append(
                self._create_chunk(
                    current_chunk, file_path, ChunkType.SECTION, chunk_id, metadata
                )
            )

        return chunks

    def _chunk_csv(
        self, content: str, file_path: str, metadata: dict[str, Any]
    ) -> list[DocumentChunk]:
        """
        Chunk CSV by rows.

        Args:
            content: CSV content
            file_path: File path
            metadata: Metadata

        Returns:
            List of chunks
        """
        chunks = []
        lines = content.split("\n")

        # Skip header row
        start_idx = 1
        if len(lines) > 1:
            header = lines[0].strip()
            if header:
                start_idx = 1

        chunk_id = 0
        for i in range(start_idx, len(lines)):
            row = lines[i].strip()
            if row:
                chunks.append(
                    self._create_chunk(
                        row,
                        file_path,
                        ChunkType.ROW,
                        chunk_id,
                        metadata,
                        f"Row {i - start_idx + 1}",
                    )
                )
                chunk_id += 1

        return chunks

    def _create_chunk(
        self,
        content: str,
        file_path: str,
        chunk_type: ChunkType,
        chunk_id: int,
        metadata: dict[str, Any],
        title: str | None = None,
        level: int = 0,
    ) -> DocumentChunk:
        """
        Create a document chunk.

        Args:
            content: Chunk content
            file_path: Source file
            chunk_type: Type of chunk
            chunk_id: Chunk identifier
            metadata: Metadata dictionary
            title: Optional title
            level: Optional heading level

        Returns:
            DocumentChunk object
        """
        return DocumentChunk(
            id=f"{file_path}#{chunk_id}",
            content=content,
            chunk_type=chunk_type,
            source_type=metadata.get(
                SourceType.FILE_TYPE.value, SourceType.MARKDOWN.value
            ),
            source_file=file_path,
            project=metadata.get("project"),
            language=metadata.get("language"),
            language_family=metadata.get("language_family"),
            tags=metadata.get("tags", []),
            created_at=metadata.get("created_at", None),
            modified_at=metadata.get("modified_at", None),
            page_number=metadata.get("page_number"),
            line_number=chunk_id,
            importance=metadata.get("importance", 0.5),
            metadata=metadata,
        )
