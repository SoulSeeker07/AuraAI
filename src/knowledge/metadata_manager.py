"""
Knowledge Metadata Manager

Extracts and manages metadata from documents.
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Any

from .models import MetadataType, SourceType

logger = logging.getLogger(__name__)


class MetadataManager:
    """
    Extracts metadata from documents.
    """

    def __init__(self):
        """Initialize metadata manager."""
        self.logger = logger

    def extract_metadata(
        self, file_path: str, file_type: SourceType, content: str
    ) -> dict[str, Any]:
        """
        Extract metadata from document.

        Args:
            file_path: Path to the document
            file_type: Type of the document
            content: Document content

        Returns:
            Dictionary of metadata
        """
        metadata = {
            MetadataType.SOURCE.value: file_path,
            MetadataType.FILE_TYPE.value: file_type.value,
            MetadataType.CREATED.value: datetime.now().isoformat(),
            MetadataType.MODIFIED.value: datetime.now().isoformat(),
        }

        # Extract based on file type
        if file_type == SourceType.PDF:
            metadata = self._extract_pdf_metadata(file_path, content, metadata)
        elif file_type == SourceType.MARKDOWN:
            metadata = self._extract_markdown_metadata(content, metadata)
        elif file_type == SourceType.PYTHON:
            metadata = self._extract_python_metadata(content, metadata)
        elif file_type == SourceType.WORD:
            metadata = self._extract_docx_metadata(file_path, metadata)
        elif file_type == SourceType.POWERPOINT:
            metadata = self._extract_pptx_metadata(file_path, metadata)
        elif file_type == SourceType.HTML:
            metadata = self._extract_html_metadata(content, metadata)
        elif file_type == SourceType.JSON:
            metadata = self._extract_json_metadata(content, metadata)
        elif file_type == SourceType.YAML:
            metadata = self._extract_yaml_metadata(content, metadata)
        elif file_type == SourceType.CSV:
            metadata = self._extract_csv_metadata(content, metadata)
        else:
            # Generic metadata
            metadata = self._extract_generic_metadata(content, metadata)

        return metadata

    def _extract_pdf_metadata(
        self, file_path: str, content: str, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract PDF metadata."""
        metadata[MetadataType.CHUNK_TYPE.value] = "page"
        metadata[MetadataType.IMPORTANCE.value] = 0.7
        return metadata

    def _extract_markdown_metadata(
        self, content: str, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract markdown metadata."""
        lines = content.split("\n")

        # Extract title from first heading
        for line in lines[:5]:
            if line.startswith("# "):
                metadata[MetadataType.TITLE.value] = line[2:].strip()
                break

        # Extract tags from frontmatter
        in_frontmatter = False
        frontmatter = {}
        for line in lines[:10]:
            if line.strip() == "---":
                if in_frontmatter:
                    break
                in_frontmatter = True
            elif in_frontmatter:
                if ":" in line:
                    key, value = line.split(":", 1)
                    frontmatter[key.strip().lower()] = value.strip()

        if "tags" in frontmatter:
            metadata[MetadataType.TAGS.value] = frontmatter["tags"].split(",")

        if "project" in frontmatter:
            metadata[MetadataType.PROJECT.value] = frontmatter["project"]

        if "author" in frontmatter:
            metadata[MetadataType.AUTHOR.value] = frontmatter["author"]

        metadata[MetadataType.CHUNK_TYPE.value] = "section"
        metadata[MetadataType.IMPORTANCE.value] = 0.8
        return metadata

    def _extract_python_metadata(
        self, content: str, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract Python code metadata."""
        lines = content.split("\n")

        # Extract class names
        classes = []
        functions = []
        for line in lines:
            if line.strip().startswith("class "):
                class_name = line.split("class ")[1].split("(")[0].strip()
                classes.append(class_name)
            elif line.strip().startswith("def "):
                func_name = line.split("def ")[1].split("(")[0].strip()
                functions.append(func_name)

        if classes:
            metadata[MetadataType.CHUNK_TYPE.value] = "class"
            metadata[MetadataType.CHUNK_TYPE.value] = "function"
            metadata[MetadataType.TAGS.value] = classes + functions

        metadata[MetadataType.CHUNK_TYPE.value] = "function"
        metadata[MetadataType.IMPORTANCE.value] = 0.9
        return metadata

    def _extract_docx_metadata(
        self, file_path: str, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract DOCX metadata."""
        metadata[MetadataType.CHUNK_TYPE.value] = "page"
        metadata[MetadataType.IMPORTANCE.value] = 0.6
        return metadata

    def _extract_pptx_metadata(
        self, file_path: str, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract PPTX metadata."""
        metadata[MetadataType.CHUNK_TYPE.value] = "slide"
        metadata[MetadataType.IMPORTANCE.value] = 0.5
        return metadata

    def _extract_html_metadata(
        self, content: str, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract HTML metadata."""
        lines = content.split("\n")

        # Extract title from <title> tag
        for line in lines:
            if "<title>" in line and "</title>" in line:
                title = line[line.find("<title>") + 7 : line.find("</title>")]
                metadata[MetadataType.TITLE.value] = title.strip()
                break

        # Check for meta description
        for line in lines:
            if '<meta name="description"' in line:
                if "content=" in line:
                    content_attr = line.split('content="')[1].split('"')[0]
                    metadata[MetadataType.DESCRIPTION.value] = content_attr
                break

        metadata[MetadataType.CHUNK_TYPE.value] = "section"
        metadata[MetadataType.IMPORTANCE.value] = 0.7
        return metadata

    def _extract_json_metadata(
        self, content: str, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract JSON metadata."""
        try:
            data = json.loads(content)
            metadata[MetadataType.PROJECT.value] = "json"
            metadata[MetadataType.CHUNK_TYPE.value] = "section"
        except json.JSONDecodeError:
            pass

        return metadata

    def _extract_yaml_metadata(
        self, content: str, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract YAML metadata."""
        lines = content.split("\n")

        in_frontmatter = False
        frontmatter = {}
        for line in lines[:10]:
            if line.strip() == "---":
                if in_frontmatter:
                    break
                in_frontmatter = True
            elif in_frontmatter:
                if ":" in line:
                    key, value = line.split(":", 1)
                    frontmatter[key.strip().lower()] = value.strip()

        if "tags" in frontmatter:
            metadata[MetadataType.TAGS.value] = frontmatter["tags"].split(",")

        if "project" in frontmatter:
            metadata[MetadataType.PROJECT.value] = frontmatter["project"]

        metadata[MetadataType.CHUNK_TYPE.value] = "section"
        return metadata

    def _extract_csv_metadata(
        self, content: str, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract CSV metadata."""
        lines = content.split("\n")
        if len(lines) > 1:
            metadata[MetadataType.CHUNK_TYPE.value] = "table"
            metadata[MetadataType.CHUNK_TYPE.value] = "row"
        return metadata

    def _extract_generic_metadata(
        self, content: str, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract generic metadata."""
        lines = content.split("\n")

        # Extract title from first non-empty line
        for line in lines[:3]:
            if line.strip():
                metadata[MetadataType.TITLE.value] = line.strip()[:100]
                break

        metadata[MetadataType.CHUNK_TYPE.value] = "paragraph"
        metadata[MetadataType.IMPORTANCE.value] = 0.4
        return metadata

    def get_file_hash(self, file_path: str) -> str:
        """
        Get file hash for change detection.

        Args:
            file_path: Path to file

        Returns:
            SHA256 hash
        """
        try:
            hash_obj = hashlib.sha256()
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating file hash: {e}")
            return ""

    def normalize_tags(self, tags: list[str]) -> list[str]:
        """
        Normalize tags (lowercase, remove duplicates).

        Args:
            tags: List of tags

        Returns:
            Normalized list of tags
        """
        return list(set(tag.lower().strip() for tag in tags if tag.strip()))

    def get_language_family(self, language: str | None) -> str:
        """
        Get language family from language code.

        Args:
            language: Language code

        Returns:
            Language family
        """
        if not language:
            return "unknown"

        language_lower = language.lower()

        # Programming languages
        programming = [
            "python",
            "javascript",
            "typescript",
            "java",
            "csharp",
            "cpp",
            "c",
            "rust",
            "go",
            "ruby",
            "php",
            "swift",
            "kotlin",
            "scala",
            "haskell",
            "r",
            "matlab",
        ]

        if language_lower in programming:
            return "programming"

        # Natural languages
        languages = {
            "en": "english",
            "es": "spanish",
            "fr": "french",
            "de": "german",
            "zh": "chinese",
            "ja": "japanese",
            "ko": "korean",
            "ru": "russian",
            "ar": "arabic",
            "pt": "portuguese",
            "it": "italian",
        }

        for code, lang in languages.items():
            if code in language_lower or lang in language_lower:
                return lang

        return "other"
