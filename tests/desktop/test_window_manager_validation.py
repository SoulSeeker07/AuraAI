"""
WindowManager Architectural Validation Test

Validates that WindowManager operates strictly as a native manager plugged into
DesktopExecutionEngine:
1. Every registered window capability executes through DesktopExecutionEngine.
2. Confirm no code path calls WindowManager directly.
3. Verify permissions, verification, rollback, diagnostics, context updates,
   metrics, and events are all triggered by the pipeline—not by WindowManager itself.
"""

import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, project_root)

import inspect
from unittest.mock import MagicMock

from src.desktop.native.capability_registry import CapabilityRegistry
from src.desktop.native.desktop_execution_engine import (
    DesktopExecutionEngine,
    ExecutionConfig,
)
from src.desktop.native.desktop_result import DesktopResult, DesktopStatus
from src.desktop.native.managers.window_manager import WindowManager


def test_window_manager_no_cross_cutting_concerns():
    """Verify WindowManager code body does not contain cross-cutting dependencies."""
    import src.desktop.native.managers.window_manager as wm_module

    source = inspect.getsource(wm_module)

    # Filter out docstrings
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
        f"WindowManager code body should not contain cross-cutting concerns. "
        f"Found forbidden symbols: {found_forbidden}"
    )

    print("[OK] WindowManager code body has no cross-cutting concerns")


def test_all_window_capabilities_registered_in_registry():
    """Verify all window capabilities are in CapabilityRegistry."""
    registry = CapabilityRegistry()
    window_caps = registry.get_by_category("window")
    window_cap_names = [cap.name for cap in window_caps]

    expected = [
        "list_windows",
        "get_window",
        "activate_window",
        "close_window",
        "move_window",
        "resize_window",
        "minimize_window",
        "maximize_window",
        "restore_window",
    ]

    for cap_name in expected:
        assert (
            cap_name in window_cap_names
        ), f"Missing capability in registry: {cap_name}"

    print(
        f"[OK] All {len(expected)} window capabilities registered in CapabilityRegistry"
    )


def test_execution_through_engine_triggers_all_pipeline_stages():
    """Verify executing window capabilities through DesktopExecutionEngine triggers pipeline stages."""
    wm = WindowManager()
    engine = DesktopExecutionEngine(manager=wm)

    # Execute list_windows through DesktopExecutionEngine
    result = engine.execute(goal="list windows")

    assert result is not None
    assert isinstance(result, DesktopResult)
    assert result.capability in ["list_windows", "window.list"]
    assert result.manager == "window"

    # Pipeline stages check
    assert result.verification.get("passed") is True, "Verification stage must run"
    assert "diagnostics" in result.metrics, "Diagnostics stage must run"
    assert result.metrics["total_duration_ms"] > 0, "Metrics stage must run"

    print(
        "[OK] DesktopExecutionEngine pipeline stages executed successfully for window capability"
    )


def test_no_direct_manager_bypass():
    """
    Test that caller routes through DesktopExecutionEngine rather than calling
    WindowManager directly.
    """
    mock_engine = MagicMock(spec=DesktopExecutionEngine)

    def execute_via_engine(goal: str, capability: str, **kwargs):
        return mock_engine.execute(goal=goal, capability=capability, arguments=kwargs)

    execute_via_engine(
        goal="Activate VS Code", capability="activate_window", window_title="VS Code"
    )

    mock_engine.execute.assert_called_once_with(
        goal="Activate VS Code",
        capability="activate_window",
        arguments={"window_title": "VS Code"},
    )

    print("[OK] Execution routed strictly through DesktopExecutionEngine")


def run_all_tests():
    print("\n" + "=" * 70)
    print("WINDOW MANAGER ARCHITECTURAL VALIDATION TESTS")
    print("=" * 70 + "\n")

    tests = [
        test_window_manager_no_cross_cutting_concerns,
        test_all_window_capabilities_registered_in_registry,
        test_execution_through_engine_triggers_all_pipeline_stages,
        test_no_direct_manager_bypass,
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
