"""
Test Native Manager Registry & Auto-Discovery Subsystem

Validates:
1. Dynamic package auto-discovery of BaseNativeManager subclasses.
2. Manager lifecycle execution (Discover -> Instantiate -> Initialize -> Health -> Register -> Shutdown).
3. Data-driven capability resolution via NativeManagerRegistry.resolve().
4. Manager Health Check framework (HEALTHY, DEGRADED, UNAVAILABLE, DISABLED).
5. Pre-flight capability validation pass with CapabilityValidator.
6. DesktopExecutionEngine integration using NativeManagerRegistry.
"""

import sys
import os
import inspect

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, project_root)

from src.desktop.native.managers.base_manager import BaseNativeManager, HealthStatus, HealthCheckResult
from src.desktop.native.managers.native_manager_registry import NativeManagerRegistry
from src.desktop.native.managers.window_manager import WindowManager
from src.desktop.native.managers.clipboard_manager import ClipboardManager
from src.desktop.native.capability_validator import CapabilityValidator, CapabilityValidationReport
from src.desktop.native.capability_registry import CapabilityRegistry
from src.desktop.native.desktop_execution_engine import DesktopExecutionEngine, ExecutionConfig


def setup_function():
    """Reset registry singleton before each test."""
    NativeManagerRegistry.reset_instance()


def teardown_function():
    """Clean up after test."""
    NativeManagerRegistry.reset_instance()


def test_base_native_manager_metadata():
    """Test BaseNativeManager metadata attributes and health check defaults."""
    wm = WindowManager()
    assert wm.name == "window"
    assert wm.NAME == "window"
    assert wm.VERSION == "1.0"
    assert wm.PRIORITY == 10
    assert "win32gui" in wm.DEPENDENCIES

    cm = ClipboardManager()
    assert cm.name == "clipboard"
    assert cm.NAME == "clipboard"
    assert cm.VERSION == "1.0"
    assert cm.PRIORITY == 10
    assert "win32clipboard" in cm.DEPENDENCIES

    # Test health check
    health_res = wm.health_check()
    assert isinstance(health_res, HealthCheckResult)
    assert health_res.manager_name == "window"
    assert health_res.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]

    print("[OK] BaseNativeManager metadata and health checks verified")


def test_auto_discovery():
    """Test dynamic package auto-discovery of native managers."""
    registry = NativeManagerRegistry.get_instance()
    discovered = registry.discover("src.desktop.native.managers")

    assert "window" in discovered, "WindowManager should be auto-discovered"
    assert "clipboard" in discovered, "ClipboardManager should be auto-discovered"
    assert len(discovered) >= 2

    # Check managers list
    managers_info = registry.list()
    names = [m["name"] for m in managers_info]
    assert "window" in names
    assert "clipboard" in names

    print(f"[OK] Auto-discovered {len(discovered)} managers: {discovered}")


def test_capability_resolution():
    """Test data-driven capability resolution."""
    registry = NativeManagerRegistry.get_instance()
    registry.discover("src.desktop.native.managers")

    # Resolve window capabilities
    wm = registry.resolve("list_windows")
    assert wm is not None
    assert wm.name == "window"

    wm_activate = registry.resolve("activate_window")
    assert wm_activate is not None
    assert wm_activate.name == "window"

    # Resolve clipboard capabilities
    cm_read = registry.resolve("clipboard.read_text")
    assert cm_read is not None
    assert cm_read.name == "clipboard"

    cm_write = registry.resolve("clipboard.write_text")
    assert cm_write is not None
    assert cm_write.name == "clipboard"

    # Resolve unknown capability
    unknown = registry.resolve("unknown.capability")
    assert unknown is None

    print("[OK] Capability resolution verified")


def test_manager_health_aggregation():
    """Test aggregated health diagnostics across all managers."""
    registry = NativeManagerRegistry.get_instance()
    registry.discover("src.desktop.native.managers")

    health_summary = registry.health()
    assert "window" in health_summary
    assert "clipboard" in health_summary
    assert health_summary["window"]["status"] in [HealthStatus.HEALTHY.value, HealthStatus.DEGRADED.value]

    diag = registry.diagnostics()
    assert diag["total_managers"] >= 2
    assert diag["auto_discovered"] is True
    assert "managers" in diag

    print("[OK] Health aggregation and diagnostics verified")


def test_capability_validation_pass():
    """Test CapabilityValidator pre-flight check."""
    cap_registry = CapabilityRegistry()
    manager_registry = NativeManagerRegistry.get_instance()
    manager_registry.discover("src.desktop.native.managers")

    validator = CapabilityValidator(
        capability_registry=cap_registry,
        manager_registry=manager_registry,
    )

    report = validator.validate_all()
    assert isinstance(report, CapabilityValidationReport)
    assert report.total_capabilities > 0
    assert report.validated_capabilities > 0
    assert report.valid is True, f"Capability validation failed with errors: {report.errors}"

    print(f"[OK] Pre-flight capability validation passed ({report.validated_capabilities}/{report.total_capabilities} capabilities validated)")


def test_execution_engine_registry_integration():
    """Test DesktopExecutionEngine executing capabilities via NativeManagerRegistry."""
    manager_registry = NativeManagerRegistry.get_instance()
    manager_registry.discover("src.desktop.native.managers")

    engine = DesktopExecutionEngine(manager_registry=manager_registry)

    # Execute window capability
    result_window = engine.execute(goal="list all open windows", capability="list_windows")
    assert result_window.success is True
    assert result_window.manager == "window"

    # Execute clipboard capability
    result_clipboard = engine.execute(goal="write hello to clipboard", capability="clipboard.write_text", text="hello")
    assert result_clipboard.success is True
    assert result_clipboard.manager == "clipboard"

    print("[OK] ExecutionEngine + NativeManagerRegistry integration verified")


def test_custom_manager_lifecycle():
    """Test full lifecycle of a custom mock manager."""
    class CustomTestManager(BaseNativeManager):
        NAME = "custom_test"
        VERSION = "1.0"
        PRIORITY = 5
        DEPENDENCIES = []

        def __init__(self):
            super().__init__()
            self._capabilities = ["custom.action"]
            self.initialized_flag = False
            self.shutdown_flag = False

        def initialize(self):
            super().initialize()
            self.initialized_flag = True

        def shutdown(self):
            super().shutdown()
            self.shutdown_flag = True

        def execute(self, capability: str, goal: str = "", arguments: dict = None):
            return True

    manager = CustomTestManager()
    registry = NativeManagerRegistry.get_instance()

    registry.register(manager)
    assert manager.initialized_flag is True
    assert registry.get("custom_test") is manager
    assert registry.resolve("custom.action") is manager

    registry.unregister("custom_test")
    assert manager.shutdown_flag is True
    assert registry.get("custom_test") is None
    assert registry.resolve("custom.action") is None

    print("[OK] Custom manager lifecycle verified")
