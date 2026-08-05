"""
NetworkManager & Network Intelligence Test Suite

Tests:
1. NetworkAdapter hierarchy & factory selection.
2. Pure native NetworkManager structure and capabilities.
3. NativeManagerRegistry auto-discovery & health aggregation.
4. Execution of Information, Diagnostic, and Control capabilities.
5. Integration with DesktopExecutionEngine in simulation mode.
"""

import pytest

from src.desktop.native.adapters.network_adapter import (
    DummyNetworkAdapter,
    NetshNetworkAdapter,
    NetworkAdapter,
    NetworkAdapterFactory,
    PsutilNetworkAdapter,
    WMINetworkAdapter,
)
from src.desktop.native.capability_registry import (
    CapabilityRegistry,
    PermissionRequired,
    RiskLevel,
)
from src.desktop.native.desktop_execution_engine import (
    DesktopExecutionEngine,
    ExecutionConfig,
    reset_desktop_execution_engine,
)
from src.desktop.native.managers.native_manager_registry import (
    HealthStatus,
    NativeManagerRegistry,
)
from src.desktop.native.managers.network_manager import NetworkManager


@pytest.fixture
def dummy_network_manager():
    """Fixture providing NetworkManager backed by DummyNetworkAdapter."""
    return NetworkManager(adapter=DummyNetworkAdapter())


@pytest.fixture
def registry():
    """Fixture providing singleton NativeManagerRegistry reset."""
    NativeManagerRegistry.reset_instance()
    reg = NativeManagerRegistry.get_instance()
    yield reg
    NativeManagerRegistry.reset_instance()


@pytest.fixture
def engine(registry):
    """Fixture providing DesktopExecutionEngine with NetworkManager registered."""
    reset_desktop_execution_engine()
    nm = NetworkManager(adapter=DummyNetworkAdapter())
    registry.register(nm)
    eng = DesktopExecutionEngine(
        manager_registry=registry,
        config=ExecutionConfig(simulation_mode=True),
    )
    yield eng
    reset_desktop_execution_engine()


# ==================== 1. Adapter Hierarchy Tests ====================


def test_dummy_network_adapter_methods():
    adapter = DummyNetworkAdapter()
    assert adapter.is_available() is True
    assert adapter.name == "dummy"

    ifs = adapter.get_interfaces()
    assert len(ifs) >= 1
    assert ifs[0]["name"] == "Wi-Fi"

    def_if = adapter.get_default_interface()
    assert def_if["ip_address"] == "192.168.1.100"

    pub_ip = adapter.get_public_ip()
    assert "public_ip" in pub_ip

    ping_res = adapter.ping("8.8.8.8")
    assert ping_res["success"] is True
    assert ping_res["packet_loss"] == 0.0

    assert adapter.enable_adapter("Wi-Fi") is True
    assert adapter.disable_adapter("Wi-Fi") is True
    assert adapter.flush_dns() is True


def test_network_adapter_factory():
    factory_adapter = NetworkAdapterFactory.get_adapter()
    assert isinstance(factory_adapter, NetworkAdapter)
    assert factory_adapter.is_available() is True

    all_adapters = NetworkAdapterFactory.get_all_adapters()
    assert len(all_adapters) >= 4
    names = [a.name for a in all_adapters]
    assert "wmi" in names or "netsh" in names or "psutil" in names or "dummy" in names


# ==================== 2. NetworkManager Pure Native Tests ====================


def test_network_manager_metadata(dummy_network_manager):
    assert dummy_network_manager.name == "network"
    assert dummy_network_manager.PRIORITY == 20
    assert "network.interfaces" in dummy_network_manager.capabilities
    assert "network.ping" in dummy_network_manager.capabilities
    assert "network.disable_adapter" in dummy_network_manager.capabilities
    assert len(dummy_network_manager.capabilities) >= 25


def test_network_manager_health_check(dummy_network_manager):
    health = dummy_network_manager.health_check()
    assert health.manager_name == "network"
    assert health.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)
    assert "active_adapter" in health.details
    assert health.details["active_adapter"] == "dummy"
    assert health.details["internet"] == "Connected"


def test_network_manager_no_cross_cutting_concerns():
    nm = NetworkManager(adapter=DummyNetworkAdapter())
    import inspect

    src = inspect.getsource(NetworkManager)
    # Pure native manager rule: no direct metrics or permissions inside manager
    assert "metrics_recorder" not in src
    assert "permission_checker" not in src


