"""
Native Middleware
Middleware chain for permission, logging, metrics, verification, and context.

New middleware becomes easy to add.
"""

from typing import Callable, Optional, Any, List
from dataclasses import dataclass
from enum import Enum

from .native_execution_context import NativeExecutionContext, ExecutionStage
from .native_exceptions import PermissionDeniedError

from .native_result import NativeResult, ResultStatus
from .native_execution_context import ExecutionStatus


class MiddlewareType(Enum):
    """Type of middleware"""
    PERMISSION = "permission"
    LOGGING = "logging"
    METRICS = "metrics"
    EXECUTION = "execution"
    VERIFICATION = "verification"
    CONTEXT = "context"
    DIAGNOSTICS = "diagnostics"


class ExecutionResult(Enum):
    """Result of middleware execution"""
    CONTINUE = "continue"
    SKIP = "skip"
    HALT = "halt"  # Stop execution
    ABORT = "abort"  # Abort with error


@dataclass
class MiddlewareResult:
    """
    Result of middleware execution.

    Contains whether to continue execution and any messages.
    """
    action: ExecutionResult = ExecutionResult.CONTINUE
    message: Optional[str] = None
    error: Optional[Exception] = None
    context_update: Optional[dict] = None


class NativeMiddleware:
    """
    Base middleware class.

    All middleware should inherit from this.
    """

    def __init__(self, middleware_type: MiddlewareType):
        """
        Initialize middleware.

        Args:
            middleware_type: Type of middleware
        """
        self.middleware_type = middleware_type

    def process(self, context: NativeExecutionContext) -> MiddlewareResult:
        """
        Process the middleware.

        Override this method in subclasses.

        Args:
            context: Execution context

        Returns:
            MiddlewareResult
        """
        return MiddlewareResult(action=ExecutionResult.CONTINUE)

    def should_execute(self, context: NativeExecutionContext) -> bool:
        """
        Check if middleware should execute.

        Can be overridden to add conditions.

        Args:
            context: Execution context

        Returns:
            True if should execute
        """
        return True

    def cleanup(self, context: NativeExecutionContext) -> None:
        """
        Cleanup after processing.

        Override if cleanup is needed.
        """
        pass


class PermissionMiddleware(NativeMiddleware):
    """
    Permission middleware.

    Checks if permission is granted before allowing execution.
    """

    def __init__(self, permission_manager: Optional[Any] = None):
        """
        Initialize permission middleware.

        Args:
            permission_manager: PermissionManager instance (optional)
        """
        super().__init__(MiddlewareType.PERMISSION)
        self.permission_manager = permission_manager

    def should_execute(self, context: NativeExecutionContext) -> bool:
        """Check if permission is required"""
        return context.permission is not None

    def process(self, context: NativeExecutionContext) -> MiddlewareResult:
        """
        Check if permission is granted.

        Args:
            context: Execution context

        Returns:
            MiddlewareResult
        """
        if not context.permission:
            return MiddlewareResult(action=ExecutionResult.CONTINUE)

        # In real implementation, this would call PermissionManager
        # For now, just check if permission_granted is set
        if context.permission_granted:
            return MiddlewareResult(action=ExecutionResult.CONTINUE)

        # Permission denied
        return MiddlewareResult(
            action=ExecutionResult.ABORT,
            error=PermissionDeniedError(
                f"Permission denied: {context.permission.value}",
                permission=context.permission
            ),
            message=f"Permission '{context.permission.value}' denied"
        )


class LoggingMiddleware(NativeMiddleware):
    """
    Logging middleware.

    Logs execution stages and important events.
    """

    def __init__(self, log_function: Optional[Callable] = None):
        """
        Initialize logging middleware.

        Args:
            log_function: Custom logging function (defaults to print)
        """
        super().__init__(MiddlewareType.LOGGING)
        self.log = log_function or print

    def process(self, context: NativeExecutionContext) -> MiddlewareResult:
        """
        Log current stage.

        Args:
            context: Execution context

        Returns:
            MiddlewareResult
        """
        self.log(f"[Middleware] {context.stage.value}: {context.capability}")
        return MiddlewareResult(action=ExecutionResult.CONTINUE)


class MetricsMiddleware(NativeMiddleware):
    """
    Metrics middleware.

    Starts and records timing for operations.
    """

    def __init__(self):
        """Initialize metrics middleware"""
        super().__init__(MiddlewareType.METRICS)

    def process(self, context: NativeExecutionContext) -> MiddlewareResult:
        """
        Start timing if entering execution stage.

        Args:
            context: Execution context

        Returns:
            MiddlewareResult
        """
        if context.stage == ExecutionStage.EXECUTE:
            context.start_metrics()
            context.log_stage(ExecutionStage.EXECUTE, "Starting execution")

        return MiddlewareResult(action=ExecutionResult.CONTINUE)


