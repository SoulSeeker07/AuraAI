"""
Python Code Parser for RAG 2.0 Knowledge Intelligence

Supports:
- Function-level chunking
- Class-level chunking
- Docstring extraction
- Imports and dependencies
"""

import logging
import ast
from typing import List, Dict, Any, Optional
from pathlib import Path
import re

from ..models import DocumentChunk, DocumentMetadata, ChunkType, SourceType

logger = logging.getLogger(__name__)


class PythonParser:
    """Parse Python code into structured chunks."""

    def __init__(self):
        self.supported_extensions = ['.py', '.pyi']

    def supports(self, file_path: Path) -> bool:
        """Check if file type is supported."""
        return file_path.suffix.lower() in self.supported_extensions

    def parse(self, file_path: Path) -> List[DocumentChunk]:
        """Parse Python file into code chunks."""
        chunks = []
        content = ""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Build AST
            tree = ast.parse(content)

            # Track function/class definitions
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_name = node.name
                    func_start = node.lineno
                    func_end = node.end_lineno

                    # Get function body
                    func_source = self._extract_code_block(content, func_start, func_end)

                    # Extract docstring
                    docstring = ast.get_docstring(node)

                    chunk = DocumentChunk(
                        id=f"{file_path.stem}_{func_name}_{func_start}",
                        content=func_source,
                        chunk_type=ChunkType.FUNCTION,
                        source_type=SourceType.PYTHON,
                        source_file=str(file_path),
                        metadata=DocumentMetadata(
                            source=str(file_path),
                            file_type="python",
                            chunk_type="function",
                            chunk_id=f"{func_name}",
                            line_start=func_start,
                            line_end=func_end,
                            docstring=docstring,
                            function_name=func_name,
                            has_imports=self._has_imports(func_source),
                            is_class_method=self._is_class_method(tree, node)
                        ),
                    )
                    chunks.append(chunk)

                elif isinstance(node, ast.ClassDef):
                    class_name = node.name
                    class_start = node.lineno
                    class_end = node.end_lineno

                    # Get class body
                    class_source = self._extract_code_block(content, class_start, class_end)

                    # Extract docstring
                    docstring = ast.get_docstring(node)

                    # Extract methods
                    methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

                    chunk = DocumentChunk(
                        id=f"{file_path.stem}_{class_name}_{class_start}",
                        content=class_source,
                        chunk_type=ChunkType.CLASS,
                        source_type=SourceType.PYTHON,
                        source_file=str(file_path),
                        metadata=DocumentMetadata(
                            source=str(file_path),
                            file_type="python",
                            chunk_type="class",
                            chunk_id=f"{class_name}",
                            line_start=class_start,
                            line_end=class_end,
                            docstring=docstring,
                            class_name=class_name,
                            methods=methods,
                            num_methods=len(methods)
                        ),
                    )
                    chunks.append(chunk)

            if not chunks:
                # Fall back to file-level chunk if no functions/classes
                chunk = DocumentChunk(
                    id=f"{file_path.stem}_file_1",
                    content=content,
                    chunk_type=ChunkType.PARAGRAPH,
                    source_type=SourceType.PYTHON,
                    source_file=str(file_path),
                    metadata=DocumentMetadata(
                        source=str(file_path),
                        file_type="python",
                        chunk_type="file",
                        chunk_id=file_path.stem,
                        line_start=1,
                        line_end=len(content.split('\n')),
                        docstring=None
                    ),
                )
                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Error parsing Python file {file_path}: {e}")
            # Fall back to simple text parsing
            chunks = self._fallback_parse(content, file_path)

        return chunks

    def extract_metadata(self, file_path: Path) -> DocumentMetadata:
        """Extract metadata from Python file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)

            # Get imports
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    for alias in (node.names if isinstance(node, ast.Import) else node.names):
                        imports.append(alias.name)

            # Get function count
            function_count = sum(1 for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))

            # Get class count
            class_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))

            return DocumentMetadata(
                source=str(file_path),
                file_type="python",
                chunk_type="file",
                chunk_id=file_path.stem,
                line_start=1,
                line_end=len(content.split('\n')),
                function_count=function_count,
                class_count=class_count,
                import_count=len(imports),
                imports=imports
            )
        except Exception as e:
            logger.error(f"Error extracting metadata from Python file {file_path}: {e}")
            return DocumentMetadata(
                source=str(file_path),
                file_type="python",
                chunk_type="file",
                chunk_id=file_path.stem,
                line_start=1,
                line_end=len(content.split('\n'))
            )

    def _extract_code_block(self, content: str, start_line: int, end_line: int) -> str:
        """Extract code block from content."""
        lines = content.split('\n')
        return '\n'.join(lines[start_line - 1:end_line])

    def _has_imports(self, code: str) -> bool:
        """Check if code has imports."""
        return bool(re.search(r'^\s*import\s+', code, re.MULTILINE) or
                   re.search(r'^\s*from\s+', code, re.MULTILINE))

    def _is_class_method(self, tree: ast.Module, func_node: ast.FunctionDef) -> bool:
        """Check if function is a class method."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if item is func_node:
                        return True
        return False

    def _fallback_parse(self, content: str, file_path: Path) -> List[DocumentChunk]:
        """
        Fallback simple text parsing.

        Args:
            content: Raw file content (may be empty if the file couldn't be read)
            file_path: Path to the source file, needed to satisfy DocumentChunk's
                       required fields (chunk_type, source_type, source_file)
        """
        lines = content.split('\n') if content else ['']

        if len(lines) > 50:
            # Split into 50-line chunks
            chunks = []
            for i in range(0, len(lines), 50):
                chunk = DocumentChunk(
                    id=f"{file_path.stem}_fallback_{i}",
                    content='\n'.join(lines[i:i + 50]),
                    chunk_type=ChunkType.CODE_BLOCK,
                    source_type=SourceType.PYTHON,
                    source_file=str(file_path),
                    metadata=DocumentMetadata(
                        source=str(file_path),
                        file_type="python",
                        chunk_type="fallback",
                        chunk_id=f"chunk_{i}",
                        line_start=i + 1,
                        line_end=min(i + 50, len(lines))
                    ),
                )
                chunks.append(chunk)
            return chunks
        else:
            return [
                DocumentChunk(
                    id=f"{file_path.stem}_fallback_1",
                    content=content,
                    chunk_type=ChunkType.CODE_BLOCK,
                    source_type=SourceType.PYTHON,
                    source_file=str(file_path),
                    metadata=DocumentMetadata(
                        source=str(file_path),
                        file_type="python",
                        chunk_type="fallback",
                        chunk_id="chunk_1",
                        line_start=1,
                        line_end=len(lines)
                    ),
                )
            ]