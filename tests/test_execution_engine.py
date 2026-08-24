"""
Tests for Tool Execution Engine
"""

import threading
import time
from datetime import datetime

import pytest

from execution import (
    BaseToolAdapter,
    CancellationToken,
    ExecutionEngine,
    ExecutionState,
    ExecutionStateManager,
    ExecutionStatus,
    FunctionToolAdapter,
    PermissionManager,
    ProgressTracker,
    RiskAnalyzer,
    TimeoutMonitor,
    ToolCategory,
    ToolExecutionResult,
    ToolManager,
    ToolMetadata,
    ToolRegistry,
    adapt_existing_tool,
    adapt_function,
)
from execution.exceptions import (
    CancellationError,
    PermissionDeniedError,
    TimeoutError,
    ToolNotFoundError,
    ToolValidationError,
)

# Test fixtures


@pytest.fixture
def tool_registry():
    """Create a fresh tool registry for each test."""
    return ToolRegistry()


@pytest.fixture
def execution_engine(tool_registry):
    """Create an execution engine with a fresh tool registry."""
    return ExecutionEngine(tool_registry=tool_registry)


@pytest.fixture
def simple_tool(execution_engine):
    """Create a simple test tool."""

    class SimpleTool:
        def __init__(self):
            self.name = "simple_tool"
            self.description = "A simple test tool"
            self.category = ToolCategory.UTILITY
            self.version = "1.0.0"
            self.supported_operations = ["read", "write"]
            self.operations_metadata = {
                "read": {"description": "Read a file"},
                "write": {"description": "Write a file"},
            }

        def get_metadata(self):
            return ToolMetadata(
                name=self.name,
                description=self.description,
                category=self.category,
                version=self.version,
            )

        def get_supported_operations(self):
            return self.supported_operations

        def validate(self, operation, parameters):
            if operation not in self.supported_operations:
                return False, [f"Operation '{operation}' not supported"]
            return True, []

        def prepare(self, operation, parameters):
            return parameters

        def execute(self, operation, parameters, context=None):
            if operation == "read":
                return {"status": "success", "data": "file_content"}
            elif operation == "write":
                return {
                    "status": "success",
                    "written": len(parameters.get("content", "")),
                }
            return {"status": "error", "message": "Unknown operation"}

        def cleanup(self, operation, parameters):
            pass

    tool = SimpleTool()
    execution_engine.tool_registry.register_tool(tool)
    return tool


# Tests for ToolRegistry


def test_tool_registry_initialization(tool_registry):
    """Test that tool registry initializes correctly."""
    assert len(tool_registry.list_tools()) == 0
    assert len(tool_registry.list_categories()) == 0
    assert tool_registry.get_tool_count() == 0


def test_tool_registry_register_tool(tool_registry):
    """Test registering a tool."""

    class TestTool:
        def get_metadata(self):
            return ToolMetadata(
                name="test_tool", description="Test tool", category=ToolCategory.UTILITY
            )

        def get_supported_operations(self):
            return ["test"]

        def validate(self, operation, parameters):
            return True, []

        def prepare(self, operation, parameters):
            return parameters

        def execute(self, operation, parameters, context=None):
            return {"result": "success"}

        def cleanup(self, operation, parameters):
            pass

    tool = TestTool()
    tool_registry.register_tool(tool)

    assert tool_registry.get_tool_count() == 1
    assert tool_registry.get_tool("test_tool") is not None
    assert len(tool_registry.list_tools()) == 1


def test_tool_registry_unregister_tool(tool_registry):
    """Test unregistering a tool."""

    class TestTool:
        def get_metadata(self):
            return ToolMetadata(
                name="test_tool", description="Test tool", category=ToolCategory.UTILITY
            )

        def get_supported_operations(self):
            return ["test"]

        def validate(self, operation, parameters):
            return True, []

        def prepare(self, operation, parameters):
            return parameters

        def execute(self, operation, parameters, context=None):
            return {"result": "success"}

        def cleanup(self, operation, parameters):
            pass

    tool = TestTool()
    tool_registry.register_tool(tool)

    assert tool_registry.get_tool_count() == 1
    assert tool_registry.unregister_tool("test_tool")
    assert tool_registry.get_tool_count() == 0


