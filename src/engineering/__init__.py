"""
Engineering Intelligence Platform

This module provides Aura's capability to understand, analyze, and manipulate
code at the architectural level, not just text level.

The platform enables:
- Repository intelligence and continuous monitoring
- AST-based code understanding and editing
- Symbol graph and dependency graph databases
- Engineering planning before implementation
- Multi-file editing with atomic transactions
- Refactoring engine with AST operations
- Import intelligence and management
- Live test engine with validation
- Bug repair loop
- Git intelligence
- Documentation generation
- Code quality monitoring
- Engineering memory
"""

from .engineering_manager import EngineeringManager
from .repository_manager import RepositoryManager, RepositoryState
from .ast_manager import ASTManager, ASTNode, ASTFile
from .symbol_graph import SymbolGraph, Symbol
from .dependency_graph import DependencyGraph, Dependency
from .engineering_planner import EngineeringPlanner, PlanningPhase
from .code_editor import CodeEditor
from .refactoring_engine import RefactoringEngine, RefactoringOperation
from .import_manager import ImportManager
from .test_engine import TestEngine, TestResult
from .bug_repair import BugRepairLoop
from .git_intelligence import GitIntelligence
from .documentation_engine import DocumentationEngine
from .quality_engine import QualityEngine
from .engineering_memory import EngineeringMemory
from .dashboard import EngineeringDashboard
from .lsp_manager import LSPManager

__version__ = "1.0.0"

__all__ = [
    "EngineeringManager",
    "RepositoryManager",
    "RepositoryState",
    "ASTManager",
    "ASTNode",
    "ASTFile",
    "SymbolGraph",
    "Symbol",
    "DependencyGraph",
    "Dependency",
    "EngineeringPlanner",
    "PlanningPhase",
    "CodeEditor",
    "RefactoringEngine",
    "RefactoringOperation",
    "ImportManager",
    "TestEngine",
    "TestResult",
    "BugRepairLoop",
    "GitIntelligence",
    "DocumentationEngine",
    "QualityEngine",
    "EngineeringMemory",
    "EngineeringDashboard",
    "LSPManager",
]
