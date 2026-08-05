"""
AST Manager

Parses and analyzes source code using Abstract Syntax Trees (ASTs).

This manager enables Aura to understand code at the structural level rather than
just text level, supporting various programming languages through their native ASTs
or language server protocols.
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ASTNode:
    """Represents a node in the AST."""

    type: str  # e.g., "FunctionDef", "ClassDef", "Import", "Module"
    name: str = ""
    value: Any = None
    children: list[ASTNode] = field(default_factory=list)
    line: int = 0
    column: int = 0
    docstring: str | None = None
    decorators: list[str] = field(default_factory=list)
    return_type: str | None = None
    parameters: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    annotations: dict[str, str] = field(default_factory=dict)
    scope: str | None = None  # Module, class, function
    is_definition: bool = False
    references: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert AST node to dictionary."""
        return {
            "type": self.type,
            "name": self.name,
            "value": self.value,
            "line": self.line,
            "column": self.column,
            "docstring": self.docstring,
            "decorators": self.decorators,
            "return_type": self.return_type,
            "parameters": self.parameters,
            "scope": self.scope,
            "is_definition": self.is_definition,
            "references": self.references,
        }

    def find_by_name(self, name: str) -> ASTNode | None:
        """Find a child node by name."""
        if self.name == name:
            return self
        for child in self.children:
            found = child.find_by_name(name)
            if found:
                return found
        return None

    def find_by_type(self, type_: str) -> list[ASTNode]:
        """Find all child nodes by type."""
        result = []
        if self.type == type_:
            result.append(self)
        for child in self.children:
            result.extend(child.find_by_type(type_))
        return result


@dataclass
class ASTFile:
    """Represents a parsed source file."""

    path: Path
    root: ASTNode
    language: str
    imports: list[str]
    classes: list[ASTNode]
    functions: list[ASTNode]
    constants: list[ASTNode]
    line_count: int
    comment_count: int
    docstring_count: int

    def get_all_symbols(self) -> list[str]:
        """Get all symbol names in the file."""
        symbols = []
        for node in self.classes + self.functions + self.constants:
            symbols.append(node.name)
        return symbols


