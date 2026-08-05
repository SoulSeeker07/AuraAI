"""
Tool Execution Engine - Execution Context Management

This module manages the execution context for tool executions, including
environment variables, working directory, and user-provided context.
"""

import os
from pathlib import Path
from typing import Any


class ExecutionContext:
    """Provides context for tool execution."""

    def __init__(
        self,
        execution_id: str,
        working_directory: str | None = None,
        environment: dict[str, str] | None = None,
        user_context: dict[str, Any] | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.execution_id = execution_id
        self.working_directory = working_directory or os.getcwd()
        self.environment = environment or {}
        self.user_context = user_context or {}
        self.session_id = session_id
        self.metadata = metadata or {}

        # Create a base environment by copying current process environment
        self._base_environment = dict(os.environ)
        self._environment_modified = False

    @property
    def resolved_working_directory(self) -> Path:
        """Get the resolved working directory."""
        return Path(self.working_directory).resolve()

    @property
    def resolved_environment(self) -> dict[str, str]:
        """Get the resolved environment dictionary."""
        env = dict(self._base_environment)
        env.update(self.environment)
        return env

    def set_environment_variable(self, key: str, value: str) -> None:
        """Set an environment variable for this execution."""
        self.environment[key] = value
        self._environment_modified = True

    def remove_environment_variable(self, key: str) -> None:
        """Remove an environment variable."""
        if key in self.environment:
            del self.environment[key]
            self._environment_modified = True

    def set_working_directory(self, directory: str) -> None:
        """Set the working directory for this execution."""
        self.working_directory = os.path.abspath(directory)

    def add_context(self, key: str, value: Any) -> None:
        """Add user-provided context."""
        self.user_context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """Get a value from user context."""
        return self.user_context.get(key, default)

    def update_metadata(self, key: str, value: Any) -> None:
        """Update execution metadata."""
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get a value from metadata."""
        return self.metadata.get(key, default)

    def get_all_metadata(self) -> dict[str, Any]:
        """Get all metadata."""
        return dict(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        """Convert execution context to dictionary."""
        return {
            "execution_id": self.execution_id,
            "working_directory": self.working_directory,
            "has_modified_environment": self._environment_modified,
            "environment_variables_count": len(self.environment),
            "session_id": self.session_id,
            "context_keys": list(self.user_context.keys()),
            "metadata_keys": list(self.metadata.keys()),
        }


class ExecutionContextManager:
    """Manages execution contexts for concurrent executions."""

    def __init__(self):
        self._contexts: dict[str, ExecutionContext] = {}
        self._lock = None  # Will be set on initialization

    def create_context(
        self,
        execution_id: str,
        working_directory: str | None = None,
        environment: dict[str, str] | None = None,
        user_context: dict[str, Any] | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionContext:
        """Create a new execution context."""
        with self._get_lock():
            context = ExecutionContext(
                execution_id,
                working_directory,
                environment,
                user_context,
                session_id,
                metadata,
            )
            self._contexts[execution_id] = context
            return context

    def get_context(self, execution_id: str) -> ExecutionContext | None:
        """Get an execution context."""
        with self._get_lock():
            return self._contexts.get(execution_id)

    def remove_context(self, execution_id: str) -> ExecutionContext | None:
        """Remove an execution context."""
        with self._get_lock():
            return self._contexts.pop(execution_id, None)

    def update_context(self, execution_id: str, **kwargs) -> ExecutionContext | None:
        """Update an execution context."""
        with self._get_lock():
            context = self._contexts.get(execution_id)
            if context:
                for key, value in kwargs.items():
                    if hasattr(context, key):
                        setattr(context, key, value)
            return context

    def clear_all(self) -> None:
        """Clear all contexts (for testing)."""
        with self._get_lock():
            self._contexts.clear()

    def _get_lock(self):
        """Get or create the lock."""
        if self._lock is None:
            self._lock = threading.RLock()
        return self._lock
