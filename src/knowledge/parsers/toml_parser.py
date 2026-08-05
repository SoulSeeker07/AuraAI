"""
TOML Parser for RAG 2.0 Knowledge Intelligence

Supports:
- Structure-based chunking of TOML data
- Key-value pairs
- Nested tables and arrays
- Compatible with Python 3.11+ tomllib
"""

import logging
import tomllib
from pathlib import Path
from typing import Any

from ..models import ChunkType, DocumentChunk, DocumentMetadata, SourceType

logger = logging.getLogger(__name__)


class TomlParser:
    """Parse TOML files into structured chunks."""

    def __init__(self):
        self.supported_extensions = [".toml"]

    def supports(self, file_path: Path) -> bool:
        """Check if file type is supported."""
        return file_path.suffix.lower() in self.supported_extensions

    def parse(self, file_path: Path) -> list[DocumentChunk]:
        """Parse TOML file into structure chunks."""
        chunks = []
        try:
            with open(file_path, "rb") as f:
                data = tomllib.load(f)

            if data is None:
                return []

            # Get file metadata first
            file_metadata = self.extract_metadata(file_path)

            # Chunk by top-level keys
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, (dict, list)):
                        chunk_content = self._format_chunk(key, value)
                        chunk = DocumentChunk(
                            id=f"{file_path.stem}_{key}",
                            content=chunk_content,
                            type=ChunkType.SECTION,
                            metadata={
                                **file_metadata,
                                "chunk_key": key,
                                "chunk_type": type(value).__name__,
                            },
                        )
                        chunks.append(chunk)
                    else:
                        # Simple key-value pairs
                        chunk_content = f"{key} = {value}"
                        chunk = DocumentChunk(
                            id=f"{file_path.stem}_{key}",
                            content=chunk_content,
                            type=ChunkType.TEXT,
                            metadata={
                                **file_metadata,
                                "chunk_key": key,
                                "chunk_type": type(value).__name__,
                            },
                        )
                        chunks.append(chunk)
            elif isinstance(data, list):
                # Handle arrays as a single chunk
                chunk_content = self._format_chunk("items", data)
                chunk = DocumentChunk(
                    id=f"{file_path.stem}_items",
                    content=chunk_content,
                    chunk_type=ChunkType.SECTION,
                    source_type=SourceType.TOML,
                    source_file=str(file_path),
                    metadata={
                        **file_metadata,
                        "chunk_key": "items",
                        "chunk_type": "list",
                    },
                )
                chunks.append(chunk)
            else:
                # Handle primitive values
                chunk = DocumentChunk(
                    id=f"{file_path.stem}_root",
                    content=str(data),
                    chunk_type=ChunkType.TEXT,
                    source_type=SourceType.TOML,
                    source_file=str(file_path),
                    metadata=file_metadata,
                )
                chunks.append(chunk)

            return chunks

        except Exception as e:
            logger.error(f"Error parsing TOML file {file_path}: {e}")
            return []

    def _format_chunk(self, key: str, value: Any) -> str:
        """Format a chunk's content."""
        if isinstance(value, list):
            items_str = ", ".join(str(item) for item in value)
            return f"{key} = [{items_str}]"
        else:
            return f"{key} = {value}"

    def extract_metadata(self, file_path: Path) -> DocumentMetadata:
        """Extract metadata from TOML file."""
        try:
            with open(file_path, "rb") as f:
                data = tomllib.load(f)

            metadata = DocumentMetadata(
                source=file_path,
                source_type=SourceType.TOML,
                title=file_path.stem,
                created_at=file_path.stat().st_ctime if file_path.exists() else None,
                modified_at=file_path.stat().st_mtime if file_path.exists() else None,
                size=file_path.stat().st_size if file_path.exists() else 0,
            )

            # Extract metadata from TOML file if present
            if isinstance(data, dict):
                if "name" in data:
                    metadata.title = data["name"]
                if "description" in data:
                    metadata.description = str(data["description"])
                # Version is stored in extra_metadata for extensibility
                if "version" in data:
                    metadata.extra_metadata["version"] = str(data["version"])

            return metadata

        except Exception as e:
            logger.error(f"Error extracting metadata from {file_path}: {e}")
            return DocumentMetadata(
                source=file_path,
                source_type=SourceType.TOML,
                title=file_path.stem,
            )
