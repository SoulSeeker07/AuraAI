"""
TypeScript & JSX Language Provider
==================================
Location: src/engineering/language_providers/typescript/provider.py

Integrates the Tree-sitter TypeScript/JavaScript AST parser with Aura's
Engineering Subsystem, ProjectIndex, ASTManager, and SymbolGraph.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional, Tuple, List, Dict

from ...ast_manager import ASTFile, ASTNode
from ...symbol_graph import Symbol, SymbolType
from .parser import TypeScriptASTParser, ParsedTypeScriptFile

logger = logging.getLogger(__name__)


class TypeScriptLanguageProvider:
    """
    Language provider for TypeScript (.ts, .tsx) and JavaScript (.js, .jsx).
    """

    SUPPORTED_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}

    def __init__(self) -> None:
        self._parser = TypeScriptASTParser()

    @classmethod
    def supports_file(cls, file_path: str | Path) -> bool:
        """Check if file extension is supported by TypeScript provider."""
        return Path(file_path).suffix.lower() in cls.SUPPORTED_EXTENSIONS

    def parse_file(self, file_path: str | Path, content: Optional[str | bytes] = None) -> ParsedTypeScriptFile:
        """Parse source file from disk or provided content."""
        p = Path(file_path)
        if content is None:
            with open(p, "rb") as f:
                source_bytes = f.read()
        elif isinstance(content, str):
            source_bytes = content.encode("utf-8")
        else:
            source_bytes = content

        return self._parser.parse_source(source_bytes, file_path=p)

    def get_symbols(self, file_path: str | Path, content: Optional[str | bytes] = None) -> list[Symbol]:
        """Extract canonical Symbol objects for SymbolGraph."""
        parsed = self.parse_file(file_path, content)
        return parsed.symbols

    def get_index_records(
        self, file_path: str | Path, content: Optional[str | bytes] = None
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[tuple[int, str]]]:
        """
        Extract records matching ProjectIndex schema:
        Returns: (symbols_dicts, imports_dicts, call_edges_unresolved)
        """
        parsed = self.parse_file(file_path, content)
        file_path_str = str(file_path)

        symbols_list: list[dict[str, Any]] = []
        call_edges_unresolved: list[tuple[int, str]] = []

        # Map symbols
        for idx, sym in enumerate(parsed.symbols):
            sym_type_str = sym.symbol_type.value
            sig = f"{sym.name}({', '.join(sym.parameters)})" if sym.parameters else sym.name
            if sym.return_type:
                sig += f": {sym.return_type}"

            symbols_list.append({
                "file_path": file_path_str,
                "symbol_type": sym_type_str,
                "name": sym.name,
                "qualified_name": sym.name,
                "signature": sig,
                "docstring": sym.documentation,
                "line_start": sym.line_number,
                "line_end": sym.line_number,
            })

            # Record internal call references from this symbol
            for ref in sym.references:
                call_edges_unresolved.append((idx, ref))

        # Map imports
        import json
        imports_list: list[dict[str, Any]] = []
        for imp in parsed.imports:
            imports_list.append({
                "file_path": file_path_str,
                "imported_module": imp["module"],
                "imported_names": json.dumps(imp["symbols"]),
            })

        return symbols_list, imports_list, call_edges_unresolved

    def get_ast_file(self, file_path: str | Path, content: Optional[str | bytes] = None) -> ASTFile:
        """Convert Tree-sitter parse result to ASTFile structure for ASTManager compatibility."""
        p = Path(file_path)
        if content is None:
            with open(p, "rb") as f:
                source_bytes = f.read()
        elif isinstance(content, str):
            source_bytes = content.encode("utf-8")
        else:
            source_bytes = content

        parsed = self._parser.parse_source(source_bytes, file_path=p)
        source_str = source_bytes.decode("utf-8", errors="replace")

        root = ASTNode(type="Program", name=p.name)
        functions: list[ASTNode] = []
        classes: list[ASTNode] = []
        constants: list[ASTNode] = []

        for sym in parsed.symbols:
            node = ASTNode(
                type=sym.symbol_type.name.capitalize(),
                name=sym.name,
                line=sym.line_number,
                return_type=sym.return_type,
                parameters=sym.parameters,
                docstring=sym.documentation,
                references=sym.references,
                scope=sym.scope,
            )
            root.children.append(node)

            if sym.symbol_type == SymbolType.FUNCTION:
                functions.append(node)
            elif sym.symbol_type == SymbolType.CLASS:
                classes.append(node)
            elif sym.symbol_type in (SymbolType.CONSTANT, SymbolType.VARIABLE):
                constants.append(node)

        return ASTFile(
            path=p,
            root=root,
            language=parsed.language,
            imports=[imp["module"] for imp in parsed.imports],
            classes=classes,
            functions=functions,
            constants=constants,
            line_count=len(source_str.splitlines()),
            comment_count=source_str.count("//") + source_str.count("/*"),
            docstring_count=sum(1 for s in parsed.symbols if s.documentation),
        )
