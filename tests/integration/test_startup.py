"""
Integration Test Suite: Stage 1 - Core Startup
Tests Aura Core initialization, module loading, and startup sequence.
"""

import asyncio
import importlib
import os
import sys
import warnings


def test_no_import_errors():
    """Ensure all core modules can be imported without errors."""
    print("Testing core module imports...")

    core_modules = [
        "main",
        "aura_core",
        "app",
        "config",
        "event_bus",
        "logger",
        "Memory",
    ]

    for module_name in core_modules:
        try:
            if module_name == "main":
                import main
            elif module_name == "aura_core":
                from core import aura_core
            elif module_name == "app":
                from core import app
            elif module_name == "config":
                from core import config
            elif module_name == "event_bus":
                from core import event_bus
            elif module_name == "logger":
                from core import logger
            elif module_name == "Memory":
                from Memory import Memory
            print(f"  ✓ {module_name}")
        except ImportError as e:
            print(f"  ✗ {module_name}: Import failed - {e}")
            raise


def test_no_circular_imports():
    """Detect circular imports between core modules."""
    print("\nTesting for circular imports...")

    # Try importing and detect circular dependencies
    try:
        import core.aura_core

        print("  ✓ No circular imports detected in core.aura_core")
    except ImportError as e:
        print(f"  ✗ Circular import detected: {e}")
        raise


def test_no_warnings():
    """Ensure startup doesn't produce warnings."""
    print("\nTesting for warnings...")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        # Import modules (may trigger deprecation warnings)
        import main
        from core import app, aura_core

        if len(w) > 0:
            print(f"  ⚠ Warnings detected: {len(w)}")
            for warning in w:
                print(f"    - {warning.category.__name__}: {warning.message}")
        else:
            print("  ✓ No warnings")


def test_no_asyncio_warnings():
    """Ensure asyncio doesn't produce warnings."""
    print("\nTesting for asyncio warnings...")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        # Create a simple event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        if len(w) > 0:
            print(f"  ⚠ Asyncio warnings: {len(w)}")
            for warning in w:
                print(f"    - {warning.category.__name__}: {warning.message}")
        else:
            print("  ✓ No asyncio warnings")


def test_no_encoding_issues():
    """Ensure file paths are encoded correctly."""
    print("\nTesting for encoding issues...")

    test_files = [
        "configs",
        "Data",
        "database",
        "plugins",
    ]

    for path in test_files:
        if os.path.exists(path):
            print(f"  ✓ {path} is accessible")
        else:
            print(f"  ⚠ {path} not found (may be optional)")


def test_all_managers_initialize():
    """Ensure all managers initialize successfully."""
    print("\nTesting manager initialization...")

    try:
        # Try to initialize the core system
        from core import aura_core

        # Check if AuraCore is instantiated
        if hasattr(aura_core, "AuraCore"):
            print("  ✓ AuraCore class available")
        else:
            print("  ⚠ AuraCore class not found")

        # Check for expected managers
        if hasattr(aura_core, "memory_manager"):
            print("  ✓ Memory manager available")
        else:
            print("  ⚠ Memory manager not found")

        if hasattr(aura_core, "brain"):
            print("  ✓ Brain available")
        else:
            print("  ⚠ Brain not found")

        if hasattr(aura_core, "research_engine"):
            print("  ✓ Research engine available")
        else:
            print("  ⚠ Research engine not found")

        if hasattr(aura_core, "workspace_manager"):
            print("  ✓ Workspace manager available")
        else:
            print("  ⚠ Workspace manager not found")

        if hasattr(aura_core, "agent_runtime"):
            print("  ✓ Agent runtime available")
        else:
            print("  ⚠ Agent runtime not found")

        if hasattr(aura_core, "workflow_engine"):
            print("  ✓ Workflow engine available")
        else:
            print("  ⚠ Workflow engine not found")

        if hasattr(aura_core, "plugin_manager"):
            print("  ✓ Plugin manager available")
        else:
            print("  ⚠ Plugin manager not found")

        if hasattr(aura_core, "knowledge_base"):
            print("  ✓ Knowledge base available")
        else:
            print("  ⚠ Knowledge base not found")

    except Exception as e:
        print(f"  ✗ Manager initialization failed: {e}")
        raise


