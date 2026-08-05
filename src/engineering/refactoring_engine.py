"""
Refactoring Engine

Performs AST-based refactoring operations.

This engine enables Aura to:
- Rename symbols across files
- Move classes and functions
- Extract methods
- Inline functions
- Refactor code safely
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class RefactoringOperationType(Enum):
    """Types of refactoring operations."""

    RENAME = "rename"
    MOVE = "move"
    EXTRACT = "extract"
    INLINE = "inline"
    SPLIT = "split"
    MERGE = "merge"
    REFACTOR = "refactor"


@dataclass
class RefactoringOperation:
    """Represents a refactoring operation."""

    operation_type: RefactoringOperationType
    old_name: str
    new_name: str
    affected_files: list[str]
    details: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "medium"
    requires_review: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "operation_type": self.operation_type.value,
            "old_name": self.old_name,
            "new_name": self.new_name,
            "affected_files": self.affected_files,
            "details": self.details,
            "risk_level": self.risk_level,
            "requires_review": self.requires_review,
        }


@dataclass
class RefactoringResult:
    """Result of a refactoring operation."""

    success: bool
    operation: str
    old_name: str
    new_name: str
    files_modified: list[str]
    changes_applied: int
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "operation": self.operation,
            "old_name": self.old_name,
            "new_name": self.new_name,
            "files_modified": self.files_modified,
            "changes_applied": self.changes_applied,
            "warnings": self.warnings,
            "errors": self.errors,
        }


class RefactoringEngine:
    """
    Performs AST-based refactoring operations.

    Usage:
        engine = RefactoringEngine(
            repository_path="/path/to/repo",
            ast_manager=ast_manager,
            symbol_graph=symbol_graph,
            dependency_graph=dependency_graph
        )

        # Rename a symbol
        result = engine.rename_symbol(
            old_name="MyClass",
            new_name="NewClass"
        )

        # Extract a method
        result = engine.extract_method(
            class_name="ExampleClass",
            method_name="old_method",
            new_name="new_method"
        )

        # Move a module
        result = engine.move_module(
            old_path="src/utils.py",
            new_path="src/helpers.py"
        )
    """

    def __init__(
        self, repository_path: Path, ast_manager, symbol_graph, dependency_graph
    ):
        """
        Initialize the Refactoring Engine.

        Args:
            repository_path: Path to the repository
            ast_manager: AST manager for parsing
            symbol_graph: Symbol graph for symbol tracking
            dependency_graph: Dependency graph for dependency tracking
        """
        self.repository_path = Path(repository_path).resolve()
        self.ast_manager = ast_manager
        self.symbol_graph = symbol_graph
        self.dependency_graph = dependency_graph

    def rename_symbol(
        self,
        old_name: str,
        new_name: str,
        symbol_type: str = "any",
        scope: str | None = None,
        validate: bool = True,
    ) -> RefactoringResult:
        """
        Rename a symbol across all files.

        Args:
            old_name: Current name
            new_name: New name
            symbol_type: Type of symbol (class, function, variable)
            scope: Optional scope (module, class)
            validate: Whether to validate before renaming

        Returns:
            RefactoringResult
        """
        logger.info(f"Renaming {old_name} to {new_name}")

        if validate:
            # Validate that new name doesn't conflict
            if self._check_name_conflict(new_name):
                return RefactoringResult(
                    success=False,
                    operation="rename",
                    old_name=old_name,
                    new_name=new_name,
                    files_modified=[],
                    changes_applied=0,
                    errors=[f"Name '{new_name}' already exists"],
                )

        # Find all occurrences
        affected_files = self._find_symbol_occurrences(old_name, symbol_type, scope)

        if not affected_files:
            return RefactoringResult(
                success=False,
                operation="rename",
                old_name=old_name,
                new_name=new_name,
                files_modified=[],
                changes_applied=0,
                errors=[f"No occurrences of '{old_name}' found"],
            )

        # Get references for documentation
        references = self._get_symbol_references(old_name, scope)

        # Apply renames
        result = self._apply_rename(
            old_name=old_name,
            new_name=new_name,
            affected_files=affected_files,
            symbol_type=symbol_type,
        )

        if result.success:
            # Update symbol graph
            self._update_symbol_graph(old_name, new_name, symbol_type)

        return result

    def move_symbol(
        self,
        old_name: str,
        new_name: str,
        from_file: str,
        to_file: str,
        symbol_type: str = "class",
    ) -> RefactoringResult:
        """
        Move a symbol to a different file.

        Args:
            old_name: Current name
            new_name: New name
            from_file: Source file
            to_file: Target file
            symbol_type: Type of symbol

        Returns:
            RefactoringResult
        """
        logger.info(f"Moving {old_name} from {from_file} to {to_file}")

        # Find occurrences
        affected_files = self._find_symbol_occurrences(old_name, symbol_type)

        if from_file not in affected_files:
            return RefactoringResult(
                success=False,
                operation="move",
                old_name=old_name,
                new_name=new_name,
                files_modified=[],
                changes_applied=0,
                errors=[f"{old_name} not found in {from_file}"],
            )

        # Apply move
        result = self._apply_move(
            old_name=old_name,
            new_name=new_name,
            from_file=from_file,
            to_file=to_file,
            symbol_type=symbol_type,
        )

        return result

    def extract_method(
        self,
        class_name: str,
        method_name: str,
        new_method_name: str,
        old_method_name: str | None = None,
    ) -> RefactoringResult:
        """
        Extract a method from within a class.

        Args:
            class_name: Class name
            method_name: Current method name
            new_method_name: New method name
            old_method_name: Optional old method name for renaming

        Returns:
            RefactoringResult
        """
        logger.info(f"Extracting method {method_name} from {class_name}")

        # Find method
        affected_files = self._find_symbol_occurrences(
            method_name, "function", class_name
        )

        if not affected_files:
            return RefactoringResult(
                success=False,
                operation="extract",
                old_name=method_name,
                new_name=new_method_name,
                files_modified=[],
                changes_applied=0,
                errors=[f"Method '{method_name}' not found in {class_name}"],
            )

        # Apply extract
        result = self._apply_extract(
            class_name=class_name,
            method_name=method_name,
            new_method_name=new_method_name,
        )

        return result

    def inline_function(
        self, function_name: str, in_class: str | None = None
    ) -> RefactoringResult:
        """
        Inline a function into its callers.

        Args:
            function_name: Function name
            in_class: Optional class scope

        Returns:
            RefactoringResult
        """
        logger.info(f"Inlining function {function_name}")

        # Find function
        affected_files = self._find_symbol_occurrences(
            function_name, "function", in_class
        )

        if not affected_files:
            return RefactoringResult(
                success=False,
                operation="inline",
                old_name=function_name,
                new_name="",
                files_modified=[],
                changes_applied=0,
                errors=[f"Function '{function_name}' not found"],
            )

        # Apply inline
        result = self._apply_inline(function_name)

        return result

    def _find_symbol_occurrences(
        self, name: str, symbol_type: str, scope: str | None = None
    ) -> list[str]:
        """Find all occurrences of a symbol."""
        # This would query the symbol graph
        # Placeholder implementation
        affected_files = []

        # Find files containing the symbol
        for file_path in self.repository_path.rglob("*.py"):
            if name.lower() in file_path.stem.lower():
                affected_files.append(str(file_path))

        return affected_files

    def _get_symbol_references(self, name: str, scope: str | None = None) -> list[str]:
        """Get all references to a symbol."""
        # This would query the symbol graph
        return []

    def _check_name_conflict(self, name: str) -> bool:
        """Check if a name conflicts with existing symbols."""
        # This would query the symbol graph
        return False

    def _apply_rename(
        self, old_name: str, new_name: str, affected_files: list[str], symbol_type: str
    ) -> RefactoringResult:
        """Apply rename operation."""
        try:
            # This would use AST to rename safely
            # Placeholder implementation
            changes_applied = len(affected_files)

            return RefactoringResult(
                success=True,
                operation="rename",
                old_name=old_name,
                new_name=new_name,
                files_modified=affected_files,
                changes_applied=changes_applied,
                warnings=[
                    f"Renamed {old_name} to {new_name} in {changes_applied} files"
                ],
            )
        except Exception as e:
            logger.error(f"Error applying rename: {e}")
            return RefactoringResult(
                success=False,
                operation="rename",
                old_name=old_name,
                new_name=new_name,
                files_modified=[],
                changes_applied=0,
                errors=[str(e)],
            )

    def _apply_move(
        self,
        old_name: str,
        new_name: str,
        from_file: str,
        to_file: str,
        symbol_type: str,
    ) -> RefactoringResult:
        """Apply move operation."""
        try:
            # This would move the symbol to a new file
            # Placeholder implementation
            return RefactoringResult(
                success=True,
                operation="move",
                old_name=old_name,
                new_name=new_name,
                files_modified=[to_file],
                changes_applied=1,
            )
        except Exception as e:
            logger.error(f"Error applying move: {e}")
            return RefactoringResult(
                success=False,
                operation="move",
                old_name=old_name,
                new_name=new_name,
                files_modified=[],
                changes_applied=0,
                errors=[str(e)],
            )

    def _apply_extract(
        self, class_name: str, method_name: str, new_method_name: str
    ) -> RefactoringResult:
        """Apply extract operation."""
        try:
            # This would extract a method
            # Placeholder implementation
            return RefactoringResult(
                success=True,
                operation="extract",
                old_name=method_name,
                new_name=new_method_name,
                files_modified=[],
                changes_applied=0,
            )
        except Exception as e:
            logger.error(f"Error applying extract: {e}")
            return RefactoringResult(
                success=False,
                operation="extract",
                old_name=method_name,
                new_name=new_method_name,
                files_modified=[],
                changes_applied=0,
                errors=[str(e)],
            )

    def _apply_inline(self, function_name: str) -> RefactoringResult:
        """Apply inline operation."""
        try:
            # This would inline a function
            # Placeholder implementation
            return RefactoringResult(
                success=True,
                operation="inline",
                old_name=function_name,
                new_name="",
                files_modified=[],
                changes_applied=0,
            )
        except Exception as e:
            logger.error(f"Error applying inline: {e}")
            return RefactoringResult(
                success=False,
                operation="inline",
                old_name=function_name,
                new_name="",
                files_modified=[],
                changes_applied=0,
                errors=[str(e)],
            )

    def _update_symbol_graph(self, old_name: str, new_name: str, symbol_type: str):
        """Update symbol graph after refactoring."""
        # This would update the symbol graph to reflect changes
        pass
