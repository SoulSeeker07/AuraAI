"""
Tool Execution Engine - Custom Exceptions

This module defines all custom exceptions used throughout the execution engine.
All exceptions derive from ExecutionError which provides a consistent interface.
"""


class ExecutionError(Exception):
    """Base exception for all execution-related errors."""
    
    def __init__(self, message: str, execution_id: str = None, details: dict = None):
        self.message = message
        self.execution_id = execution_id
        self.details = details or {}
        super().__init__(message)
    
    def __str__(self):
        if self.execution_id:
            return f"[{self.execution_id}] {self.message}"
        return self.message


class ToolValidationError(ExecutionError):
    """Raised when a tool fails validation."""
    
    def __init__(self, message: str, execution_id: str = None, invalid_params: dict = None):
        self.invalid_params = invalid_params or {}
        super().__init__(message, execution_id, {"error_type": "validation_error"})


class PermissionDeniedError(ExecutionError):
    """Raised when a tool execution is denied due to permission issues."""
    
    def __init__(
        self, 
        message: str, 
        execution_id: str = None, 
        required_permission: str = None,
        permission_level: str = None,
        resource: str = None
    ):
        self.required_permission = required_permission
        self.permission_level = permission_level
        self.resource = resource
        super().__init__(message, execution_id, {
            "error_type": "permission_denied",
            "required_permission": required_permission,
            "permission_level": permission_level,
            "resource": resource
        })


class RiskLevelError(ExecutionError):
    """Raised when a tool execution exceeds allowed risk level."""
    
    def __init__(
        self, 
        message: str, 
        execution_id: str = None,
        tool_risk_level: str = None,
        allowed_risk_level: str = None,
        operation: str = None
    ):
        self.tool_risk_level = tool_risk_level
        self.allowed_risk_level = allowed_risk_level
        self.operation = operation
        super().__init__(message, execution_id, {
            "error_type": "risk_level_exceeded",
            "tool_risk_level": tool_risk_level,
            "allowed_risk_level": allowed_risk_level,
            "operation": operation
        })


class TimeoutError(ExecutionError):
    """Raised when a tool execution times out."""
    
    def __init__(
        self, 
        message: str, 
        execution_id: str = None,
        timeout_seconds: int = None,
        tool_name: str = None
    ):
        self.timeout_seconds = timeout_seconds
        self.tool_name = tool_name
        super().__init__(message, execution_id, {
            "error_type": "timeout_error",
            "timeout_seconds": timeout_seconds,
            "tool_name": tool_name
        })


class CancellationError(ExecutionError):
    """Raised when a tool execution is cancelled."""
    
    def __init__(self, message: str = "Execution cancelled by user", execution_id: str = None):
        super().__init__(message, execution_id, {"error_type": "cancelled"})


class ToolNotFoundError(ExecutionError):
    """Raised when a requested tool is not found."""
    
    def __init__(self, tool_name: str, execution_id: str = None, tool_category: str = None):
        self.tool_name = tool_name
        self.tool_category = tool_category
        message = f"Tool '{tool_name}' not found"
        if tool_category:
            message += f" in category '{tool_category}'"
        super().__init__(message, execution_id, {
            "error_type": "tool_not_found",
            "tool_name": tool_name,
            "tool_category": tool_category
        })


class ToolExecutionError(ExecutionError):
    """Raised when a tool execution fails."""
    
    def __init__(
        self, 
        message: str, 
        execution_id: str = None,
        tool_name: str = None,
        tool_category: str = None,
        original_error: Exception = None
    ):
        self.tool_name = tool_name
        self.tool_category = tool_category
        self.original_error = original_error
        super().__init__(message, execution_id, {
            "error_type": "tool_execution_error",
            "tool_name": tool_name,
            "tool_category": tool_category
        })


class ResultValidationError(ExecutionError):
    """Raised when a tool result is invalid."""
    
    def __init__(self, message: str, execution_id: str = None, invalid_fields: list = None):
        self.invalid_fields = invalid_fields or []
        super().__init__(message, execution_id, {
            "error_type": "result_validation_error",
            "invalid_fields": invalid_fields
        })


class ParallelExecutionError(ExecutionError):
    """Raised when parallel execution fails."""
    
    def __init__(
        self, 
        message: str, 
        execution_id: str = None,
        failed_tasks: list = None
    ):
        self.failed_tasks = failed_tasks or []
        super().__init__(message, execution_id, {
            "error_type": "parallel_execution_error",
            "failed_tasks": failed_tasks
        })
