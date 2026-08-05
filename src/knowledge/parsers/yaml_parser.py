"""
YAML Parser for RAG 2.0 Knowledge Intelligence

Supports:
- Structure-based chunking
- Key-value pairs
- Nested mappings and sequences
"""

import logging
from pathlib import Path
from typing import Any

import yaml

from ..models import ChunkType, DocumentChunk, DocumentMetadata, SourceType

logger = logging.getLogger(__name__)


class YAMLParser:
    """Parse YAML files into structured chunks."""

    def __init__(self):
        self.supported_extensions = [".yaml", ".yml"]

    def supports(self, file_path: Path) -> bool:
        """Check if file type is supported."""
        return file_path.suffix.lower() in self.supported_extensions

    def parse(self, file_path: Path) -> list[DocumentChunk]:
        """Parse YAML file into structure chunks."""
        chunks = []
        try:
            with open(file_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if data is None:
                return []

            # Get file metadata first
            file_metadata = self.extract_metadata(file_path)

            # Chunk by top-level keys
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, (dict, list)):
                        chunk_content = yaml.dump(
                            {key: value}, default_flow_style=False, allow_unicode=True
                        )
                        chunk = DocumentChunk(
                            id=f"{file_path.stem}_{key}",
                            content=chunk_content,
                            chunk_type=ChunkType.PARAGRAPH,
                            source_type=SourceType.YAML,
                            source_file=str(file_path),
                            metadata=DocumentMetadata(
                                source=str(file_path),
                                file_type="yaml",
                                chunk_type="key_value",
                                chunk_id=key,
                                line_start=1,
                                line_end=1,
                                key_name=key,
                                value_type=type(value).__name__,
                                value_structure=self._get_value_structure(value),
                            ),
                            embeddings=None,
                        )
                        chunks.append(chunk)
                    else:
                        chunk = DocumentChunk(
                            id=f"{file_path.stem}_{key}",
                            content=f"{key}: {value}",
                            chunk_type=ChunkType.PARAGRAPH,
                            source_type=SourceType.YAML,
                            source_file=str(file_path),
                            metadata=DocumentMetadata(
                                source=str(file_path),
                                file_type="yaml",
                                chunk_type="key_value",
                                chunk_id=key,
                                line_start=1,
                                line_end=1,
                                key_name=key,
                                value=str(value),
                                value_type=type(value).__name__,
                            ),
                            embeddings=None,
                        )
                        chunks.append(chunk)
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    chunk = DocumentChunk(
                        id=f"{file_path.stem}_item_{i}",
                        content=yaml.dump(
                            item, default_flow_style=False, allow_unicode=True
                        ),
                        chunk_type=ChunkType.PARAGRAPH,
                        source_type=SourceType.YAML,
                        source_file=str(file_path),
                        metadata=DocumentMetadata(
                            source=str(file_path),
                            file_type="yaml",
                            chunk_type="list_item",
                            chunk_id=f"item_{i}",
                            line_start=i + 1,
                            line_end=i + 1,
                            item_index=i,
                            item_structure=self._get_value_structure(item),
                        ),
                        embeddings=None,
                    )
                    chunks.append(chunk)
            else:
                chunks.append(
                    DocumentChunk(
                        id=f"{file_path.stem}_root",
                        content=yaml.dump(
                            data, default_flow_style=False, allow_unicode=True
                        ),
                        chunk_type=ChunkType.PARAGRAPH,
                        source_type=SourceType.YAML,
                        source_file=str(file_path),
                        metadata=file_metadata,
                        embeddings=None,
                    )
                )

        except Exception as e:
            logger.error(f"Error parsing YAML file {file_path}: {e}")
            chunks.append(
                DocumentChunk(
                    id=f"{file_path.stem}_error",
                    content=f"Error parsing YAML: {e}",
                    chunk_type=ChunkType.PARAGRAPH,
                    source_type=SourceType.YAML,
                    source_file=str(file_path),
                    metadata=DocumentMetadata(
                        source=str(file_path),
                        file_type="yaml",
                        chunk_type="error",
                        chunk_id="error",
                        line_start=1,
                        line_end=1,
                        error_message=str(e),
                    ),
                    embeddings=None,
                )
            )

        return chunks

    def extract_metadata(self, file_path: Path) -> DocumentMetadata:
        """Extract metadata from YAML file."""
        try:
            with open(file_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if data is None:
                return DocumentMetadata(
                    source=str(file_path),
                    file_type="yaml",
                    chunk_type="file",
                    chunk_id=file_path.stem,
                    line_start=1,
                    line_end=0,
                )

            # Count nested levels
            depth = self._count_depth(data)

            # Count keys if dict
            key_count = len(data.keys()) if isinstance(data, dict) else 0
            item_count = len(data) if isinstance(data, list) else 0

            return DocumentMetadata(
                source=str(file_path),
                file_type="yaml",
                chunk_type="file",
                chunk_id=file_path.stem,
                line_start=1,
                line_end=1,
                key_count=key_count,
                item_count=item_count,
                max_depth=depth,
                root_type=type(data).__name__,
            )
        except Exception as e:
            logger.error(f"Error extracting metadata from YAML file {file_path}: {e}")
            return DocumentMetadata(
                source=str(file_path),
                file_type="yaml",
                chunk_type="file",
                chunk_id=file_path.stem,
                line_start=1,
                line_end=0,
            )

    def _get_value_structure(self, value: Any) -> str:
        """Get structure type of value."""
        if isinstance(value, dict):
            return "mapping"
        elif isinstance(value, list):
            return "sequence"
        else:
            return "primitive"

    def _count_depth(self, data: Any, current_depth: int = 0) -> int:
        """Count maximum nesting depth."""
        current_depth += 1
        if isinstance(data, dict):
            max_depth = current_depth
            for value in data.values():
                max_depth = max(max_depth, self._count_depth(value, current_depth))
            return max_depth
        elif isinstance(data, list):
            max_depth = current_depth
            for item in data:
                max_depth = max(max_depth, self._count_depth(item, current_depth))
            return max_depth
        else:
            return current_depth
