"""
Test PowerManager & PowerAdapter Hierarchy

Validates:
1. PowerAdapter hierarchy and fallback chain (WMIPowerAdapter -> Win32PowerAdapter -> DummyPowerAdapter).
2. Generic BaseAdapterFactory functionality.
3. PowerManager pure native structure (zero cross-cutting concerns).
4. Auto-discovery by NativeManagerRegistry.
5. Health check reporting.
6. Capability execution through DesktopExecutionEngine.
"""

import inspect
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, project_root)

import desktop.native.managers.power_manager as pm_module
from desktop.native.adapters.power_adapter import (
    DummyPowerAdapter,
    PowerAdapter,
    PowerAdapterFactory,
    Win32PowerAdapter,
    WMIPowerAdapter,
)
from desktop.native.desktop_execution_engine import DesktopExecutionEngine
from desktop.native.managers.base_manager import HealthStatus
from desktop.native.managers.native_manager_registry import NativeManagerRegistry
from desktop.native.managers.power_manager import PowerManager


def setup_function():
    """Reset registry singleton before test."""
    NativeManagerRegistry.reset_instance()


def teardown_function():
    """Reset registry singleton after test."""
    NativeManagerRegistry.reset_instance()


def test_power_adapter_hierarchy():
    """Test PowerAdapter hierarchy and fallback selection via BaseAdapterFactory."""
    dummy = DummyPowerAdapter()
    assert dummy.is_available() is True
    assert "percent" in dummy.get_battery_status()
    assert dummy.lock_workstation() is True

    win32_adapter = Win32PowerAdapter()
    assert isinstance(win32_adapter, PowerAdapter)

    wmi_adapter = WMIPowerAdapter()
    assert isinstance(wmi_adapter, PowerAdapter)

    # Factory selection via BaseAdapterFactory
    active_adapter = PowerAdapterFactory.get_adapter()
    assert isinstance(active_adapter, PowerAdapter)
    assert active_adapter.is_available() is True

    all_adapters = PowerAdapterFactory.get_all_adapters()
    assert len(all_adapters) == 3

    print(
        f"[OK] PowerAdapter hierarchy & BaseAdapterFactory verified (active: {active_adapter.name})"
    )


def test_power_manager_native_structure():
    """Test that PowerManager follows pure native manager structure."""
    manager = PowerManager(adapter=DummyPowerAdapter())
    assert manager.name == "power"
    assert manager.NAME == "power"
    assert manager.VERSION == "1.0"
    assert manager.PRIORITY == 20
    assert "wmi" in manager.DEPENDENCIES
    assert len(manager.capabilities) >= 10

    # Verify no cross-cutting concerns in code body
    source = inspect.getsource(pm_module)
    forbidden_symbols = [
        "PermissionMiddleware",
        "MetricsRecorder",
        "DiagnosticsStage",
        "get_desktop_context",
        "NativeEventBus",
    ]
    for symbol in forbidden_symbols:
        assert (
            symbol not in source
        ), f"PowerManager code body contains forbidden symbol: {symbol}"

    print("[OK] PowerManager native structure verified")


def test_power_manager_auto_discovery_and_health():
    """Test PowerManager auto-discovery and health checks."""
    registry = NativeManagerRegistry.get_instance()
    discovered = registry.discover("desktop.native.managers")

    assert "power" in discovered
    power_manager = registry.get("power")
    assert power_manager is not None
    assert power_manager.name == "power"

    health_res = power_manager.health_check()
    assert health_res.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]

    print(
        f"[OK] PowerManager auto-discovery and health check verified (status: {health_res.status.value})"
    )


def test_power_capabilities_execution():
    """Test executing power capabilities through DesktopExecutionEngine."""
    registry = NativeManagerRegistry.get_instance()
    registry.discover("desktop.native.managers")

    engine = DesktopExecutionEngine(manager_registry=registry)

    # Test Stage 1 Read-only capabilities
    res_batt = engine.execute(goal="get battery level", capability="power.battery")
    assert res_batt.success is True
    assert "percent" in res_batt.data

    res_ac = engine.execute(goal="get AC power status", capability="power.ac_status")
    assert res_ac.success is True
    assert "ac_online" in res_ac.data

    res_plan = engine.execute(
        goal="get active power plan", capability="power.power_plan"
    )
    assert res_plan.success is True
    assert "name" in res_plan.data

    # Test Stage 2 Safe actions
    res_lock = engine.execute(goal="lock screen", capability="power.lock")
    assert res_lock.success is True

    # Test Stage 3 Controlled actions (with dummy adapter to avoid real shutdown)
    power_mgr = registry.get("power")
    power_mgr._adapter = DummyPowerAdapter()

    res_shutdown = engine.execute(
        goal="shutdown computer", capability="power.shutdown", force=False
    )
    assert res_shutdown.success is True
    assert res_shutdown.data["status"] == "shutdown_initiated"

    res_restart = engine.execute(
        goal="restart computer", capability="power.restart", force=False
    )
    assert res_restart.success is True
    assert res_restart.data["status"] == "restart_initiated"

    print("[OK] PowerManager capability execution through engine verified")
