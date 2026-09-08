"""
Test PrinterManager & Win32 Print Capability Subsystem

Validates:
1. PrinterManager metadata attributes (NAME, VERSION, PRIORITY, DEPENDENCIES, MUTATING_CAPABILITIES).
2. Lifecycle execution: initialize, health_check, shutdown.
3. Auto-discovery and capability resolution in NativeManagerRegistry.
4. Read-only capabilities (printer.list, printer.default, printer.status, printer.queue).
5. HMAC human approval gate on mutating capabilities (printer.default [set], printer.print_file, printer.cancel_job).
6. Execution with valid HMAC approval ticket and signature.
7. Verification and error handling for invalid/missing arguments and failed tickets.
"""

import os
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(project_root, "src"))

from desktop.native.desktop_result import DesktopResult
from desktop.native.managers.base_manager import HealthCheckResult, HealthStatus
from desktop.native.managers.native_manager_registry import NativeManagerRegistry
from desktop.native.managers.printer_manager import (
    PrinterManager,
    _decode_job_status_flags,
    _decode_job_status_text,
    _decode_printer_status_flags,
    _decode_printer_status_text,
)


def setup_function():
    """Reset registry singleton before each test."""
    NativeManagerRegistry.reset_instance()


def teardown_function():
    """Clean up after each test."""
    NativeManagerRegistry.reset_instance()


def test_printer_manager_metadata():
    """Test PrinterManager metadata attributes and contract conformance."""
    mgr = PrinterManager()
    assert mgr.name == "printer"
    assert mgr.NAME == "printer"
    assert mgr.VERSION == "1.0"
    assert mgr.PRIORITY == 28
    assert "win32print" in mgr.DEPENDENCIES
    assert "printer.print_file" in mgr.MUTATING_CAPABILITIES
    assert "printer.cancel_job" in mgr.MUTATING_CAPABILITIES
    assert "printer.set_default" in mgr.MUTATING_CAPABILITIES

    assert len(mgr.capabilities) == 6
    assert "printer.list" in mgr.capabilities
    assert "printer.default" in mgr.capabilities
    assert "printer.status" in mgr.capabilities
    assert "printer.queue" in mgr.capabilities
    assert "printer.print_file" in mgr.capabilities
    assert "printer.cancel_job" in mgr.capabilities


def test_printer_manager_lifecycle():
    """Test initialize, health_check, and shutdown lifecycle."""
    mgr = PrinterManager()
    assert mgr.initialize() is True

    health = mgr.health_check()
    assert isinstance(health, HealthCheckResult)
    assert health.manager_name == "printer"
    assert health.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
    assert health.total_capabilities == 6
    assert health.details["initialized"] is True

    mgr.shutdown()
    assert mgr._initialized is False


def test_printer_status_decoding():
    """Test Win32 printer status bitmask decoding logic."""
    assert _decode_printer_status_text(0) == "Ready"
    assert _decode_printer_status_flags(0) == []

    # Test error & paper jam (0x02 | 0x08 = 0x0A)
    flags = _decode_printer_status_flags(0x02 | 0x08)
    assert "Error" in flags
    assert "Paper Jam" in flags

    text = _decode_printer_status_text(0x02 | 0x08)
    assert "Error" in text
    assert "Paper Jam" in text

    # Test job status
    assert _decode_job_status_text(0) == "Ready"
    job_flags = _decode_job_status_flags(0x10 | 0x08)  # Printing | Spooling
    assert "Printing" in job_flags
    assert "Spooling" in job_flags


def test_registry_auto_discovery_and_resolution():
    """Test discovery and capability resolution by NativeManagerRegistry."""
    registry = NativeManagerRegistry.get_instance()
    discovered = registry.discover("desktop.native.managers")
    assert "printer" in discovered

    mgr = registry.get("printer")
    assert mgr is not None
    assert mgr.name == "printer"

    for cap in [
        "printer.list",
        "printer.default",
        "printer.status",
        "printer.queue",
        "printer.print_file",
        "printer.cancel_job",
    ]:
        resolved = registry.resolve(cap)
        assert resolved is not None
        assert resolved.name == "printer"


def test_printer_list_execution():
    """Test printer.list capability returns expected structured output."""
    mgr = PrinterManager()
    mgr.initialize()

    result = mgr.execute("printer.list", "List all printers")
    assert isinstance(result, DesktopResult)
    assert result.success is True
    assert "printers" in result.data
    assert "count" in result.data
    assert isinstance(result.data["printers"], list)

    for p in result.data["printers"]:
        assert "name" in p
        assert "is_default" in p
        assert "status" in p


def test_printer_default_read_execution():
    """Test printer.default read is safe and not HMAC-gated."""
    mgr = PrinterManager()
    mgr.initialize()

    result = mgr.execute("printer.default", "Get default printer")
    assert isinstance(result, DesktopResult)
    # On systems with installed printers, should succeed
    if result.success:
        assert "name" in result.data
        assert "default_printer" in result.data
        assert result.data["is_default"] is True


def test_printer_status_execution():
    """Test printer.status capability for a valid printer or default."""
    mgr = PrinterManager()
    mgr.initialize()

    list_res = mgr.execute("printer.list")
    if list_res.success and list_res.data["printers"]:
        target_name = list_res.data["printers"][0]["name"]
        res = mgr.execute("printer.status", "Check status", {"name": target_name})
        assert res.success is True
        assert res.data["name"] == target_name
        assert "status" in res.data
        assert "status_flags" in res.data
        assert "job_count" in res.data


