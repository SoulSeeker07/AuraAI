"""
Engineering Intelligence Manager

Main orchestrator for the Engineering Intelligence Platform.

This is the entry point that coordinates all engineering capabilities:
- Repository intelligence
- AST-based editing
- Symbol and dependency graphs
- Planning and refactoring
- Testing and quality
- Git and documentation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .ast_manager import ASTManager, ASTNode
from .bug_repair import BugRepairLoop
from .code_editor import CodeEditor
from .dashboard import EngineeringDashboard
from .dependency_graph import DependencyGraph
from .documentation_engine import DocumentationEngine
from .engineering_memory import EngineeringMemory
from .engineering_planner import EngineeringPlanner, PlanningPhase
from .git_intelligence import GitIntelligence
from .import_manager import ImportManager
from .lsp_manager import LSPManager
from .quality_engine import QualityEngine
from .refactoring_engine import RefactoringEngine, RefactoringOperation
from .repository_manager import RepositoryManager, RepositoryState
from .symbol_graph import Symbol, SymbolGraph
from .test_engine import TestEngine

logger = logging.getLogger(__name__)


@dataclass
class EngineeringContext:
    """Context for engineering operations."""

    repository_path: Path
    repository_state: RepositoryState
    symbol_graph: SymbolGraph
    dependency_graph: DependencyGraph
    active_files: list[Path] = field(default_factory=list)
    recent_changes: list[str] = field(default_factory=list)
    last_sync: datetime = field(default_factory=datetime.now)


class EngineeringManager:
    """
      Main orchestrator for the Engineering Intelligence Platform.

      Coordinates all engineering capabilities to enable Aura to:
      - Understand repositories at the architectural level
      - Plan before implementing
      - Edit code safely using ASTs
      - Validate every change
      - Learn and remember engineering decisions

      Architecture:
          Aura Brain
               │
               ▼
       Engineering Intelligence Platform
               │
       ┌───────┼───────┐
       ▼       ▼       ▼
    Repository  AST   Symbol
    Manager    Manager   Graph
       │       │       │
       └───────┼───────┘
               ▼
         Dependency Graph
               │
               ▼
       Engineering Planner
               │
       ┌───────┼───────┐
       ▼       ▼       ▼
     Code     Test     Git
     Editor   Engine  Intelligence
       │
       ▼
    Refactoring
         Engine

      Usage:
          manager = EngineeringManager(repository_path)

          # Understand repository
          state = manager.repository_state

          # Plan before editing
          plan = manager.planner.plan_refactoring(old_name, new_name)

          # Execute with validation
          result = manager.code_editor.apply_refactoring(
              old_name,
              new_name,
              commit=True
          )

          # Monitor quality
          quality = manager.quality_engine.analyze_repository()
    """

    def __init__(
        self,
        repository_path: Path,
        config: dict[str, Any] | None = None,
        enable_lsp: bool = True,
        enable_auto_sync: bool = True,
    ):
        """
        Initialize the Engineering Manager.

        Args:
            repository_path: Path to the repository to analyze
            config: Configuration dictionary
            enable_lsp: Whether to use LSP for language-specific intelligence
            enable_auto_sync: Whether to automatically sync on file changes
        """
        self.repository_path = Path(repository_path).resolve()
        self.config = config or {}
        self.enable_lsp = enable_lsp
        self.enable_auto_sync = enable_auto_sync

        # Initialize sub-managers
        self.repository_manager = RepositoryManager(
            repository_path=self.repository_path, auto_sync=enable_auto_sync
        )

        self.ast_manager = ASTManager(
            repository_path=self.repository_path, enable_lsp=enable_lsp
        )

        self.symbol_graph = SymbolGraph(repository_path=self.repository_path)

        self.dependency_graph = DependencyGraph(repository_path=self.repository_path)

        self.engineering_planner = EngineeringPlanner(
            repository_path=self.repository_path
        )

        self.code_editor = CodeEditor(
            repository_path=self.repository_path,
            ast_manager=self.ast_manager,
            symbol_graph=self.symbol_graph,
            dependency_graph=self.dependency_graph,
        )

        self.refactoring_engine = RefactoringEngine(
            repository_path=self.repository_path,
            ast_manager=self.ast_manager,
            symbol_graph=self.symbol_graph,
            dependency_graph=self.dependency_graph,
        )

        self.import_manager = ImportManager(
            repository_path=self.repository_path, ast_manager=self.ast_manager
        )

        self.test_engine = TestEngine(repository_path=self.repository_path)

        self.bug_repair = BugRepairLoop(
            repository_path=self.repository_path,
            test_engine=self.test_engine,
            ast_manager=self.ast_manager,
        )

        self.git_intelligence = GitIntelligence(repository_path=self.repository_path)

        self.documentation_engine = DocumentationEngine(
            repository_path=self.repository_path,
            ast_manager=self.ast_manager,
            symbol_graph=self.symbol_graph,
        )

        self.quality_engine = QualityEngine(
            repository_path=self.repository_path,
            ast_manager=self.ast_manager,
            symbol_graph=self.symbol_graph,
        )

        self.engineering_memory = EngineeringMemory(
            repository_path=self.repository_path
        )

        self.dashboard = EngineeringDashboard(
            repository_path=self.repository_path,
            repository_manager=self.repository_manager,
            quality_engine=self.quality_engine,
            symbol_graph=self.symbol_graph,
            dependency_graph=self.dependency_graph,
        )

        self.lsp_manager = LSPManager(
            repository_path=self.repository_path, enable_lsp=enable_lsp
        )

        # Load repository state
        self.repository_state = self.repository_manager.get_repository_state()

        logger.info(f"EngineeringManager initialized for: {self.repository_path}")

    def sync_repository(self) -> RepositoryState:
        """
        Sync the repository with the engineering intelligence system.

        Returns:
            Updated repository state
        """
        logger.info("Syncing repository...")

        # Sync repository
        self.repository_manager.sync()

        # Rebuild symbol graph
        self.symbol_graph.build_from_files()

        # Rebuild dependency graph
        self.dependency_graph.build_from_symbols()

        # Update state
        self.repository_state = self.repository_manager.get_repository_state()

        logger.info("Repository sync complete")

        return self.repository_state

    def understand_code(self, file_path: Path) -> ASTNode:
        """
        Get a deep understanding of a file using AST.

        Args:
            file_path: Path to the file

        Returns:
            AST node representing the file structure
        """
        return self.ast_manager.parse_file(file_path)

    def get_symbol(self, symbol_name: str, scope: str | None = None) -> Symbol | None:
        """
        Get a symbol from the symbol graph.

        Args:
            symbol_name: Name of the symbol
            scope: Optional scope (module/class)

        Returns:
            Symbol if found, None otherwise
        """
        return self.symbol_graph.get_symbol(symbol_name, scope)

    def plan_refactoring(
        self, old_name: str, new_name: str, context: dict[str, Any] | None = None
    ) -> PlanningPhase:
        """
        Plan a refactoring operation.

        Args:
            old_name: Current name
            new_name: New name
            context: Additional context

        Returns:
            Planning phase with details
        """
        return self.engineering_planner.plan_refactoring(
            old_name=old_name, new_name=new_name, context=context
        )

    def apply_refactoring(
        self,
        operation: RefactoringOperation,
        validate: bool = True,
        commit: bool = False,
    ) -> dict[str, Any]:
        """
        Apply a refactoring operation.

        Args:
            operation: Refactoring operation to apply
            validate: Whether to validate changes first
            commit: Whether to commit changes to git

        Returns:
            Result of the refactoring operation
        """
        return self.code_editor.apply_refactoring(
            operation=operation, validate=validate, commit=commit
        )

    def analyze_repository(self) -> dict[str, Any]:
        """
        Get a comprehensive analysis of the repository.

        Returns:
            Analysis dictionary with repository metrics
        """
        return self.dashboard.get_repository_analysis()

    def get_quality_report(self) -> dict[str, Any]:
        """
        Get a quality report for the repository.

        Returns:
            Quality report with metrics and issues
        """
        return self.quality_engine.analyze_repository()

    def repair_bug(
        self, test_file: Path, expected_output: Any, max_attempts: int = 3
    ) -> dict[str, Any]:
        """
        Repair a bug using the bug repair loop.

        Args:
            test_file: Path to test file
            expected_output: Expected test output
            max_attempts: Maximum number of repair attempts

        Returns:
            Bug repair result
        """
        return self.bug_repair.repair_bug(
            test_file=test_file,
            expected_output=expected_output,
            max_attempts=max_attempts,
        )

    def generate_documentation(
        self, target: str = "all", format: str = "markdown"
    ) -> dict[str, Any]:
        """
        Generate documentation for the repository.

        Args:
            target: What to document ("all", "api", "architecture", etc.)
            format: Output format ("markdown", "html", "pdf")

        Returns:
            Documentation generation result
        """
        return self.documentation_engine.generate_documentation(
            target=target, format=format
        )

    def get_engineering_context(self) -> EngineeringContext:
        """
        Get the current engineering context.

        Returns:
            Engineering context with all relevant information
        """
        return EngineeringContext(
            repository_path=self.repository_path,
            repository_state=self.repository_state,
            symbol_graph=self.symbol_graph,
            dependency_graph=self.dependency_graph,
            active_files=self.repository_state.active_files,
            recent_changes=self.repository_state.recent_changes,
            last_sync=self.repository_state.last_sync,
        )

    def close(self):
        """Clean up resources."""
        logger.info("Closing EngineeringManager")
        self.symbol_graph.close()
        self.dependency_graph.close()
        self.ast_manager.close()
        self.lsp_manager.close()
