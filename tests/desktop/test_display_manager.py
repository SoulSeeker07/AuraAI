"""
Test DisplayManager Pattern & Execution

Validates:
1. DisplayManager follows pure native structure (zero cross-cutting concerns).
2. Auto-discovery by NativeManagerRegistry.
3. Capability execution through DesktopExecutionEngine.
"""

import sys
import os
import inspect

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, project_root)

from src.desktop.native.managers.display_manager import DisplayManager
from src.desktop.native.managers.native_manager_registry import NativeManagerRegistry
from src.desktop.native.desktop_execution_engine import DesktopExecutionEngine
import src.desktop.native.managers.display_manager as dm_module


def setup_function():
    """Reset registry singleton before test."""
    NativeManagerRegistry.reset_instance()


def teardown_function():
    """Reset registry singleton after test."""
    NativeManagerRegistry.reset_instance()


def test_display_manager_native_structure():
    """Test that DisplayManager follows pure native manager structure."""
    manager = DisplayManager()
    assert manager.name == "display"
    assert manager.NAME == "display"
    assert manager.VERSION == "1.0"
    assert manager.PRIORITY == 20
    assert "win32api" in manager.DEPENDENCIES

    assert hasattr(manager, "execute")
    assert len(manager.capabilities) >= 9

    # Verify no cross-cutting concerns in code body
    source = inspect.getsource(dm_module)
    forbidden_symbols = [
        "PermissionMiddleware",
        "MetricsRecorder",
        "DiagnosticsStage",
        "get_desktop_context",
        "NativeEventBus",
    ]
    for symbol in forbidden_symbols:
        assert symbol not in source, f"DisplayManager code body contains forbidden symbol: {symbol}"

    print("[OK] DisplayManager native structure verified")


def test_display_manager_auto_discovery():
    """Test DisplayManager auto-discovery."""
    registry = NativeManagerRegistry.get_instance()
    discovered = registry.discover("src.desktop.native.managers")

    assert "display" in discovered
    display_manager = registry.get("display")
    assert display_manager is not None
    assert display_manager.name == "display"

    print("[OK] DisplayManager auto-discovery verified")


def test_display_capabilities_execution():
    """Test executing display capabilities through DesktopExecutionEngine."""
    registry = NativeManagerRegistry.get_instance()
    registry.discover("src.desktop.native.managers")

    engine = DesktopExecutionEngine(manager_registry=registry)

    # Test list_displays
    res_list = engine.execute(goal="list connected displays", capability="list_displays")
    assert res_list.success is True
    assert "monitors" in res_list.data
    assert res_list.manager == "display"

    # Test display.list
    res_list_dot = engine.execute(goal="list connected monitors", capability="display.list")
    assert res_list_dot.success is True

    # Test get_primary_display
    res_primary = engine.execute(goal="get primary monitor", capability="get_primary_display")
    assert res_primary.success is True
    assert "primary_display" in res_primary.data

    # Test get_display_layout
    res_layout = engine.execute(goal="get virtual screen layout", capability="get_display_layout")
    assert res_layout.success is True
    assert "virtual_screen" in res_layout.data

    # Test get_dpi
    res_dpi = engine.execute(goal="get monitor dpi", capability="get_dpi")
    assert res_dpi.success is True
    assert "dpi_x" in res_dpi.data

    # Test get_brightness
    res_bright = engine.execute(goal="get screen brightness", capability="get_brightness")
    assert res_bright.success is True

    print("[OK] DisplayManager capability execution through engine verified")