def test_tool_registry_duplicate_registration(tool_registry):
    """Test that duplicate tool registration raises an error."""

    class TestTool:
        def get_metadata(self):
            return ToolMetadata(
                name="test_tool", description="Test tool", category=ToolCategory.UTILITY
            )

        def get_supported_operations(self):
            return ["test"]

        def validate(self, operation, parameters):
            return True, []

        def prepare(self, operation, parameters):
            return parameters

        def execute(self, operation, parameters, context=None):
            return {"result": "success"}

        def cleanup(self, operation, parameters):
            pass

    tool = TestTool()
    tool_registry.register_tool(tool)

    with pytest.raises(ValueError, match="already registered"):
        tool_registry.register_tool(tool)


def test_tool_registry_search_tools(tool_registry):
    """Test searching for tools."""

    class TestTool:
        def get_metadata(self):
            return ToolMetadata(
                name="searchable_tool",
                description="A searchable tool",
                category=ToolCategory.UTILITY,
                tags=["search", "test"],
            )

        def get_supported_operations(self):
            return ["test"]

        def validate(self, operation, parameters):
            return True, []

        def prepare(self, operation, parameters):
            return parameters

        def execute(self, operation, parameters, context=None):
            return {"result": "success"}

        def cleanup(self, operation, parameters):
            pass

    tool = TestTool()
    tool_registry.register_tool(tool)

    results = tool_registry.search_tools("searchable")
    assert len(results) == 1

    results = tool_registry.search_tools("invalid")
    assert len(results) == 0


def test_tool_registry_list_by_category(tool_registry):
    """Test listing tools by category."""

    class FileTool:
        def get_metadata(self):
            return ToolMetadata(
                name="file_tool", description="File tool", category=ToolCategory.FILE
            )

        def get_supported_operations(self):
            return ["read"]

        def validate(self, operation, parameters):
            return True, []

        def prepare(self, operation, parameters):
            return parameters

        def execute(self, operation, parameters, context=None):
            return {"result": "success"}

        def cleanup(self, operation, parameters):
            pass

    class UtilityTool:
        def get_metadata(self):
            return ToolMetadata(
                name="utility_tool",
                description="Utility tool",
                category=ToolCategory.UTILITY,
            )

        def get_supported_operations(self):
            return ["test"]

        def validate(self, operation, parameters):
            return True, []

        def prepare(self, operation, parameters):
            return parameters

        def execute(self, operation, parameters, context=None):
            return {"result": "success"}

        def cleanup(self, operation, parameters):
            pass

    file_tool = FileTool()
    utility_tool = UtilityTool()
    tool_registry.register_tool(file_tool)
    tool_registry.register_tool(utility_tool)

    file_tools = tool_registry.list_tools_by_category("file")
    assert len(file_tools) == 1
    assert file_tools[0].name == "file_tool"

    utility_tools = tool_registry.list_tools_by_category("utility")
    assert len(utility_tools) == 1
    assert utility_tools[0].name == "utility_tool"


# Tests for ToolManager


def test_tool_manager_discovery(tool_manager):
    """Test tool discovery."""
    # This test would need actual tools in the plugins/tools directory
    # For now, we just verify the method exists
    count = tool_manager.discover_tools()
    assert isinstance(count, int)


def test_tool_manager_auto_load(tool_manager):
    """Test automatic loading of tools."""
    # This test would need actual tools in the plugins/tools directory
    # For now, we just verify the method exists
    count = tool_manager.auto_load()
    assert isinstance(count, int)


# Tests for ExecutionStateManager


def test_execution_state_manager():
    """Test execution state management."""
    manager = ExecutionStateManager()

    # Create execution
    state = manager.create_execution(
        execution_id="test_id", tool_name="test_tool", tool_category="test"
    )

    assert state is not None
    assert state.status == ExecutionStatus.PENDING

    # Start execution
    state.start()
    assert state.status == ExecutionStatus.RUNNING

    # Update progress
    state.update_progress(50, "Processing")
    assert state.progress == 50.0
    assert len(state.status_history) == 2  # PENDING and RUNNING

    # Complete execution
    result = {"status": "success"}
    state.complete(result=result)
    assert state.status == ExecutionStatus.COMPLETED
    assert state.result == result

    # Get execution
    retrieved = manager.get_execution("test_id")
    assert retrieved == state

    # List all executions
    all_executions = manager.list_executions()
    assert len(all_executions) == 1

    # List running executions
    running = manager.get_running_executions()
    assert len(running) == 0


