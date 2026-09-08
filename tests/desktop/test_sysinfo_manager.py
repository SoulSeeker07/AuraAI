"""
Unit & Integration Tests for SystemInfoManager
Location: tests/desktop/test_sysinfo_manager.py

Validates:
1. Manager metadata (NAME, VERSION, PRIORITY, DEPENDENCIES).
2. Lifecycle operations (initialize, health_check, shutdown).
3. Execution of all 8 primary capabilities (os, cpu, ram, disk, gpu, uptime, environment_vars, summary).
4. Graceful handling of edge cases, filters, and aliases.
5. Auto-discovery and capability resolution via NativeManagerRegistry.
"""

import os
import sys
from unittest.mock import MagicMock, patch

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
src_root = os.path.join(project_root, "src")
if src_root not in sys.path:
    sys.path.insert(0, src_root)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from desktop.native.desktop_result import DesktopResult
from desktop.native.managers.base_manager import HealthCheckResult, HealthStatus
from desktop.native.managers.native_manager_registry import NativeManagerRegistry
from desktop.native.managers.sysinfo_manager import SystemInfoManager


def setup_function():
    """Reset registry singleton before each test."""
    NativeManagerRegistry.reset_instance()


def teardown_function():
    """Reset registry singleton after each test."""
    NativeManagerRegistry.reset_instance()


def test_sysinfo_metadata():
    """Verify class-level metadata and interface adherence."""
    mgr = SystemInfoManager()
    assert mgr.name == "sysinfo"
    assert mgr.NAME == "sysinfo"
    assert mgr.VERSION == "1.0"
    assert mgr.PRIORITY == 25
    assert mgr.DEPENDENCIES == ["psutil"]

    expected_caps = [
        "sysinfo.os",
        "sysinfo.cpu",
        "sysinfo.ram",
        "sysinfo.disk",
        "sysinfo.gpu",
        "sysinfo.uptime",
        "sysinfo.environment_vars",
        "sysinfo.summary",
    ]
    assert mgr.capabilities == expected_caps
    assert len(mgr.capabilities) == 8


def test_sysinfo_lifecycle_and_health():
    """Verify initialize, health_check, and shutdown lifecycle."""
    mgr = SystemInfoManager()
    assert mgr.initialize() is True

    health = mgr.health_check()
    assert isinstance(health, HealthCheckResult)
    assert health.manager_name == "sysinfo"
    assert health.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)
    assert health.total_capabilities == 8
    assert health.details["initialized"] is True

    mgr.shutdown()
    assert mgr._initialized is False


def test_sysinfo_os():
    """Verify sysinfo.os capability return structure."""
    mgr = SystemInfoManager()
    res = mgr.execute("sysinfo.os", goal="Get OS telemetry")

    assert isinstance(res, DesktopResult)
    assert res.success is True
    assert "sysinfo_os_retrieved" in res.events
    data = res.data
    assert "system" in data
    assert "release" in data
    assert "version" in data
    assert "machine" in data
    assert "username" in data
    assert "platform" in data
    assert "hostname" in data


def test_sysinfo_cpu():
    """Verify sysinfo.cpu capability return structure."""
    mgr = SystemInfoManager()
    res = mgr.execute("sysinfo.cpu", goal="Get CPU telemetry", arguments={"interval": 0.1, "per_cpu": True})

    assert isinstance(res, DesktopResult)
    assert res.success is True
    assert "sysinfo_cpu_retrieved" in res.events
    data = res.data
    assert "physical_cores" in data
    assert "logical_cores" in data
    assert "processor" in data
    assert "frequency" in data
    assert "usage_percent" in data
    assert "per_cpu_percent" in data


def test_sysinfo_ram():
    """Verify sysinfo.ram capability return structure."""
    mgr = SystemInfoManager()
    res = mgr.execute("sysinfo.ram", goal="Get RAM telemetry")

    assert isinstance(res, DesktopResult)
    assert res.success is True
    assert "sysinfo_ram_retrieved" in res.events
    data = res.data
    assert "total" in data
    assert "available" in data
    assert "used" in data
    assert "percent" in data
    assert "swap" in data
    assert "total" in data["swap"]
    assert "percent" in data["swap"]


