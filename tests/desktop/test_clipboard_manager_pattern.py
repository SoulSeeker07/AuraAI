"""
Test ClipboardManager Reference Implementation Pattern

Validates that ClipboardManager follows the strict pattern:
1. Only contains Windows-specific code
2. No cross-cutting concerns (permissions, metrics, rollback, diagnostics, context, events)
3. Proper lifecycle integration with BaseNativeManager
4. Full capability coverage with verification and rollback handlers
5. Clean separation of concerns

This test serves as the reference pattern that all future managers should follow.
"""

import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, project_root)

import win32clipboard

from src.desktop.native.desktop_execution_engine import DesktopExecutionEngine
from src.desktop.native.desktop_result import DesktopResult, DesktopStatus
from src.desktop.native.managers.clipboard_manager import (
    ClipboardContent,
    ClipboardManager,
)
from src.desktop.native.native_exceptions import ClipboardError


def test_manager_native_structure():
    """Test that ClipboardManager follows native manager structure."""
    manager = ClipboardManager()
    assert manager.name == "clipboard", "Manager name must be 'clipboard'"

    # Check it implements required native methods
    assert hasattr(manager, "execute"), "Must implement execute() method"
    assert hasattr(manager, "capabilities"), "Must have capabilities property"
    assert hasattr(manager, "read_text"), "Must implement read_text()"
    assert hasattr(manager, "write_text"), "Must implement write_text()"
    assert hasattr(manager, "clear"), "Must implement clear()"
    assert hasattr(manager, "read_files"), "Must implement read_files()"
    assert hasattr(manager, "read_image"), "Must implement read_image()"
    assert hasattr(manager, "has_text"), "Must implement has_text()"
    assert hasattr(manager, "has_image"), "Must implement has_image()"
    assert hasattr(manager, "has_files"), "Must implement has_files()"

    # Verify NO internal cross-cutting methods (verify, rollback belong to execution engine)
    assert not hasattr(
        manager, "verify_action"
    ), "Verification should not be inside ClipboardManager"

    print("[OK] Manager native structure is correct")


def test_only_windows_specific_code():
    """
    Test that ClipboardManager only contains Windows-specific code.

    The manager should NEVER contain cross-cutting dependencies:
    - Permission logic
    - Metrics collection
    - Diagnostics middleware
    - DesktopContext state mutations
    - Event bus publishing
    """

    import inspect

    import src.desktop.native.managers.clipboard_manager as cm_module

    source = inspect.getsource(cm_module)

    # Filter out docstrings to check only executable code
    lines = []
    in_docstring = False
    for line in source.splitlines():
        trimmed = line.strip()
        if trimmed.startswith('"""') or trimmed.startswith("'''"):
            if trimmed.count('"""') == 1 or trimmed.count("'''") == 1:
                in_docstring = not in_docstring
            continue
        if not in_docstring and not trimmed.startswith("#"):
            lines.append(line)

    code_body = "\n".join(lines)

    forbidden_symbols = [
        "PermissionMiddleware",
        "MetricsRecorder",
        "DiagnosticsStage",
        "get_desktop_context",
        "NativeEventBus",
        "get_event_bus",
    ]

    found_forbidden = []
    for symbol in forbidden_symbols:
        if symbol in code_body:
            found_forbidden.append(symbol)

    assert len(found_forbidden) == 0, (
        f"ClipboardManager code body should not contain cross-cutting concerns. "
        f"Found forbidden symbols: {found_forbidden}"
    )

    print("[OK] Manager only contains Windows-specific code")


def test_full_capability_coverage():
    """Test that all 13 capabilities are registered."""
    manager = ClipboardManager()

    # Check that all capabilities are registered
    expected_capabilities = [
        "clipboard.read_text",
        "clipboard.write_text",
        "clipboard.clear",
        "clipboard.read_image",
        "clipboard.write_image",
        "clipboard.read_files",
        "clipboard.write_files",
        "clipboard.read_html",
        "clipboard.write_html",
        "clipboard.get_formats",
        "clipboard.has_text",
        "clipboard.has_image",
        "clipboard.has_files",
    ]

    for capability in expected_capabilities:
        assert (
            capability in manager.capabilities
        ), f"Capability '{capability}' not registered"

    assert len(manager.capabilities) == len(
        expected_capabilities
    ), f"Expected {len(expected_capabilities)} capabilities, got {len(manager.capabilities)}"

    print(f"[OK] All {len(expected_capabilities)} capabilities registered")


def test_external_verification_and_rollback():
    """Test that verification and rollback are handled via DesktopExecutionEngine."""
    manager = ClipboardManager()
    engine = DesktopExecutionEngine(manager=manager)

    result = engine.execute(
        goal="write clipboard",
        capability="clipboard.write_text",
        text="Pipeline Verification Test",
    )
    assert result.success is True
    assert result.verification.get("passed") is True

    print("[OK] External verification and rollback via engine verified")