# ==================== 3. Registry & Discovery Tests ====================


def test_network_manager_auto_discovery(registry):
    discovered = registry.discover("src.desktop.native.managers")
    assert "network" in discovered

    nm = registry.get("network")
    assert nm is not None
    assert nm.name == "network"

    resolved = registry.resolve("network.ping")
    assert resolved.name == "network"


def test_capability_registry_network_descriptors():
    cap_reg = CapabilityRegistry()
    desc_ping = cap_reg.get("network.ping")
    assert desc_ping is not None
    assert desc_ping.manager == "network"
    assert desc_ping.risk_level == RiskLevel.LOW

    desc_disable = cap_reg.get("network.disable_adapter")
    assert desc_disable is not None
    assert desc_disable.risk_level == RiskLevel.CRITICAL
    assert desc_disable.is_destructive is True
    assert desc_disable.requires_confirmation is True
    assert desc_disable.permission == PermissionRequired.CONTROL


# ==================== 4. Capability Execution Tests ====================


def test_network_information_capabilities(dummy_network_manager):
    res_ifs = dummy_network_manager.execute("network.interfaces")
    assert res_ifs.success is True
    assert "interfaces" in res_ifs.data

    res_pub = dummy_network_manager.execute("network.public_ip")
    assert res_pub.success is True
    assert "public_ip" in res_pub.data

    res_loc = dummy_network_manager.execute("network.local_ip")
    assert res_loc.success is True
    assert "local_ip" in res_loc.data

    res_gw = dummy_network_manager.execute("network.gateway")
    assert res_gw.success is True
    assert "gateway" in res_gw.data

    res_dns = dummy_network_manager.execute("network.dns")
    assert res_dns.success is True
    assert "dns_servers" in res_dns.data

    res_wifi = dummy_network_manager.execute("network.wifi_name")
    assert res_wifi.success is True
    assert "wifi_name" in res_wifi.data


def test_network_diagnostic_capabilities(dummy_network_manager):
    res_ping = dummy_network_manager.execute(
        "network.ping", arguments={"host": "8.8.8.8"}
    )
    assert res_ping.success is True
    assert res_ping.data["host"] == "8.8.8.8"
    assert res_ping.data["success"] is True

    res_tr = dummy_network_manager.execute(
        "network.traceroute", arguments={"host": "8.8.8.8"}
    )
    assert res_tr.success is True
    assert "total_hops" in res_tr.data

    res_lk = dummy_network_manager.execute(
        "network.lookup", arguments={"domain": "google.com"}
    )
    assert res_lk.success is True
    assert "addresses" in res_lk.data

    res_inet = dummy_network_manager.execute("network.internet")
    assert res_inet.success is True
    assert res_inet.data["connected"] is True

    res_spd = dummy_network_manager.execute("network.speed")
    assert res_spd.success is True
    assert "download_mbps" in res_spd.data


def test_network_control_capabilities(dummy_network_manager):
    res_flush = dummy_network_manager.execute("network.flush_dns")
    assert res_flush.success is True
    assert res_flush.data["status"] == "dns_flushed"
    assert "dns_flushed" in res_flush.events

    res_dis = dummy_network_manager.execute("network.disconnect_wifi")
    assert res_dis.success is True
    assert res_dis.data["status"] == "wifi_disconnected"

    res_con = dummy_network_manager.execute(
        "network.connect_wifi", arguments={"ssid": "Home-5G"}
    )
    assert res_con.success is True
    assert res_con.data["ssid"] == "Home-5G"


# ==================== 5. DesktopExecutionEngine Pipeline Integration ====================


def test_network_engine_execution(engine):
    res_goal = engine.execute(goal="check local ip address")
    assert res_goal.success is True
    assert res_goal.capability == "network.local_ip"
    assert res_goal.manager == "network"

    res_ping_goal = engine.execute(goal="ping google host", host="8.8.8.8")
    assert res_ping_goal.success is True
    assert res_ping_goal.capability == "network.ping"


def test_engine_simulation_mode_for_destructive_actions(engine):
    # Destructive network action in simulation mode
    res_dis = engine.execute(
        goal="disable wifi adapter",
        capability="network.disable_adapter",
        adapter_name="Wi-Fi",
    )
    assert res_dis.success is True
    assert res_dis.data.get("simulated") is True
    assert res_dis.data.get("status") == "simulated_execution"
