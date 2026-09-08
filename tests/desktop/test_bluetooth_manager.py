"""
Test suite for BluetoothManager
Location: tests/desktop/test_bluetooth_manager.py
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from src.desktop.native.desktop_result import DesktopResult
from src.desktop.native.managers.base_manager import HealthStatus
from src.desktop.native.managers.bluetooth_manager import BluetoothManager
from src.desktop.native.security.approval_authority import CryptographicApprovalAuthority


@pytest.fixture
def mock_auth():
    CryptographicApprovalAuthority.reset_instance()
    auth = CryptographicApprovalAuthority.get_instance()
    yield auth
    CryptographicApprovalAuthority.reset_instance()


@pytest.fixture
def manager(mock_auth):
    mgr = BluetoothManager(auth=mock_auth)
    mgr.initialize()
    yield mgr
    mgr.shutdown()


SAMPLE_PNP_DEVICES = [
    {
        "Status": "OK",
        "Name": "Intel(R) Wireless Bluetooth(R)",
        "InstanceId": "USB\\VID_8087&PID_0026\\5&299D89E&0&14",
        "Present": True,
        "Service": "BTHUSB",
        "Class": "Bluetooth",
    },
    {
        "Status": "OK",
        "Name": "Xbox Wireless Controller",
        "InstanceId": "BTHENUM\\DEV_832506306980\\7&1CF76D3A&0&BLUETOOTHDEVICE_832506306980",
        "Present": True,
        "Service": None,
        "Class": "Bluetooth",
    },
    {
        "Status": "OK",
        "Name": "JBL Flip Essential 2",
        "InstanceId": "BTHENUM\\DEV_90F2607B395D\\7&1CF76D3A&0&BLUETOOTHDEVICE_90F2607B395D",
        "Present": False,
        "Service": None,
        "Class": "Bluetooth",
    },
    {
        "Status": "OK",
        "Name": "Microsoft Bluetooth Enumerator",
        "InstanceId": "BTH\\MS_BTHBRB\\6&14345297&0&1",
        "Present": True,
        "Service": "BthEnum",
        "Class": "Bluetooth",
    },
    {
        "Status": "OK",
        "Name": "JBL Flip Essential 2 Avrcp Transport",
        "InstanceId": "BTHENUM\\{0000110C-0000-1000-8000-00805F9B34FB}_LOCALMFG&0002\\7&1CF76D3A&0&90F2607B395D_C00000000",
        "Present": False,
        "Service": "Microsoft_Bluetooth_AvrcpTransport",
        "Class": "Bluetooth",
    },
]


def test_bluetooth_metadata(manager):
    assert manager.name == "bluetooth"
    assert manager.VERSION == "1.0"
    assert manager.PRIORITY == 22
    assert manager.DEPENDENCIES == []
    assert set(manager.MUTATING_CAPABILITIES) == {"bluetooth.toggle"}
    assert "bluetooth.status" in manager.capabilities
    assert "bluetooth.toggle" in manager.capabilities
    assert "bluetooth.list_devices" in manager.capabilities
    assert "bluetooth.connect" in manager.capabilities
    assert "bluetooth.disconnect" in manager.capabilities


def test_bluetooth_health_check(manager):
    hc = manager.health_check()
    assert hc.status == HealthStatus.HEALTHY
    assert hc.total_capabilities == 5
    assert hc.available_capabilities == 5
    assert "initialized" in hc.details
    assert hc.details["initialized"] is True


def test_bluetooth_status(manager):
    with patch.object(manager, "_get_pnp_devices", return_value=SAMPLE_PNP_DEVICES):
        res = manager.execute("bluetooth.status")
        assert res.success is True
        assert res.data["radio_enabled"] is True
        assert res.data["radio_status"] == "OK"
        assert res.data["adapter_name"] == "Intel(R) Wireless Bluetooth(R)"
        assert res.data["paired_devices_count"] == 2
        assert res.data["connected_devices_count"] == 1


def test_bluetooth_list_devices_all_and_filtered(manager):
    with patch.object(manager, "_get_pnp_devices", return_value=SAMPLE_PNP_DEVICES):
        # All devices
        res_all = manager.execute("bluetooth.list_devices")
        assert res_all.success is True
        assert res_all.data["total_entries"] == 5
        assert res_all.data["paired_count"] == 2

        # Filtered paired only
        res_paired = manager.execute("bluetooth.list_devices", arguments={"only_paired": True})
        assert res_paired.success is True
        assert len(res_paired.data["devices"]) == 2
        names = [d["name"] for d in res_paired.data["devices"]]
        assert "Xbox Wireless Controller" in names
        assert "JBL Flip Essential 2" in names


def test_bluetooth_toggle_requires_hmac_ticket(manager):
    res = manager.execute("bluetooth.toggle", arguments={"enable": False})
    assert res.success is False
    assert res.data.get("requires_confirmation") is True
    assert "approval_ticket_id" in res.data
    assert res.data.get("action_type") == "bluetooth.toggle"


def test_bluetooth_toggle_with_invalid_signature(manager):
    res = manager.execute(
        "bluetooth.toggle",
        arguments={
            "enable": False,
            "approval_ticket_id": "tkt_invalid123",
            "approval_signature": "bad_sig",
        },
    )
    assert res.success is False
    assert res.data.get("security_alert") == "unauthorized_or_forged_approval"


def test_bluetooth_toggle_with_valid_signature(manager, mock_auth):
    with patch.object(manager, "_get_pnp_devices", return_value=SAMPLE_PNP_DEVICES), \
         patch.object(manager, "_run_powershell", return_value=(0, "", "")):
        # 1. First trigger to generate ticket
        res1 = manager.execute("bluetooth.toggle", arguments={"enable": True})
        ticket_id = res1.data["approval_ticket_id"]

        # 2. Sign ticket using authority
        sig = mock_auth.sign_ticket(ticket_id)
        assert sig is not None

        # 3. Redeem with valid signature
        res2 = manager.execute(
            "bluetooth.toggle",
            arguments={
                "enable": True,
                "approval_ticket_id": ticket_id,
                "approval_signature": sig,
            },
        )
        assert res2.success is True
        assert res2.data["enabled"] is True
        assert res2.data["adapter_name"] == "Intel(R) Wireless Bluetooth(R)"
        assert "bluetooth_enabled" in res2.events


def test_bluetooth_toggle_unsafe_instance_id(manager, mock_auth):
    target = "bluetooth_radio_enable=True"
    action_params = {"capability": "bluetooth.toggle", "enable": True, "target": target}
    ticket_id = mock_auth.create_ticket("bluetooth.toggle", target, action_params)
    sig = mock_auth.sign_ticket(ticket_id)

    res = manager.execute(
        "bluetooth.toggle",
        arguments={
            "enable": True,
            "instance_id": "USB\\VID_1234; malicious_cmd --hack",
            "approval_ticket_id": ticket_id,
            "approval_signature": sig,
        },
    )
    assert res.success is False
    assert "Invalid or unsafe Bluetooth instance ID format" in res.error


def test_bluetooth_connect_assists_settings(manager):
    with patch.object(manager, "_get_pnp_devices", return_value=SAMPLE_PNP_DEVICES), \
         patch.object(manager, "_open_bluetooth_settings", return_value=(True, "")):
        res = manager.execute("bluetooth.connect", arguments={"device_name": "Xbox Wireless Controller"})
        assert res.success is True
        assert res.data["settings_launched"] is True
        assert res.data["is_known_device"] is True
        assert res.data["matched_device"]["name"] == "Xbox Wireless Controller"
        assert "bluetooth_connect_requested" in res.events


def test_bluetooth_disconnect_assists_settings(manager):
    with patch.object(manager, "_get_pnp_devices", return_value=SAMPLE_PNP_DEVICES), \
         patch.object(manager, "_open_bluetooth_settings", return_value=(True, "")):
        res = manager.execute("bluetooth.disconnect", arguments={"device_name": "JBL Flip"})
        assert res.success is True
        assert res.data["settings_launched"] is True
        assert res.data["is_known_device"] is True
        assert res.data["matched_device"]["name"] == "JBL Flip Essential 2"
        assert "bluetooth_disconnect_requested" in res.events


def test_unsupported_capability(manager):
    res = manager.execute("bluetooth.unknown_feature")
    assert res.success is False
    assert "Unsupported capability" in res.error
