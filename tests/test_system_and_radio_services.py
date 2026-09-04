"""
Unit and integration tests for Bluetooth, Wi-Fi, Network, and System Diagnostics Services.
"""

from unittest.mock import patch, MagicMock
from tools.bluetooth_service import BluetoothDiagnosticsService
from tools.network_service import NetworkDiagnosticsService
from tools.system_diagnostics_service import SystemDiagnosticsService
from tools.battery_service import BatteryDiagnosticsService
from brain.intent_router import IntentRouter
from brain.models import Intent
from Memory import Memory


def test_bluetooth_diagnostics_formatting():
    with patch.object(BluetoothDiagnosticsService, "get_radio_state", return_value="On"), \
         patch.object(BluetoothDiagnosticsService, "get_paired_devices", return_value=[
             {"name": "JBL Flip 6", "status": "OK", "present": True, "connected": True},
             {"name": "Xbox Controller", "status": "OK", "present": True, "connected": False},
         ]):
        report = BluetoothDiagnosticsService.get_full_bluetooth_report()
        assert report["radio_state"] == "On"
        assert report["connected_count"] == 1
        assert "JBL Flip 6" in report["markdown"]
        assert "Xbox Controller" in report["markdown"]
        assert "**Connected Devices:** 1" in report["markdown"]


def test_network_diagnostics_formatting():
    with patch.object(NetworkDiagnosticsService, "get_wifi_radio_state", return_value="On"), \
         patch.object(NetworkDiagnosticsService, "get_wifi_interface_info", return_value={
             "connected": True, "ssid": "HomeNetwork", "signal": "90%", "state": "connected", "radio_type": "802.11ax"
         }), \
         patch.object(NetworkDiagnosticsService, "get_active_ip_adapters", return_value=[
             {"alias": "Wi-Fi", "ipv4": "192.168.1.50", "gateway": "192.168.1.1", "dns": "1.1.1.1"}
         ]):
        report = NetworkDiagnosticsService.get_full_network_report(wifi_only=True)
        assert "HomeNetwork" in report["markdown"]
        assert "90%" in report["markdown"]

        full_report = NetworkDiagnosticsService.get_full_network_report(wifi_only=False)
        assert "192.168.1.50" in full_report["markdown"]


def test_system_diagnostics_formatting():
    report = SystemDiagnosticsService.get_full_system_report()
    assert "cpu" in report
    assert "ram" in report
    assert "disks" in report
    assert "markdown" in report
    assert "CPU Model" in report["markdown"]
    assert "RAM Memory" in report["markdown"]


def test_battery_diagnostics_desktop_fallback():
    with patch("psutil.sensors_battery", return_value=None), \
         patch("subprocess.run") as mock_sub:
        mock_proc = MagicMock()
        mock_proc.stdout = ""
        mock_sub.return_value = mock_proc

        report = BatteryDiagnosticsService.get_full_battery_report()
        assert report["has_battery"] is False
        assert "Direct AC Power" in report["markdown"]


def test_intent_router_detects_hardware_intents():
    mem = Memory(db_path=":memory:")
    router = IntentRouter(mem)

    # Bluetooth
    intent = router.detect("bluetooth status")
    assert intent.name == "bluetooth_status"

    intent = router.detect("turn on bluetooth")
    assert intent.name == "bluetooth_control"
    assert intent.data["enable"] is True

    intent = router.detect("turn off bluetooth")
    assert intent.name == "bluetooth_control"
    assert intent.data["enable"] is False

    # Wi-Fi
    intent = router.detect("wifi status")
    assert intent.name == "wifi_status"

    intent = router.detect("turn on wifi")
    assert intent.name == "wifi_control"
    assert intent.data["enable"] is True

    # Network / IP
    intent = router.detect("my ip address")
    assert intent.name == "network_status"

    intent = router.detect("network status")
    assert intent.name == "network_status"

    # System Status / Hardware Telemetry
    intent = router.detect("system status")
    assert intent.name == "system_status"

    intent = router.detect("cpu usage")
    assert intent.name == "system_status"

    intent = router.detect("hardware specs")
    assert intent.name == "system_status"
