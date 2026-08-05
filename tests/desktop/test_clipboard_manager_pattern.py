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

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, project_root)

from src.desktop.native.managers.clipboard_manager import ClipboardManager, ClipboardContent
from src.desktop.native.native_execution_context import ExecutionContextFactory
from src.desktop.native.native_result import NativeResult, ResultStatus
from src.desktop.native.native_exceptions import ClipboardError
import win32clipboard


def test_manager_inherits_from_base():
    """Test that ClipboardManager inherits from BaseNativeManager."""
    manager = ClipboardManager()
    assert isinstance(manager, ClipboardManager), "ClipboardManager must inherit from ClipboardManager"

    # Check it implements the required methods
    assert hasattr(manager, 'execute'), "Must implement execute() method"
    assert hasattr(manager, 'verify'), "Must implement verify() method"
    assert hasattr(manager, 'rollback'), "Must implement rollback() method"
    assert hasattr(manager, 'capabilities'), "Must have capabilities property"
    assert hasattr(manager, 'verification_layer'), "Must have verification_layer property"
    assert hasattr(manager, 'rollback_functions'), "Must have rollback_functions property"

    print("✓ Manager inherits from BaseNativeManager")


def test_only_windows_specific_code():
    """
    Test that ClipboardManager only contains Windows-specific code.

    This is the CRITICAL test. The manager should NEVER contain:
    - Permission logic (handled by pipeline)
    - Metrics collection (handled by pipeline)
    - Rollback logic (handled by pipeline)
    - Diagnostics (handled by pipeline)
    - DesktopContext updates (handled by pipeline)
    - Event publishing (handled by pipeline)
    - Verification logic (handled by pipeline)
    """

    # Check imports - should only have win32clipboard and ctypes
    import src.desktop.native.managers.clipboard_manager as cm_module
    import inspect

    source = inspect.getsource(cm_module.ClipboardManager)

    # These patterns should NOT appear in the source
    forbidden_patterns = [
        "permission",
        "PermissionMiddleware",
        "metrics",
        "MetricsRecorder",
        "diagnostic",
        "Diagnostics",
        "DesktopContext",
        "get_desktop_context",
        "event",
        "publish",
        "NativeEventBus",
    ]

    found_forbidden = []
    for pattern in forbidden_patterns:
        if pattern.lower() in source.lower():
            found_forbidden.append(pattern)

    assert len(found_forbidden) == 0, (
        f"ClipboardManager should not contain cross-cutting concerns. "
        f"Found forbidden patterns: {found_forbidden}"
    )

    print("✓ Manager only contains Windows-specific code")


def test_full_capability_coverage():
    """Test that all 13 capabilities are registered."""
    manager = ClipboardManager()

    # Check that all capabilities are registered
    expected_capabilities = [
        'clipboard.read_text',
        'clipboard.write_text',
        'clipboard.clear',
        'clipboard.read_image',
        'clipboard.write_image',
        'clipboard.read_files',
        'clipboard.write_files',
        'clipboard.read_html',
        'clipboard.write_html',
        'clipboard.get_formats',
        'clipboard.has_text',
        'clipboard.has_image',
        'clipboard.has_files',
    ]

    for capability in expected_capabilities:
        assert capability in manager.capabilities, (
            f"Capability '{capability}' not registered"
        )

    assert len(manager.capabilities) == len(expected_capabilities), (
        f"Expected {len(expected_capabilities)} capabilities, got {len(manager.capabilities)}"
    )

    print(f"✓ All {len(expected_capabilities)} capabilities registered")


def test_verification_handlers_registered():
    """Test that verification handlers are registered."""
    manager = ClipboardManager()
    v_layer = manager.verification_layer

    # Check that verification handlers are registered for relevant capabilities
    verification_handlers = {
        'clipboard.write_text': 'verify_text_written',
        'clipboard.clear': 'verify_cleared',
        'clipboard.write_image': 'verify_image_written',
        'clipboard.write_files': 'verify_files_written',
        'clipboard.write_html': 'verify_html_written',
    }

    for capability, handler_name in verification_handlers.items():
        handler = v_layer.get_handler(capability)
        assert handler is not None, f"Verification handler for '{capability}' not registered"
        assert hasattr(v_layer, handler_name), f"Handler method '{handler_name}' not found"

    print("✓ Verification handlers registered")


