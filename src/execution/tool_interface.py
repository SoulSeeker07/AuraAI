"""
Tool Execution Engine - Tool Interface

This module defines the interface that all tools must implement to work
with the execution engine. Tools must follow this interface to ensure
consistent behavior, error handling, and progress reporting.
"""


from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from .exceptions import ToolValidationError, ToolExecutionError


class ToolCategory(Enum):
    """Tool categories."""
    FILESYSTEM = "filesystem"
    DESKTOP = "desktop"
    BROWSER = "browser"
    GIT = "git"
    TERMINAL = "terminal"
    VISION = "vision"
    VOICE = "voice"
    KNOWLEDGE = "knowledge"
    NETWORKING = "networking"
    DOCKER = "docker"
    OFFICE = "office"
    EMAIL = "email"
    CALENDAR = "calendar"
    MCP = "mcp"
    GENERAL = "general"


class ToolMetadata:
    """Metadata about a tool."""
    
    def __init__(
        self,
        name: str,
        category: ToolCategory,
        version: str = "1.0.0",
        description: str = "",
        author: str = "",
        tags: List[str] = None,
        capabilities: List[str] = None,
        requires_confirmation: bool = False
    ):
        """
        Initialize tool metadata.
        
        Args:
            name: Tool name
            category: Tool category
            version: Tool version
            description: Tool description
            author: Tool author
            tags: List of tags for categorization
            capabilities: List of capabilities/operations this tool supports
            requires_confirmation: Whether tool requires user confirmation
        """
        self.name = name
        self.category = category
        self.version = version
        self.description = description
        self.author = author
        self.tags = tags or []
        self.capabilities = capabilities or []
        self.requires_confirmation = requires_confirmation
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "category": self.category.value,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "tags": self.tags,
            "capabilities": self.capabilities,
            "requires_confirmation": self.requires_confirmation
        }


class ToolInterface(ABC):
    """
    Abstract base class that all tools must implement.
    
    This interface defines the standard lifecycle and behavior
    for all tools in the execution engine.
    """
    
    def __init__(self, metadata: ToolMetadata = None):
        """
        Initialize the tool.
        
        Args:
            metadata: Tool metadata (optional)
        """
        self._metadata = metadata or self._create_default_metadata()
        self._initialized = False
    
    @abstractmethod
    def get_metadata(self) -> ToolMetadata:
        """
        Get the tool's metadata.
        
        Returns:
            ToolMetadata instance
        """
        pass
    
    @abstractmethod
    def get_supported_operations(self) -> List[str]:
        """
        Get the list of operations supported by this tool.
        
        Returns:
            List of operation names
        """
        pass
    
    @abstractmethod
    def validate(
        self,
        operation: str,
        parameters: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate parameters for an operation.
        
        Args:
            operation: The operation to validate
            parameters: Operation parameters
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        pass
    
    def prepare(self, operation: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare the execution environment.
        
        This is a hook method that can be overridden by tools.
        Default implementation returns parameters as-is.
        
        Args:
            operation: The operation to prepare
            parameters: Operation parameters
            
        Returns:
            Prepared parameters
            
        Raises:
            ToolValidationError: If preparation fails
        """
        return parameters
    
    def execute(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Any:
        """
        Execute an operation.
        
        This is the main method that tools must implement.
        
        Args:
            operation: The operation to execute
            parameters: Operation parameters
            context: Execution context
            
        Returns:
            Operation result
            
        Raises:
            ToolExecutionError: If execution fails
        """
        raise NotImplementedError(f"Tool '{self._metadata.name}' must implement execute()")
    
    def cleanup(self, operation: str, parameters: Dict[str, Any]) -> None:
        """
        Clean up resources after execution.
        
        This is a hook method that can be overridden by tools.
        Default implementation does nothing.
        
        Args:
            operation: The operation that was executed
            parameters: Operation parameters
        """
        pass
    
    def get_risk_level(self, operation: str) -> str:
        """
        Get the risk level for an operation.
        
        This can be overridden by tools to provide more specific
        risk analysis.
        
        Args:
            operation: The operation
            
        Returns:
            Risk level string (e.g., "low", "medium", "high", "critical")
        """
        # Default implementation returns "medium"
        return "medium"
    
    def requires_confirmation(self, operation: str) -> bool:
        """
        Check if confirmation is required for an operation.
        
        Args:
            operation: The operation
            
        Returns:
            True if confirmation is required
        """
        return self.get_metadata().requires_confirmation
    
    def get_execution_time_estimate(self, operation: str) -> Optional[float]:
        """
        Get an estimated execution time for an operation.
        
        Args:
            operation: The operation
            
        Returns:
            Estimated time in seconds, or None if unknown
        """
        return None
    
    def can_handle_operation(self, operation: str) -> bool:
        """
        Check if the tool can handle a specific operation.
        
        Args:
            operation: The operation to check
            
        Returns:
            True if the tool can handle the operation
        """
        return operation in self.get_supported_operations()
    
    def initialize(self) -> None:
        """Initialize the tool (called once when the tool is loaded)."""
        self._initialized = True
    
    def is_initialized(self) -> bool:
        """Check if the tool is initialized."""
        return self._initialized
    
    def _create_default_metadata(self) -> ToolMetadata:
        """Create default metadata."""
        return ToolMetadata(
            name=self.__class__.__name__,
            category=ToolCategory.GENERAL,
            description="Tool without metadata"
        )


class ProgressReportingTool(ToolInterface):
    """
    Extended interface for tools that support progress reporting.
    """
    
    def update_progress(
        self,
        progress: float,
        current_step: str = None,
        message: str = None
    ) -> None:
        """
        Update progress during execution.
        
        Args:
            progress: Progress value (0.0 to 100.0)
            current_step: Current step description
            message: Optional message
        """
        pass  # Default: do nothing
    
    def set_status(self, status: str) -> None:
        """
        Set execution status.
        
        Args:
            status: Status string (e.g., "started", "completed", "failed")
        """
        pass  # Default: do nothing
    
    def log(self, message: str) -> None:
        """
        Log a message during execution.
        
        Args:
            message: Log message
        """
        pass  # Default: do nothing
    
    def log_warning(self, message: str) -> None:
        """
        Log a warning message.
        
        Args:
            message: Warning message
        """
        pass  # Default: do nothing


class BatchSupportTool(ToolInterface):
    """
    Extended interface for tools that support batch operations.
    """
    
    def execute_batch(
        self,
        operations: List[Dict[str, Any]]
    ) -> List[Any]:
        """
        Execute multiple operations in batch.
        
        Args:
            operations: List of operations to execute
            
        Returns:
            List of results, one for each operation
        """
        results = []
        for op in operations:
            try:
                result = self.execute(
                    op.get("operation"),
                    op.get("parameters", {}),
                    op.get("context", {})
                )
                results.append({"success": True, "result": result})
            except Exception as e:
                results.append({
                    "success": False,
                    "error": str(e),
                    "operation": op.get("operation")
                })
        return results