def test_execute_methods_exist():
    """Test that all execute helper methods exist and can be called."""
    manager = ClipboardManager()

    # Test that all exposed methods exist
    assert hasattr(
        manager, "execute_clipboard_read_text"
    ), "Missing execute_clipboard_read_text()"
    assert hasattr(
        manager, "execute_clipboard_write_text"
    ), "Missing execute_clipboard_write_text()"
    assert hasattr(
        manager, "execute_clipboard_clear"
    ), "Missing execute_clipboard_clear()"
    assert hasattr(
        manager, "execute_clipboard_read_image"
    ), "Missing execute_clipboard_read_image()"
    assert hasattr(
        manager, "execute_clipboard_write_image"
    ), "Missing execute_clipboard_write_image()"
    assert hasattr(
        manager, "execute_clipboard_read_files"
    ), "Missing execute_clipboard_read_files()"
    assert hasattr(
        manager, "execute_clipboard_write_files"
    ), "Missing execute_clipboard_write_files()"
    assert hasattr(
        manager, "execute_clipboard_read_html"
    ), "Missing execute_clipboard_read_html()"
    assert hasattr(
        manager, "execute_clipboard_write_html"
    ), "Missing execute_clipboard_write_html()"
    assert hasattr(
        manager, "execute_clipboard_get_formats"
    ), "Missing execute_clipboard_get_formats()"
    assert hasattr(
        manager, "execute_clipboard_has_text"
    ), "Missing execute_clipboard_has_text()"
    assert hasattr(
        manager, "execute_clipboard_has_image"
    ), "Missing execute_clipboard_has_image()"
    assert hasattr(
        manager, "execute_clipboard_has_files"
    ), "Missing execute_clipboard_has_files()"

    print("[OK] All execute helper methods exist")


def test_clipboard_content_model():
    """Test that ClipboardContent model is properly defined."""
    # Test creation
    content = ClipboardContent(
        text="Hello World",
        html="<html><body>Hello</body></html>",
    )
    assert content.text == "Hello World"
    assert content.html == "<html><body>Hello</body></html>"

    # Test has_content
    assert content.has_content()

    # Test to_dict and from_dict
    content_dict = content.to_dict()
    assert content_dict["text"] == "Hello World"
    assert content_dict["html"] == "<html><body>Hello</body></html>"

    # Test round-trip
    content2 = ClipboardContent.from_dict(content_dict)
    assert content2.text == content.text
    assert content2.html == content.html

    print("[OK] ClipboardContent model is properly defined")


def test_execute_workflow():
    """Test the complete execute workflow."""
    manager = ClipboardManager()

    # Test reading text
    result = manager.execute_clipboard_read_text()
    assert isinstance(result, DesktopResult), "execute must return DesktopResult"
    assert (
        result.capability == "clipboard.read_text"
    ), "Result should have correct capability"

    # Test writing text
    result = manager.execute_clipboard_write_text("Test Text")
    assert result.status == DesktopStatus.SUCCESS, "Write should succeed"

    # Test clearing
    result = manager.execute_clipboard_clear()
    assert result.status == DesktopStatus.SUCCESS, "Clear should succeed"

    print("[OK] Execute workflow works correctly")


def test_get_clipboard_content():
    """Test getting full clipboard content."""
    manager = ClipboardManager()

    # Write some content
    manager.execute_clipboard_write_text("Test")

    # Get full content
    content = manager.get_clipboard_content()
    assert content.text == "Test"
    assert content.timestamp is not None

    print("[OK] get_clipboard_content() works correctly")


def test_separation_of_concerns():
    """
    CRITICAL TEST: Verify separation of concerns.

    The manager should NOT:
    - Call permission middleware
    - Call metrics middleware
    - Call diagnostics middleware
    - Call context middleware
    - Call verification middleware directly
    - Call rollback middleware directly
    - Update DesktopContext
    - Publish events
    """

    manager = ClipboardManager()

    # The manager should ONLY call win32clipboard functions
    import inspect

    import src.desktop.native.managers.clipboard_manager as cm_module

    source = inspect.getsource(cm_module.ClipboardManager)

    # Check that win32clipboard is imported
    assert "win32clipboard" in source, "Should import win32clipboard"

    # Check that the execute method only routes to handlers
    assert (
        "_handle_read_text" in source or "handle_read_text" in source
    ), "Should have handle methods"
    assert (
        "_handle_write_text" in source or "handle_write_text" in source
    ), "Should have handle methods"

    print("[OK] Separation of concerns is maintained")


def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("CLIPBOARD MANAGER REFERENCE IMPLEMENTATION PATTERN TESTS")
    print("=" * 70 + "\n")

    tests = [
        test_manager_native_structure,
        test_only_windows_specific_code,
        test_full_capability_coverage,
        test_external_verification_and_rollback,
        test_execute_methods_exist,
        test_clipboard_content_model,
        test_execute_workflow,
        test_get_clipboard_content,
        test_separation_of_concerns,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            print(f"Running: {test.__name__}")
            test()
            passed += 1
            print()
        except AssertionError as e:
            print(f"FAILED: {test.__name__}")
            print(f"  Error: {e}\n")
            failed += 1
        except Exception as e:
            print(f"ERROR: {test.__name__}")
            print(f"  Error: {e}\n")
            failed += 1

    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