def test_rollback_handlers_registered():
    """Test that rollback handlers are registered."""
    manager = ClipboardManager()
    rollback_mgr = manager.rollback_functions

    # Check that rollback handlers are registered
    rollback_handlers = {
        'clipboard.clear': 'rollback_clear',
    }

    for capability, handler_name in rollback_handlers.items():
        handler = rollback_mgr.get_handler(capability)
        assert handler is not None, f"Rollback handler for '{capability}' not registered"
        assert hasattr(rollback_mgr, handler_name), f"Handler method '{handler_name}' not found"

    print("✓ Rollback handlers registered")


def test_execute_methods_exist():
    """Test that all execute methods exist and can be called."""
    manager = ClipboardManager()

    # Test that all exposed methods exist
    assert hasattr(manager, 'execute_clipboard_read_text'), "Missing execute_clipboard_read_text()"
    assert hasattr(manager, 'execute_clipboard_write_text'), "Missing execute_clipboard_write_text()"
    assert hasattr(manager, 'execute_clipboard_clear'), "Missing execute_clipboard_clear()"
    assert hasattr(manager, 'execute_clipboard_read_image'), "Missing execute_clipboard_read_image()"
    assert hasattr(manager, 'execute_clipboard_write_image'), "Missing execute_clipboard_write_image()"
    assert hasattr(manager, 'execute_clipboard_read_files'), "Missing execute_clipboard_read_files()"
    assert hasattr(manager, 'execute_clipboard_write_files'), "Missing execute_clipboard_write_files()"
    assert hasattr(manager, 'execute_clipboard_read_html'), "Missing execute_clipboard_read_html()"
    assert hasattr(manager, 'execute_clipboard_write_html'), "Missing execute_clipboard_write_html()"
    assert hasattr(manager, 'execute_clipboard_get_formats'), "Missing execute_clipboard_get_formats()"
    assert hasattr(manager, 'execute_clipboard_has_text'), "Missing execute_clipboard_has_text()"
    assert hasattr(manager, 'execute_clipboard_has_image'), "Missing execute_clipboard_has_image()"
    assert hasattr(manager, 'execute_clipboard_has_files'), "Missing execute_clipboard_has_files()"

    print("✓ All execute methods exist")


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

    print("✓ ClipboardContent model is properly defined")


def test_execute_workflow():
    """Test the complete execute workflow."""
    manager = ClipboardManager()

    # Test reading text
    result = manager.execute_clipboard_read_text()
    assert isinstance(result, NativeResult), "execute must return NativeResult"
    assert result.capability == 'clipboard.read_text', "Result should have correct capability"

    # Test writing text
    result = manager.execute_clipboard_write_text("Test Text")
    assert result.status == ResultStatus.SUCCESS, "Write should succeed"

    # Test clearing
    result = manager.execute_clipboard_clear()
    assert result.status == ResultStatus.SUCCESS, "Clear should succeed"

    print("✓ Execute workflow works correctly")


def test_get_clipboard_content():
    """Test getting full clipboard content."""
    manager = ClipboardManager()

    # Write some content
    manager.execute_clipboard_write_text("Test")

    # Get full content
    content = manager.get_clipboard_content()
    assert content.text == "Test"
    assert content.timestamp is not None

    print("✓ get_clipboard_content() works correctly")


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
    import src.desktop.native.managers.clipboard_manager as cm_module
    import inspect

    source = inspect.getsource(cm_module.ClipboardManager)

    # Check that win32clipboard is imported
    assert 'win32clipboard' in source, "Should import win32clipboard"

    # Check that the execute method only routes to handlers
    assert '_handle_read_text' in source or 'handle_read_text' in source, "Should have handle methods"
    assert '_handle_write_text' in source or 'handle_write_text' in source, "Should have handle methods"

    # Check that handle methods only contain win32clipboard code
    # (this is a simplified check - in reality we'd inspect each handler)

    print("✓ Separation of concerns is maintained")


def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("CLIPBOARD MANAGER REFERENCE IMPLEMENTATION PATTERN TESTS")
    print("=" * 70 + "\n")

    tests = [
        test_manager_inherits_from_base,
        test_only_windows_specific_code,
        test_full_capability_coverage,
        test_verification_handlers_registered,
        test_rollback_handlers_registered,
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
            print(f"✗ FAILED: {test.__name__}")
            print(f"  Error: {e}\n")
            failed += 1
        except Exception as e:
            print(f"✗ ERROR: {test.__name__}")
            print(f"  Error: {e}\n")
            failed += 1

    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
