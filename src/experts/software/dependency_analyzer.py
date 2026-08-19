"""
Dependency Analyzer for Software Engineering Expert (M25 Phase 2)
Location: src/experts/software/dependency_analyzer.py

Analyzes module dependencies, circular import cycles, and missing prerequisites.
Pure in-memory analysis, zero file mutation.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .ast_analyzer import ASTAnalyzer

logger = logging.getLogger(__name__)


class DependencyAnalyzer:
    """
    Constructs dependency graphs and detects architectural cycles and missing imports.
    """

    def __init__(self, ast_analyzer: ASTAnalyzer | None = None) -> None:
        self.ast_analyzer = ast_analyzer or ASTAnalyzer()

    def build_import_graph(self, file_sources: dict[str, str]) -> dict[str, set[str]]:
        """
        Builds a module-level import graph from a dictionary of {module_name: source_code}.
        """
        graph: dict[str, set[str]] = {mod: set() for mod in file_sources}
        for mod, src in file_sources.items():
            ast_res = self.ast_analyzer.analyze_source(src, file_path=mod)
            for imp in ast_res.get("imports", []):
                top_pkg = imp.split(".")[0]
                if top_pkg in file_sources and top_pkg != mod:
                    graph[mod].add(top_pkg)
                elif imp in file_sources and imp != mod:
                    graph[mod].add(imp)
        return graph

    def detect_circular_dependencies(self, graph: dict[str, set[str]]) -> list[list[str]]:
        """
        Detects circular dependency cycles using depth-first search cycle detection.
        """
        cycles: list[list[str]] = []
        visited: set[str] = set()
        rec_stack: list[str] = []

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.append(node)

            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    # Cycle found
                    cycle_start = rec_stack.index(neighbor)
                    cycle = rec_stack[cycle_start:] + [neighbor]
                    if cycle not in cycles:
                        cycles.append(cycle)

            rec_stack.pop()

        for node in list(graph.keys()):
            if node not in visited:
                dfs(node)

        return cycles

    def find_unresolved_dependencies(
        self,
        imports: list[str],
        known_modules: set[str],
        stdlib_names: set[str] | None = None,
    ) -> list[str]:
        """Identifies imports that cannot be resolved against stdlib or known project modules."""
        import sys
        stdlib = stdlib_names or set(sys.stdlib_module_names if hasattr(sys, "stdlib_module_names") else [])
        unresolved: list[str] = []
        for imp in imports:
            root_pkg = imp.split(".")[0]
            if root_pkg not in stdlib and root_pkg not in known_modules:
                unresolved.append(imp)
        return sorted(list(set(unresolved)))