def test_sysinfo_disk():
    """Verify sysinfo.disk capability return structure."""
    mgr = SystemInfoManager()
    res = mgr.execute("sysinfo.disk", goal="Get disk storage usage")

    assert isinstance(res, DesktopResult)
    assert res.success is True
    assert "sysinfo_disk_retrieved" in res.events
    data = res.data
    assert "partitions" in data
    assert "partition_count" in data
    assert data["partition_count"] >= 1
    first_part = data["partitions"][0]
    assert "device" in first_part
    assert "mountpoint" in first_part


def test_sysinfo_gpu():
    """Verify sysinfo.gpu capability return structure."""
    mgr = SystemInfoManager()
    res = mgr.execute("sysinfo.gpu", goal="Get GPU telemetry")

    assert isinstance(res, DesktopResult)
    assert res.success is True
    assert "sysinfo_gpu_retrieved" in res.events
    data = res.data
    assert "gpus" in data
    assert "count" in data
    assert isinstance(data["gpus"], list)


def test_sysinfo_uptime():
    """Verify sysinfo.uptime capability return structure."""
    mgr = SystemInfoManager()
    res = mgr.execute("sysinfo.uptime", goal="Get system uptime")

    assert isinstance(res, DesktopResult)
    assert res.success is True
    assert "sysinfo_uptime_retrieved" in res.events
    data = res.data
    assert "boot_time" in data
    assert "boot_time_iso" in data
    assert "uptime_seconds" in data
    assert "uptime_formatted" in data
    assert data["uptime_seconds"] >= 0


def test_sysinfo_environment_vars():
    """Verify sysinfo.environment_vars capability return structure and filtering."""
    mgr = SystemInfoManager()

    # Unfiltered
    res_all = mgr.execute("sysinfo.environment_vars", goal="Get all environment variables")
    assert res_all.success is True
    assert "sysinfo_environment_vars_retrieved" in res_all.events
    assert "environment_variables" in res_all.data
    assert res_all.data["count"] > 0

    # Filtered
    res_filtered = mgr.execute(
        "sysinfo.environment_vars",
        goal="Get PATH variable",
        arguments={"filter": "PATH"},
    )
    assert res_filtered.success is True
    assert "PATH" in str(list(res_filtered.data["environment_variables"].keys()))


def test_sysinfo_summary():
    """Verify sysinfo.summary combines OS, CPU, RAM, disk, and uptime."""
    mgr = SystemInfoManager()
    res = mgr.execute("sysinfo.summary", goal="Get comprehensive summary", arguments={"include_gpu": True})

    assert isinstance(res, DesktopResult)
    assert res.success is True
    assert "sysinfo_summary_retrieved" in res.events
    data = res.data
    assert "os" in data
    assert "cpu" in data
    assert "ram" in data
    assert "disk" in data
    assert "uptime" in data
    assert "gpu" in data


def test_sysinfo_aliases():
    """Verify short aliases dispatch properly."""
    mgr = SystemInfoManager()
    for alias in ("os", "cpu", "ram", "disk", "gpu", "uptime", "env", "summary"):
        res = mgr.execute(alias, goal=f"Test alias {alias}")
        assert res.success is True, f"Alias '{alias}' should execute successfully"


def test_unsupported_capability():
    """Verify unsupported capability returns failure."""
    mgr = SystemInfoManager()
    res = mgr.execute("sysinfo.nonexistent_feature", goal="Invalid cap")
    assert res.success is False
    assert "Unsupported capability" in res.error


def test_registry_auto_discovery_and_resolution():
    """Verify NativeManagerRegistry discovers and resolves SystemInfoManager."""
    registry = NativeManagerRegistry.get_instance()
    discovered = registry.discover("desktop.native.managers")

    assert "sysinfo" in discovered
    resolved_summary = registry.resolve("sysinfo.summary")
    assert resolved_summary is not None
    assert resolved_summary.name == "sysinfo"

    resolved_gpu = registry.resolve("sysinfo.gpu")
    assert resolved_gpu is not None
    assert resolved_gpu.name == "sysinfo"
