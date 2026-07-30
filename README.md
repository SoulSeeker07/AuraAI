# Aura

An AI OS companion shell for Windows. Sprint 1 focuses on the native desktop
experience: a control center window, system tray presence, dark theme,
overlay prompt, and Alt + Space activation.

## Structure
- src/ - application source code
- assets/ - images and static files
- database/ - database files and models
- plugins/ - extension/plugin modules
- tests/ - test suite
- docs/ - documentation

## Aura Shell
- `src/gui/main_window.py` - frameless desktop control center
- `src/gui/titlebar.py` - custom draggable title bar
- `src/gui/overlay.py` - Alt + Space assistant overlay
- `src/gui/tray.py` - Windows system tray integration
- `src/gui/theme.py` - shared dark theme engine
- `src/gui/animations.py` - reusable UI animation helpers
- `src/core/app.py` - application bootstrap and lifecycle
- `src/core/config.py` - app constants and runtime paths
- `src/core/event_bus.py` - decoupled app-wide messaging
- `src/core/settings.py` - persistent user settings
- `src/core/plugin_manager.py` - plugin discovery and loading
- `src/core/window_manager.py` - GUI window orchestration
- `src/core/overlay_manager.py` - overlay prompt handling
- `src/core/live_screen.py` - continuous screen capture session manager
- `src/core/screen_context.py` - screenshot and latest-frame capture helpers

## Setup
1. Activate the virtual environment
2. Install dependencies: `pip install -r requirements.txt`
3. Add your API keys to `.env`

## Run
```powershell
python src/main.py
```

Close the main window to keep Aura running in the tray. Use Alt + Space to open
the overlay, or choose "Show Overlay" from the tray menu.

If the local `.venv` launcher is broken, use the bundled-runtime launcher:
```powershell
.\scripts\run_aura.ps1
```

## Tool Execution Engine

Aura AI includes a powerful, unified tool execution engine that provides a secure,
reliable, and feature-rich execution pipeline for all tool operations. The execution
engine implements a comprehensive 8-stage pipeline:

```
Request → Validation → Permission → Preparation → Execution → Monitoring → Completion → Cleanup → Result
```

### Core Components

#### 1. Tool Interface ([tool_interface.py](src/execution/tool_interface.py))
Abstract base class defining the contract for all tools. Tools must implement:
- `execute(operation, parameters, context)` - Main execution method
- `get_metadata()` - Return tool metadata
- `get_supported_operations()` - List supported operations
- `requires_confirmation(operation)` - Check if permission is required

#### 2. Tool Registry ([tool_registry.py](src/execution/tool_registry.py))
Manages tool registration and lifecycle. Features:
- Dynamic tool registration and discovery
- Operation validation
- Tool metadata management
- Built-in tool adapters (FunctionToolAdapter, ClassToolAdapter)

#### 3. Execution Engine ([execution_engine.py](src/execution/execution_engine.py))
Core orchestration component that coordinates all tool executions:
- Unified interface for tool execution
- Permission and risk management
- Timeout handling and cancellation support
- Progress tracking and logging
- Result formatting

#### 4. Permission Manager ([permission_manager.py](src/execution/permission_manager.py))
Implements risk-based access control with four permission levels:
- **SAFE** - Read-only operations (e.g., READ_FILE, ACCESS_CLIPBOARD)
- **MEDIUM** - Non-destructive operations (e.g., WRITE_FILE, EXECUTE_COMMAND)
- **HIGH** - Destructive operations (e.g., DELETE_FILE, MODIFY_REGISTRY)
- **CRITICAL** - System-level operations (e.g., SHUTDOWN_SYSTEM, FORMAT_DISK)

Includes `PermissionAction` enum defining all permission types and `REQUIRED_PERMISSIONS`
mappings from actions to required permission levels.

#### 5. Risk Analyzer ([risk_analyzer.py](src/execution/risk_analyzer.py))
Analyzes operations and determines risk level and confirmation requirements:
- `check_if_confirmation_required(tool_name, operation, parameters)` - Returns
  (requires_confirm, risk_level, suggested_permissions)
- Risk levels: LOW, MEDIUM, HIGH, CRITICAL
- Context-aware risk assessment

#### 6. Execution State ([execution_state.py](src/execution/execution_state.py))
Tracks execution lifecycle with:
- Progress tracking (0.0 - 100.0)
- Status history and logging
- Permission requests and grants
- Cancellation support
- Metadata storage
- Thread-safe operations using RLock()

#### 7. Progress Tracker ([progress_tracker.py](src/execution/progress_tracker.py))
Provides progress updates with callbacks:
- Real-time progress reporting
- Log and warning collection
- Success/failure tracking
- Customizable update callbacks

#### 8. Cancellation Support ([cancellation.py](src/execution/cancellation.py))
Safe cancellation system:
- `CancellationToken` for tracking cancellation state
- `CancellationHandler` for managing cancellation
- `CancellationError` for handling cancelled operations
- Thread-safe cancellation checks

#### 9. Timeout Monitor ([timeout_manager.py](src/execution/timeout_manager.py))
Handles operation timeouts:
- Configurable timeout duration
- Timeout detection and reporting
- Integration with execution engine

#### 10. Tool Execution Result ([result.py](src/execution/result.py))
Standardized result formatting:
- `ToolExecutionResult` dataclass for success results
- `ToolExecutionResult.error_result()` for error results
- Metadata and logging tracking
- Integration with ExecutionState

