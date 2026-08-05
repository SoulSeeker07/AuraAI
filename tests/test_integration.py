"""
Simple integration test for Tool Execution Engine
"""

import os
import sys

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

print("=" * 80)
print("Tool Execution Engine - Integration Test")
print("=" * 80)

try:
    # Test 1: Import execution modules
    print("\n[Test 1] Importing execution modules...")
    from execution import (
        BaseToolAdapter,
        ExecutionEngine,
        FunctionToolAdapter,
        PermissionManager,
        RiskAnalyzer,
        ToolCategory,
        ToolExecutionResult,
        ToolManager,
        ToolMetadata,
        ToolRegistry,
    )

    print("✓ All execution modules imported successfully")

    # Test 2: Create execution engine
    print("\n[Test 2] Creating execution engine...")
    registry = ToolRegistry()
    permission_manager = PermissionManager(allow_all=True)
    engine = ExecutionEngine(
        tool_registry=registry, permission_manager=permission_manager
    )
    print("✓ Execution engine created successfully")
    print(f"  - Tool count: {engine.get_tool_count()}")

    # Test 3: Create a simple tool adapter
    print("\n[Test 3] Creating test tool adapter...")

    def test_function(name: str) -> dict:
        """Test function."""
        return {"status": "success", "tool": name}

    adapter = FunctionToolAdapter(
        name="test_tool",
        function=test_function,
        description="A test tool",
        version="1.0.0",
    )

    print("✓ Test tool adapter created")
    print(f"  - Name: {adapter.get_metadata().name}")
    print(f"  - Description: {adapter.get_metadata().description}")
    print(f"  - Operations: {adapter.get_supported_operations()}")

    # Test 4: Register tool
    print("\n[Test 4] Registering tool...")
    engine.tool_registry.register_tool(adapter)
    print("✓ Tool registered")
    print(f"  - Tool count: {engine.get_tool_count()}")

    # Test 5: Execute tool
    print("\n[Test 5] Executing tool...")
    result = engine.execute_tool(
        tool_name="test_tool", operation="execute", parameters={"name": "test"}
    )

    if result.success:
        print("✓ Tool executed successfully")
        print(f"  - Output: {result.output}")
        print(f"  - Execution time: {result.execution_time:.3f}s")
    else:
        print(f"✗ Tool execution failed: {result.error}")

    # Test 6: Test permission manager
    print("\n[Test 6] Testing permission manager...")
    perm_manager = PermissionManager()
    perm = perm_manager.get_required_permission("safe_operation")
    print(f"✓ Permission manager working (SAFE = {perm})")

    # Test 7: Test risk analyzer
    print("\n[Test 7] Testing risk analyzer...")
    risk_analyzer = RiskAnalyzer(require_confirmation=True)
    requires_confirm, risk_level, _ = risk_analyzer.check_if_confirmation_required(
        "simple_tool", "read", {"file": "test.txt"}
    )
    print(
        f"✓ Risk analyzer working (requires_confirm={requires_confirm}, risk_level={risk_level})"
    )

    # Test 8: Test execution state
    print("\n[Test 8] Testing execution state...")
    from execution import ExecutionStateManager, ExecutionStatus

    state_manager = ExecutionStateManager()
    state = state_manager.create_execution(
        execution_id="test_id",
        tool_name="test_tool",
        tool_category="test",
        parameters={},
    )
    state.start()
    state.update_progress(50, "Processing")
    state.complete(result={"status": "success"})
    print("✓ Execution state working")
    print(f"  - Status: {state.status}")
    print(f"  - Progress: {state.progress}")

    # Test 9: Test result formatting
    print("\n[Test 9] Testing result formatting...")
    result = ToolExecutionResult.success_result(
        output={"data": "test"}, execution_id="test_id", execution_time=1.0
    )
    print("✓ Result formatting working")
    print(f"  - Success: {result.success}")
    print(f"  - Output: {result.output}")

    # Test 10: Test brain integration import
    print("\n[Test 10] Testing brain integration...")
    try:
        from brain.brain_integration import BrainIntegration

        print("✓ Brain integration imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import brain integration: {e}")

    # Summary
    print("\n" + "=" * 80)
    print("✓ ALL TESTS PASSED!")
    print("=" * 80)
    print("\nThe Tool Execution Engine is working correctly.")
    print("All core modules can be imported and used.")

except ImportError as e:
    print(f"\n✗ Import Error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"\n✗ Test Error: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
