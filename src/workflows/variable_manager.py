"""
Variable Manager

Manages workflow variables and provides variable storage, retrieval, and manipulation.
"""


import json
from typing import Any, Dict, Optional
from datetime import datetime

from .models import TriggerData


class VariableManager:
    """
    Manages workflow variables and their values.
    Provides methods for setting, getting, updating, and persisting variables.
    """

    def __init__(self, trigger_data: Optional[TriggerData] = None):
        """
        Initialize variable manager.

        Args:
            trigger_data: Optional trigger data to initialize variables from
        """
        self._variables: Dict[str, Any] = {}
        self._variable_history: Dict[str, List[Dict[str, Any]]] = {}
        self._created_at = datetime.now()
        self._trigger_data = trigger_data

        # Initialize with trigger data if provided
        if trigger_data and trigger_data.trigger_data:
            for key, value in trigger_data.trigger_data.items():
                self.set_variable(key, value, init=True)

    def set_variable(
        self,
        name: str,
        value: Any,
        init: bool = False,
        source: str = "workflow",
        step_id: Optional[str] = None,
        persistent: bool = True
    ) -> bool:
        """
        Set a variable to a value.

        Args:
            name: Variable name
            value: Variable value
            init: Whether this is an initialization (doesn't create history)
            source: Source of the variable (workflow, trigger, step, system)
            step_id: ID of the step that set the variable
            persistent: Whether variable should persist

        Returns:
            True if successful, False otherwise
        """
        if not init:
            # Add to history
            self._variable_history[name] = self._variable_history.get(name, [])
            self._variable_history[name].append({
                "timestamp": datetime.now().isoformat(),
                "value": value,
                "source": source,
                "step_id": step_id
            })

        # Update variable
        self._variables[name] = value
        return True

    def get_variable(self, name: str, default: Any = None) -> Any:
        """
        Get a variable value.

        Args:
            name: Variable name
            default: Default value if variable doesn't exist

        Returns:
            Variable value or default
        """
        return self._variables.get(name, default)

    def update_variable(self, name: str, value: Any) -> bool:
        """
        Update an existing variable.

        Args:
            name: Variable name
            value: New value

        Returns:
            True if successful, False if variable doesn't exist
        """
        if name in self._variables:
            return self.set_variable(name, value)
        return False

    def delete_variable(self, name: str) -> bool:
        """
        Delete a variable.

        Args:
            name: Variable name

        Returns:
            True if successful, False if variable doesn't exist
        """
        if name in self._variables:
            del self._variables[name]
            if name in self._variable_history:
                del self._variable_history[name]
            return True
        return False

    def get_all_variables(self) -> Dict[str, Any]:
        """
        Get all variables.

        Returns:
            Dictionary of all variables
        """
        return self._variables.copy()

    def get_variable_history(self, name: str) -> List[Dict[str, Any]]:
        """
        Get variable history.

        Args:
            name: Variable name

        Returns:
            List of history entries
        """
        return self._variable_history.get(name, [])

    def clear_variable_history(self, name: Optional[str] = None) -> None:
        """
        Clear variable history.

        Args:
            name: Variable name, or None to clear all histories
        """
        if name:
            self._variable_history[name] = []
        else:
            self._variable_history = {}

    def get_variable_types(self) -> Dict[str, str]:
        """
        Get all variable types.

        Returns:
            Dictionary mapping variable names to types
        """
        types = {}
        for name, value in self._variables.items():
            types[name] = type(value).__name__
        return types

    def check_variable_exists(self, name: str) -> bool:
        """
        Check if a variable exists.

        Args:
            name: Variable name

        Returns:
            True if variable exists
        """
        return name in self._variables

    def validate_variable(self, name: str, expected_type: type) -> bool:
        """
        Validate a variable has the expected type.

        Args:
            name: Variable name
            expected_type: Expected type

        Returns:
            True if variable exists and matches expected type
        """
        value = self.get_variable(name)
        if value is None:
            return False
        return isinstance(value, expected_type)

    def get_variable_count(self) -> int:
        """
        Get the number of variables.

        Returns:
            Number of variables
        """
        return len(self._variables)

    def export_variables(self) -> Dict[str, Any]:
        """
        Export all variables.

        Returns:
            Dictionary of all variables with metadata
        """
        return {
            "variables": self._variables,
            "variable_count": len(self._variables),
            "created_at": self._created_at.isoformat(),
            "last_updated": datetime.now().isoformat()
        }

    def import_variables(self, data: Dict[str, Any]) -> bool:
        """
        Import variables from data.

        Args:
            data: Dictionary containing variables and metadata

        Returns:
            True if successful
        """
        try:
            variables = data.get("variables", {})
            for name, value in variables.items():
                self.set_variable(name, value)
            return True
        except Exception:
            return False

    def reset_variables(self) -> None:
        """Reset all variables to empty state."""
        self._variables = {}
        self._variable_history = {}

    def set_context_data(self, data: Dict[str, Any]) -> None:
        """
        Set context data (non-persistent).

        Args:
            data: Dictionary of context data
        """
        for key, value in data.items():
            if key.startswith("_ctx_"):
                self._variables[key] = value

    def get_context_data(self) -> Dict[str, Any]:
        """
        Get all context data.

        Returns:
            Dictionary of context data
        """
        return {
            k: v for k, v in self._variables.items() if k.startswith("_ctx_")
        }

    def clear_context_data(self) -> None:
        """Clear all context data."""
        self._variables = {
            k: v for k, v in self._variables.items() if not k.startswith("_ctx_")
        }

    def merge_variables(self, other_manager: 'VariableManager') -> None:
        """
        Merge variables from another manager.

        Args:
            other_manager: Another VariableManager instance
        """
        for name, value in other_manager._variables.items():
            self.set_variable(name, value)

    def deep_clone(self) -> 'VariableManager':
        """
        Create a deep clone of this variable manager.

        Returns:
            New VariableManager instance
        """
        import copy
        new_manager = VariableManager(self._trigger_data)
        new_manager._variables = copy.deepcopy(self._variables)
        new_manager._variable_history = copy.deepcopy(self._variable_history)
        return new_manager

    def get_variable_summary(self) -> Dict[str, Any]:
        """
        Get a summary of variables.

        Returns:
            Dictionary with variable summary information
        """
        return {
            "total_variables": len(self._variables),
            "variable_types": self.get_variable_types(),
            "created_at": self._created_at.isoformat(),
            "last_updated": datetime.now().isoformat()
        }

    def add_variable_comment(self, name: str, comment: str) -> bool:
        """
        Add a comment to a variable.

        Args:
            name: Variable name
            comment: Comment to add

        Returns:
            True if successful, False if variable doesn't exist
        """
        if name in self._variables:
            if not hasattr(self._variables[name], "__comments__"):
                self._variables[name].__comments__ = []
            self._variables[name].__comments__.append(comment)
            return True
        return False

    def get_variable_comments(self, name: str) -> List[str]:
        """
        Get comments for a variable.

        Args:
            name: Variable name

        Returns:
            List of comments
        """
        value = self.get_variable(name)
        if value and hasattr(value, "__comments__"):
            return value.__comments__
        return []