#### 11. ToolExecutionResult Class
Execution result with:
- `success`, `output`, `error` properties
- `execution_id`, `execution_time`, `affected_files`, `affected_directories`
- `next_suggestions`, `execution_metadata`
- Factory methods: `success_result()`, `error_result()`

#### 12. Execution State ([execution_state.py](src/execution/execution_state.py))
Tracks execution state with:
- Status: PENDING, VALIDATING, PREPARING, RUNNING, COMPLETED, FAILED, CANCELLED, TIMEOUT
- Progress: float (0.0 - 100.0)
- Permissions requested/granted/denied
- Risk level and timeout tracking
- Thread-safe operations with RLock()

#### 13. Tool Metadata Class
Metadata container with:
- `name`, `category`, `version`, `description`, `author`
- `tags`, `capabilities`, `requires_confirmation`
- `to_dict()` method for serialization

#### 14. Tool Categories Enum ([tool_interface.py](src/execution/tool_interface.py))
Supported categories:
- FILESYSTEM, DESKTOP, BROWSER, GIT, TERMINAL, VISION, VOICE
- KNOWLEDGE, NETWORKING, DOCKER, OFFICE, EMAIL, CALENDAR, MCP, GENERAL

#### 15. Execution Status Enum ([execution_state.py](src/execution/execution_state.py))
Status values:
- PENDING, VALIDATING, PREPARING, RUNNING, COMPLETED, FAILED, CANCELLED, TIMEOUT

### Permission System

#### Permission Actions ([permission_manager.py](src/execution/permission_manager.py))
15 permission types:
- READ_FILE, WRITE_FILE, DELETE_FILE, RENAME_FILE
- EXECUTE_COMMAND, SHUTDOWN_SYSTEM, FORMAT_DISK
- MODIFY_REGISTRY, DELETE_SYSTEM32
- OPEN_APPLICATION, CLOSE_APPLICATION
- ACCESS_CLIPBOARD, NETWORK_ACCESS, MAIL_SEND, CALENDAR_MODIFY

#### Permission Level Requirements
```python
REQUIRED_PERMISSIONS = {
    PermissionAction.READ_FILE: PermissionLevel.SAFE,
    PermissionAction.WRITE_FILE: PermissionLevel.MEDIUM,
    PermissionAction.DELETE_FILE: PermissionLevel.HIGH,
    PermissionAction.EXECUTE_COMMAND: PermissionLevel.MEDIUM,
    # ... etc
}
```

### Usage Example

```python
from execution import (
    ExecutionEngine,
    ToolRegistry,
    FunctionToolAdapter,
    ToolMetadata,
    ToolCategory
)

# Create a simple function tool
def read_file(name: str) -> dict:
    return {"content": f"File contents of {name}"}

# Create tool adapter
adapter = FunctionToolAdapter(
    name="file_reader",
    function=read_file,
    description="Read a file",
    category=ToolCategory.FILESYSTEM,
    capabilities=["read", "write", "delete"]
)

# Initialize execution engine
engine = ExecutionEngine(
    default_timeout=30,
    require_confirmation=True
)

# Register tool
engine.tool_registry.register_tool(adapter)

# Execute tool
result = engine.execute_tool(
    tool_name="file_reader",
    operation="read",
    parameters={"name": "test.txt"}
)

if result.success:
    print(f"Success: {result.output}")
else:
    print(f"Error: {result.error}")
```

### Brain Integration

The Tool Execution Engine integrates seamlessly with AuraBrain ([brain_integration.py](src/brain/brain_integration.py)):
- Unified interface for tool execution
- Backward compatibility with ToolRouter
- Automatic tool registration
- Result formatting for AuraBrain

```python
from brain.brain_integration import BrainIntegration

integration = BrainIntegration(
    workspace_manager=workspace_manager,
    tool_router=existing_tool_router
)
integration.initialize()

result = integration.execute_tool("file_writer", "write", {"content": "hello"})
```

### Architecture

The execution engine follows a modular architecture:
- **Abstraction Layer**: ToolInterface defines the contract
- **Orchestration Layer**: ExecutionEngine coordinates the pipeline
- **Support Layer**: Permission, risk, timeout, and cancellation modules
- **Integration Layer**: BrainIntegration bridges with AuraBrain

### Security Features

1. **Risk-Based Access Control**: Four permission levels with automatic assessment
2. **Confirmation Requirements**: Risky operations require user confirmation
3. **Timeout Protection**: Operations have configurable timeouts
4. **Cancellation Support**: Safe, thread-safe operation cancellation
5. **Audit Logging**: Complete execution history and logging

### Testing

The engine includes comprehensive integration tests ([test_integration.py](test_integration.py)):
- Module imports
- Execution engine creation
- Tool registration and execution
- Permission and risk management
- State tracking and result formatting
- Brain integration

All tests pass successfully:
```powershell
python test_integration.py
```

### Key Features

✓ **Unified Interface**: Single entry point for all tool executions
✓ **Thread-Safe**: Uses RLock() for concurrent execution
✓ **Secure**: Risk-based permission system with confirmation requirements
✓ **Flexible**: Adapters for function and class-based tools
✓ **Monitorable**: Real-time progress tracking and logging
✓ **Reliable**: Timeout handling and cancellation support
✓ **Extensible**: Easy to add new tools and categories
✓ **Integrated**: Works seamlessly with AuraBrain and existing ToolRouter
