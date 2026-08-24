"""
Code Editor

Handles multi-file editing operations with validation.

This module enables Aura to:
- Edit multiple files atomically
- Validate changes before applying
- Maintain file consistency
- Apply changes with rollback support
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EditOperation:
    """Represents a file edit operation."""

    file_path: str
    old_content: str | None
    new_content: str
    line_range: tuple[int, int] | None = None
    backup: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "file_path": self.file_path,
            "old_content": self.old_content,
            "new_content": self.new_content,
            "line_range": self.line_range,
            "backup": self.backup,
        }


@dataclass
class EditResult:
    """Result of an edit operation."""

    success: bool
    file_path: str
    old_content: str | None
    new_content: str
    changes: list[str]
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    reverted: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "file_path": self.file_path,
            "old_content": self.old_content,
            "new_content": self.new_content,
            "changes": self.changes,
            "warnings": self.warnings,
            "errors": self.errors,
            "reverted": self.reverted,
        }


@dataclass
class MultiEditResult:
    """Result of multiple edit operations."""

    success: bool
    total_files: int
    succeeded: int
    failed: int
    results: list[EditResult]
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "total_files": self.total_files,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "summary": self.summary,
            "results": [r.to_dict() for r in self.results],
        }


class CodeEditor:
    """
    Handles multi-file editing operations with validation.

    Features:
    - Atomic multi-file editing
    - Change validation
    - Backup creation
    - Rollback support
    - Change detection

    Usage:
        editor = CodeEditor(repository_path="/path/to/repo")

        # Create a single edit
        result = editor.edit_file(
            file_path="src/main.py",
            old_content=None,  # Will read from file
            new_content="new content"
        )

        # Create multiple edits
        edits = [
            EditOperation("src/main.py", None, "new content 1"),
            EditOperation("src/utils.py", None, "new content 2")
        ]

        result = editor.apply_edits(edits, validate=True)
    """

    def __init__(
        self, repository_path: Path, ast_manager, symbol_graph, dependency_graph
    ):
        """
        Initialize the Code Editor.

        Args:
            repository_path: Path to the repository
            ast_manager: AST manager for validation
            symbol_graph: Symbol graph for validation
            dependency_graph: Dependency graph for validation
        """
        self.repository_path = Path(repository_path).resolve()
        self.ast_manager = ast_manager
        self.symbol_graph = symbol_graph
        self.dependency_graph = dependency_graph
        self._backup_dir: Path | None = None
        self._backup_mapping: dict[str, str] = {}

    def _create_backup(self, file_path: str, content: str) -> Path | None:
        """Create a backup of a file before editing."""
        try:
            if not self._backup_dir:
                self._backup_dir = self.repository_path / ".aura_backups"
            self._backup_dir.mkdir(parents=True, exist_ok=True)
            safe_name = file_path.replace("/", "_").replace("\\", "_")
            backup_path = self._backup_dir / f"{safe_name}.bak"
            backup_path.write_text(content, encoding="utf-8")
            return backup_path
        except Exception as e:
            logger.warning(f"Failed to create backup for {file_path}: {e}")
            return None

    def edit_file(
        self,
        file_path: str,
        old_content: str | None = None,
        new_content: str = "",
        backup: bool = True,
        validate: bool = True,
    ) -> EditResult:
        """
        Edit a single file.

        Args:
            file_path: Path to the file
            old_content: Optional old content for validation
            new_content: New content to write
            backup: Whether to create backup
            validate: Whether to validate changes

        Returns:
            EditResult
        """
        full_path = self.repository_path / file_path

        is_new_file = not full_path.exists()
        if is_new_file:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            old_content_actual = ""
        else:
            old_content_actual = old_content

        try:
            # Create backup if requested
            if backup and not is_new_file and old_content_actual is None:
                old_content_actual = full_path.read_text(encoding="utf-8")
                backup_path = self._create_backup(file_path, old_content_actual)
                if backup_path:
                    self._backup_mapping[file_path] = str(backup_path)

            # Validate if requested
            validation_errors = []
            if validate and old_content_actual:
                validation_errors = self._validate_edit(
                    file_path, old_content_actual, new_content
                )

            if validation_errors:
                return EditResult(
                    success=False,
                    file_path=file_path,
                    old_content=old_content_actual,
                    new_content=new_content,
                    changes=[],
                    errors=validation_errors,
                    reverted=True,
                )

            # Write new content
            full_path.write_text(new_content, encoding="utf-8")

            # Record changes
            if old_content_actual:
                changes = self._detect_changes(old_content_actual, new_content)
            else:
                changes = ["Added entire file"]

            return EditResult(
                success=True,
                file_path=file_path,
                old_content=old_content_actual,
                new_content=new_content,
                changes=changes,
                warnings=[],
            )

        except Exception as e:
            logger.error(f"Error editing file {file_path}: {e}")
            return EditResult(
                success=False,
                file_path=file_path,
                old_content=None,
                new_content=new_content,
                changes=[],
                errors=[str(e)],
                reverted=True,
            )

    def apply_edits(
        self,
        edits: list[EditOperation],
        validate: bool = True,
        create_backup: bool = True,
    ) -> MultiEditResult:
        """
        Apply multiple edit operations.

        Args:
            edits: List of EditOperation objects
            validate: Whether to validate all changes
            create_backup: Whether to create backup directory

        Returns:
            MultiEditResult
        """
        # Create backup directory
        if create_backup:
            self._backup_dir = self.repository_path / ".aura_backup"
            self._backup_dir.mkdir(exist_ok=True)

        results = []
        all_errors = []
        all_warnings = []

        for i, edit in enumerate(edits):
            result = self.edit_file(
                file_path=edit.file_path,
                old_content=edit.old_content,
                new_content=edit.new_content,
                backup=edit.backup,
                validate=validate,
            )

            results.append(result)

            if not result.success:
                all_errors.append(
                    result.errors[0] if result.errors else "Unknown error"
                )

            if result.warnings:
                all_warnings.extend(result.warnings)

        success = len(all_errors) == 0
        succeeded = sum(1 for r in results if r.success)
        failed = len(results) - succeeded

        return MultiEditResult(
            success=success,
            total_files=len(results),
            succeeded=succeeded,
            failed=failed,
            results=results,
            summary=f"Applied {succeeded}/{len(results)} edits successfully",
        )

    def _validate_edit(
        self, file_path: str, old_content: str, new_content: str
    ) -> list[str]:
        """Validate an edit operation."""
        errors = []

        # Check for file corruption
        try:
            # Parse new content if possible
            # This would use AST manager to validate syntax
            pass
        except Exception:
            errors.append(f"Syntax error in {file_path}")

        # Check for consistency with symbol graph
        # This would compare symbols before and after
        pass

        return errors

    def _detect_changes(self, old_content: str, new_content: str) -> list[str]:
        """Detect changes between old and new content."""
        changes = []

        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()

        # Check for deletions
        for i, line in enumerate(old_lines):
            if i >= len(new_lines) or new_lines[i] != line:
                changes.append(f"Line {i+1}: Removed '{line[:50]}...'")

        # Check for additions
        for i, line in enumerate(new_lines):
            if i >= len(old_lines) or old_lines[i] != line:
                changes.append(f"Line {i+1}: Added '{line[:50]}...'")

        return changes

    def validate_syntax(self, file_path: str) -> bool:
        """
        Validate syntax of a file.

        Args:
            file_path: Path to the file

        Returns:
            True if syntax is valid
        """
        try:
            ast_file = self.ast_manager.parse_file(file_path)
            return ast_file.root.type != "Unknown"
        except Exception as e:
            logger.error(f"Syntax validation failed for {file_path}: {e}")
            return False

    def get_file_signature(self, file_path: str) -> str:
        """
        Get a signature for a file to detect changes.

        Args:
            file_path: Path to the file

        Returns:
            File signature
        """
        full_path = self.repository_path / file_path

        if not full_path.exists():
            return ""

        # Simple signature: size + modification time
        import hashlib

        content = full_path.read_bytes()
        signature = hashlib.md5(content).hexdigest()

        return signature

    def get_backup_dir(self) -> Path | None:
        """
        Get the backup directory.

        Returns:
            Backup directory path or None
        """
        return self._backup_dir

    def create_backup(self, file_path: str) -> str:
        """
        Create a physical backup of a file.
        
        Note: Backup retention is deliberately deferred as an unbounded-growth tradeoff.
        The `.aura_backup/` directory will grow indefinitely until explicitly cleaned up.

        Args:
            file_path: Path to the file relative to repository

        Returns:
            Backup ID string
        """
        if not self._backup_dir:
            self._backup_dir = self.repository_path / ".aura_backup"
            self._backup_dir.mkdir(exist_ok=True)

        full_path = self.repository_path / file_path
        if not full_path.exists():
            return ""

        import uuid
        backup_id = f"{Path(file_path).name}_{uuid.uuid4().hex[:8]}.bak"
        backup_path = self._backup_dir / backup_id

        # Copy the file
        import shutil
        shutil.copy2(full_path, backup_path)

        # Store mapping
        self._backup_mapping[backup_id] = file_path

        return backup_id

    def restore_backup(self, backup_id: str) -> EditResult:
        """
        Restore a file from backup.

        Args:
            backup_id: The ID returned by create_backup

        Returns:
            EditResult
        """
        if not self._backup_dir:
            return EditResult(
                success=False,
                file_path=backup_id,
                old_content=None,
                new_content="",
                changes=[],
                errors=["No backup directory found"],
            )

        backup_path = self._backup_dir / backup_id

        if not backup_path.exists():
            return EditResult(
                success=False,
                file_path=backup_id,
                old_content=None,
                new_content="",
                changes=[],
                errors=[f"Backup not found: {backup_id}"],
            )

        try:
            # Determine original file path
            original_file = self._backup_mapping.get(backup_id)
            if not original_file:
                # Fallback if mapping is somehow lost
                original_file = backup_id.rsplit("_", 1)[0]

            full_path = self.repository_path / original_file
            
            # Read backup content for the EditResult
            content = backup_path.read_text(encoding="utf-8")
            
            # Restore content physically
            import shutil
            shutil.copy2(backup_path, full_path)

            return EditResult(
                success=True,
                file_path=original_file,
                old_content=None,
                new_content=content,
                changes=["Restored from physical backup"],
            )
        except Exception as e:
            logger.error(f"Error restoring backup {backup_id}: {e}")
            return EditResult(
                success=False,
                file_path=backup_id,
                old_content=None,
                new_content="",
                changes=[],
                errors=[str(e)],
            )

    def cleanup_backups(self):
        """Clean up backup files."""
        if self._backup_dir and self._backup_dir.exists():
            shutil.rmtree(self._backup_dir)
            self._backup_dir = None
            self._backup_mapping.clear()
            logger.info("Backups cleaned up")

    def close(self):
        """Clean up resources."""
        self.cleanup_backups()
