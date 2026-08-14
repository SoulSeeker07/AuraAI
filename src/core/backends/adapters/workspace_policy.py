import os
from pathlib import Path

class WorkspacePolicyError(Exception):
    """Raised when a workspace policy is violated."""
    pass


class WorkspacePolicy:
    """
    Deterministic workspace policy to enforce file safety boundaries 
    during automated code generation.
    """

    # Protected paths that the LLM is never allowed to overwrite
    PROTECTED_PATHS = {
        ".git",
        ".env",
        ".venv",
        "node_modules",
        "__pycache__",
        "src/core/backends/adapters",  # protecting the adapter itself
    }

    # Allowed extensions for generation (can be extended)
    ALLOWED_EXTENSIONS = {
        ".py",
        ".js",
        ".ts",
        ".html",
        ".css",
        ".json",
        ".md",
        ".txt",
        ".yaml",
        ".yml",
        ".sh",
    }

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root.resolve()

    def validate_path(self, file_path: str) -> Path:
        """
        Normalizes and resolves the requested file path.
        Returns the absolute Path if valid, otherwise raises WorkspacePolicyError.
        """
        # Normalize slashes and resolve
        clean_path = os.path.normpath(file_path)
        if clean_path.startswith("/") or clean_path.startswith("\\"):
            raise WorkspacePolicyError(f"Absolute paths are not allowed: {file_path}")

        if ".." in clean_path.split(os.sep):
            raise WorkspacePolicyError(f"Path traversal is not allowed: {file_path}")

        target_path = (self.workspace_root / clean_path).resolve()
        return target_path

    def validate_boundary(self, target_path: Path) -> None:
        """Ensures the target path is strictly within the workspace root."""
        try:
            target_path.relative_to(self.workspace_root)
        except ValueError:
            raise WorkspacePolicyError(
                f"Path breaks workspace boundary: {target_path}"
            )

    def validate_extension(self, target_path: Path) -> None:
        """Ensures the file extension is allowed."""
        # Allow files without extensions (e.g. Dockerfile) or specific extensions
        if not target_path.suffix:
            return
            
        if target_path.suffix.lower() not in self.ALLOWED_EXTENSIONS:
            raise WorkspacePolicyError(
                f"File extension not allowed for automated generation: {target_path.suffix}"
            )

    def validate_protected_path(self, target_path: Path) -> None:
        """Ensures the file does not reside in a protected directory."""
        try:
            rel_path = target_path.relative_to(self.workspace_root)
            parts = rel_path.parts
            
            # Check if any part of the path is protected
            for i in range(len(parts)):
                sub_path = "/".join(parts[:i+1])
                if sub_path in self.PROTECTED_PATHS or parts[i] in self.PROTECTED_PATHS:
                    raise WorkspacePolicyError(
                        f"Path intersects with protected paths: {target_path}"
                    )
        except ValueError:
            pass # Already caught by boundary check

    def check_existing_file(self, target_path: Path, allow_overwrite: bool = False) -> None:
        """Ensures we don't silently overwrite existing user files."""
        if target_path.exists() and not allow_overwrite:
            raise WorkspacePolicyError(
                f"File already exists and overwrite is not authorized: {target_path}"
            )

    def authorize_write(self, file_path: str, allow_overwrite: bool = False) -> Path:
        """
        Executes all validation checks and returns the authorized absolute Path.
        """
        target_path = self.validate_path(file_path)
        self.validate_boundary(target_path)
        
        # M20.5: Enforce project directory policy for generic files
        rel_path = target_path.relative_to(self.workspace_root)
        if len(rel_path.parts) == 1 and rel_path.name.lower() in ["app.py", "main.py", "script.py", "index.py", "index.js", "index.html"]:
            raise WorkspacePolicyError(f"Attempted to write generic file '{rel_path.name}' directly to root. Please place it in a project subdirectory.")

        self.validate_extension(target_path)
        self.validate_protected_path(target_path)
        self.check_existing_file(target_path, allow_overwrite=allow_overwrite)
        return target_path
