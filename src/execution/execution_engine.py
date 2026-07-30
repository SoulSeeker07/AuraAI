"""
Tool Execution Engine - Main Execution Engine

This is the core component that integrates all execution engine modules.
It provides a unified interface for executing tools with consistent
lifecycle, error handling, and progress reporting.
"""


import uuid
import time
from typing import Dict, Any, List, Optional, Callable, Tuple
from datetime import datetime
from .exceptions import (
    ToolNotFoundError,
    ToolValidationError,
    PermissionDeniedError,
    RiskLevelError,
    TimeoutError,
    CancellationError,
    ToolExecutionError,
    ResultValidationError,
    ParallelExecutionError
)
from .execution_state import ExecutionState, ExecutionStatus
from .execution_context import ExecutionContext
from .result import ToolExecutionResult
from .permission_manager import PermissionManager, PermissionContext, PermissionAction
from .risk_analyzer import RiskAnalyzer
from .progress_tracker import ProgressTracker
from .cancellation import CancellationToken, CancellationHandler
from .timeout_manager import TimeoutMonitor, execute_with_timeout_and_cancellation
from .tool_interface import ToolInterface
from .tool_registry import ToolRegistry


class ExecutionEngine:
    """
    Main execution engine for tool executions.
    
    This is the central component that coordinates all tool executions,
    managing the entire lifecycle from request to result.
    """
    
    def __init__(
        self,
        permission_manager: PermissionManager = None,
        risk_analyzer: RiskAnalyzer = None,
        tool_registry: ToolRegistry = None,
        execution_state_manager = None,
        default_timeout: int = 300,
        require_confirmation: bool = True
    ):
        """
        Initialize the execution engine.
        
        Args:
            permission_manager: Permission manager instance
            risk_analyzer: Risk analyzer instance
            tool_registry: Tool registry instance
            execution_state_manager: Execution state manager
            default_timeout: Default timeout in seconds
            require_confirmation: Whether confirmation is required for risky operations
        """
        self.permission_manager = permission_manager or PermissionManager()
        self.risk_analyzer = risk_analyzer or RiskAnalyzer(require_confirmation)
        self.tool_registry = tool_registry or ToolRegistry()
        self.execution_state_manager = execution_state_manager
        self.default_timeout = default_timeout
        self.require_confirmation = require_confirmation
        
        # Create default state manager if not provided
        if self.execution_state_manager is None:
            from .execution_state import ExecutionStateManager
            self.execution_state_manager = ExecutionStateManager()
    
    def create_execution_id(self) -> str:
        """Create a unique execution ID."""
        return str(uuid.uuid4())
    
    def _map_operation_to_permission_action(self, operation: str) -> PermissionAction:
        """
        Map operation name to PermissionAction enum.
        
        Args:
            operation: Operation name string
            
        Returns:
            PermissionAction enum value
        """
        # Map common operation names to PermissionAction enum
        action_mapping = {
            "execute": PermissionAction.EXECUTE_COMMAND,
            "read": PermissionAction.READ_FILE,
            "write": PermissionAction.WRITE_FILE,
            "create": PermissionAction.WRITE_FILE,
            "delete": PermissionAction.DELETE_FILE,
            "update": PermissionAction.WRITE_FILE,
            "rename": PermissionAction.RENAME_FILE,
        }
        
        return action_mapping.get(operation, PermissionAction.EXECUTE_COMMAND)
    
    def execute_tool(
        self,
        tool_name: str,
        operation: str,
        parameters: Dict[str, Any] = None,
        context: Dict[str, Any] = None,
        user_id: str = "default_user",
        timeout: int = None,
        require_confirmation: bool = None,
        allow_parallel: bool = False
    ) -> ToolExecutionResult:
        """
        Execute a tool operation.
        
        Args:
            tool_name: Name of the tool to execute
            operation: Operation to perform
            parameters: Operation parameters
            context: Execution context
            user_id: User ID for permission checking
            timeout: Timeout in seconds (overrides default)
            require_confirmation: Whether to require confirmation
            allow_parallel: Whether to allow parallel execution (for batch ops)
            
        Returns:
            ToolExecutionResult with standardized output
        """
        # Set defaults
        parameters = parameters or {}
        context = context or {}
        timeout = timeout or self.default_timeout
        require_confirmation = require_confirmation or self.require_confirmation
        
        # Create execution ID
        execution_id = self.create_execution_id()
        
        try:
            # Create execution state
            execution_state = self.execution_state_manager.create_execution(
                execution_id=execution_id,
                tool_name=tool_name,
                tool_category=context.get("tool_category", "general"),
                parameters=parameters
            )
            
            # Create cancellation token
            cancellation_token = CancellationToken()
            execution_state.set_cancellation_token(cancellation_token)
            
            # Create execution context
            execution_context = ExecutionContext(
                execution_id=execution_id,
                working_directory=context.get("working_directory"),
                environment=context.get("environment"),
                user_context=context.get("user_context"),
                session_id=context.get("session_id"),
                metadata=context.get("metadata", {})
            )
            
            # Store context information in execution state metadata
            execution_state.metadata.update({
                "working_directory": execution_context.resolved_working_directory,
                "environment_variables_count": len(execution_context.environment),
                "context_keys": list(execution_context.user_context.keys()),
                "metadata_keys": list(execution_context.metadata.keys()),
                "session_id": context.get("session_id")
            })
            
            # Create permission context
            permission_context = PermissionContext(
                user_id=user_id,
                execution_id=execution_id,
                permission_manager=self.permission_manager
            )
            
            # Check if tool exists
            tool = self.tool_registry.get_tool(tool_name)
            if not tool:
                raise ToolNotFoundError(
                    tool_name=tool_name,
                    execution_id=execution_id,
                    tool_category=context.get("tool_category", "general")
                )
            
            # Set tool metadata in execution state
            tool_metadata = tool.get_metadata()
            execution_state.tool_name = tool_name
            execution_state.tool_category = tool_metadata.category.value
            
            # Validate operation
            is_valid, error_messages = tool.validate(operation, parameters)
            if not is_valid:
                execution_state.fail(ToolValidationError(
                    message=f"Validation failed: {', '.join(error_messages)}",
                    execution_id=execution_id,
                    invalid_params={op: error for op, error in enumerate(error_messages)}
                ))
                raise ToolValidationError(
                    message=f"Validation failed: {', '.join(error_messages)}",
                    execution_id=execution_id,
                    invalid_params={op: error for op, error in enumerate(error_messages)}
                )
            
            execution_state.update_progress(10, "Validated")
            
            # Check permissions
            required_permission = self.permission_manager.get_required_permission(operation)
            permission_context.set_permission_level(required_permission)
            
            execution_state.request_permission(required_permission.value)
            permission_context.check_permission(self._map_operation_to_permission_action(operation))
            execution_state.grant_permission(required_permission.value)
            
            # Analyze risk
            requires_confirmation, risk_level, risk_factors = self.risk_analyzer.check_if_confirmation_required(
                tool_name=tool_name,
                operation=operation,
                parameters=parameters
            )

            execution_state.risk_level = risk_level.value
            
            # Check confirmation requirements
            if requires_confirmation:
                if not tool.requires_confirmation(operation):
                    tool.requires_confirmation(operation)
                
                if not self.permission_manager.request_permission(
                    user_id, operation, require_confirmation
                ):
                    execution_state.deny_permission(required_permission.value)
                    execution_state.fail(PermissionDeniedError(
                        message=f"Permission denied: {required_permission.value}",
                        execution_id=execution_id,
                        required_permission=required_permission.value,
                        permission_level=risk_level.value
                    ))
                    raise PermissionDeniedError(
                        message=f"Permission denied: {required_permission.value}",
                        execution_id=execution_id,
                        required_permission=required_permission.value,
                        permission_level=risk_level.value
                    )
                else:
                    execution_state.grant_permission(required_permission.value)
            
            execution_state.update_progress(20, "Permission checked")
            
            # Set timeout
            timeout_monitor = TimeoutMonitor(timeout_seconds=timeout)
            execution_state.set_timeout(timeout)
            timeout_monitor.start()
            
            # Prepare execution
            prepared_parameters = tool.prepare(operation, parameters)
            execution_state.update_progress(30, "Prepared")
            
            # Track progress and logs
            progress_update_count = [0]
            
            def progress_callback(update):
                """Callback for progress updates."""
                execution_state.update_progress(update.progress, update.current_step)
                execution_state.add_log(f"Progress: {update.progress}% - {update.message}")
                progress_update_count[0] += 1
            
            # Create progress tracker
            progress_tracker = ProgressTracker(update_callback=progress_callback)
            progress_tracker.start()
            
            # Create cancellation handler
            cancellation_handler = CancellationHandler(
                cancellation_token=cancellation_token,
                on_cancel=lambda reason: None
            )
            
            # Check for cancellation before starting
            if cancellation_token.is_set():
                execution_state.cancel()
                execution_state.update_progress(0, "Cancelled")
                return ToolExecutionResult.error_result(
                    error="Operation cancelled",
                    execution_id=execution_id
                )
            
            execution_state.start()
            execution_state.update_progress(40, "Starting execution")

            # Execute the operation with timeout and cancellation support
            def execute_operation():
                """Execute the operation."""
                try:
                    result = tool.execute(operation, prepared_parameters, context)
                    return result
                except Exception as e:
                    raise

            try:
                # Execute with timeout and cancellation support
                result = execute_with_timeout_and_cancellation(
                    operation=execute_operation,
                    timeout_seconds=timeout,
                    cancellation_token=cancellation_token,
                    operation_name=f"{tool_name}:{operation}"
                )

                # Check if timeout occurred during execution
                if timeout_monitor.check():
                    execution_state.timeout()
                    execution_state.update_progress(100, "Timeout")
                    raise TimeoutError(
                        f"Operation timed out after {timeout} seconds",
                        timeout_seconds=timeout,
                        tool_name=tool_name
                    )
                
                # Check for cancellation
                if cancellation_token.is_set():
                    execution_state.cancel()
                    execution_state.update_progress(0, "Cancelled")
                    raise CancellationError("Operation cancelled")
                
                # Complete execution
                execution_time = time.time() - execution_state.start_time.timestamp()
                execution_state.complete(result=result)
                progress_tracker.complete()
                
                # Update execution state with completion
                execution_state.progress = 100.0
                execution_state.current_step = "Completed"
                
                # Create success result
                tool_result = ToolExecutionResult.success_result(
                    output=result,
                    execution_id=execution_id,
                    execution_time=execution_time,
                    affected_files=execution_state.affected_files,
                    affected_directories=execution_state.affected_directories,
                    next_suggestions=execution_state.next_suggestions,
                    execution_metadata={
                        "execution_id": execution_id,
                        "tool_name": tool_name,
                        "operation": operation,
                        "risk_level": risk_level.value,
                        "permission_level": required_permission.value,
                        "timeout_used": timeout,
                        "execution_time": execution_time,
                        "progress_updates": progress_update_count[0],
                        "warnings": execution_state.warning_messages
                    }
                )
                
                return tool_result
                
            except (TimeoutError, CancellationError) as e:
                # Handle timeout or cancellation errors
                execution_state.update_progress(0, "Failed")
                execution_state.fail(e)
                return ToolExecutionResult.error_result(
                    error=str(e),
                    execution_id=execution_id,
                    execution_time=execution_time,
                    execution_metadata={
                        "error_type": type(e).__name__,
                        "error_details": str(e)
                    }
                )
            
            except Exception as e:
                # Handle other errors
                execution_state.update_progress(0, "Failed")
                execution_state.fail(e)
                return ToolExecutionResult.error_result(
                    error=str(e),
                    execution_id=execution_id,
                    execution_time=execution_time,
                    tool_name=tool_name,
                    tool_category=tool.get_metadata().category.value,
                    execution_metadata={
                        "error_type": type(e).__name__,
                        "error_details": str(e),
                        "tool_name": tool_name,
                        "tool_category": tool.get_metadata().category.value
                    }
                )
            
            finally:
                # Cleanup
                try:
                    tool.cleanup(operation, prepared_parameters)
                except Exception as e:
                    # Log cleanup errors but don't fail
                    pass
                
                progress_tracker.reset()
        
        except Exception as e:
            # Catch-all for unexpected errors
            return ToolExecutionResult.error_result(
                error=str(e),
                execution_id=execution_id,
                execution_metadata={
                    "error_type": type(e).__name__,
                    "error_details": str(e),
                    "traceback": str(e.__traceback__)
                }
            )
    
    def execute_batch(
        self,
        operations: List[Dict[str, Any]]
    ) -> List[ToolExecutionResult]:
        """
        Execute multiple operations in sequence.
        
        Args:
            operations: List of operation dictionaries with:
                - tool_name
                - operation
                - parameters (optional)
                - context (optional)
                - timeout (optional)
                
        Returns:
            List of results
        """
        results = []
        
        for i, op in enumerate(operations):
            result = self.execute_tool(
                tool_name=op["tool_name"],
                operation=op["operation"],
                parameters=op.get("parameters", {}),
                context=op.get("context", {}),
                timeout=op.get("timeout", self.default_timeout)
            )
            results.append(result)
        
        return results
    
    def execute_parallel(
        self,
        operations: List[Dict[str, Any]]
    ) -> Dict[str, ToolExecutionResult]:
        """
        Execute multiple operations in parallel.
        
        Args:
            operations: List of operation dictionaries (same format as execute_batch)
            
        Returns:
            Dictionary mapping operation index to result
        """
        import concurrent.futures
        
        results = {}
        errors = []
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Submit all operations
            future_to_op = {
                executor.submit(
                    self.execute_tool,
                    op["tool_name"],
                    op["operation"],
                    op.get("parameters", {}),
                    op.get("context", {}),
                    op.get("user_id", "default_user"),
                    op.get("timeout", self.default_timeout)
                ): i
                for i, op in enumerate(operations)
            }
            
            # Collect results
            for future in concurrent.futures.as_completed(future_to_op):
                op_index = future_to_op[future]
                try:
                    result = future.result()
                    results[op_index] = result
                except Exception as e:
                    results[op_index] = ToolExecutionResult.error_result(
                        error=str(e),
                        execution_metadata={
                            "error_type": type(e).__name__,
                            "error_details": str(e)
                        }
                    )
                    errors.append((op_index, e))
        
        # Sort results by index
        sorted_results = {}
        for i in range(len(operations)):
            sorted_results[i] = results.get(i)
        
        return sorted_results
    
    def get_execution_state(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the state of an execution.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            Execution state dictionary or None
        """
        state = self.execution_state_manager.get_execution(execution_id)
        if state:
            return state.to_dict()
        return None
    
    def list_executions(self) -> List[Dict[str, Any]]:
        """
        List all executions.
        
        Returns:
            List of execution state dictionaries
        """
        return self.execution_state_manager.list_executions()
    
    def list_running_executions(self) -> List[Dict[str, Any]]:
        """
        List all running executions.
        
        Returns:
            List of running execution state dictionaries
        """
        return [state.to_dict() for state in self.execution_state_manager.get_running_executions()]
    
    def cancel_execution(self, execution_id: str, reason: str = None) -> bool:
        """
        Cancel a running execution.
        
        Args:
            execution_id: Execution ID
            reason: Reason for cancellation
            
        Returns:
            True if cancellation was requested
        """
        state = self.execution_state_manager.get_execution(execution_id)
        if state and state.cancellation_token:
            return state.cancellation_token.request_cancellation(reason)
        return False
    
    def get_tool_count(self) -> int:
        """Get the number of registered tools."""
        return self.tool_registry.get_tool_count()
    
    def get_tool_count_by_category(self, category: str) -> int:
        """Get the number of tools in a category."""
        return self.tool_registry.get_tool_count_by_category(category)
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """List all registered tools."""
        metadata_list = self.tool_registry.list_tools()
        return [m.to_dict() for m in metadata_list]
    
    def list_tools_by_category(self, category: str) -> List[Dict[str, Any]]:
        """List tools by category."""
        metadata_list = self.tool_registry.list_tools_by_category(category)
        return [m.to_dict() for m in metadata_list]
