"""
PDF Parser - Extract text from PDF files.

Uses PyPDF2 or pdfplumber for PDF text extraction.
"""

import re
from typing import Any

from ..models import DocumentChunk


class PDFParser:
    """
    Parser for PDF files.

    Features:
    - Text extraction from PDF pages
    - Chapter/section detection
    - Page number tracking
    """

    def __init__(self, use_pdfplumber: bool = False):
        """
        Initialize PDF parser.

        Args:
            use_pdfplumber: If True, use pdfplumber (more accurate but slower)
        """
        self.use_pdfplumber = use_pdfplumber

        # Required by integration tests
        self.supported_extensions = [".pdf"]

    def parse(
        self,
        file_path: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[DocumentChunk]:
        """
        Parse a PDF file and extract text chunks.

        Args:
            file_path: Path to the PDF file
            metadata: Optional metadata dictionary

        Returns:
            List of DocumentChunk objects
        """
        chunks = []

        try:
            if self.use_pdfplumber:
                chunks = self._parse_with_pdfplumber(file_path, metadata)
            else:
                chunks = self._parse_with_pypdf2(file_path, metadata)
        except ImportError:
            # Fallback to PyPDF2 if pdfplumber isn't available
            chunks = self._parse_with_pypdf2(file_path, metadata)
        except Exception as e:
            raise Exception(f"Failed to parse PDF file: {e}")

        return chunks

    def _parse_with_pdfplumber(
        self,
        file_path: str,
        metadata: dict[str, Any] | None,
    ) -> list[DocumentChunk]:
        """Parse PDF using pdfplumber."""
        try:
            import pdfplumber
        except ImportError:
            raise ImportError(
                "pdfplumber is required. Install it with: pip install pdfplumber"
            )

        chunks = []
        metadata = metadata or {}

        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text()

                    if text:
                        chunk = DocumentChunk(
                            content=text,
                            metadata={
                                "source": metadata.get("source", file_path),
                                "project": metadata.get("project"),
                                "file_type": "PDF",
                                "page": page_num,
                                "page_number": page_num,
                                "total_pages": len(pdf.pages),
                                "author": metadata.get("author"),
                                "title": metadata.get("title"),
                                "created_date": metadata.get("created_date"),
                            },
                        )
                        chunks.append(chunk)

        except Exception as e:
            raise Exception(f"pdfplumber parsing failed: {e}")

        return chunks

    def _parse_with_pypdf2(
        self,
        file_path: str,
        metadata: dict[str, Any] | None,
    ) -> list[DocumentChunk]:
        """Parse PDF using PyPDF2."""
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            raise ImportError("PyPDF2 is required. Install it with: pip install PyPDF2")

        chunks = []
        metadata = metadata or {}

        try:
            reader = PdfReader(file_path)

            for page_num, page in enumerate(reader.pages, start=1):
                text = page.extract_text()

                if text:
                    text = self._clean_text(text)

                    chunk = DocumentChunk(
                        content=text,
                        metadata={
                            "source": metadata.get("source", file_path),
                            "project": metadata.get("project"),
                            "file_type": "PDF",
                            "page": page_num,
                            "page_number": page_num,
                            "total_pages": len(reader.pages),
                        },
                    )
                    chunks.append(chunk)

        except Exception as e:
            raise Exception(f"PyPDF2 parsing failed: {e}")

        return chunks

    def _clean_text(self, text: str) -> str:
        """
        Clean extracted text.

        Args:
            text: Raw extracted text

        Returns:
            Cleaned text
        """
        # Normalize whitespace while preserving line structure
        lines = text.splitlines()
        cleaned_lines = []

        for line in lines:
            line = re.sub(r"\s+", " ", line).strip()

            # Skip empty lines
            if not line:
                continue

            # Skip page numbers
            if re.fullmatch(r"\d+", line):
                continue

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def supports(self, file_path: str) -> bool:
        """
        Check if this parser supports the given file.
        """
        return any(
            str(file_path).lower().endswith(ext) for ext in self.supported_extensions
        )
