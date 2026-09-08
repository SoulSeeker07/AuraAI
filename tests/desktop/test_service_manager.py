"""
Unit & Integration Tests for ServiceManager
Location: tests/desktop/test_service_manager.py

Validates:
1. Manager metadata (NAME, VERSION, PRIORITY, DEPENDENCIES, MUTATING_CAPABILITIES).
2. Lifecycle operations (initialize, health_check, shutdown).
3. Capability 1: service.list (psutil.win_service_iter, AccessDenied/NoSuchProcess per-service handling, filtering).
4. Capability 2: service.status (psutil.win_service_get, valid, missing, AccessDenied, NoSuchProcess).
5. Capability 3: service.start (HMAC gate, ticket issuance, forged signature block, sc.exe start).
6. Capability 4: service.stop (HMAC gate, ticket issuance, forged signature block, sc.exe stop).
7. Capability 5: service.restart (HMAC gate, stop -> pause -> start sequence).
8. Validation of service name against injection/invalid characters.
9. Dynamic discovery via NativeManagerRegistry.
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

import psutil
from desktop.native.desktop_result import DesktopResult
from desktop.native.managers.base_manager import HealthCheckResult, HealthStatus
from desktop.native.managers.native_manager_registry import NativeManagerRegistry
from desktop.native.managers.service_manager import ServiceManager
from desktop.native.security.approval_authority import CryptographicApprovalAuthority


def setup_function():
    """Reset registry singleton before each test."""
    NativeManagerRegistry.reset_instance()


def teardown_function():
    """Reset registry singleton after each test."""
    NativeManagerRegistry.reset_instance()


def test_service_metadata():
    """Verify class-level metadata and interface adherence."""
    mgr = ServiceManager()
    assert mgr.name == "service"
    assert mgr.NAME == "service"
    assert mgr.VERSION == "1.0"
    assert mgr.PRIORITY == 35
    assert mgr.DEPENDENCIES == ["psutil"]
    assert mgr.MUTATING_CAPABILITIES == {
        "service.start",
        "service.stop",
        "service.restart",
    }

    expected_caps = [
        "service.list",
        "service.status",
        "service.start",
        "service.stop",
        "service.restart",
    ]
    assert mgr.capabilities == expected_caps
    assert len(mgr.capabilities) == 5


def test_service_lifecycle():
    """Verify initialize, health_check, and shutdown lifecycle."""
    mgr = ServiceManager()
    assert mgr.initialize() is True

    hc = mgr.health_check()
    assert isinstance(hc, HealthCheckResult)
    assert hc.manager_name == "service"
    assert hc.status == HealthStatus.HEALTHY
    assert hc.total_capabilities == 5
    assert hc.available_capabilities == 5
    assert hc.details["initialized"] is True
    assert hc.details["psutil_available"] is True

    mgr.shutdown()
    assert mgr._initialized is False


def test_service_list_success():
    """Verify service.list enumerates services and extracts all required fields."""
    mgr = ServiceManager()
    res = mgr.execute("service.list")

    assert res.success is True
    assert "services" in res.data
    assert "count" in res.data
    assert res.data["count"] >= 0

    if res.data["count"] > 0:
        svc = res.data["services"][0]
        assert "name" in svc
        assert "display_name" in svc
        assert "status" in svc
        assert "start_type" in svc
        assert "pid" in svc


def test_service_list_handles_exceptions_gracefully():
    """Verify service.list gracefully catches AccessDenied and NoSuchProcess per-service."""
    mock_svc_good = MagicMock()
    mock_svc_good.name.return_value = "GoodService"
    mock_svc_good.display_name.return_value = "Good Service Display"
    mock_svc_good.status.return_value = "running"
    mock_svc_good.start_type.return_value = "automatic"
    mock_svc_good.pid.return_value = 1234

    mock_svc_access_denied = MagicMock()
    mock_svc_access_denied.name.return_value = "RestrictedService"
    mock_svc_access_denied.display_name.return_value = "Restricted Service Display"
    mock_svc_access_denied.status.side_effect = psutil.AccessDenied()
    mock_svc_access_denied.start_type.side_effect = psutil.AccessDenied()
    mock_svc_access_denied.pid.side_effect = psutil.AccessDenied()

    mock_svc_ghost = MagicMock()
    mock_svc_ghost.name.side_effect = psutil.NoSuchProcess(pid=None, name="GhostService")

    mgr = ServiceManager()
    with patch("psutil.win_service_iter", return_value=[mock_svc_good, mock_svc_access_denied, mock_svc_ghost]):
        res = mgr.execute("service.list")

    assert res.success is True
    assert res.data["count"] == 2
    assert res.data["services"][0]["name"] == "GoodService"
    assert res.data["services"][0]["status"] == "running"
    assert res.data["services"][0]["pid"] == 1234

    # Restricted service handled gracefully with access_denied values
    assert res.data["services"][1]["name"] == "RestrictedService"
    assert res.data["services"][1]["status"] == "access_denied"
    assert res.data["services"][1]["start_type"] == "access_denied"
    assert res.data["services"][1]["pid"] is None


def test_service_status_success():
    """Verify service.status returns dict representation of service."""
    mock_svc = MagicMock()
    mock_svc.as_dict.return_value = {
        "name": "TestService",
        "display_name": "Test Service Display",
        "status": "running",
        "start_type": "automatic",
        "pid": 5678,
    }

    mgr = ServiceManager()
    with patch("psutil.win_service_get", return_value=mock_svc) as mock_get:
        res = mgr.execute("service.status", arguments={"name": "TestService"})

    mock_get.assert_called_once_with("TestService")
    assert res.success is True
    assert res.data["name"] == "TestService"
    assert res.data["status"] == "running"
    assert "service_status_queried" in res.events


def test_service_status_not_found():
    """Verify service.status fails gracefully when service does not exist."""
    mgr = ServiceManager()
    with patch("psutil.win_service_get", side_effect=psutil.NoSuchProcess(pid=None, name="NonexistentService")):
        res = mgr.execute("service.status", arguments={"name": "NonexistentService"})

    assert res.success is False
    assert "does not exist" in res.error
    assert res.data["exists"] is False


def test_service_status_access_denied():
    """Verify service.status fails gracefully when access is denied."""
    mgr = ServiceManager()
    with patch("psutil.win_service_get", side_effect=psutil.AccessDenied()):
        res = mgr.execute("service.status", arguments={"name": "ProtectedService"})

    assert res.success is False
    assert "Access denied" in res.error
    assert res.data["access_denied"] is True


def test_service_name_validation():
    """Verify service name validation blocks injection characters and empty strings."""
    mgr = ServiceManager()

    # Empty
    res_empty = mgr.execute("service.status", arguments={"name": "   "})
    assert res_empty.success is False
    assert "empty" in res_empty.error

    # Slash / Path traversal
    res_slash = mgr.execute("service.status", arguments={"name": "test/path"})
    assert res_slash.success is False
    assert "path separators" in res_slash.error

    # Metacharacters
    res_meta = mgr.execute("service.status", arguments={"name": "test; rm -rf"})
    assert res_meta.success is False
    assert "invalid or forbidden" in res_meta.error


def test_service_start_hmac_flow():
    """Verify service.start full HMAC approval gate lifecycle and command execution."""
    mgr = ServiceManager()

    # 1. Unapproved call -> issues ticket, returns requires_confirmation
    res_unapproved = mgr.execute("service.start", arguments={"name": "MockSvc"})
    assert res_unapproved.success is False
    assert res_unapproved.data["requires_confirmation"] is True
    ticket_id = res_unapproved.data["approval_ticket_id"]
    assert ticket_id.startswith("tkt_")

    # 2. Forged signature -> rejected
    res_forged = mgr.execute(
        "service.start",
        arguments={
            "name": "MockSvc",
            "approval_ticket_id": ticket_id,
            "approval_signature": "invalid_sig_abc123",
        },
    )
    assert res_forged.success is False
    assert "Cryptographic signature verification failed" in res_forged.error
    assert res_forged.data.get("security_alert") == "unauthorized_or_forged_approval"

    # 3. Legitimate human signature -> approved and executed
    valid_sig = mgr.auth.generate_human_signature(ticket_id)
    assert valid_sig is not None

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "[SC] StartService SUCCESS"
    mock_proc.stderr = ""

    with patch("subprocess.run", return_value=mock_proc) as mock_sub:
        res_approved = mgr.execute(
            "service.start",
            arguments={
                "name": "MockSvc",
                "approval_ticket_id": ticket_id,
                "approval_signature": valid_sig,
            },
        )

    mock_sub.assert_called_once_with(["sc.exe", "start", "MockSvc"], capture_output=True, text=True, timeout=30.0)
    assert res_approved.success is True
    assert res_approved.data["service_name"] == "MockSvc"
    assert "service_started" in res_approved.events


def test_service_stop_hmac_flow():
    """Verify service.stop HMAC approval gate and sc.exe stop execution."""
    mgr = ServiceManager()

    res_unapproved = mgr.execute("service.stop", arguments={"name": "MockSvc"})
    assert res_unapproved.success is False
    ticket_id = res_unapproved.data["approval_ticket_id"]

    valid_sig = mgr.auth.generate_human_signature(ticket_id)
    assert valid_sig is not None

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "[SC] ControlService SUCCESS"
    mock_proc.stderr = ""

    with patch("subprocess.run", return_value=mock_proc) as mock_sub:
        res_approved = mgr.execute(
            "service.stop",
            arguments={
                "name": "MockSvc",
                "approval_ticket_id": ticket_id,
                "approval_signature": valid_sig,
            },
        )

    mock_sub.assert_called_once_with(["sc.exe", "stop", "MockSvc"], capture_output=True, text=True, timeout=30.0)
    assert res_approved.success is True
    assert res_approved.data["service_name"] == "MockSvc"
    assert "service_stopped" in res_approved.events


def test_service_restart_flow():
    """Verify service.restart executes stop, pauses, and executes start."""
    mgr = ServiceManager()

    res_unapproved = mgr.execute("service.restart", arguments={"name": "MockSvc"})
    assert res_unapproved.success is False
    ticket_id = res_unapproved.data["approval_ticket_id"]

    valid_sig = mgr.auth.generate_human_signature(ticket_id)
    assert valid_sig is not None

    mock_stop_proc = MagicMock()
    mock_stop_proc.returncode = 0
    mock_stop_proc.stdout = "[SC] ControlService STOP SUCCESS"
    mock_stop_proc.stderr = ""

    mock_start_proc = MagicMock()
    mock_start_proc.returncode = 0
    mock_start_proc.stdout = "[SC] StartService START SUCCESS"
    mock_start_proc.stderr = ""

    with patch("subprocess.run", side_effect=[mock_stop_proc, mock_start_proc]) as mock_sub, patch("time.sleep") as mock_sleep:
        res_approved = mgr.execute(
            "service.restart",
            arguments={
                "name": "MockSvc",
                "approval_ticket_id": ticket_id,
                "approval_signature": valid_sig,
            },
        )

    assert mock_sub.call_count == 2
    mock_sleep.assert_called_once_with(1.5)
    assert res_approved.success is True
    assert res_approved.data["service_name"] == "MockSvc"
    assert "service_restarted" in res_approved.events


def test_service_registry_discovery():
    """Verify NativeManagerRegistry dynamically discovers and registers ServiceManager."""
    reg = NativeManagerRegistry()
    reg.discover("src.desktop.native.managers")

    assert "service" in reg._managers
    for cap in ["service.list", "service.status", "service.start", "service.stop", "service.restart"]:
        assert cap in reg._capability_map
        assert reg._capability_map[cap].name == "service"