def test_execution_state_timeouts():
    """Test execution state timeout tracking."""
    manager = ExecutionStateManager()

    state = manager.create_execution(
        execution_id="timeout_test", tool_name="test_tool", tool_category="test"
    )

    state.start()
    state.set_timeout(10)

    # Check timeout
    assert state.check_timeout()
    assert state.status == ExecutionStatus.TIMEOUT


def test_execution_state_cancellation():
    """Test execution state cancellation."""
    manager = ExecutionStateManager()

    state = manager.create_execution(
        execution_id="cancel_test", tool_name="test_tool", tool_category="test"
    )

    state.start()
    state.set_cancellation_token(CancellationToken())

    # Request cancellation
    state.cancellation_token.request_cancellation("Test cancellation")
    assert state.cancellation_requested
    assert state.status == ExecutionStatus.CANCELLED


def test_execution_state_permission():
    """Test execution state permission tracking."""
    manager = ExecutionStateManager()

    state = manager.create_execution(
        execution_id="perm_test", tool_name="test_tool", tool_category="test"
    )

    # Request permission
    state.request_permission("HIGH")
    state.grant_permission("HIGH")
    assert state.permission_level == "HIGH"

    # Deny permission
    state.deny_permission("CRITICAL")
    assert state.permission_level == "CRITICAL"


# Tests for PermissionManager


def test_permission_manager_levels():
    """Test permission levels."""
    manager = PermissionManager()

    # Check SAFE level
    assert manager.get_required_permission("safe_operation") == "SAFE"

    # Check MEDIUM level
    assert manager.get_required_permission("medium_operation") == "MEDIUM"

    # Check HIGH level
    assert manager.get_required_permission("high_operation") == "HIGH"

    # Check CRITICAL level
    assert manager.get_required_permission("critical_operation") == "CRITICAL"


def test_permission_manager_user_permissions():
    """Test user-specific permissions."""
    manager = PermissionManager()

    # Set user permission
    manager.set_user_permission("user1", "HIGH", "file_operation")

    # Check user permission
    assert manager.check_permission("user1", "file_operation") == "HIGH"

    # Check default permission
    assert manager.check_permission("user2", "file_operation") == "SAFE"


def test_permission_manager_request():
    """Test permission request."""
    manager = PermissionManager()

    # Request permission
    result = manager.request_permission(
        user_id="test_user", operation="test_operation", require_confirmation=False
    )
    assert result is True


def test_permission_manager_global_permissions():
    """Test global permissions."""
    manager = PermissionManager()

    # Set global permission
    manager.set_global_permission("HIGH", "restricted_operation")

    # Check global permission
    assert manager.get_required_permission("restricted_operation") == "HIGH"


# Tests for RiskAnalyzer


def test_risk_analyzer_levels():
    """Test risk levels."""
    analyzer = RiskAnalyzer()

    # Check LOW risk
    risk = analyzer.analyze_operation(
        tool_name="simple_tool",
        operation="read_file",
        parameters={"file_path": "/path/to/file"},
    )
    assert risk.level == "LOW"

    # Check HIGH risk
    risk = analyzer.analyze_operation(
        tool_name="delete_tool",
        operation="delete",
        parameters={"file_path": "/path/to/file"},
    )
    assert risk.level == "HIGH"


def test_risk_analyzer_confirmation():
    """Test risk-based confirmation."""
    analyzer = RiskAnalyzer(require_confirmation=True)

    # LOW risk doesn't require confirmation
    requires_confirm, risk, _ = analyzer.check_if_confirmation_required(
        "simple_tool", "read", {"file": "test.txt"}
    )
    assert not requires_confirm
    assert risk == "LOW"

    # HIGH risk requires confirmation
    requires_confirm, risk, _ = analyzer.check_if_confirmation_required(
        "delete_tool", "delete", {"file": "test.txt"}
    )
    assert requires_confirm
    assert risk == "HIGH"


# Tests for ProgressTracker


def test_progress_tracker():
    """Test progress tracking."""
    tracker = ProgressTracker()

    # Start tracking
    tracker.start()
    assert tracker.status == "running"

    # Update progress
    tracker.update(10, "Starting")
    assert tracker.progress == 10
    assert tracker.status == "running"

    # Complete
    tracker.complete()
    assert tracker.progress == 100
    assert tracker.status == "completed"

    # Fail
    tracker.fail(Exception("Test error"))
    assert tracker.status == "failed"


def test_progress_tracker_callbacks():
    """Test progress tracker callbacks."""
    callback_calls = []

    def callback(update):
        callback_calls.append(update)

    tracker = ProgressTracker(update_callback=callback)

    tracker.update(50, "Halfway")
    assert len(callback_calls) == 1
    assert callback_calls[0].progress == 50
    assert callback_calls[0].current_step == "Halfway"


