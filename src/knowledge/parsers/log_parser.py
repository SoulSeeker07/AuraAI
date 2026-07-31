"""
Log Parser for RAG 2.0 Knowledge Intelligence

Supports:
- Log-level chunking
- Log level classification
- Timestamp extraction
"""

import logging
import re
from typing import List, Dict, Any, Optional
from pathlib import Path

from ..models import DocumentChunk, DocumentMetadata

logger = logging.getLogger(__name__)


class LogParser:
    """Parse log files into log-level chunks."""

    def __init__(self):
        self.supported_extensions = ['.log']

    def supports(self, file_path: Path) -> bool:
        """Check if file type is supported."""
        return file_path.suffix.lower() in self.supported_extensions

    def parse(self, file_path: Path) -> List[DocumentChunk]:
        """Parse log file into log-level chunks."""
        chunks = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Parse logs by level
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if not line.strip():
                    continue

                # Extract log level
                level, level_cleaned = self._extract_log_level(line)

                # Format log chunk
                chunk = DocumentChunk(
                    id=f"{file_path.stem}_log_{i}",
                    content=line,
                    metadata=DocumentMetadata(
                        source=str(file_path),
                        file_type="log",
                        chunk_type="log_entry",
                        chunk_id=f"log_{i}",
                        line_start=i + 1,
                        line_end=i + 1,
                        log_level=level,
                        log_level_cleaned=level_cleaned,
                        message=line.strip()
                    ),
                    embeddings=None
                )
                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Error parsing log file {file_path}: {e}")
            chunks.append(DocumentChunk(
                id=f"{file_path.stem}_error",
                content=f"Error parsing log: {e}",
                metadata=DocumentMetadata(
                    source=str(file_path),
                    file_type="log",
                    chunk_type="error",
                    chunk_id="error",
                    line_start=1,
                    line_end=1,
                    error_message=str(e)
                ),
                embeddings=None
            ))

        return chunks

    def extract_metadata(self, file_path: Path) -> DocumentMetadata:
        """Extract metadata from log file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Count log levels
            level_counts = {}
            for line in content.split('\n'):
                level, _ = self._extract_log_level(line)
                if level:
                    level_counts[level] = level_counts.get(level, 0) + 1

            return DocumentMetadata(
                source=str(file_path),
                file_type="log",
                chunk_type="file",
                chunk_id=file_path.stem,
                line_start=1,
                line_end=len(content.split('\n')),
                log_level_counts=level_counts,
                total_lines=len(content.split('\n')),
                loggable_lines=sum(level_counts.values())
            )
        except Exception as e:
            logger.error(f"Error extracting metadata from log file {file_path}: {e}")
            return DocumentMetadata(
                source=str(file_path),
                file_type="log",
                chunk_type="file",
                chunk_id=file_path.stem,
                line_start=1,
                line_end=0
            )

    def _extract_log_level(self, line: str) -> tuple[Optional[str], Optional[str]]:
        """
        Extract log level from line.
        Returns (level, level_cleaned) or (None, None) if not found.
        """
        # Common log level patterns
        patterns = [
            (r'(?i)^\[?(\w+)-', r'\1'),  # [ERROR], [DEBUG], etc.
            (r'(?i)^\w+ (\w+) [\d:]', r'\1'),  # ERROR 2023-01-01 10:00:00
            (r'(?i)^(\w+):\d+', r'\1'),  # ERROR: message
            (r'(?i)^\w{3} \d{1,2} \d{2}:\d{2}:\d{2} (\w+)', r'\1'),  # Mon Jan 01 10:00:00 ERROR
        ]

        for pattern, replacement in patterns:
            match = re.match(pattern, line)
            if match:
                level = match.group(1).upper()
                return level, replacement

        return None, None
