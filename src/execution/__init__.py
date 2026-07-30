"""
Tool Execution Engine
"""

from .execution_engine import ExecutionEngine
from .execution_state import ExecutionState, ExecutionStatus, ExecutionStateManager
from .tool_registry import ToolRegistry, ToolManager
from .tool_interface import ToolInterface, ToolMetadata, ToolCategory
from .tool_adapter import (
    BaseToolAdapter,
    FunctionToolAdapter,
    ExistingToolAdapter,
    adapt_function,
    adapt_existing_tool
)
from .result import ToolExecutionResult, ExecutionResultManager
from .permission_manager import PermissionManager, PermissionContext
from .risk_analyzer import RiskAnalyzer
from .progress_tracker import ProgressTracker
from .cancellation import CancellationToken
from .timeout_manager import TimeoutMonitor
from .exceptions import (
    ExecutionError,
    ToolValidationError,
    PermissionDeniedError,
    RiskLevelError,
    TimeoutError,
    CancellationError,
    ToolNotFoundError,
    ToolExecutionError,
    ResultValidationError,
    ParallelExecutionError
)

__all__ = [
    # Main components
    'ExecutionEngine',
    'ToolRegistry',
    'ToolManager',
    
    # Execution state
    'ExecutionState',
    'ExecutionStatus',
    'ExecutionStateManager',
    
    # Tool interface
    'ToolInterface',
    'ToolMetadata',
    'ToolCategory',
    
    # Adapters
    'BaseToolAdapter',
    'FunctionToolAdapter',
    'ExistingToolAdapter',
    'adapt_function',
    'adapt_existing_tool',
    
    # Results
    'ToolExecutionResult',
    'ExecutionResultManager',
    
    # Permission
    'PermissionManager',
    'PermissionContext',
    
    # Risk analyzer
    'RiskAnalyzer',
    
    # Progress
    'ProgressTracker',
    
    # Cancellation
    'CancellationToken',
    
    # Timeout
    'TimeoutMonitor',
    
    # Exceptions
    'ExecutionError',
    'ToolValidationError',
    'PermissionDeniedError',
    'RiskLevelError',
    'TimeoutError',
    'CancellationError',
    'ToolNotFoundError',
    'ToolExecutionError',
    'ResultValidationError',
    'ParallelExecutionError',
]
