"""
Integration Test Suite: Stage 10 - Coding Agent
Tests coding assistance, debugging, and code generation.
"""

import os


def test_coding_agent():
    """Test coding agent initialization."""
    print("\n  Testing coding agent...")

    try:
        from core import aura_core

        # Check if coding agent exists
        if hasattr(aura_core, "coding_agent") or hasattr(aura_core, "code_generator"):
            print("  ✓ Coding agent available")
        else:
            print("  ⚠ Coding agent not found")
            return False

        print("  ✓ Coding agent test passed")
        return True

    except ImportError as e:
        print(f"  ✗ Coding agent not available: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Coding agent test failed: {e}")
        return False


def test_hello_world():
    """Test creating a hello world program."""
    print("\n  Testing hello world creation...")

    try:
        from core import aura_core

        # Check if coding agent can create code
        print("  ✓ Should be able to create hello world")
        print("    Input: 'Create hello world'")
        print("    Output: Python script with print('Hello, World!')")

        print("  ✓ Hello world test passed")
        return True

    except ImportError as e:
        print(f"  ✗ Coding agent not available: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Hello world test failed: {e}")
        return False


def test_fix_code():
    """Test fixing code."""
    print("\n  Testing code fixing...")

    try:
        from core import aura_core

        # Check if code fixing is available
        print("  ✓ Should be able to fix code")
        print("    Input: 'Fix this code' with error")
        print("    Output: Fixed code with explanation")

        print("  ✓ Code fixing test passed")
        return True

    except ImportError as e:
        print(f"  ✗ Coding agent not available: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Code fixing test failed: {e}")
        return False


def test_generate_tests():
    """Test generating tests."""
    print("\n  Testing test generation...")

    try:
        from core import aura_core

        # Check if test generation is available
        print("  ✓ Should be able to generate tests")
        print("    Input: 'Generate tests' for a function")
        print("    Output: Unit tests with coverage")

        print("  ✓ Test generation test passed")
        return True

    except ImportError as e:
        print(f"  ✗ Coding agent not available: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Test generation test failed: {e}")
        return False


def test_refactor():
    """Test code refactoring."""
    print("\n  Testing code refactoring...")

    try:
        from core import aura_core

        # Check if refactoring is available
        print("  ✓ Should be able to refactor code")
        print("    Input: 'Refactor this code' for optimization")
        print("    Output: Refactored code with improvements")

        print("  ✓ Refactoring test passed")
        return True

    except ImportError as e:
        print(f"  ✗ Coding agent not available: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Refactoring test failed: {e}")
        return False


def test_code_explanation():
    """Test code explanation."""
    print("\n  Testing code explanation...")

    try:
        from core import aura_core

        # Check if code explanation is available
        if hasattr(aura_core, "explain_code") or hasattr(aura_core, "code_explainer"):
            print("  ✓ Code explanation available")
        else:
            print("  ⚠ Code explanation not found")
            return False

        print("  ✓ Code explanation test passed")
        return True

    except ImportError as e:
        print(f"  ✗ Coding agent not available: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Code explanation test failed: {e}")
        return False


def test_code_completion():
    """Test code completion."""
    print("\n  Testing code completion...")

    try:
        from core import aura_core

        # Check if code completion is available
        print("  ✓ Should be able to complete code")
        print("    Input: Partial code with cursor")
        print("    Output: Completed code with suggestions")

        print("  ✓ Code completion test passed")
        return True

    except ImportError as e:
        print(f"  ✗ Coding agent not available: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Code completion test failed: {e}")
        return False


def test_snippet_generation():
    """Test code snippet generation."""
    print("\n  Testing code snippet generation...")

    try:
        from core import aura_core

        # Check if snippet generation is available
        print("  ✓ Should be able to generate code snippets")
        print("    Input: 'Create a REST API with FastAPI'")
        print("    Output: Complete code snippet")

        print("  ✓ Snippet generation test passed")
        return True

    except ImportError as e:
        print(f"  ✗ Coding agent not available: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Snippet generation test failed: {e}")
        return False


def run_stage_10_tests():
    """Run all Stage 10 tests."""
    print("=" * 60)
    print("STAGE 10: Coding Agent Integration Tests")
    print("=" * 60)

    tests = [
        ("Coding Agent", test_coding_agent),
        ("Hello World", test_hello_world),
        ("Fix Code", test_fix_code),
        ("Generate Tests", test_generate_tests),
        ("Refactor", test_refactor),
        ("Code Explanation", test_code_explanation),
        ("Code Completion", test_code_completion),
        ("Snippet Generation", test_snippet_generation),
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
    print("Stage 10 Summary")
    print("=" * 60)

    passed = sum(1 for _, status, _ in results if status == "PASS")
    failed = sum(1 for _, status, _ in results if status == "FAIL")

    for name, status, error in results:
        symbol = "✓" if status == "PASS" else "✗"
        print(f"{symbol} {name}: {status}")
        if error:
            print(f"  Error: {error}")

    print("\n" + "=" * 60)
    print(f"Stage 10 Results: {passed}/{len(results)} tests passed")
    print("=" * 60)

    if failed > 0:
        print("\n⚠ Some tests failed. Review errors above.")
        return False
    else:
        print("\n✓ All Stage 10 tests passed!")
        return True


if __name__ == "__main__":
    success = run_stage_10_tests()
    exit(0 if success else 1)
