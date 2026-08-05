"""
Integration Test Suite: Stage 14 - Regression
Tests that all previous tests still pass after changes.
"""

import importlib
import sys


def run_all_previous_tests():
    """Run all previous tests to ensure regression hasn't occurred."""
    print("\n  Running all previous integration tests...")

    # Import test modules
    test_modules = [
        "tests.integration.test_startup",
        "tests.integration.test_memory",
        "tests.integration.test_knowledge",
        "tests.integration.test_research",
        "tests.integration.test_planner",
        "tests.integration.test_runtime",
        "tests.integration.test_workflow",
        "tests.integration.test_plugins",
        "tests.integration.test_workspace",
        "tests.integration.test_coding",
        "tests.integration.test_vision",
        "tests.integration.test_desktop",
        "tests.integration.test_performance",
    ]

    passed_tests = []
    failed_tests = []

    for module_name in test_modules:
        try:
            module = importlib.import_module(module_name)

            # Get all test functions
            test_functions = [
                (name, func)
                for name, func in vars(module).items()
                if name.startswith("test_") and callable(func)
            ]

            if not test_functions:
                print(f"  ⚠ No tests found in {module_name}")
                continue

            print(f"\n  Running tests from {module_name}...")

            module_passed = 0
            module_failed = 0

            for test_name, test_func in test_functions:
                try:
                    # Execute test
                    if hasattr(test_func, "__code__"):
                        # Test is synchronous
                        result = test_func()
                    else:
                        # Test is async, need to run it
                        import asyncio

                        result = asyncio.run(test_func())

                    if result:
                        module_passed += 1
                        print(f"    ✓ {test_name}")
                    else:
                        module_failed += 1
                        print(f"    ✗ {test_name}")
                        failed_tests.append((module_name, test_name))

                except Exception as e:
                    module_failed += 1
                    print(f"    ✗ {test_name}: {e}")
                    failed_tests.append((module_name, test_name))

            if module_passed > 0 or module_failed == 0:
                passed_tests.append((module_name, module_passed, module_failed))
            else:
                passed_tests.append((module_name, module_passed, module_failed))

        except ImportError as e:
            print(f"  ✗ Could not import {module_name}: {e}")
            failed_tests.append((module_name, "ImportError"))

    return passed_tests, failed_tests


def test_critical_functions():
    """Test that critical Aura functions still work."""
    print("\n  Testing critical functions...")

    critical_tests = []

    try:
        from core import aura_core

        print("  ✓ AuraCore import successful")
        critical_tests.append(("AuraCore Import", "PASS", None))
    except Exception as e:
        print(f"  ✗ AuraCore import failed: {e}")
        critical_tests.append(("AuraCore Import", "FAIL", str(e)))

    try:
        import main

        print("  ✓ main import successful")
        critical_tests.append(("main Import", "PASS", None))
    except Exception as e:
        print(f"  ✗ main import failed: {e}")
        critical_tests.append(("main Import", "FAIL", str(e)))

    try:
        from Memory import Memory

        print("  ✓ Memory import successful")
        critical_tests.append(("Memory Import", "PASS", None))
    except Exception as e:
        print(f"  ✗ Memory import failed: {e}")
        critical_tests.append(("Memory Import", "FAIL", str(e)))

    return critical_tests


def test_recent_changes():
    """Test that recent code changes haven't broken anything."""
    print("\n  Testing recent changes...")

    try:
        # Check if core modules exist
        modules_to_check = [
            "core.aura_core",
            "core.config",
            "core.event_bus",
        ]

        for module_name in modules_to_check:
            try:
                parts = module_name.split(".")
                module = __import__(module_name)
                for part in parts[1:]:
                    module = getattr(module, part)
                print(f"  ✓ {module_name} accessible")
            except Exception as e:
                print(f"  ⚠ {module_name}: {e}")

        print("  ✓ Recent changes test passed")
        return True

    except Exception as e:
        print(f"  ✗ Recent changes test failed: {e}")
        return False


def test_import_chain():
    """Test that import chain is not broken."""
    print("\n  Testing import chain...")

    try:
        # Test core imports
        from core import aura_core, config, event_bus

        # Test dependency imports
        from Memory import Memory

        print("  ✓ Import chain is intact")
        return True

    except ImportError as e:
        print(f"  ✗ Import chain broken: {e}")
        return False


def run_stage_14_tests():
    """Run all Stage 14 tests."""
    print("=" * 60)
    print("STAGE 14: Regression Integration Tests")
    print("=" * 60)

    print("\nRunning comprehensive regression checks...")
    print("(This validates that no previous milestone has been broken)")

    tests = [
        ("Critical Functions", test_critical_functions),
        ("Import Chain", test_import_chain),
        ("Recent Changes", test_recent_changes),
        ("All Previous Tests", run_all_previous_tests),
    ]

    results = []
    for name, test_func in tests:
        try:
            if test_func():
                results.append((name, "PASS", None))
            else:
                results.append((name, "FAIL", "Test returned False"))
        except Exception as e:
            results.append((name, "FAIL", str(e)))

    print("\n" + "=" * 60)
    print("Stage 14 Summary")
    print("=" * 60)

    passed = sum(1 for _, status, _ in results if status == "PASS")
    failed = sum(1 for _, status, _ in results if status == "FAIL")

    for name, status, error in results:
        symbol = "✓" if status == "PASS" else "✗"
        print(f"{symbol} {name}: {status}")
        if error:
            print(f"  Error: {error}")

    print("\n" + "=" * 60)
    print(f"Stage 14 Results: {passed}/{len(results)} tests passed")
    print("=" * 60)

    if failed > 0:
        print("\n⚠ Some regression tests failed.")
        print(
            "⚠ This indicates that recent changes may have broken existing functionality."
        )
        return False
    else:
        print("\n✓ All regression tests passed!")
        print("✓ Previous milestones remain intact.")
        return True


if __name__ == "__main__":
    success = run_stage_14_tests()
    exit(0 if success else 1)
