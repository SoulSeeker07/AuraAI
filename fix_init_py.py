#!/usr/bin/env python3
"""Script to update __init__.py with missing imports."""

import re

# Read the current __init__.py file
with open('src/execution/__init__.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Update the __all__ list to include all new classes
old_all = """__all__ = [
    # Main components
    'ExecutionEngine',
    'ToolRegistry',
    'ToolManager',
    
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
]"""

new_all = """__all__ = [
    # Main components
    'ExecutionEngine',
    'ToolRegistry',
    'ToolManager',
    
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
    
    # Management
    'PermissionManager',
    'PermissionContext',
    'RiskAnalyzer',
    'ProgressTracker',
    'CancellationToken',
    'TimeoutMonitor',
    
    # Execution state
    'ExecutionState',
    'ExecutionStateManager',
    
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
]"""

# Replace the old __all__ with the new one
content = content.replace(old_all, new_all)

# Write the updated content back to the file
with open('src/execution/__init__.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Updated __init__.py __all__ list successfully")
print("\nAdded to exports:")
print("  - PermissionManager, PermissionContext")
print("  - RiskAnalyzer")
print("  - ProgressTracker")
print("  - CancellationToken")
print("  - TimeoutMonitor")
print("  - ExecutionState, ExecutionStateManager")
print("  - All exception classes")