def test_progress_tracker_throttling():
    """Test progress tracker throttling."""
    callback_calls = []

    def callback(update):
        callback_calls.append(update)

    tracker = ProgressTracker(update_callback=callback, minimum_interval=0.1)  # 100ms

    # Update multiple times quickly
    tracker.update(10, "Step 1")
    tracker.update(20, "Step 2")
    tracker.update(30, "Step 3")

    # Should only get one callback due to throttling
    assert len(callback_calls) == 1


# Tests for CancellationToken


def test_cancellation_token():
    """Test cancellation token."""
    token = CancellationToken()

    # Initially not cancelled
    assert not token.is_set()

    # Request cancellation
    token.request_cancellation("Test cancellation")
    assert token.is_set()
    assert token.reason == "Test cancellation"

    # Check cancellation
    assert token.check_cancellation()


def test_cancellation_token_callbacks():
    """Test cancellation token callbacks."""
    callback_calls = []

    def callback(reason):
        callback_calls.append(reason)

    token = CancellationToken()
    token.add_callback(callback)

    token.request_cancellation("Test")
    assert len(callback_calls) == 1
    assert callback_calls[0] == "Test"


# Tests for TimeoutMonitor


def test_timeout_monitor():
    """Test timeout monitor."""
    monitor = TimeoutMonitor(timeout_seconds=1)

    # Start monitoring
    monitor.start()

    # Wait and check
    time.sleep(1.5)
    assert monitor.check()
    assert monitor.elapsed_time() > 1.0


def test_timeout_monitor_remaining():
    """Test remaining time calculation."""
    monitor = TimeoutMonitor(timeout_seconds=5)
    monitor.start()

    time.sleep(0.5)
    remaining = monitor.remaining_time()
    assert remaining <= 4.5


def test_timeout_monitor_elapsed():
    """Test elapsed time calculation."""
    monitor = TimeoutMonitor(timeout_seconds=10)
    monitor.start()

    time.sleep(0.5)
    elapsed = monitor.elapsed_time()
    assert elapsed >= 0.5


# Tests for ToolExecutionResult


def test_success_result():
    """Test creating a success result."""
    result = ToolExecutionResult.success_result(
        output={"data": "test"}, execution_id="test_id", execution_time=1.0
    )

    assert result.success
    assert result.output == {"data": "test"}
    assert result.execution_id == "test_id"
    assert result.execution_time == 1.0


def test_error_result():
    """Test creating an error result."""
    result = ToolExecutionResult.error_result(
        error="Test error", execution_id="test_id"
    )

    assert not result.success
    assert result.error == "Test error"
    assert result.execution_id == "test_id"


def test_partial_result():
    """Test creating a partial result."""
    result = ToolExecutionResult.partial_result(
        output={"data": "partial"}, execution_id="test_id"
    )

    assert not result.success
    assert result.output == {"data": "partial"}
    assert result.execution_id == "test_id"


# Tests for ExecutionEngine


def test_execution_engine_initialization(execution_engine):
    """Test execution engine initialization."""
    assert execution_engine.tool_registry is not None
    assert execution_engine.permission_manager is not None
    assert execution_engine.risk_analyzer is not None
    assert execution_engine.default_timeout == 300


def test_execution_engine_execute_tool(execution_engine, simple_tool):
    """Test executing a tool."""
    result = execution_engine.execute_tool(
        tool_name="simple_tool",
        operation="read",
        parameters={"file": "test.txt"},
        context={"working_directory": "/tmp"},
    )

    assert result.success
    assert result.output["status"] == "success"
    assert result.execution_metadata["tool_name"] == "simple_tool"


def test_execution_engine_list_executions(execution_engine, simple_tool):
    """Test listing executions."""
    result = execution_engine.execute_tool(
        tool_name="simple_tool", operation="read", parameters={"file": "test.txt"}
    )

    executions = execution_engine.list_executions()
    assert len(executions) == 1
    assert executions[0]["tool_name"] == "simple_tool"
    assert executions[0]["status"] == "completed"


def test_execution_engine_list_running_executions(execution_engine, simple_tool):
    """Test listing running executions."""

    # Execute in background to have running execution
    def execute_async():
        execution_engine.execute_tool(
            tool_name="simple_tool", operation="read", parameters={"file": "test.txt"}
        )

    thread = threading.Thread(target=execute_async)
    thread.start()
    time.sleep(0.1)  # Give thread time to start

    running = execution_engine.list_running_executions()
    assert len(running) >= 1

    thread.join()


