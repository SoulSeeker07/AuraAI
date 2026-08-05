"""
Simple debug script to test if the category issue occurs during execution
"""

import os
import sys

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from execution import ExecutionEngine, FunctionToolAdapter, ToolRegistry


def test_func(name: str):
    """Test function."""
    print(f"Test function called with name: {name}")
    return {"status": "success", "tool": name}


print("Creating test tool...")
adapter = FunctionToolAdapter(
    name="test_tool", function=test_func, description="A test tool", version="1.0.0"
)

print("Getting metadata before registration...")
metadata = adapter.get_metadata()
print(f"Category type: {type(metadata.category)}")
print(f"Category value: {metadata.category}")
print(f"Has .value attribute: {hasattr(metadata.category, 'value')}")
if hasattr(metadata.category, "value"):
    print(f"Category .value: {metadata.category.value}")

print("\nRegistering tool...")
registry = ToolRegistry()
registry.register_tool(adapter)

print("Getting metadata after registration...")
retrieved_tool = registry.get_tool("test_tool")
metadata2 = retrieved_tool.get_metadata()
print(f"Category type: {type(metadata2.category)}")
print(f"Category value: {metadata2.category}")
print(f"Has .value attribute: {hasattr(metadata2.category, 'value')}")
if hasattr(metadata2.category, "value"):
    print(f"Category .value: {metadata2.category.value}")

print("\nCreating execution engine...")
engine = ExecutionEngine(tool_registry=registry)

print("\nExecuting tool...")
try:
    result = engine.execute_tool(
        tool_name="test_tool", operation="execute", parameters={"name": "test"}
    )
    print(f"Execution result: {result}")
    print(f"Success: {result.success}")
    print(f"Output: {result.output}")
    print(f"Error: {result.error}")
    if hasattr(result, "execution_metadata") and result.execution_metadata:
        print(f"Execution metadata: {result.execution_metadata}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback

    traceback.print_exc()
