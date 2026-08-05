"""
Parser Registry for RAG 2.0 Knowledge Intelligence

This module provides a central registry for all document parsers and
a unified interface for parsing documents of any type.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Type

from ..models import DocumentChunk, DocumentMetadata


class Parser(ABC):
    """Base parser interface."""

    @abstractmethod
    def supports(self, file_path: Path) -> bool:
        """Check if file type is supported."""
        pass

    @abstractmethod
    def parse(self, file_path: Path) -> list[DocumentChunk]:
        """Parse document into chunks."""
        pass

    @abstractmethod
    def extract_metadata(self, file_path: Path) -> DocumentMetadata:
        """Extract metadata from document."""
        pass


# Import all parsers
from .csv_parser import CSVParser
from .docx_parser import DOCXParser
from .html_parser import HTMLParser
from .json_parser import JSONParser
from .log_parser import LogParser
from .markdown_parser import MarkdownParser
from .pdf_parser import PDFParser
from .pptx_parser import PPTXParser
from .python_parser import PythonParser
from .toml_parser import TomlParser
from .txt_parser import TxtParser
from .yaml_parser import YAMLParser


class ParserRegistry:
    """Registry for all document parsers."""

    def __init__(self):
        self._parsers: list[type[Parser]] = []
        self._name_map: Dict[str, type[Parser]] = {}

    def register(self, parser_class: type[Parser]):
        """
        Register a parser class.

        Args:
            parser_class: The parser class to register
        """
        parser_instance = parser_class()
        parser_name = parser_instance.__class__.__name__.replace("Parser", "").lower()

        self._parsers.append(parser_class)
        self._name_map[parser_name] = parser_class

    def unregister(self, parser_name: str):
        """Unregister a parser by name."""
        if parser_name in self._name_map:
            parser_class = self._name_map[parser_name]
            self._parsers.remove(parser_class)
            del self._name_map[parser_name]

    def get_parser(self, file_path: Path) -> type[Parser] | None:
        """
        Get the appropriate parser for a file.

        Args:
            file_path: Path to the file

        Returns:
            Parser class if found, None otherwise
        """
        # Handle files with no extension
        if not file_path.suffix:
            logger.debug(f"No extension found for file: {file_path}")
            return None

        for parser_class in self._parsers:
            parser_instance = parser_class()
            if parser_instance.supports(file_path):
                return parser_class
        return None

    def parse(self, file_path: Path) -> list[DocumentChunk]:
        """
        Parse a file using the appropriate parser.

        Args:
            file_path: Path to the file

        Returns:
            List of document chunks

        Raises:
            ValueError: If no parser supports the file type
        """
        parser_class = self.get_parser(file_path)
        if parser_class:
            parser_instance = parser_class()
            return parser_instance.parse(file_path)
        else:
            suffix = file_path.suffix if file_path.suffix else "no extension"
            raise ValueError(
                f"No parser supports file type: '{suffix}' for file: {file_path}"
            )

    def extract_metadata(self, file_path: Path) -> DocumentMetadata:
        """
        Extract metadata from a file.

        Args:
            file_path: Path to the file

        Returns:
            Document metadata

        Raises:
            ValueError: If no parser supports the file type
        """
        parser_class = self.get_parser(file_path)
        if parser_class:
            parser_instance = parser_class()
            return parser_instance.extract_metadata(file_path)
        else:
            suffix = file_path.suffix if file_path.suffix else "no extension"
            raise ValueError(
                f"No parser supports file type: '{suffix}' for file: {file_path}"
            )

    def list_supported_extensions(self) -> list[str]:
        """Get list of all supported file extensions."""
        extensions = set()
        for parser_class in self._parsers:
            parser_instance = parser_class()
            extensions.update(parser_instance.supported_extensions)
        return sorted(list(extensions))

    def list_parsers(self) -> list[str]:
        """Get list of all registered parser names."""
        return sorted(self._name_map.keys())


# Create and register default parsers
registry = ParserRegistry()

# Register all parsers
registry.register(PDFParser)
registry.register(MarkdownParser)
registry.register(PythonParser)
registry.register(DOCXParser)
registry.register(PPTXParser)
registry.register(HTMLParser)
registry.register(JSONParser)
registry.register(YAMLParser)
registry.register(CSVParser)
registry.register(LogParser)
registry.register(TomlParser)
registry.register(TxtParser)


def get_parser_registry() -> ParserRegistry:
    """Get the global parser registry instance."""
    return registry
