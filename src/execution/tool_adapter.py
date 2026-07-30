"""
Tool Execution Engine - Tool Adapter

This module provides adapters for wrapping existing tools to work
with the new ToolInterface. It maintains backward compatibility
while providing the new execution pipeline.
"""


from typing import Dict, Any, List, Optional, Tuple, Callable
from .tool_interface import ToolInterface, ToolMetadata, ToolCategory
from .exceptions import ToolValidationError, ToolNotFoundError


class BaseToolAdapter(ToolInterface):
    """
    Base adapter class for wrapping existing tools.
    
    This class provides a default implementation of the ToolInterface
    that can be extended to wrap existing tools.
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        category: ToolCategory = ToolCategory.GENERAL,
        tags: List[str] = None,
        version: str = "1.0.0",
        requires_confirmation: bool = True
    ):
        """
        Initialize the tool adapter.
        
        Args:
            name: Tool name
            description: Tool description
            category: Tool category
            tags: List of tags
            version: Tool version
            requires_confirmation: Whether confirmation is required
        """
        self._name = name
        self._description = description
        self._category = category
        self._tags = tags or []
        self._version = version
        self._requires_confirmation = requires_confirmation
        
        # Internal state
        self._progress: Dict[str, Any] = {}
        self._status: str = "idle"
        self._supported_operations: List[str] = []
        self._operation_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Progress tracking (optional)
        self.update_progress = None
        self.set_status = None
        self.log = None
        self.log_warning = None
    
    def get_metadata(self) -> ToolMetadata:
        """Get tool metadata."""
        return ToolMetadata(
            name=self._name,
            category=self._category,
            version=self._version,
            description=self._description,
            author="Aura AI",
            tags=self._tags,
            capabilities=self._supported_operations
        )
    
    def get_supported_operations(self) -> List[str]:
        """Get list of supported operations."""
        return self._supported_operations.copy()
    
    def get_operation_metadata(self, operation: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific operation."""
        return self._operation_metadata.get(operation)
    
    def validate(
        self,
        operation: str,
        parameters: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate parameters for an operation.
        
        Args:
            operation: Operation name
            parameters: Parameters to validate
            
        Returns:
            Tuple of (is_valid, list_of_error_messages)
        """
        if operation not in self._supported_operations:
            return False, [f"Operation '{operation}' not supported"]
        
        # Default validation - subclasses should override
        return True, []
    
    def prepare(
        self,
        operation: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepare parameters for execution.
        
        Args:
            operation: Operation name
            parameters: Parameters to prepare
            
        Returns:
            Prepared parameters
        """
        return parameters.copy()
    
    def execute(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Any:
        """
        Execute the operation.
        
        Args:
            operation: Operation name
            parameters: Parameters
            context: Execution context
            
        Returns:
            Operation result
        """
        raise NotImplementedError(
            f"Subclass '{self.__class__.__name__}' must implement 'execute'"
        )
    
    def cleanup(
        self,
        operation: str,
        parameters: Dict[str, Any]
    ) -> None:
        """
        Cleanup after execution.
        
        Args:
            operation: Operation name
            parameters: Parameters
        """
        pass
    
    def get_risk_level(self, operation: str) -> str:
        """
        Get the risk level of an operation.
        
        Args:
            operation: Operation name
            
        Returns:
            Risk level string (LOW, MEDIUM, HIGH, CRITICAL)
        """
        metadata = self._operation_metadata.get(operation, {})
        return metadata.get("risk_level", "MEDIUM")
    
    def requires_confirmation(self, operation: str) -> bool:
        """
        Check if confirmation is required for an operation.
        
        Args:
            operation: Operation name
            
        Returns:
            True if confirmation is required
        """
        return self._requires_confirmation
    
    def add_operation(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any] = None,
        risk_level: str = "MEDIUM",
        requires_confirmation: bool = True
    ) -> None:
        """
        Add a supported operation.
        
        Args:
            name: Operation name
            description: Operation description
            parameters: Operation parameters schema
            risk_level: Risk level (LOW, MEDIUM, HIGH, CRITICAL)
            requires_confirmation: Whether confirmation is required
        """
        self._supported_operations.append(name)
        self._operation_metadata[name] = {
            "description": description,
            "parameters": parameters or {},
            "risk_level": risk_level,
            "requires_confirmation": requires_confirmation
        }
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current progress state."""
        return self._progress.copy()
    
    def set_progress(self, progress: Dict[str, Any]) -> None:
        """Set progress state."""
        self._progress = progress.copy()
    
    def get_status(self) -> str:
        """Get current status."""
        return self._status
    
    def set_status(self, status: str) -> None:
        """Set status."""
        self._status = status
    
    def update_log(self, message: str, level: str = "info") -> None:
        """Update log message."""
        pass
    
    def update_log_warning(self, message: str) -> None:
        """Update warning message."""
        pass


class ProgressReportingAdapterMixin:
    """
    Mixin for tools that support progress reporting.
    
    This mixin provides progress tracking callbacks that can be
    used by tools to report progress during execution.
    """
    
    def set_progress(self, progress: Dict[str, Any]) -> None:
        """
        Set progress state.
        
        Args:
            progress: Progress dictionary with keys like:
                - progress: float (0.0-100.0)
                - current_step: str
                - message: str
                - total: int (optional)
                - completed: int (optional)
        """
        self._progress = progress.copy()
        if self.update_progress:
            self.update_progress(progress)
    
    def update_progress(
        self,
        current_progress: float,
        current_step: str = None,
        message: str = None,
        total: int = None,
        completed: int = None
    ) -> None:
        """
        Update progress.
        
        Args:
            current_progress: Current progress percentage (0.0-100.0)
            current_step: Current step name
            message: Progress message
            total: Total items (for percentage calculation)
            completed: Number of completed items (for percentage calculation)
        """
        progress = {
            "progress": current_progress
        }
        
        if current_step:
            progress["current_step"] = current_step
        
        if message:
            progress["message"] = message
        
        if total is not None and completed is not None:
            progress["total"] = total
            progress["completed"] = completed
            progress["progress"] = (completed / total) * 100
        
        self.set_progress(progress)
    
    def set_status(self, status: str, message: str = None) -> None:
        """
        Set status.
        
        Args:
            status: Status string
            message: Status message
        """
        self._status = status
        if self.set_status:
            self.set_status(status, message)
    
    def update_log(self, message: str, level: str = "info") -> None:
        """
        Update log.
        
        Args:
            message: Log message
            level: Log level (info, warning, error)
        """
        if self.log:
            self.log(message, level)
    
    def update_log_warning(self, message: str) -> None:
        """
        Update warning log.
        
        Args:
            message: Warning message
        """
        if self.log_warning:
            self.log_warning(message)


class CancellationSupportMixin:
    """
    Mixin for tools that support cancellation.
    
    This mixin provides cancellation checks that can be used by
    tools to check for cancellation requests during execution.
    """
    
    def check_cancellation(self) -> bool:
        """
        Check if cancellation is requested.
        
        Returns:
            True if cancellation is requested
        """
        return self._cancellation_requested if hasattr(self, '_cancellation_requested') else False
    
    def set_cancellation_requested(self, requested: bool) -> None:
        """
        Set cancellation requested flag.
        
        Args:
            requested: Whether cancellation is requested
        """
        if hasattr(self, '_cancellation_requested'):
            self._cancellation_requested = requested


class ExistingToolAdapter(BaseToolAdapter, ProgressReportingAdapterMixin, CancellationSupportMixin):
    """
    Adapter for wrapping existing tools with progress and cancellation support.
    
    This adapter wraps existing tool functions/classes and provides
    progress tracking and cancellation support.
    """
    
    def __init__(
        self,
        name: str,
        original_tool: Any,
        description: str,
        category: ToolCategory = ToolCategory.GENERAL,
        tags: List[str] = None,
        version: str = "1.0.0"
    ):
        """
        Initialize the tool adapter.
        
        Args:
            name: Tool name
            original_tool: Existing tool object or callable
            description: Tool description
            category: Tool category
            tags: List of tags
            version: Tool version
        """
        super().__init__(name, description, category, tags, version)
        self.original_tool = original_tool
        self._cancellation_requested = False
        
        # Infer supported operations from tool
        self._infer_operations()
    
    def _infer_operations(self) -> None:
        """
        Infer supported operations from the original tool.
        
        Checks if the tool has methods that might be operations.
        """
        if hasattr(self.original_tool, 'get_supported_operations'):
            try:
                operations = self.original_tool.get_supported_operations()
                for op in operations:
                    self.add_operation(op, f"Operation: {op}")
            except Exception:
                pass  # Continue with default operations
        
        # If no operations inferred, add a default execute operation
        if not self._supported_operations:
            self.add_operation("execute", "Execute the tool", requires_confirmation=False)
    
    def validate(
        self,
        operation: str,
        parameters: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate parameters for an operation.
        
        Args:
            operation: Operation name
            parameters: Parameters to validate
            
        Returns:
            Tuple of (is_valid, list_of_error_messages)
        """
        if operation not in self._supported_operations:
            return False, [f"Operation '{operation}' not supported"]
        
        # Default validation
        if not parameters:
            return True, []
        
        return True, []
    
    def execute(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Any:
        """
        Execute the operation using the original tool.
        
        Args:
            operation: Operation name
            parameters: Parameters
            context: Execution context
            
        Returns:
            Operation result
        """
        if operation not in self._supported_operations:
            raise ToolValidationError(
                f"Operation '{operation}' not supported",
                invalid_params={"operation": operation}
            )
        
        # Check for cancellation
        if self.check_cancellation():
            raise Exception("Operation cancelled")
        
        # Execute using the original tool
        if hasattr(self.original_tool, 'execute'):
            return self.original_tool.execute(operation, parameters, context)
        
        if callable(self.original_tool):
            if len(parameters) == 1:
                return self.original_tool(list(parameters.values())[0])
            return self.original_tool(**parameters)
        
        raise ToolValidationError(
            f"Tool '{self._name}' does not have a callable execute method"
        )
    
    def cleanup(self, operation: str, parameters: Dict[str, Any]) -> None:
        """
        Cleanup after execution.
        
        Args:
            operation: Operation name
            parameters: Parameters
        """
        if hasattr(self.original_tool, 'cleanup'):
            try:
                self.original_tool.cleanup(operation, parameters)
            except Exception:
                pass


class FunctionToolAdapter(BaseToolAdapter, ProgressReportingAdapterMixin, CancellationSupportMixin):
    """
    Adapter for wrapping a simple function as a tool.
    
    This adapter provides a simple way to wrap a function as a tool
    without requiring any modifications to the function itself.
    """
    
    def __init__(
        self,
        name: str,
        function: Callable,
        description: str,
        parameters_schema: Dict[str, Any] = None,
        category: ToolCategory = ToolCategory.GENERAL,
        tags: List[str] = None,
        version: str = "1.0.0"
    ):
        """
        Initialize the function tool adapter.
        
        Args:
            name: Tool name
            function: Callable function to wrap
            description: Tool description
            parameters_schema: Schema for function parameters
            category: Tool category
            tags: List of tags
            version: Tool version
        """
        super().__init__(name, description, category, tags, version)
        self.function = function
        self._parameters_schema = parameters_schema or {}
        
        # Infer operation from function name
        self.add_operation("execute", description, parameters=self._parameters_schema)
    
    def execute(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Any:
        """
        Execute the function.
        
        Args:
            operation: Operation name (should be "execute")
            parameters: Function parameters
            context: Execution context
            
        Returns:
            Function result
        """
        if operation != "execute":
            raise ToolValidationError(
                f"Operation '{operation}' not supported",
                invalid_params={"operation": operation}
            )
        
        # Check for cancellation
        if self.check_cancellation():
            raise Exception("Operation cancelled")
        
        # Call the function
        try:
            result = self.function(**parameters)
            return result
        except Exception as e:
            raise ToolExecutionError(
                f"Function execution failed: {str(e)}",
                original_error=e
            )


# Utility functions for adapting existing tools

def adapt_existing_tool(
    original_tool: Any,
    name: str = None,
    description: str = None,
    category: ToolCategory = ToolCategory.GENERAL,
    tags: List[str] = None,
    version: str = "1.0.0"
) -> ExistingToolAdapter:
    """
    Adapt an existing tool to work with the execution engine.
    
    Args:
        original_tool: Existing tool object or callable
        name: Tool name (defaults to tool's class name or function name)
        description: Tool description
        category: Tool category
        tags: List of tags
        version: Tool version
        
    Returns:
        ExistingToolAdapter instance
    """
    if name is None:
        name = getattr(original_tool, '__name__', original_tool.__class__.__name__)
    
    if description is None:
        description = f"Adapter for existing tool: {name}"
    
    return ExistingToolAdapter(
        name=name,
        original_tool=original_tool,
        description=description,
        category=category,
        tags=tags,
        version=version
    )


def adapt_function(
    function: Callable,
    name: str = None,
    description: str = None,
    parameters_schema: Dict[str, Any] = None,
    category: ToolCategory = ToolCategory.GENERAL,
    version: str = "1.0.0"
) -> FunctionToolAdapter:
    """
    Adapt a function to work with the execution engine.
    
    Args:
        function: Callable function to adapt
        name: Tool name (defaults to function name)
        description: Tool description
        parameters_schema: Schema for function parameters
        category: Tool category
        version: Tool version
        
    Returns:
        FunctionToolAdapter instance
    """
    if name is None:
        name = function.__name__
    
    if description is None:
        description = f"Function: {name}"
    
    return FunctionToolAdapter(
        name=name,
        function=function,
        description=description,
        parameters_schema=parameters_schema,
        category=category,
        version=version
    )