def test_execution_engine_cancel(execution_engine, simple_tool):
    """Test cancelling an execution."""
    result = execution_engine.execute_tool(
        tool_name="simple_tool", operation="read", parameters={"file": "test.txt"}
    )

    # Cancel the execution
    cancelled = execution_engine.cancel_execution(result.execution_id)
    assert cancelled

    # Check that execution is cancelled
    state = execution_engine.get_execution_state(result.execution_id)
    assert state is not None
    assert state["status"] == "cancelled"


def test_execution_engine_tool_count(execution_engine, simple_tool):
    """Test getting tool count."""
    count = execution_engine.get_tool_count()
    assert count == 1


def test_execution_engine_list_tools(execution_engine, simple_tool):
    """Test listing tools."""
    tools = execution_engine.list_tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "simple_tool"


# Tests for ToolAdapter


def test_function_tool_adapter():
    """Test creating a function tool adapter."""

    def test_function(param1, param2):
        return {"result": f"{param1} + {param2}"}

    adapter = adapt_function(
        function=test_function, name="math_add", description="Add two numbers"
    )

    result = adapter.execute("execute", {"param1": 5, "param2": 3})
    assert result == {"result": "5 + 3"}


def test_existing_tool_adapter():
    """Test creating an existing tool adapter."""

    class TestTool:
        def __init__(self):
            self.name = "test_tool"
            self.description = "Test tool"

        def get_metadata(self):
            from execution import ToolCategory, ToolMetadata

            return ToolMetadata(
                name=self.name,
                description=self.description,
                category=ToolCategory.UTILITY,
            )

        def get_supported_operations(self):
            return ["test_op"]

        def validate(self, operation, parameters):
            return True, []

        def prepare(self, operation, parameters):
            return parameters

        def execute(self, operation, parameters, context=None):
            return {"result": "success"}

        def cleanup(self, operation, parameters):
            pass

    original_tool = TestTool()
    adapter = adapt_existing_tool(original_tool=original_tool, name="test_tool")

    result = adapter.execute("test_op", {})
    assert result == {"result": "success"}


# Test execution pipeline


def test_execution_pipeline(execution_engine, simple_tool):
    """Test the complete execution pipeline."""

    # Step 1: Validate tool
    tool = execution_engine.tool_registry.get_tool("simple_tool")
    assert tool is not None

    # Step 2: Get metadata
    metadata = tool.get_metadata()
    assert metadata.name == "simple_tool"

    # Step 3: Execute tool
    result = execution_engine.execute_tool(
        tool_name="simple_tool", operation="read", parameters={"file": "test.txt"}
    )

    # Step 4: Verify result
    assert result.success
    assert result.execution_metadata["tool_name"] == "simple_tool"

    # Step 5: Check execution state
    state = execution_engine.get_execution_state(result.execution_id)
    assert state is not None
    assert state["status"] == "completed"
    assert state["progress"] == 100


def test_execution_pipeline_error_handling(execution_engine):
    """Test error handling in execution pipeline."""

    # Try to execute non-existent tool
    with pytest.raises(ToolNotFoundError):
        execution_engine.execute_tool(tool_name="nonexistent_tool", operation="test")


def test_execution_pipeline_timeout(execution_engine, simple_tool):
    """Test timeout handling in execution pipeline."""

    def slow_operation():
        time.sleep(2)
        return {"result": "done"}

    # Mock the tool to be slow
    class SlowTool:
        def get_metadata(self):
            return ToolMetadata(
                name="slow_tool", description="Slow tool", category=ToolCategory.UTILITY
            )

        def get_supported_operations(self):
            return ["slow_op"]

        def validate(self, operation, parameters):
            return True, []

        def prepare(self, operation, parameters):
            return parameters

        def execute(self, operation, parameters, context=None):
            return slow_operation()

        def cleanup(self, operation, parameters):
            pass

    execution_engine.tool_registry.unregister_tool("simple_tool")
    execution_engine.tool_registry.register_tool(SlowTool())

    result = execution_engine.execute_tool(
        tool_name="slow_tool", operation="slow_op", timeout=0.1  # 100ms timeout
    )

    # Should have timed out
    assert not result.success
    assert "timeout" in result.error.lower() or "timed out" in result.error.lower()


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