class ContextMiddleware(NativeMiddleware):
    """
    Context middleware.

    Updates desktop context with execution results.
    """

    def __init__(self):
        """Initialize context middleware"""
        super().__init__(MiddlewareType.CONTEXT)

    def process(self, context: NativeExecutionContext) -> MiddlewareResult:
        """
        Update context if needed.

        Args:
            context: Execution context

        Returns:
            MiddlewareResult
        """
        # If the operation updated context, trigger context update
        if context.result and context.result.events_triggered:
            for event in context.result.events_triggered:
                context.add_event(event)

        # If the result contains window info, update context
        if context.result and context.result.data:
            if hasattr(context.result.data, 'title'):
                # Window info
                window = context.result.data
                context.desktop_context.update_windows([window])

        return MiddlewareResult(action=ExecutionResult.CONTINUE)


class DiagnosticsMiddleware(NativeMiddleware):
    """
    Diagnostics middleware.

    Collects detailed timing and diagnostic information.
    """

    def __init__(self):
        """Initialize diagnostics middleware"""
        super().__init__(MiddlewareType.DIAGNOSTICS)

    def process(self, context: NativeExecutionContext) -> MiddlewareResult:
        """
        Log detailed diagnostics.

        Args:
            context: Execution context

        Returns:
            MiddlewareResult
        """
        if context.stage == ExecutionStage.COMPLETE or context.stage == ExecutionStatus.FAILED:
            diagnostics = context.to_diagnostics()
            self.log(f"[Diagnostics] Capability: {diagnostics['capability']}")
            self.log(f"[Diagnostics] Duration: {diagnostics['timing']['duration_ms']:.2f}ms")
            self.log(f"[Diagnostics] Status: {diagnostics['status']}")
            self.log(f"[Diagnostics] Verification: {diagnostics['verification']['passed']}")
            self.log(f"[Diagnostics] Events: {diagnostics['events']}")

        return MiddlewareResult(action=ExecutionResult.CONTINUE)


class NativePipeline:
    """
    Pipeline for executing native operations.

    Executes through a chain of middleware, then the actual capability,
    then verification.
    """

    def __init__(self, middlewares: Optional[List[NativeMiddleware]] = None):
        """
        Initialize pipeline.

        Args:
            middlewares: List of middleware to use
        """
        self.middlewares = middlewares or []
        self.default_middlewares = self._create_default_middlewares()

    def _create_default_middlewares(self) -> List[NativeMiddleware]:
        """Create default middleware chain"""
        return [
            LoggingMiddleware(),
            PermissionMiddleware(),
            MetricsMiddleware(),
            ContextMiddleware(),
            DiagnosticsMiddleware(),
        ]

    def add_middleware(self, middleware: NativeMiddleware) -> None:
        """
        Add middleware to the pipeline.

        Args:
            middleware: Middleware to add
        """
        self.middlewares.append(middleware)

    def execute(
        self,
        context: NativeExecutionContext,
        execution_callback: Callable[[NativeExecutionContext], Any]
    ) -> NativeResult:
        """
        Execute the pipeline.

        Args:
            context: Execution context
            execution_callback: Function that executes the actual capability

        Returns:
            NativeResult
        """
        # Setup context
        context.set_stage(ExecutionStage.INIT)

        # Try to execute the pipeline
        try:
            # Execute pre-execution middleware
            for middleware in self.middlewares:
                if middleware.should_execute(context):
                    result = middleware.process(context)
                    if result.action in [ExecutionResult.ABORT, ExecutionResult.HALT]:
                        # Middleware aborted execution
                        return self._create_failure_result(context, result.error or Exception("Middleware halted execution"))

            # Execute the capability
            context.set_stage(ExecutionStage.EXECUTE)
            execution_callback(context)

            # Check if execution was aborted
            if context.aborted:
                return self._create_failure_result(context, Exception(context.abort_reason or "Execution aborted"))

            # Execute post-execution middleware
            for middleware in self.middlewares:
                if middleware.should_execute(context):
                    result = middleware.process(context)
                    if result.action in [ExecutionResult.ABORT, ExecutionResult.HALT]:
                        return self._create_failure_result(context, result.error or Exception("Middleware halted execution"))

            # Complete timing
            context.complete_metrics()
            context.set_stage(ExecutionStage.COMPLETE)

            # Return result
            if context.result:
                return context.result
            else:
                return self._create_failure_result(context, Exception("No result returned"))

        except Exception as e:
            # Handle exceptions
            context.set_exception(e)
            context.complete_metrics()
            context.set_stage(ExecutionStage.COMPLETE)
            return self._create_failure_result(context, e)

    def _create_failure_result(self, context: NativeExecutionContext, error: Exception) -> NativeResult:
        """
        Create a failure result.

        Args:
            context: Execution context
            error: Exception that occurred

        Returns:
            NativeResult
        """
        from .native_exceptions import NativeError

        if isinstance(error, NativeError):
            return NativeResult(
                status=ResultStatus.FAILED,
                error=error,
                capability=context.capability,
                manager=context.manager_name,
                action=context.action_name,
                undo_available=False
            )
        else:
            return NativeResult(
                status=ResultStatus.FAILED,
                error=NativeError(str(error), capability=context.capability),
                capability=context.capability,
                manager=context.manager_name,
                action=context.action_name,
                undo_available=False
            )

    def cleanup(self, context: NativeExecutionContext) -> None:
        """
        Cleanup after execution.

        Args:
            context: Execution context
        """
        for middleware in self.middlewares:
            middleware.cleanup(context)
