"""
Symbol Graph

Maintains a graph of symbols and their relationships.

This database enables Aura to understand:
- What symbols exist
- Where they are defined
- What they reference
- How they're related
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)


class SymbolType(Enum):
    """Types of symbols."""

    FUNCTION = "function"
    CLASS = "class"
    VARIABLE = "variable"
    CONSTANT = "constant"
    IMPORT = "import"
    MODULE = "module"
    INTERFACE = "interface"
    TYPE_ALIAS = "type_alias"
    ENUM = "enum"


@dataclass
class Symbol:
    """Represents a symbol in the codebase."""

    name: str
    symbol_type: SymbolType
    file_path: str
    line_number: int
    scope: str | None = None  # Module, class, function
    module: str | None = None
    imports: list[str] = field(default_factory=list)
    defined_in: str | None = None  # Where this symbol is defined
    references: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    return_type: str | None = None
    parameters: list[str] = field(default_factory=list)
    is_public: bool = True
    is_static: bool = False
    documentation: str | None = None
    tags: list[str] = field(default_factory=list)

    def add_reference(self, reference: str):
        """Add a reference to this symbol."""
        if reference not in self.references:
            self.references.append(reference)

    def to_dict(self) -> dict[str, Any]:
        """Convert symbol to dictionary."""
        return {
            "name": self.name,
            "type": self.symbol_type.value,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "scope": self.scope,
            "module": self.module,
            "defined_in": self.defined_in,
            "references": self.references,
            "decorators": self.decorators,
            "return_type": self.return_type,
            "parameters": self.parameters,
            "is_public": self.is_public,
            "is_static": self.is_static,
        }


class SymbolGraph:
    """
    Maintains a graph of symbols and their relationships.

    Enables Aura to understand:
    - What symbols exist and where they're defined
    - What symbols reference what
    - The call graph between functions
    - Class inheritance hierarchies
    - Module dependencies
    - Cross-file references

    Usage:
        graph = SymbolGraph(repository_path="/path/to/repo")

        # Build from files
        graph.build_from_files()

        # Find a symbol
        symbol = graph.get_symbol("MyClass")

        # Find all references
        refs = graph.get_references("MyClass")

        # Get call graph
        call_graph = graph.get_call_graph("function_name")

        # Find class hierarchy
        hierarchy = graph.get_class_hierarchy("BaseClass")
    """

    def __init__(self, repository_path: Path):
        """
        Initialize the Symbol Graph.

        Args:
            repository_path: Path to the repository
        """
        self.repository_path = Path(repository_path).resolve()
        self._graph = nx.DiGraph()
        self._symbols: dict[str, Symbol] = {}
        self._module_index: dict[str, list[str]] = {}

    def build_from_files(self, file_paths: list[Path] | None = None):
        """
        Build symbol graph from source files.

        Args:
            file_paths: List of files to analyze, or None for all Python files
        """
        logger.info("Building symbol graph from files")

        # Find files to analyze
        if file_paths is None:
            file_paths = list(self.repository_path.rglob("*.py"))

        # Clear existing data
        self._graph.clear()
        self._symbols.clear()
        self._module_index.clear()

        # Build symbols from each file
        for file_path in file_paths:
            if file_path.is_file():
                self._add_symbols_from_file(file_path)

        # Build relationships
        self._build_relationships()

        logger.info(f"Symbol graph built with {len(self._symbols)} symbols")

    def _add_symbols_from_file(self, file_path: Path):
        """Add symbols from a single file."""
        # This would parse the file and extract symbols
        # For now, we'll use a placeholder
        module_name = file_path.stem
        self._module_index[module_name] = []

        # Add module as a symbol
        module_symbol = Symbol(
            name=module_name,
            symbol_type=SymbolType.MODULE,
            file_path=str(file_path),
            line_number=1,
            scope=None,
            module=module_name,
        )
        self._add_symbol(module_symbol)

    def _add_symbol(self, symbol: Symbol):
        """Add a symbol to the graph."""
        # Create unique key
        key = f"{symbol.module or ''}.{symbol.name}"

        # Add to symbols dict
        self._symbols[key] = symbol

        # Add to graph
        self._graph.add_node(
            key,
            name=symbol.name,
            type=symbol.symbol_type.value,
            file_path=symbol.file_path,
            line_number=symbol.line_number,
        )

        # Add to module index
        if symbol.module:
            if symbol.module not in self._module_index:
                self._module_index[symbol.module] = []
            self._module_index[symbol.module].append(key)

    def _build_relationships(self):
        """Build relationships between symbols."""
        # This would analyze imports and references
        # For now, we'll add placeholder edges
        pass

    def get_symbol(self, name: str, scope: str | None = None) -> Symbol | None:
        """
        Get a symbol by name.

        Args:
            name: Symbol name
            scope: Optional scope (module or class)

        Returns:
            Symbol if found, None otherwise
        """
        # Try exact match
        if scope:
            key = f"{scope}.{name}"
            return self._symbols.get(key)

        # Try with module prefix
        for module, symbols in self._module_index.items():
            for sym_key in symbols:
                if sym_key.endswith(f".{name}"):
                    return self._symbols[sym_key]

        # Try exact match without module
        return self._symbols.get(name)

    def get_all_symbols(self, module: str | None = None) -> list[Symbol]:
        """
        Get all symbols in a module.

        Args:
            module: Module name, or None for all symbols

        Returns:
            List of symbols
        """
        if module:
            keys = self._module_index.get(module, [])
            return [self._symbols.get(k) for k in keys if k in self._symbols]
        return list(self._symbols.values())

    def get_references(self, name: str, scope: str | None = None) -> list[str]:
        """
        Get all references to a symbol.

        Args:
            name: Symbol name
            scope: Optional scope

        Returns:
            List of reference strings
        """
        symbol = self.get_symbol(name, scope)
        if symbol:
            return symbol.references
        return []

    def get_call_graph(
        self, function_name: str, module: str | None = None
    ) -> nx.DiGraph:
        """
        Get the call graph for a function.

        Args:
            function_name: Function name
            module: Module name

        Returns:
            NetworkX DiGraph representing the call graph
        """
        # This would analyze the call graph
        # For now, return empty graph
        return nx.DiGraph()

    def get_class_hierarchy(self, class_name: str) -> list[str]:
        """
        Get the class hierarchy for a class.

        Args:
            class_name: Class name

        Returns:
            List of class names in the hierarchy
        """
        # This would analyze inheritance
        # For now, return empty list
        return []

    def get_symbols_by_type(self, symbol_type: SymbolType) -> list[Symbol]:
        """
        Get all symbols of a specific type.

        Args:
            symbol_type: Type of symbol

        Returns:
            List of symbols
        """
        return [s for s in self._symbols.values() if s.symbol_type == symbol_type]

    def get_dependencies(self, symbol_name: str) -> list[str]:
        """
        Get dependencies of a symbol.

        Args:
            symbol_name: Symbol name

        Returns:
            List of dependency names
        """
        symbol = self.get_symbol(symbol_name)
        if symbol:
            return symbol.imports
        return []

    def get_imports(self) -> dict[str, list[str]]:
        """
        Get all imports.

        Returns:
            Dictionary mapping modules to their imports
        """
        result = {}
        for symbol in self._symbols.values():
            if symbol.symbol_type == SymbolType.IMPORT:
                module = symbol.module or "root"
                if module not in result:
                    result[module] = []
                result[module].append(symbol.name)
        return result

    def get_statistics(self) -> dict[str, Any]:
        """
        Get graph statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "total_symbols": len(self._symbols),
            "total_nodes": self._graph.number_of_nodes(),
            "total_edges": self._graph.number_of_edges(),
            "modules": len(self._module_index),
            "by_type": {
                st.value: len(
                    [s for s in self._symbols.values() if s.symbol_type == st]
                )
                for st in SymbolType
            },
        }

    def search_symbols(
        self, query: str, symbol_type: SymbolType | None = None
    ) -> list[Symbol]:
        """
        Search symbols by name.

        Args:
            query: Search query
            symbol_type: Optional type filter

        Returns:
            List of matching symbols
        """
        results = []
        query_lower = query.lower()

        for symbol in self._symbols.values():
            if query_lower in symbol.name.lower():
                if symbol_type is None or symbol.symbol_type == symbol_type:
                    results.append(symbol)

        return results

    def get_usages(self, name: str) -> dict[str, list[str]]:
        """
        Get all usages of a symbol across the codebase.

        Args:
            name: Symbol name

        Returns:
            Dictionary with usage locations
        """
        symbol = self.get_symbol(name)
        if not symbol:
            return {}

        # This would analyze all files for references
        # For now, return the symbol's references
        return {
            "symbol_name": name,
            "references": symbol.references,
            "defined_in": symbol.defined_in,
            "file_path": symbol.file_path,
        }

    def get_symbols_in_module(self, module: str) -> list[Symbol]:
        """
        Get all symbols in a module.

        Args:
            module: Module name

        Returns:
            List of symbols
        """
        return self.get_all_symbols(module)

    def get_callees(self, function_name: str) -> list[str]:
        """
        Get functions called by a given function.

        Args:
            function_name: Function name

        Returns:
            List of callee function names
        """
        return []

    def get_callers(self, function_name: str) -> list[str]:
        """
        Get functions that call a given function.

        Args:
            function_name: Function name

        Returns:
            List of caller function names
        """
        return []

    def close(self):
        """Clean up resources."""
        self._graph.clear()
        self._symbols.clear()
        self._module_index.clear()