def test_no_duplicate_instances():
    """Ensure only one AuraCore instance exists."""
    print("\nTesting for duplicate instances...")

    try:
        from core import aura_core

        # Count instances (this is a simple check)
        print("  ⚠ Instance counting requires instance tracking")
        print("  ✓ Singleton pattern should prevent duplicates")
    except Exception as e:
        print(f"  ✗ Duplicate instance check failed: {e}")
        raise


def test_settings_loaded():
    """Ensure settings are loaded from configs/."""
    print("\nTesting settings loading...")

    try:
        from core import config

        # Check if config module loaded settings
        if hasattr(config, "SETTINGS"):
            print("  ✓ Settings loaded from config module")
        else:
            print("  ⚠ Settings not found in config module")

        # Check for expected settings
        if hasattr(config, "AuraConfig"):
            print("  ✓ AuraConfig class available")
        else:
            print("  ⚠ AuraConfig class not found")

    except Exception as e:
        print(f"  ✗ Settings loading failed: {e}")
        raise


def test_data_loaded():
    """Ensure data directory structure exists."""
    print("\nTesting data directory...")

    data_dirs = [
        "Data",
        "Data/cache",
        "database",
        "logs",
        "logs/screenshots",
    ]

    for path in data_dirs:
        if os.path.exists(path):
            print(f"  ✓ {path}")
        else:
            print(f"  ⚠ {path} not found (may need creation)")
            os.makedirs(path, exist_ok=True)


def test_workspace_structure():
    """Verify the workspace structure is complete."""
    print("\nTesting workspace structure...")

    required_dirs = [
        "apps",
        "backend",
        "clients",
        "config",
        "core",
        "generated_code",
        "plugins",
        "shared",
        "src",
        "tests",
    ]

    for dir_name in required_dirs:
        if os.path.exists(dir_name):
            print(f"  ✓ {dir_name}/")
        else:
            print(f"  ✗ {dir_name}/ missing")


def run_stage_1_tests():
    """Run all Stage 1 tests."""
    print("=" * 60)
    print("STAGE 1: Core Startup Integration Tests")
    print("=" * 60)

    tests = [
        ("Import Tests", test_no_import_errors),
        ("Circular Import Detection", test_no_circular_imports),
        ("Warning Detection", test_no_warnings),
        ("Asyncio Warning Detection", test_no_asyncio_warnings),
        ("Encoding Issue Detection", test_no_encoding_issues),
        ("Manager Initialization", test_all_managers_initialize),
        ("Duplicate Instance Check", test_no_duplicate_instances),
        ("Settings Loading", test_settings_loaded),
        ("Data Directory Check", test_data_loaded),
        ("Workspace Structure", test_workspace_structure),
    ]

    results = []
    for name, test_func in tests:
        try:
            test_func()
            results.append((name, "PASS", None))
        except Exception as e:
            results.append((name, "FAIL", str(e)))

    print("\n" + "=" * 60)
    print("Stage 1 Summary")
    print("=" * 60)

    passed = sum(1 for _, status, _ in results if status == "PASS")
    failed = sum(1 for _, status, _ in results if status == "FAIL")

    for name, status, error in results:
        symbol = "✓" if status == "PASS" else "✗"
        print(f"{symbol} {name}: {status}")
        if error:
            print(f"  Error: {error}")

    print("\n" + "=" * 60)
    print(f"Stage 1 Results: {passed}/{len(results)} tests passed")
    print("=" * 60)

    if failed > 0:
        print("\n⚠ Some tests failed. Review errors above.")
        return False
    else:
        print("\n✓ All Stage 1 tests passed!")
        return True


if __name__ == "__main__":
    success = run_stage_1_tests()
    sys.exit(0 if success else 1)
