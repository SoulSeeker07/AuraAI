"""
Tool Execution Engine - Standardized Result Object

This module defines the standardized result object that all tools must return.
This ensures consistent output format across all tool executions.
"""


import json
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from dataclasses import dataclass, asdict
from .exceptions import ExecutionError


@dataclass
class ToolExecutionResult:
    """Standardized result object for tool executions."""
    
    success: bool
    output: Any
    execution_id: Optional[str] = None
    execution_time: Optional[float] = None
    error: Optional[str] = None
    warnings: List[str] = None
    affected_files: List[str] = None
    affected_directories: List[str] = None
    execution_metadata: Dict[str, Any] = None
    logs: List[str] = None
    next_suggestions: List[str] = None
    tool_name: Optional[str] = None
    tool_category: Optional[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.affected_files is None:
            self.affected_files = []
        if self.affected_directories is None:
            self.affected_directories = []
        if self.execution_metadata is None:
            self.execution_metadata = {}
        if self.logs is None:
            self.logs = []
        if self.next_suggestions is None:
            self.next_suggestions = []
    
    @classmethod
    def success_result(
        cls,
        output: Any,
        execution_id: str = None,
        execution_time: float = None,
        affected_files: List[str] = None,
        affected_directories: List[str] = None,
        next_suggestions: List[str] = None,
        **metadata
    ) -> 'ToolExecutionResult':
        """Create a successful result."""
        return cls(
            success=True,
            output=output,
            execution_id=execution_id,
            execution_time=execution_time,
            affected_files=affected_files or [],
            affected_directories=affected_directories or [],
            next_suggestions=next_suggestions or [],
            execution_metadata=metadata
        )
    
    @classmethod
    def error_result(
        cls,
        error: str,
        execution_id: str = None,
        execution_time: float = None,
        warnings: List[str] = None,
        tool_name: str = None,
        tool_category: str = None,
        **metadata
    ) -> 'ToolExecutionResult':
        """Create a failed result."""
        return cls(
            success=False,
            output=None,
            error=error,
            execution_id=execution_id,
            execution_time=execution_time,
            warnings=warnings or [],
            tool_name=tool_name,
            tool_category=tool_category,
            execution_metadata=metadata
        )
    
    @classmethod
    def partial_result(
        cls,
        output: Any,
        execution_id: str = None,
        warnings: List[str] = None,
        **metadata
    ) -> 'ToolExecutionResult':
        """Create a partial result (success but with warnings)."""
        return cls(
            success=True,
            output=output,
            execution_id=execution_id,
            warnings=warnings or [],
            execution_metadata=metadata
        )
    
    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self.warnings.append(warning)
    
    def add_log(self, log: str) -> None:
        """Add a log message."""
        self.logs.append(log)
    
    def add_affected_file(self, file_path: str) -> None:
        """Add an affected file path."""
        if file_path not in self.affected_files:
            self.affected_files.append(file_path)
    
    def add_affected_directory(self, directory_path: str) -> None:
        """Add an affected directory path."""
        if directory_path not in self.affected_directories:
            self.affected_directories.append(directory_path)
    
    def add_next_suggestion(self, suggestion: str) -> None:
        """Add a suggestion for next steps."""
        if suggestion not in self.next_suggestions:
            self.next_suggestions.append(suggestion)
    
    def update_metadata(self, key: str, value: Any) -> None:
        """Update execution metadata."""
        self.execution_metadata[key] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        result_dict = asdict(self)
        
        # Convert datetime to ISO format if present
        if 'execution_time' in result_dict and result_dict['execution_time'] is not None:
            result_dict['execution_time'] = float(result_dict['execution_time'])
        
        return result_dict
    
    def to_json(self, indent: int = 2) -> str:
        """Convert result to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ToolExecutionResult':
        """Create result from dictionary."""
        return cls(**data)
    
    @classmethod
    def from_error(cls, error: Exception, execution_id: str = None) -> 'ToolExecutionResult':
        """Create a result from an exception."""
        return cls.error_result(
            error=str(error),
            execution_id=execution_id,
            execution_metadata={
                'error_type': type(error).__name__,
                'error_details': str(error)
            }
        )


class ExecutionResultManager:
    """Manages tool execution results."""
    
    def __init__(self):
        self._results: Dict[str, ToolExecutionResult] = {}
    
    def create_result(
        self,
        execution_id: str,
        success: bool,
        output: Any = None,
        **kwargs
    ) -> ToolExecutionResult:
        """Create a new result."""
        result = ToolExecutionResult(success=success, output=output, execution_id=execution_id, **kwargs)
        self._results[execution_id] = result
        return result
    
    def get_result(self, execution_id: str) -> Optional[ToolExecutionResult]:
        """Get a result."""
        return self._results.get(execution_id)
    
    def remove_result(self, execution_id: str) -> Optional[ToolExecutionResult]:
        """Remove a result."""
        return self._results.pop(execution_id, None)
    
    def update_result(
        self,
        execution_id: str,
        **kwargs
    ) -> Optional[ToolExecutionResult]:
        """Update a result."""
        result = self._results.get(execution_id)
        if result:
            for key, value in kwargs.items():
                if hasattr(result, key):
                    setattr(result, key, value)
        return result
    
    def list_results(self) -> List[Dict[str, Any]]:
        """List all results."""
        return [result.to_dict() for result in self._results.values()]
    
    def get_success_count(self) -> int:
        """Get the count of successful results."""
        return sum(1 for result in self._results.values() if result.success)
    
    def get_failure_count(self) -> int:
        """Get the count of failed results."""
        return sum(1 for result in self._results.values() if not result.success)
    
    def clear_all(self) -> None:
        """Clear all results (for testing)."""
        self._results.clear()
