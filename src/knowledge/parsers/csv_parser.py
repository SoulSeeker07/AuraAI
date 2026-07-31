"""
CSV Parser for RAG 2.0 Knowledge Intelligence

Supports:
- Row-level chunking
- Column metadata extraction
- Data analysis ready
"""

import logging
import csv
from typing import List, Dict, Any, Optional
from pathlib import Path
import io

from ..models import DocumentChunk, DocumentMetadata, ChunkType, SourceType

logger = logging.getLogger(__name__)


class CSVParser:
    """Parse CSV files into row-based chunks."""

    def __init__(self):
        self.supported_extensions = ['.csv']

    def supports(self, file_path: Path) -> bool:
        """Check if file type is supported."""
        return file_path.suffix.lower() in self.supported_extensions

    def parse(self, file_path: Path) -> List[DocumentChunk]:
        """Parse CSV file into row chunks."""
        chunks = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                if not reader.fieldnames:
                    # No header, create one
                    reader.fieldnames = [f"column_{i}" for i in range(10)]  # Limit to 10 columns
                    reader.line_num = 1

                header = reader.fieldnames

                for row_num, row in enumerate(reader, start=1):
                    # Create row chunk
                    row_content = {}
                    for col in header:
                        row_content[col] = row.get(col, '')

                    chunk = DocumentChunk(
                        id=f"{file_path.stem}_row_{row_num}",
                        content=self._format_row_as_text(row_num, header, row),
                        chunk_type=ChunkType.ROW,
                        source_type=SourceType.CSV,
                        source_file=str(file_path),
                        metadata=DocumentMetadata(
                            source=str(file_path),
                            file_type="csv",
                            chunk_type="row",
                            chunk_id=f"row_{row_num}",
                            line_start=row_num,
                            line_end=row_num + 1,
                            row_number=row_num,
                            column_names=header,
                            data=row,
                            data_size=len(header)
                        ),
                        embeddings=None
                    )
                    chunks.append(chunk)

        except Exception as e:
            logger.error(f"Error parsing CSV file {file_path}: {e}")
            chunks.append(DocumentChunk(
                id=f"{file_path.stem}_error",
                content=f"Error parsing CSV: {e}",
                chunk_type=ChunkType.PARAGRAPH,
                source_type=SourceType.CSV,
                source_file=str(file_path),
                metadata=DocumentMetadata(
                    source=str(file_path),
                    file_type="csv",
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
        """Extract metadata from CSV file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)

                header = next(reader, None)
                rows = list(reader)

            if not header:
                header = [f"column_{i}" for i in range(10)]

            return DocumentMetadata(
                source=str(file_path),
                file_type="csv",
                chunk_type="file",
                chunk_id=file_path.stem,
                line_start=1,
                line_end=len(rows) + 1,
                column_count=len(header),
                row_count=len(rows),
                data_size=len(header) * len(rows),
                column_names=header
            )
        except Exception as e:
            logger.error(f"Error extracting metadata from CSV file {file_path}: {e}")
            return DocumentMetadata(
                source=str(file_path),
                file_type="csv",
                chunk_type="file",
                chunk_id=file_path.stem,
                line_start=1,
                line_end=0
            )

    def _format_row_as_text(self, row_num: int, header: List[str], row: Dict[str, Any]) -> str:
        """Format row as text string."""
        lines = [f"Row {row_num}:"]
        for col in header:
            value = row.get(col, '')
            lines.append(f"  {col}: {value}")
        return '\n'.join(lines)
