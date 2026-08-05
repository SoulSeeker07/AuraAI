"""
Tool Execution Engine
"""

from core.backends.adapters import AntigravityBackendAdapter
from core.orchestration import MasterOrchestrator

from .cancellation import CancellationToken
from .exceptions import (
    CancellationError,
    ExecutionError,
    ParallelExecutionError,
    PermissionDeniedError,
    ResultValidationError,
    RiskLevelError,
    TimeoutError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolValidationError,
)
from .execution_context import ExecutionContext
from .execution_engine import ExecutionEngine
from .execution_state import ExecutionState, ExecutionStateManager, ExecutionStatus
from .permission_manager import PermissionContext, PermissionManager
from .progress_tracker import ProgressTracker
from .result import ExecutionResultManager, ToolExecutionResult
from .risk_analyzer import RiskAnalyzer
from .timeout_manager import TimeoutMonitor
from .tool_adapter import (
    BaseToolAdapter,
    ExistingToolAdapter,
    FunctionToolAdapter,
    adapt_existing_tool,
    adapt_function,
)
from .tool_interface import ToolCategory, ToolInterface, ToolMetadata
from .tool_registry import ToolManager, ToolRegistry

__all__ = [
    # Main components
    "ExecutionEngine",
    "ExecutionContext",
    "ToolRegistry",
    "ToolManager",
    "MasterOrchestrator",
    "AntigravityBackendAdapter",
    # Execution state
    "ExecutionState",
    "ExecutionStatus",
    "ExecutionStateManager",
    # Tool interface
    "ToolInterface",
    "ToolMetadata",
    "ToolCategory",
    # Adapters
    "BaseToolAdapter",
    "FunctionToolAdapter",
    "ExistingToolAdapter",
    "adapt_function",
    "adapt_existing_tool",
    # Results
    "ToolExecutionResult",
    "ExecutionResultManager",
    # Permission
    "PermissionManager",
    "PermissionContext",
    # Risk analyzer
    "RiskAnalyzer",
    # Progress
    "ProgressTracker",
    # Cancellation
    "CancellationToken",
    # Timeout
    "TimeoutMonitor",
    # Exceptions
    "ExecutionError",
    "ToolValidationError",
    "PermissionDeniedError",
    "RiskLevelError",
    "TimeoutError",
    "CancellationError",
    "ToolNotFoundError",
    "ToolExecutionError",
    "ResultValidationError",
    "ParallelExecutionError",
]
