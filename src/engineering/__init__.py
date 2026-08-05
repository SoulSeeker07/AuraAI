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

from .ast_manager import ASTFile, ASTManager, ASTNode
from .bug_repair import BugRepairLoop
from .code_editor import CodeEditor
from .dashboard import EngineeringDashboard
from .dependency_graph import Dependency, DependencyGraph
from .doctor import AuraDoctor, AuraVerifier
from .documentation_engine import DocumentationEngine
from .engineering_manager import EngineeringManager
from .engineering_memory import EngineeringMemory
from .engineering_planner import EngineeringPlanner, PlanningPhase
from .git_intelligence import GitIntelligence
from .import_manager import ImportManager
from .inspector import AuraInspector
from .lsp_manager import LSPManager
from .quality_engine import QualityEngine
from .refactoring_engine import RefactoringEngine, RefactoringOperation
from .repository_manager import RepositoryManager, RepositoryState

__version__ = "1.0.0"

__all__ = [
    "AuraDoctor",
    "AuraVerifier",
    "AuraInspector",
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
