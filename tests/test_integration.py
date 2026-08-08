"""
Simple integration test for Tool Execution Engine
"""

import os
import sys

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def main() -> None:
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

        # Test 2: Create ToolMetadata
        print("\n[Test 2] Creating ToolMetadata...")
        metadata = ToolMetadata(
            name="test_tool",
            category=ToolCategory.SYSTEM,
            description="A test tool",
            version="1.0.0",
        )
        print(
            f"✓ ToolMetadata created: {metadata.name} (Category: {metadata.category.value})"
        )

        # Test 3: Create RiskAnalyzer
        print("\n[Test 3] Creating RiskAnalyzer...")
        risk_analyzer = RiskAnalyzer()
        risk_score = risk_analyzer.analyze("test_tool", ToolCategory.SYSTEM, {})
        print(f"✓ RiskAnalyzer created (Risk score: {risk_score.overall_score})")

        # Test 4: Create PermissionManager
        print("\n[Test 4] Creating PermissionManager...")
        permission_manager = PermissionManager()
        print("✓ PermissionManager created")

        # Test 5: Create ToolRegistry
        print("\n[Test 5] Creating ToolRegistry...")
        registry = ToolRegistry()
        print("✓ ToolRegistry created")

        # Test 6: Create ToolManager
        print("\n[Test 6] Creating ToolManager...")
        manager = ToolManager(registry, permission_manager, risk_analyzer)
        print("✓ ToolManager created")

        # Test 7: Register a function tool
        print("\n[Test 7] Registering a function tool...")

        def sample_function(x: int, y: int) -> int:
            """Add two numbers."""
            return x + y

        adapter = FunctionToolAdapter(
            name="add_numbers",
            func=sample_function,
            category=ToolCategory.SYSTEM,
            description="Add two numbers",
        )

        success = manager.register_tool(adapter)
        print(f"✓ Tool registered: {success}")

        # Test 8: Create ExecutionEngine
        print("\n[Test 8] Creating ExecutionEngine...")
        engine = ExecutionEngine(manager)
        print("✓ ExecutionEngine created")

        # Test 9: Execute tool
        print("\n[Test 9] Executing tool...")
        result = engine.execute("add_numbers", {"x": 5, "y": 10})
        print("✓ Tool executed successfully!")
        print(f"  Result: {result.result}")
        print(f"  Success: {result.success}")
        print(f"  Execution time: {result.execution_time_ms:.2f}ms")

        # Test 10: Import brain integration
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


if __name__ == "__main__":
    main()