class ASTManager:
    """
    Manages AST parsing and code analysis.

    Supports multiple languages through native parsers and LSP.

    Usage:
        manager = ASTManager(repository_path="/path/to/repo")

        # Parse a Python file
        ast_file = manager.parse_file("src/main.py")

        # Get all functions
        functions = ast_file.root.find_by_type("FunctionDef")

        # Find a specific symbol
        class_def = ast_file.root.find_by_name("MyClass")

        # Get file structure
        structure = manager.get_file_structure("src/main.py")
    """

    def __init__(
        self, repository_path: Path, enable_lsp: bool = True, language: str = "auto"
    ):
        """
        Initialize the AST Manager.

        Args:
            repository_path: Path to the repository
            enable_lsp: Whether to use LSP for language-specific intelligence
            language: Language to focus on ("python", "typescript", etc.) or "auto"
        """
        self.repository_path = Path(repository_path).resolve()
        self.enable_lsp = enable_lsp
        self.language = language
        self._cache: dict[Path, ASTFile] = {}

    def parse_file(self, file_path: str) -> ASTFile:
        """
        Parse a file and generate an AST.

        Args:
            file_path: Path to the file (relative to repository root)

        Returns:
            ASTFile object
        """
        full_path = self.repository_path / file_path

        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {full_path}")

        # Check cache
        if full_path in self._cache:
            logger.debug(f"Using cached AST for: {file_path}")
            return self._cache[full_path]

        logger.info(f"Parsing file: {file_path}")

        # Determine language
        if self.language == "auto":
            ext = full_path.suffix
            lang_map = {
                ".py": "python",
                ".ts": "typescript",
                ".tsx": "typescript",
                ".js": "javascript",
                ".jsx": "javascript",
                ".java": "java",
                ".cpp": "cpp",
                ".cc": "cpp",
                ".cxx": "cpp",
                ".c": "c",
                ".go": "go",
                ".rs": "rust",
                ".cs": "csharp",
                ".kt": "kotlin",
            }
            language = lang_map.get(ext, "unknown")
        else:
            language = self.language

        # Parse based on language
        if language == "python":
            ast_file = self._parse_python(full_path)
        elif language == "typescript":
            ast_file = self._parse_javascript(full_path)
        elif language == "javascript":
            ast_file = self._parse_javascript(full_path)
        elif language == "java":
            ast_file = self._parse_java(full_path)
        elif language == "cpp":
            ast_file = self._parse_cpp(full_path)
        elif language == "go":
            ast_file = self._parse_go(full_path)
        elif language == "rust":
            ast_file = self._parse_rust(full_path)
        elif language == "csharp":
            ast_file = self._parse_csharp(full_path)
        elif language == "kotlin":
            ast_file = self._parse_kotlin(full_path)
        else:
            logger.warning(f"Unsupported language: {language}")
            ast_file = ASTFile(
                path=full_path,
                root=ASTNode(type="Unknown", name="unknown"),
                language=language,
                imports=[],
                classes=[],
                functions=[],
                constants=[],
                line_count=0,
                comment_count=0,
                docstring_count=0,
            )

        # Cache the result
        self._cache[full_path] = ast_file

        return ast_file

    def _parse_python(self, file_path: Path) -> ASTFile:
        """Parse a Python file."""
        with open(file_path, encoding="utf-8") as f:
            source = f.read()

        # Parse AST
        tree = ast.parse(source, filename=str(file_path))

        # Count lines and comments
        line_count = len(source.splitlines())
        comment_count = source.count("#")

        # Convert to our AST format
        root = self._python_ast_to_node(tree)

        # Collect symbols
        imports = []
        classes = []
        functions = []
        constants = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")
            elif isinstance(node, ast.ClassDef):
                classes.append(root.find_by_name(node.name))
            elif isinstance(node, ast.FunctionDef):
                functions.append(root.find_by_name(node.name))
            elif isinstance(node, ast.Assign) and len(node.targets) == 1:
                if isinstance(node.targets[0], ast.Name):
                    constants.append(root.find_by_name(node.targets[0].id))

        return ASTFile(
            path=file_path,
            root=root,
            language="python",
            imports=imports,
            classes=classes,
            functions=functions,
            constants=constants,
            line_count=line_count,
            comment_count=comment_count,
            docstring_count=sum(
                1
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.ClassDef))
                and ast.get_docstring(node)
            ),
        )

    def _parse_javascript(self, file_path: Path) -> ASTFile:
        """Parse a JavaScript/TypeScript file."""
        # For JavaScript, we can use js2py or similar
        # For now, use a simple approach with regex
        with open(file_path, encoding="utf-8") as f:
            source = f.read()

        line_count = len(source.splitlines())
        comment_count = len(re.findall(r"//.*", source)) + len(
            re.findall(r"/\*.*?\*/", source, re.DOTALL)
        )

        # Build a simple AST structure
        root = ASTNode(type="Program", name="root")

        # Extract functions (simplified)
        func_pattern = r"function\s+(\w+)\s*\([^)]*\)"
        class_pattern = r"class\s+(\w+)"

        for match in re.finditer(func_pattern, source):
            func_node = ASTNode(
                type="FunctionDeclaration",
                name=match.group(1),
                line=source[: match.start()].count("\n") + 1,
            )
            root.children.append(func_node)

        for match in re.finditer(class_pattern, source):
            class_node = ASTNode(
                type="ClassDeclaration",
                name=match.group(1),
                line=source[: match.start()].count("\n") + 1,
            )
            root.children.append(class_node)

        return ASTFile(
            path=file_path,
            root=root,
            language="typescript" if file_path.suffix == ".ts" else "javascript",
            imports=[],
            classes=[],
            functions=[],
            constants=[],
            line_count=line_count,
            comment_count=comment_count,
            docstring_count=0,
        )

    def _parse_java(self, file_path: Path) -> ASTFile:
        """Parse a Java file."""
        # Java parsing requires a Java parser
        # For now, use a simple approach
        with open(file_path, encoding="utf-8") as f:
            source = f.read()

        line_count = len(source.splitlines())
        comment_count = len(re.findall(r"//.*", source)) + len(
            re.findall(r"/\*.*?\*/", source, re.DOTALL)
        )

        root = ASTNode(type="CompilationUnit", name="root")

        # Extract classes
        class_pattern = r"class\s+(\w+)"
        interface_pattern = r"interface\s+(\w+)"
        enum_pattern = r"enum\s+(\w+)"

        for match in re.finditer(class_pattern, source):
            class_node = ASTNode(
                type="ClassDeclaration",
                name=match.group(1),
                line=source[: match.start()].count("\n") + 1,
            )
            root.children.append(class_node)

        for match in re.finditer(interface_pattern, source):
            interface_node = ASTNode(
                type="InterfaceDeclaration",
                name=match.group(1),
                line=source[: match.start()].count("\n") + 1,
            )
            root.children.append(interface_node)

        for match in re.finditer(enum_pattern, source):
            enum_node = ASTNode(
                type="EnumDeclaration",
                name=match.group(1),
                line=source[: match.start()].count("\n") + 1,
            )
            root.children.append(enum_node)

        return ASTFile(
            path=file_path,
            root=root,
            language="java",
            imports=[],
            classes=[],
            functions=[],
            constants=[],
            line_count=line_count,
            comment_count=comment_count,
            docstring_count=0,
        )

    def _parse_cpp(self, file_path: Path) -> ASTFile:
        """Parse a C++ file."""
        with open(file_path, encoding="utf-8") as f:
            source = f.read()

        line_count = len(source.splitlines())
        comment_count = len(re.findall(r"//.*", source)) + len(
            re.findall(r"/\*.*?\*/", source, re.DOTALL)
        )

        root = ASTNode(type="TranslationUnit", name="root")

        # Extract classes
        class_pattern = r"class\s+(\w+)"
        struct_pattern = r"struct\s+(\w+)"

        for match in re.finditer(class_pattern, source):
            class_node = ASTNode(
                type="ClassDeclaration",
                name=match.group(1),
                line=source[: match.start()].count("\n") + 1,
            )
            root.children.append(class_node)

        for match in re.finditer(struct_pattern, source):
            struct_node = ASTNode(
                type="StructDeclaration",
                name=match.group(1),
                line=source[: match.start()].count("\n") + 1,
            )
            root.children.append(struct_node)

        return ASTFile(
            path=file_path,
            root=root,
            language="cpp",
            imports=[],
            classes=[],
            functions=[],
            constants=[],
            line_count=line_count,
            comment_count=comment_count,
            docstring_count=0,
        )

    def _parse_go(self, file_path: Path) -> ASTFile:
        """Parse a Go file."""
        with open(file_path, encoding="utf-8") as f:
            source = f.read()

        line_count = len(source.splitlines())

        root = ASTNode(type="Package", name="root")

        # Extract functions and structs
        func_pattern = r"func\s+(\w+)\s*\([^)]*\)"
        struct_pattern = r"struct\s+(\w+)"

        for match in re.finditer(func_pattern, source):
            func_node = ASTNode(
                type="Function",
                name=match.group(1),
                line=source[: match.start()].count("\n") + 1,
            )
            root.children.append(func_node)

        for match in re.finditer(struct_pattern, source):
            struct_node = ASTNode(
                type="Struct",
                name=match.group(1),
                line=source[: match.start()].count("\n") + 1,
            )
            root.children.append(struct_node)

        return ASTFile(
            path=file_path,
            root=root,
            language="go",
            imports=[],
            classes=[],
            functions=[],
            constants=[],
            line_count=line_count,
            comment_count=0,
            docstring_count=0,
        )

    def _parse_rust(self, file_path: Path) -> ASTFile:
        """Parse a Rust file."""
        with open(file_path, encoding="utf-8") as f:
            source = f.read()

        line_count = len(source.splitlines())

        root = ASTNode(type="Crate", name="root")

        # Extract functions and structs
        func_pattern = r"fn\s+(\w+)\s*\([^)]*\)"
        struct_pattern = r"struct\s+(\w+)"

        for match in re.finditer(func_pattern, source):
            func_node = ASTNode(
                type="Function",
                name=match.group(1),
                line=source[: match.start()].count("\n") + 1,
            )
            root.children.append(func_node)

        for match in re.finditer(struct_pattern, source):
            struct_node = ASTNode(
                type="Struct",
                name=match.group(1),
                line=source[: match.start()].count("\n") + 1,
            )
            root.children.append(struct_node)

        return ASTFile(
            path=file_path,
            root=root,
            language="rust",
            imports=[],
            classes=[],
            functions=[],
            constants=[],
            line_count=line_count,
            comment_count=0,
            docstring_count=0,
        )

    def _parse_csharp(self, file_path: Path) -> ASTFile:
        """Parse a C# file."""
        with open(file_path, encoding="utf-8") as f:
            source = f.read()

        line_count = len(source.splitlines())

        root = ASTNode(type="CompilationUnit", name="root")

        # Extract classes
        class_pattern = r"class\s+(\w+)"

        for match in re.finditer(class_pattern, source):
            class_node = ASTNode(
                type="Class",
                name=match.group(1),
                line=source[: match.start()].count("\n") + 1,
            )
            root.children.append(class_node)

        return ASTFile(
            path=file_path,
            root=root,
            language="csharp",
            imports=[],
            classes=[],
            functions=[],
            constants=[],
            line_count=line_count,
            comment_count=0,
            docstring_count=0,
        )

    def _parse_kotlin(self, file_path: Path) -> ASTFile:
        """Parse a Kotlin file."""
        with open(file_path, encoding="utf-8") as f:
            source = f.read()

        line_count = len(source.splitlines())

        root = ASTNode(type="CompilationUnit", name="root")

        # Extract classes
        class_pattern = r"class\s+(\w+)"
        interface_pattern = r"interface\s+(\w+)"

        for match in re.finditer(class_pattern, source):
            class_node = ASTNode(
                type="Class",
                name=match.group(1),
                line=source[: match.start()].count("\n") + 1,
            )
            root.children.append(class_node)

        for match in re.finditer(interface_pattern, source):
            interface_node = ASTNode(
                type="Interface",
                name=match.group(1),
                line=source[: match.start()].count("\n") + 1,
            )
            root.children.append(interface_node)

        return ASTFile(
            path=file_path,
            root=root,
            language="kotlin",
            imports=[],
            classes=[],
            functions=[],
            constants=[],
            line_count=line_count,
            comment_count=0,
            docstring_count=0,
        )

    def _python_ast_to_node(self, tree: ast.AST) -> ASTNode:
        """Convert Python AST to our node format."""
        node = ASTNode(type=tree.__class__.__name__)

        for field, value in ast.iter_fields(tree):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        child = self._python_ast_to_node(item)
                        node.children.append(child)
            elif isinstance(value, ast.AST):
                child = self._python_ast_to_node(value)
                node.children.append(child)

        # Set name if available
        if hasattr(tree, "name") and tree.name:
            node.name = tree.name

        # Set line number
        if hasattr(tree, "lineno") and tree.lineno:
            node.line = tree.lineno

        return node

    def get_file_structure(self, file_path: str) -> dict[str, Any]:
        """
        Get the structure of a file.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary with file structure information
        """
        ast_file = self.parse_file(file_path)

        return {
            "path": str(ast_file.path),
            "language": ast_file.language,
            "line_count": ast_file.line_count,
            "comment_count": ast_file.comment_count,
            "docstring_count": ast_file.docstring_count,
            "classes": [c.to_dict() for c in ast_file.classes],
            "functions": [f.to_dict() for f in ast_file.functions],
            "constants": [c.to_dict() for c in ast_file.constants],
            "imports": ast_file.imports,
        }

    def get_all_symbols(self, file_path: str) -> list[str]:
        """
        Get all symbols in a file.

        Args:
            file_path: Path to the file

        Returns:
            List of symbol names
        """
        ast_file = self.parse_file(file_path)
        return ast_file.get_all_symbols()

    def clear_cache(self):
        """Clear the AST cache."""
        self._cache.clear()
        logger.info("AST cache cleared")

    def close(self):
        """Clean up resources."""
        self.clear_cache()
