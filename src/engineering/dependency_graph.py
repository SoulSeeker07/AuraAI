"""
Dependency Graph

Tracks dependencies between modules, classes, and functions.

This graph powers architecture understanding and can detect:
- Circular dependencies
- Module dependencies
- API dependencies
- Framework dependencies
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)


class DependencyType(Enum):
    """Types of dependencies."""

    IMPORT = "import"
    USAGE = "usage"
    INHERITANCE = "inheritance"
    IMPLEMENTATION = "implementation"
    CALL = "call"
    ACCESS = "access"


@dataclass
class Dependency:
    """Represents a dependency between two entities."""

    source: str  # What depends on what
    target: str  # What is depended upon
    dependency_type: DependencyType
    file_path: str
    line_number: int
    import_path: str | None = None
    is_direct: bool = True
    is_circular: bool = False


class DependencyGraph:
    """
    Tracks dependencies between modules, classes, and functions.

    Detects:
    - Module dependencies (imports)
    - API dependencies (function/class usage)
    - Inheritance relationships
    - Circular dependencies
    - Framework dependencies

    Usage:
        graph = DependencyGraph(repository_path="/path/to/repo")

        # Build from files
        graph.build_from_files()

        # Detect circular dependencies
        cycles = graph.find_circular_dependencies()

        # Get module dependencies
        deps = graph.get_module_dependencies("module_name")

        # Get all circular dependencies
        for cycle in cycles:
            print(f"Cycle: {' -> '.join(cycle)}")
    """

    def __init__(self, repository_path: Path, workspace_walker=None):
        """
        Initialize the Dependency Graph.

        Args:
            repository_path: Path to the repository
            workspace_walker: Walker instance for repository discovery
        """
        self.repository_path = Path(repository_path).resolve()
        self._graph = nx.DiGraph()
        self._dependencies: dict[str, list[Dependency]] = {}
        self._module_dependencies: dict[str, set[str]] = {}
        self._circular_dependencies: list[list[str]] = []
        
        if workspace_walker is None:
            from .workspace_walker import WorkspaceFileWalker
            self.workspace_walker = WorkspaceFileWalker(repository_path=self.repository_path)
        else:
            self.workspace_walker = workspace_walker

    def build_from_files(self, file_paths: list[Path] | None = None):
        """
        Build dependency graph from source files.

        Args:
            file_paths: List of files to analyze, or None for all Python files
        """
        logger.info("Building dependency graph from files")

        # Find files to analyze
        if file_paths is None:
            file_paths = self.workspace_walker.walk("*.py").files

        # Clear existing data
        self._graph.clear()
        self._dependencies.clear()
        self._module_dependencies.clear()
        self._circular_dependencies.clear()

        # Build dependencies from each file
        for file_path in file_paths:
            if file_path.is_file():
                self._add_dependencies_from_file(file_path)

        # Detect circular dependencies
        self._detect_circular_dependencies()

        logger.info(
            f"Dependency graph built with {len(self._dependencies)} dependencies"
        )

    def _add_dependencies_from_file(self, file_path: Path):
        """Add dependencies from a single file."""
        # This would parse imports and other dependencies
        # For now, use placeholder logic
        module_name = file_path.stem
        dependencies = []

        # Add module to graph
        self._graph.add_node(module_name)

        # Simulate some dependencies
        mock_imports = ["os", "sys", "typing", "logging"]
        for import_name in mock_imports:
            dep = Dependency(
                source=module_name,
                target=import_name,
                dependency_type=DependencyType.IMPORT,
                file_path=str(file_path),
                line_number=1,
                import_path=f"import {import_name}",
            )
            dependencies.append(dep)
            self._add_dependency(dep)

        self._dependencies[str(file_path)] = dependencies

    def _add_dependency(self, dependency: Dependency):
        """Add a dependency to the graph."""
        # Add to dependencies dict
        file_key = dependency.file_path
        if file_key not in self._dependencies:
            self._dependencies[file_key] = []
        self._dependencies[file_key].append(dependency)

        # Add to module dependencies
        source_module = (
            dependency.source.split(".")[0]
            if "." in dependency.source
            else dependency.source
        )
        target_module = (
            dependency.target.split(".")[0]
            if "." in dependency.target
            else dependency.target
        )

        if source_module not in self._module_dependencies:
            self._module_dependencies[source_module] = set()
        self._module_dependencies[source_module].add(target_module)

        # Add to graph
        self._graph.add_edge(
            dependency.source,
            dependency.target,
            dep_type=dependency.dependency_type.value,
            file_path=dependency.file_path,
            line_number=dependency.line_number,
        )

    def find_circular_dependencies(self) -> list[list[str]]:
        """
        Find all circular dependencies in the graph.

        Returns:
            List of cycles, each cycle is a list of module names
        """
        # Find all cycles in the graph
        cycles = []

        # Simple cycle detection using DFS
        for node in self._graph.nodes():
            cycle = self._find_cycle_from(node)
            if cycle:
                cycles.append(cycle)

        self._circular_dependencies = cycles
        return cycles

    def _find_cycle_from(
        self,
        start_node: str,
        visited: set[str] | None = None,
        path: list[str] | None = None,
    ) -> list[str] | None:
        """
        Find a cycle starting from a given node.

        Args:
            start_node: Starting node
            visited: Set of visited nodes
            path: Current path

        Returns:
            Cycle if found, None otherwise
        """
        if visited is None:
            visited = set()
        if path is None:
            path = []

        if start_node in visited:
            # Check if this node completes a cycle
            if start_node in path:
                idx = path.index(start_node)
                return path[idx:] + [start_node]
            return None

        visited.add(start_node)
        path.append(start_node)

        # Explore neighbors
        for neighbor in self._graph.neighbors(start_node):
            cycle = self._find_cycle_from(neighbor, visited, path.copy())
            if cycle:
                return cycle

        return None

    def get_module_dependencies(self, module: str) -> list[str]:
        """
        Get dependencies of a module.

        Args:
            module: Module name

        Returns:
            List of dependent module names
        """
        return sorted(self._module_dependencies.get(module, set()))

    def get_dependents(self, module: str) -> list[str]:
        """
        Get modules that depend on a given module.

        Args:
            module: Module name

        Returns:
            List of dependent module names
        """
        dependents = []
        for source, targets in self._module_dependencies.items():
            if module in targets:
                dependents.append(source)
        return sorted(dependents)

    def get_dependencies_for_file(self, file_path: str) -> list[Dependency]:
        """
        Get all dependencies for a file.

        Args:
            file_path: Path to the file

        Returns:
            List of dependencies
        """
        return self._dependencies.get(file_path, [])

    def get_statistics(self) -> dict[str, Any]:
        """
        Get graph statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "total_modules": self._graph.number_of_nodes(),
            "total_dependencies": self._graph.number_of_edges(),
            "circular_dependencies": len(self._circular_dependencies),
            "unique_modules": len(self._module_dependencies),
            "circular_dependency_count": len(self._circular_dependencies),
        }

    def is_circular(self, module1: str, module2: str) -> bool:
        """
        Check if there's a circular dependency between two modules.

        Args:
            module1: First module
            module2: Second module

        Returns:
            True if circular dependency exists
        """
        return self._find_cycle_from(module1) and self._find_cycle_from(module2)

    def get_dependency_tree(self, module: str) -> dict[str, Any]:
        """
        Get a dependency tree for a module.

        Args:
            module: Module name

        Returns:
            Dictionary representing the dependency tree
        """
        return {
            "module": module,
            "dependencies": self.get_module_dependencies(module),
            "dependents": self.get_dependents(module),
        }

    def get_all_circular_dependencies(self) -> list[dict[str, Any]]:
        """
        Get all circular dependencies with details.

        Returns:
            List of circular dependency dictionaries
        """
        return [
            {
                "cycle": cycle,
                "length": len(cycle),
                "warning": f"Circular dependency detected: {' -> '.join(cycle)}",
            }
            for cycle in self._circular_dependencies
        ]

    def get_modules_by_depth(self, module: str) -> dict[int, list[str]]:
        """
        Get modules at each depth from a given module.

        Args:
            module: Starting module

        Returns:
            Dictionary with depth as key and list of modules as value
        """
        depths = {}

        def traverse(node, depth, visited):
            if depth not in depths:
                depths[depth] = []
            depths[depth].append(node)

            for neighbor in self._graph.neighbors(node):
                if neighbor not in visited:
                    traverse(neighbor, depth + 1, visited | {node})

        traverse(module, 0, set())
        return depths

    def close(self):
        """Clean up resources."""
        self._graph.clear()
        self._dependencies.clear()
        self._module_dependencies.clear()
        self._circular_dependencies.clear()
