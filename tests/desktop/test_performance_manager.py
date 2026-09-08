"""
Unit & Integration Tests for PerformanceManager
Location: tests/desktop/test_performance_manager.py

Validates:
1. Class metadata (NAME, VERSION, PRIORITY, DEPENDENCIES, capabilities).
2. Lifecycle operations (initialize, health_check, shutdown).
3. Auto-discovery and resolution by NativeManagerRegistry.
4. All 6 performance capabilities (perf.cpu_usage, perf.memory_usage, perf.disk_io,
   perf.network_io, perf.snapshot, perf.top_processes).
5. Error handling and edge cases (unsupported capability, fallback behavior).
"""

import os
import sys
from unittest.mock import MagicMock, patch

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from desktop.native.desktop_result import DesktopResult, DesktopStatus
from desktop.native.managers.base_manager import HealthCheckResult, HealthStatus
from desktop.native.managers.native_manager_registry import NativeManagerRegistry
from desktop.native.managers.performance_manager import PerformanceManager


def setup_function():
    """Reset registry singleton before each test."""
    NativeManagerRegistry.reset_instance()


def teardown_function():
    """Reset registry singleton after each test."""
    NativeManagerRegistry.reset_instance()


def test_performance_manager_metadata():
    """Validate PerformanceManager class metadata and property contracts."""
    mgr = PerformanceManager()
    assert mgr.name == "performance"
    assert mgr.NAME == "performance"
    assert mgr.VERSION == "1.0"
    assert mgr.PRIORITY == 22
    assert mgr.DEPENDENCIES == ["psutil"]

    expected_caps = [
        "perf.cpu_usage",
        "perf.memory_usage",
        "perf.disk_io",
        "perf.network_io",
        "perf.snapshot",
        "perf.top_processes",
    ]
    assert len(mgr.capabilities) == 6
    for cap in expected_caps:
        assert cap in mgr.capabilities


def test_performance_manager_lifecycle():
    """Validate initialize, health check, and shutdown lifecycle."""
    mgr = PerformanceManager()
    assert mgr._initialized is False

    init_ok = mgr.initialize()
    assert init_ok is True
    assert mgr._initialized is True

    health = mgr.health_check()
    assert isinstance(health, HealthCheckResult)
    assert health.manager_name == "performance"
    assert health.status in (HealthStatus.HEALTHY, HealthStatus.UNAVAILABLE)
    assert health.total_capabilities == 6
    assert health.details.get("initialized") is True

    mgr.shutdown()
    assert mgr._initialized is False


def test_auto_discovery_and_resolution():
    """Validate that NativeManagerRegistry discovers and resolves PerformanceManager."""
    registry = NativeManagerRegistry.get_instance()
    discovered = registry.discover("desktop.native.managers")

    assert "performance" in discovered
    resolved = registry.resolve("perf.cpu_usage")
    assert resolved is not None
    assert resolved.name == "performance"

    resolved_snap = registry.resolve("perf.snapshot")
    assert resolved_snap is not None
    assert resolved_snap.name == "performance"


def test_perf_cpu_usage():
    """Validate perf.cpu_usage capability execution and data format."""
    mgr = PerformanceManager()
    result = mgr.execute("perf.cpu_usage", arguments={"interval": 0.1})

    assert isinstance(result, DesktopResult)
    assert result.success is True
    assert result.status == DesktopStatus.SUCCESS
    assert "overall" in result.data
    assert "overall_percent" in result.data
    assert "per_core" in result.data
    assert "per_core_percent" in result.data
    assert "core_count" in result.data
    assert isinstance(result.data["per_core"], list)
    assert len(result.data["per_core"]) > 0
    assert result.data["core_count"] == len(result.data["per_core"])


def test_perf_memory_usage():
    """Validate perf.memory_usage capability execution and data format."""
    mgr = PerformanceManager()
    result = mgr.execute("perf.memory_usage")

    assert isinstance(result, DesktopResult)
    assert result.success is True
    assert result.status == DesktopStatus.SUCCESS

    required_keys = [
        "total",
        "available",
        "used",
        "percent",
        "swap_total",
        "swap_used",
        "swap_percent",
    ]
    for key in required_keys:
        assert key in result.data, f"Missing key in memory_usage: {key}"
        assert isinstance(result.data[key], (int, float))
        assert result.data[key] >= 0


def test_perf_disk_io():
    """Validate perf.disk_io capability execution and data format."""
    mgr = PerformanceManager()
    result = mgr.execute("perf.disk_io")

    assert isinstance(result, DesktopResult)
    assert result.success is True
    assert result.status == DesktopStatus.SUCCESS

    # Should allow accessing via disks grouping key or direct disk names
    assert "disks" in result.data
    disks = result.data["disks"]
    assert isinstance(disks, dict)

    if disks:
        first_disk = next(iter(disks.values()))
        assert "read_bytes" in first_disk
        assert "write_bytes" in first_disk
        assert "read_count" in first_disk
        assert "write_count" in first_disk