def test_printer_queue_execution():
    """Test printer.queue capability returns list of jobs."""
    mgr = PrinterManager()
    mgr.initialize()

    list_res = mgr.execute("printer.list")
    if list_res.success and list_res.data["printers"]:
        target_name = list_res.data["printers"][0]["name"]
        res = mgr.execute("printer.queue", "Get queue", {"name": target_name})
        assert res.success is True
        assert res.data["printer_name"] == target_name
        assert isinstance(res.data["jobs"], list)
        assert "count" in res.data


def test_printer_default_set_hmac_gate():
    """Test setting default printer requires HMAC ticket and signature."""
    mgr = PrinterManager()
    mgr.initialize()

    # Attempt setting without ticket
    res_gate = mgr.execute(
        "printer.default",
        "Change default printer",
        {"name": "Microsoft Print to PDF"},
    )
    assert res_gate.success is False
    assert res_gate.data.get("requires_confirmation") is True
    ticket_id = res_gate.data.get("approval_ticket_id")
    assert ticket_id is not None
    assert res_gate.data.get("action_type") == "printer.set_default"

    # Sign ticket using process authority
    sig = mgr.auth.generate_human_signature(ticket_id)
    assert sig is not None

    # Execute with verified ticket and signature
    res_approved = mgr.execute(
        "printer.default",
        "Change default printer",
        {
            "name": "Microsoft Print to PDF",
            "approval_ticket_id": ticket_id,
            "approval_signature": sig,
        },
    )
    assert res_approved.success is True
    assert res_approved.data["default_printer"] == "Microsoft Print to PDF"
    assert res_approved.data["updated"] is True


def test_printer_cancel_job_hmac_gate():
    """Test printer.cancel_job is HMAC-gated and executes when signed."""
    mgr = PrinterManager()
    mgr.initialize()

    # Attempt without ticket
    res_gate = mgr.execute(
        "printer.cancel_job",
        "Cancel print job",
        {"printer_name": "Microsoft Print to PDF", "job_id": 99999},
    )
    assert res_gate.success is False
    assert res_gate.data.get("requires_confirmation") is True
    ticket_id = res_gate.data.get("approval_ticket_id")
    assert ticket_id is not None

    # Sign ticket
    sig = mgr.auth.generate_human_signature(ticket_id)
    assert sig is not None

    # Mock win32print.SetJob to verify execution path
    with patch("win32print.OpenPrinter", return_value=12345), \
         patch("win32print.SetJob", return_value=None), \
         patch("win32print.ClosePrinter"):

        res_approved = mgr.execute(
            "printer.cancel_job",
            "Cancel print job",
            {
                "printer_name": "Microsoft Print to PDF",
                "job_id": 99999,
                "approval_ticket_id": ticket_id,
                "approval_signature": sig,
            },
        )
        assert res_approved.success is True
        assert res_approved.data["cancelled"] is True
        assert res_approved.data["job_id"] == 99999


def test_printer_print_file_hmac_gate(tmp_path: Path):
    """Test printer.print_file is HMAC-gated and calls print API when signed."""
    mgr = PrinterManager()
    mgr.initialize()

    test_file = tmp_path / "test_doc.txt"
    test_file.write_text("Test printer document content.")

    # Attempt without ticket
    res_gate = mgr.execute(
        "printer.print_file",
        "Print test document",
        {"file_path": str(test_file)},
    )
    assert res_gate.success is False
    assert res_gate.data.get("requires_confirmation") is True
    ticket_id = res_gate.data.get("approval_ticket_id")
    assert ticket_id is not None

    # Sign ticket
    sig = mgr.auth.generate_human_signature(ticket_id)
    assert sig is not None

    # Mock win32api.ShellExecute to avoid physical printing during tests
    with patch("win32api.ShellExecute", return_value=42) as mock_shell:
        res_approved = mgr.execute(
            "printer.print_file",
            "Print test document",
            {
                "file_path": str(test_file),
                "approval_ticket_id": ticket_id,
                "approval_signature": sig,
            },
        )
        assert res_approved.success is True
        assert res_approved.data["printed"] is True
        assert "file_path" in res_approved.data
        mock_shell.assert_called_once()


def test_hmac_signature_tampering_rejected():
    """Test that forged or tampered signatures are rejected."""
    mgr = PrinterManager()
    mgr.initialize()

    res_gate = mgr.execute(
        "printer.cancel_job",
        "Cancel job",
        {"printer_name": "Microsoft Print to PDF", "job_id": 42},
    )
    ticket_id = res_gate.data.get("approval_ticket_id")

    # Pass an invalid/forged signature
    res_forged = mgr.execute(
        "printer.cancel_job",
        "Cancel job",
        {
            "printer_name": "Microsoft Print to PDF",
            "job_id": 42,
            "approval_ticket_id": ticket_id,
            "approval_signature": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        },
    )
    assert res_forged.success is False
    assert res_forged.data.get("security_alert") == "unauthorized_or_forged_approval"


def test_unsupported_capability():
    """Test that unsupported capabilities fail gracefully."""
    mgr = PrinterManager()
    mgr.initialize()

    res = mgr.execute("printer.invalid_action", "Do unknown task")
    assert res.success is False
    assert "Unsupported capability" in res.error
