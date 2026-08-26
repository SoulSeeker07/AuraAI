"""
Text Parser for RAG 2.0 Knowledge Intelligence

Supports:
- Plain text files
- Line-based chunking
- File metadata extraction
"""

import logging
from pathlib import Path

from ..models import ChunkType, DocumentChunk, DocumentMetadata, SourceType

logger = logging.getLogger(__name__)


class TxtParser:
    """Parse plain text files into chunks."""

    def __init__(self):
        self.supported_extensions = [".txt"]

    def supports(self, file_path: Path) -> bool:
        """Check if file type is supported."""
        return file_path.suffix.lower() in self.supported_extensions

    def parse(self, file_path: Path, chunk_size: int = 1000) -> list[DocumentChunk]:
        """
        Parse text file into chunks.

        Args:
            file_path: Path to the file
            chunk_size: Number of characters per chunk

        Returns:
            List of document chunks
        """
        chunks = []
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            if not content:
                return []

            # Get file metadata first
            file_meta_obj = self.extract_metadata(file_path)
            file_metadata = file_meta_obj.to_dict() if hasattr(file_meta_obj, "to_dict") else {}

            # Split content into chunks
            lines = content.split("\n")
            current_chunk = []
            current_length = 0
            chunk_id = 1

            for line in lines:
                line_length = len(line)

                # Add line to current chunk
                if current_length + line_length > chunk_size and current_chunk:
                    # Create a chunk if we have content
                    chunk_content = "\n".join(current_chunk)

                    chunk = DocumentChunk(
                        id=f"{file_path.stem}_chunk_{chunk_id}",
                        content=chunk_content,
                        chunk_type=ChunkType.TEXT,
                        source_type=SourceType.TXT,
                        source_file=str(file_path),
                        metadata={
                            **file_metadata,
                            "chunk_id": chunk_id,
                            "chunk_index": len(chunks),
                            "line_count": len(current_chunk),
                        },
                    )
                    chunks.append(chunk)

                    # Reset for next chunk
                    current_chunk = []
                    current_length = 0
                    chunk_id += 1

                current_chunk.append(line)
                current_length += line_length + 1  # +1 for newline

            # Don't forget the last chunk
            if current_chunk:
                chunk_content = "\n".join(current_chunk)

                chunk = DocumentChunk(
                    id=f"{file_path.stem}_chunk_{chunk_id}",
                    content=chunk_content,
                    chunk_type=ChunkType.TEXT,
                    source_type=SourceType.TXT,
                    source_file=str(file_path),
                    metadata={
                        **file_metadata,
                        "chunk_id": chunk_id,
                        "chunk_index": len(chunks),
                        "line_count": len(current_chunk),
                    },
                )
                chunks.append(chunk)

            return chunks

        except UnicodeDecodeError:
            # Try with UTF-8 fallback
            logger.warning(f"UTF-8 decoding failed for {file_path}, trying latin-1")
            try:
                with open(file_path, encoding="latin-1") as f:
                    content = f.read()

                if not content:
                    return []

                file_meta_obj = self.extract_metadata(file_path)
                file_metadata = file_meta_obj.to_dict() if hasattr(file_meta_obj, "to_dict") else {}

                lines = content.split("\n")
                current_chunk = []
                current_length = 0
                chunk_id = 1

                for line in lines:
                    line_length = len(line)

                    if current_length + line_length > chunk_size and current_chunk:
                        chunk_content = "\n".join(current_chunk)
                        chunk = DocumentChunk(
                            id=f"{file_path.stem}_chunk_{chunk_id}",
                            content=chunk_content,
                            chunk_type=ChunkType.TEXT,
                            source_type=SourceType.TXT,
                            source_file=str(file_path),
                            metadata={
                                **file_metadata,
                                "chunk_id": chunk_id,
                                "chunk_index": len(chunks),
                                "line_count": len(current_chunk),
                                "encoding": "latin-1",
                            },
                        )
                        chunks.append(chunk)

                        current_chunk = []
                        current_length = 0
                        chunk_id += 1

                    current_chunk.append(line)
                    current_length += line_length + 1

                if current_chunk:
                    chunk_content = "\n".join(current_chunk)
                    chunk = DocumentChunk(
                        id=f"{file_path.stem}_chunk_{chunk_id}",
                        content=chunk_content,
                        chunk_type=ChunkType.TEXT,
                        source_type=SourceType.TXT,
                        source_file=str(file_path),
                        metadata={
                            **file_metadata,
                            "chunk_id": chunk_id,
                            "chunk_index": len(chunks),
                            "line_count": len(current_chunk),
                            "encoding": "latin-1",
                        },
                    )
                    chunks.append(chunk)

                return chunks
            except Exception as e:
                logger.error(f"Failed to read {file_path} with any encoding: {e}")
                return []
        except Exception as e:
            logger.error(f"Error parsing text file {file_path}: {e}")
            return []

    def extract_metadata(self, file_path: Path) -> DocumentMetadata:
        """Extract metadata from text file."""
        from datetime import datetime
        metadata = DocumentMetadata(
            source=str(file_path),
            source_type=SourceType.TXT,
            title=file_path.stem,
            created_at=datetime.fromtimestamp(file_path.stat().st_ctime) if file_path.exists() else None,
            modified_at=datetime.fromtimestamp(file_path.stat().st_mtime) if file_path.exists() else None,
            size=file_path.stat().st_size if file_path.exists() else 0,
        )

        # Try to extract first line as title if it looks like a title
        try:
            with open(file_path, encoding="utf-8") as f:
                first_line = f.readline().strip()
                if first_line and len(first_line) > 10 and len(first_line) < 100:
                    # Check if it doesn't look like a path or absolute path
                    if "." not in first_line and not first_line.startswith("/"):
                        metadata.title = first_line
        except Exception as e:
            logger.debug(f"Could not extract title from {file_path}: {e}")

        return metadata