def test_perf_network_io():
    """Validate perf.network_io capability execution and data format."""
    mgr = PerformanceManager()
    result = mgr.execute("perf.network_io")

    assert isinstance(result, DesktopResult)
    assert result.success is True
    assert result.status == DesktopStatus.SUCCESS

    # Should allow accessing via interfaces grouping key
    assert "interfaces" in result.data
    interfaces = result.data["interfaces"]
    assert isinstance(interfaces, dict)

    if interfaces:
        first_nic = next(iter(interfaces.values()))
        assert "bytes_sent" in first_nic
        assert "bytes_recv" in first_nic
        assert "packets_sent" in first_nic
        assert "packets_recv" in first_nic


def test_perf_snapshot():
    """Validate perf.snapshot capability combines all subsystems and top 5 processes."""
    mgr = PerformanceManager()
    result = mgr.execute("perf.snapshot")

    assert isinstance(result, DesktopResult)
    assert result.success is True
    assert result.status == DesktopStatus.SUCCESS

    # Snapshot required components
    assert "cpu" in result.data
    assert "memory" in result.data
    assert "disk_io" in result.data
    assert "network_io" in result.data
    assert "top_processes" in result.data
    assert "timestamp" in result.data

    # CPU metrics check
    assert "overall" in result.data["cpu"]
    assert "per_core" in result.data["cpu"]

    # Memory metrics check
    assert "total" in result.data["memory"]
    assert "available" in result.data["memory"]
    assert "percent" in result.data["memory"]

    # Top processes check (at most 5)
    top_procs = result.data["top_processes"]
    assert isinstance(top_procs, list)
    assert len(top_procs) <= 5
    for proc in top_procs:
        assert "pid" in proc
        assert "name" in proc
        assert "cpu_percent" in proc
        assert "memory_percent" in proc


def test_perf_top_processes_cpu():
    """Validate perf.top_processes capability sorted by CPU."""
    mgr = PerformanceManager()
    result = mgr.execute("perf.top_processes", arguments={"sort_by": "cpu", "count": 5, "interval": 0.1})

    assert isinstance(result, DesktopResult)
    assert result.success is True
    assert "processes" in result.data
    assert result.data["sort_by"] == "cpu"

    procs = result.data["processes"]
    assert len(procs) <= 5
    for p in procs:
        assert "pid" in p
        assert "name" in p
        assert "cpu_percent" in p
        assert "memory_percent" in p


def test_perf_top_processes_memory():
    """Validate perf.top_processes capability sorted by memory."""
    mgr = PerformanceManager()
    result = mgr.execute("perf.top_processes", arguments={"sort_by": "memory", "count": 5})

    assert isinstance(result, DesktopResult)
    assert result.success is True
    assert "processes" in result.data
    assert result.data["sort_by"] == "memory"

    procs = result.data["processes"]
    assert len(procs) <= 5
    # Verify memory sorted in descending order
    for i in range(len(procs) - 1):
        assert procs[i]["memory_percent"] >= procs[i + 1]["memory_percent"]


def test_unsupported_capability():
    """Validate failure on unknown capability."""
    mgr = PerformanceManager()
    result = mgr.execute("perf.invalid_operation")

    assert isinstance(result, DesktopResult)
    assert result.success is False
    assert result.status == DesktopStatus.FAILURE
    assert "Unsupported capability" in (result.error or "")


def test_top_processes_with_mocks():
    """Validate process extraction with mock Process objects."""
    mgr = PerformanceManager()

    mock_p1 = MagicMock()
    mock_p1.info = {"pid": 101, "name": "app1.exe", "cpu_percent": 80.0, "memory_percent": 15.0}
    mock_p2 = MagicMock()
    mock_p2.info = {"pid": 102, "name": "app2.exe", "cpu_percent": 40.0, "memory_percent": 30.0}

    with patch("psutil.process_iter", return_value=[mock_p1, mock_p2]):
        res_cpu = mgr.execute("perf.top_processes", arguments={"sort_by": "cpu", "count": 2, "interval": 0})
        assert res_cpu.success is True
        assert res_cpu.data["processes"][0]["pid"] == 101
        assert res_cpu.data["processes"][0]["cpu_percent"] == 80.0

        res_mem = mgr.execute("perf.top_processes", arguments={"sort_by": "memory", "count": 2, "interval": 0})
        assert res_mem.success is True
        assert res_mem.data["processes"][0]["pid"] == 102
        assert res_mem.data["processes"][0]["memory_percent"] == 30.0
