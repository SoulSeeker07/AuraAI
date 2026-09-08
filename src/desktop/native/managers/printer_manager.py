"""
Printer Manager — Win32 Native Printer Enumeration, Queue, and Control
Location: src/desktop/native/managers/printer_manager.py

Provides native Win32 printer management for AuraAI using win32print,
win32api, and PowerShell subprocess fallback mechanisms.
Supports printer enumeration, status diagnostics, print job queue listing,
file printing, default printer configuration, and print job cancellation.
Mutating and hardware-altering capabilities are protected by HMAC-SHA256
human approval gating.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

# Graceful imports for Win32 print APIs
try:
    import win32print

    _WIN32PRINT_AVAILABLE = True
except ImportError:
    win32print = None
    _WIN32PRINT_AVAILABLE = False

try:
    import win32api

    _WIN32API_AVAILABLE = True
except ImportError:
    win32api = None
    _WIN32API_AVAILABLE = False

from ..desktop_result import DesktopResult
from .base_manager import BaseNativeManager, HealthCheckResult, HealthStatus
from ..security.approval_authority import CryptographicApprovalAuthority

logger = logging.getLogger(__name__)

# Win32 Printer Status Bitmask Definitions
PRINTER_STATUS_FLAGS: dict[int, str] = {
    0x00000001: "Paused",
    0x00000002: "Error",
    0x00000004: "Pending Deletion",
    0x00000008: "Paper Jam",
    0x00000010: "Paper Out",
    0x00000020: "Manual Feed",
    0x00000040: "Paper Problem",
    0x00000080: "Offline",
    0x00000100: "I/O Active",
    0x00000200: "Busy",
    0x00000400: "Printing",
    0x00000800: "Output Bin Full",
    0x00001000: "Not Available",
    0x00002000: "Waiting",
    0x00004000: "Processing",
    0x00008000: "Initializing",
    0x00010000: "Warming Up",
    0x00020000: "Toner Low",
    0x00040000: "No Toner",
    0x00080000: "Page Punt",
    0x00100000: "User Intervention Required",
    0x00200000: "Out of Memory",
    0x00400000: "Door Open",
    0x00800000: "Server Unknown",
    0x01000000: "Power Save",
}

# Win32 Job Status Bitmask Definitions
JOB_STATUS_FLAGS: dict[int, str] = {
    0x00000001: "Paused",
    0x00000002: "Error",
    0x00000004: "Deleting",
    0x00000008: "Spooling",
    0x00000010: "Printing",
    0x00000020: "Offline",
    0x00000040: "Paper Out",
    0x00000080: "Printed",
    0x00000100: "Deleted",
    0x00000200: "Blocked",
    0x00000400: "User Intervention Required",
    0x00000800: "Restart",
    0x00001000: "Complete",
}


def _decode_printer_status_flags(status_code: int) -> list[str]:
    """Decode Win32 PRINTER_STATUS_* integer bitmask into list of flag names."""
    return [text for mask, text in PRINTER_STATUS_FLAGS.items() if status_code & mask]


def _decode_printer_status_text(status_code: int) -> str:
    """Convert printer status bitmask to human-readable string representation."""
    if status_code == 0:
        return "Ready"
    flags = _decode_printer_status_flags(status_code)
    return ", ".join(flags) if flags else f"Status({status_code})"


def _decode_job_status_flags(status_code: int) -> list[str]:
    """Decode Win32 JOB_STATUS_* integer bitmask into list of flag names."""
    return [text for mask, text in JOB_STATUS_FLAGS.items() if status_code & mask]


def _decode_job_status_text(status_code: int) -> str:
    """Convert job status bitmask to human-readable string representation."""
    if status_code == 0:
        return "Ready"
    flags = _decode_job_status_flags(status_code)
    return ", ".join(flags) if flags else f"Status({status_code})"


class PrinterManager(BaseNativeManager):
    """
    Win32 Native Printer Manager for AuraAI.

    Manages printer enumeration, status diagnostics, print queues,
    default printer configuration, file printing, and job cancellation.
    All mutating actions are protected by HMAC-SHA256 human approval gating.
    """

    NAME = "printer"
    VERSION = "1.0"
    PRIORITY = 28
    DEPENDENCIES: list[str] = ["win32print"]

    MUTATING_CAPABILITIES = {
        "printer.print_file",
        "printer.cancel_job",
        "printer.set_default",
    }

    def __init__(self, auth: CryptographicApprovalAuthority | None = None) -> None:
        """Initialize PrinterManager with approval authority."""
        super().__init__()
        self._auth: CryptographicApprovalAuthority = (
            auth or CryptographicApprovalAuthority.get_instance()
        )
        self._initialized = False

    @property
    def name(self) -> str:
        """Manager name."""
        return self.NAME

    @property
    def auth(self) -> CryptographicApprovalAuthority:
        """Cryptographic approval authority."""
        return self._auth

    @property
    def capabilities(self) -> list[str]:
        """List of supported capabilities."""
        return [
            "printer.list",
            "printer.default",
            "printer.status",
            "printer.queue",
            "printer.print_file",
            "printer.cancel_job",
        ]

    def initialize(self) -> bool:
        """Initialize manager and internal resources."""
        self._initialized = True
        return True

    def health_check(self) -> HealthCheckResult:
        """Check availability of win32print dependencies and fallbacks."""
        missing = []
        fallbacks = []

        if not _WIN32PRINT_AVAILABLE:
            missing.append("win32print")
            fallbacks.append("powershell")
        if not _WIN32API_AVAILABLE:
            fallbacks.append("os.startfile")

        status = HealthStatus.HEALTHY if _WIN32PRINT_AVAILABLE else HealthStatus.DEGRADED

        return HealthCheckResult(
            manager_name=self.name,
            status=status,
            missing_dependencies=missing,
            available_fallbacks=fallbacks,
            total_capabilities=len(self.capabilities),
            available_capabilities=len(self.capabilities),
            details={
                "initialized": self._initialized,
                "win32print_available": _WIN32PRINT_AVAILABLE,
                "win32api_available": _WIN32API_AVAILABLE,
                "security_model": "cryptographic_hmac_human_approval_gate",
            },
        )

    def shutdown(self) -> None:
        """Shutdown manager and clean up state."""
        self._initialized = False

    def execute(
        self,
        capability: str,
        goal: str = "",
        arguments: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> DesktopResult:
        """
        Execute native printer operation with HMAC human approval enforcement.

        Args:
            capability: Target printer capability name.
            goal: Natural language goal or description.
            arguments: Dictionary of arguments for the operation.
            **kwargs: Extra parameters passed by caller.

        Returns:
            DesktopResult indicating success or failure.
        """
        args = dict(arguments or {})
        args.update(kwargs)
        cap = capability.lower().strip()

        try:
            # 1. Mutating capabilities: Require HMAC human approval gate
            is_mutating = False
            action_type = cap
            target = ""
            action_params: dict[str, Any] = {}
            description = ""

            if cap in ("printer.default", "printer.set_default"):
                target_printer = args.get("name") or args.get("printer_name")
                if target_printer or cap == "printer.set_default":
                    is_mutating = True
                    action_type = "printer.set_default"
                    target = str(target_printer or "").strip()
                    action_params = {
                        "capability": "printer.set_default",
                        "name": target,
                    }
                    description = (
                        f"Human authorization required to change default printer to '{target}'"
                    )
            elif cap == "printer.print_file":
                is_mutating = True
                action_type = "printer.print_file"
                target_file = str(
                    args.get("file_path") or args.get("path") or args.get("file") or ""
                ).strip()
                p_name = str(args.get("printer_name") or args.get("printer") or "").strip()
                target = target_file
                action_params = {
                    "capability": "printer.print_file",
                    "file_path": target_file,
                    "printer_name": p_name,
                }
                description = f"Human authorization required to print file '{target_file}'"
            elif cap == "printer.cancel_job":
                is_mutating = True
                action_type = "printer.cancel_job"
                p_name = str(
                    args.get("printer_name") or args.get("name") or args.get("printer") or ""
                ).strip()
                jid = args.get("job_id") or args.get("id") or 0
                target = f"{p_name}:{jid}"
                action_params = {
                    "capability": "printer.cancel_job",
                    "printer_name": p_name,
                    "job_id": jid,
                }
                description = (
                    f"Human authorization required to cancel print job {jid} on printer '{p_name}'"
                )

            if is_mutating:
                ticket_id = args.get("approval_ticket_id") or args.get("ticket_id")
                signature = args.get("approval_signature") or args.get("signature")

                if not ticket_id or not signature:
                    issued_ticket_id = self._auth.create_ticket(
                        action_type=action_type,
                        target=target,
                        parameters=action_params,
                        description=description,
                    )
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=(
                            f"Printer operation '{capability}' alters hardware/system state "
                            "and requires cryptographic human approval."
                        ),
                        data={
                            "requires_confirmation": True,
                            "approval_ticket_id": issued_ticket_id,
                            "action_type": action_type,
                            "target": target,
                            "risk_tier": "confirmation_required",
                        },
                    )

                valid_sig, auth_err = self._auth.verify_and_redeem(
                    ticket_id,
                    signature,
                    action_type=action_type,
                    target=target,
                    parameters=action_params,
                )
                if not valid_sig:
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Human authorization failed: {auth_err}",
                        data={"security_alert": "unauthorized_or_forged_approval"},
                    )

            # 2. Dispatch capability handlers
            if cap == "printer.list":
                return self._handle_list(goal=goal, capability=capability, arguments=args)
            elif cap == "printer.default":
                if args.get("name") or args.get("printer_name"):
                    return self._handle_set_default(
                        goal=goal, capability=capability, arguments=args
                    )
                return self._handle_get_default(
                    goal=goal, capability=capability, arguments=args
                )
            elif cap == "printer.set_default":
                return self._handle_set_default(
                    goal=goal, capability=capability, arguments=args
                )
            elif cap == "printer.status":
                return self._handle_status(goal=goal, capability=capability, arguments=args)
            elif cap in ("printer.queue", "printer.jobs", "queue", "jobs"):
                return self._handle_queue(goal=goal, capability=capability, arguments=args)
            elif cap == "printer.print_file":
                return self._handle_print_file(
                    goal=goal, capability=capability, arguments=args
                )
            elif cap == "printer.cancel_job":
                return self._handle_cancel_job(
                    goal=goal, capability=capability, arguments=args
                )
            else:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"Unsupported capability: {capability}",
                )

        except Exception as exc:
            logger.error(f"PrinterManager.{cap} failed: {exc}", exc_info=True)
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Operation failed: {exc}",
            )

    # ==================== Capability Handlers ====================

    def _get_printer_status_code(self, printer_name: str) -> int:
        """Fetch raw numeric status flags for a named printer."""
        if not _WIN32PRINT_AVAILABLE:
            return 0
        handle = None
        try:
            handle = win32print.OpenPrinter(printer_name)
            info = win32print.GetPrinter(handle, 2)
            return int(info.get("Status", 0))
        except Exception:
            return 0
        finally:
            if handle is not None:
                try:
                    win32print.ClosePrinter(handle)
                except Exception:
                    pass

    def _handle_list(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        """
        List all installed printers with default and status flags.
        Uses win32print.EnumPrinters(PRINTER_ENUM_LOCAL | PRINTER_ENUM_CONNECTIONS).
        """
        default_printer: str | None = None
        printers_list: list[dict[str, Any]] = []

        if _WIN32PRINT_AVAILABLE:
            try:
                try:
                    default_printer = win32print.GetDefaultPrinter()
                except Exception:
                    default_printer = None

                flags = (
                    win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
                )
                raw_printers = win32print.EnumPrinters(flags)

                for item in raw_printers:
                    if isinstance(item, dict):
                        pname = str(item.get("pPrinterName") or item.get("name", "")).strip()
                        raw_status = int(item.get("Status", 0))
                    elif isinstance(item, (tuple, list)):
                        pname = str(item[2] if len(item) > 2 else item[0]).strip()
                        raw_status = self._get_printer_status_code(pname)
                    else:
                        pname = str(item).strip()
                        raw_status = 0

                    is_def = pname == default_printer if default_printer else False
                    status_text = _decode_printer_status_text(raw_status)
                    status_flags = _decode_printer_status_flags(raw_status)

                    printers_list.append(
                        {
                            "name": pname,
                            "is_default": is_def,
                            "status": status_text,
                            "status_code": raw_status,
                            "status_flags": status_flags,
                        }
                    )

                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={
                        "printers": printers_list,
                        "count": len(printers_list),
                        "default_printer": default_printer,
                    },
                    events=["printer_list_enumerated"],
                )
            except Exception as exc:
                logger.warning(f"win32print.EnumPrinters failed, trying PowerShell: {exc}")

        # PowerShell fallback
        try:
            ps_cmd = (
                "Get-CimInstance -ClassName Win32_Printer | "
                "Select-Object Name, Default, PrinterStatus, WorkOffline | "
                "ConvertTo-Json -Compress"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout.strip())
                if isinstance(data, dict):
                    data = [data]
                for item in data:
                    pname = str(item.get("Name", "")).strip()
                    is_def = bool(item.get("Default", False))
                    if is_def:
                        default_printer = pname
                    status_text = "Offline" if item.get("WorkOffline") else "Ready"
                    raw_st = int(item.get("PrinterStatus", 3))
                    printers_list.append(
                        {
                            "name": pname,
                            "is_default": is_def,
                            "status": status_text,
                            "status_code": raw_st,
                            "status_flags": [status_text],
                        }
                    )

                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={
                        "printers": printers_list,
                        "count": len(printers_list),
                        "default_printer": default_printer,
                    },
                    events=["printer_list_enumerated"],
                )
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"PowerShell enumeration failed: {res.stderr.strip()}",
            )
        except Exception as fallback_exc:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Failed to list printers: {fallback_exc}",
            )

    def _handle_get_default(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        """Get the current default printer."""
        if _WIN32PRINT_AVAILABLE:
            try:
                default_name = win32print.GetDefaultPrinter()
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={
                        "name": default_name,
                        "default_printer": default_name,
                        "is_default": True,
                    },
                )
            except Exception as exc:
                logger.warning(f"win32print.GetDefaultPrinter failed: {exc}")

        # PowerShell fallback
        try:
            ps_cmd = (
                "(Get-CimInstance -ClassName Win32_Printer | Where-Object Default).Name"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=10,
            )
            out_name = res.stdout.strip()
            if res.returncode == 0 and out_name:
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={
                        "name": out_name,
                        "default_printer": out_name,
                        "is_default": True,
                    },
                )
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="No default printer configured on system.",
            )
        except Exception as exc:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Failed to get default printer: {exc}",
            )

    def _handle_set_default(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        """
        Set the default printer (HMAC human authorization verified).
        Uses win32print.SetDefaultPrinter(name).
        """
        name = str(arguments.get("name") or arguments.get("printer_name") or "").strip()
        if not name:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="Missing required argument: 'name' (printer name).",
            )

        prev_default = None
        if _WIN32PRINT_AVAILABLE:
            try:
                prev_default = win32print.GetDefaultPrinter()
            except Exception:
                prev_default = None

        if _WIN32PRINT_AVAILABLE:
            try:
                win32print.SetDefaultPrinter(name)

                def rollback_set_default() -> bool:
                    if prev_default and _WIN32PRINT_AVAILABLE:
                        try:
                            win32print.SetDefaultPrinter(prev_default)
                            return True
                        except Exception as r_err:
                            logger.error(f"Rollback default printer failed: {r_err}")
                            return False
                    return False

                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={
                        "name": name,
                        "default_printer": name,
                        "previous_default": prev_default,
                        "updated": True,
                        "method": "win32print.SetDefaultPrinter",
                    },
                    events=["printer_default_changed"],
                    rollback=rollback_set_default,
                )
            except Exception as exc:
                logger.warning(f"win32print.SetDefaultPrinter failed: {exc}")

        # PowerShell fallback via WScript.Network COM object
        try:
            ps_cmd = (
                f"(New-Object -ComObject WScript.Network).SetDefaultPrinter('{name}')"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode == 0:
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={
                        "name": name,
                        "default_printer": name,
                        "previous_default": prev_default,
                        "updated": True,
                        "method": "subprocess.wscript_network",
                    },
                    events=["printer_default_changed"],
                )
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"PowerShell SetDefaultPrinter failed: {res.stderr.strip()}",
            )
        except Exception as exc:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Failed to set default printer: {exc}",
            )

    def _handle_status(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        """
        Get status of a named printer.
        Uses win32print.OpenPrinter(name) then win32print.GetPrinter(handle, 2).
        """
        name = str(arguments.get("name") or arguments.get("printer_name") or "").strip()
        if not name:
            if _WIN32PRINT_AVAILABLE:
                try:
                    name = win32print.GetDefaultPrinter()
                except Exception:
                    pass
            if not name:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error="Missing required argument: 'name' (printer name).",
                )

        if _WIN32PRINT_AVAILABLE:
            handle = None
            try:
                handle = win32print.OpenPrinter(name)
                info = win32print.GetPrinter(handle, 2)
                raw_status = int(info.get("Status", 0))
                status_flags = _decode_printer_status_flags(raw_status)
                status_text = _decode_printer_status_text(raw_status)

                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={
                        "name": name,
                        "status": status_text,
                        "status_code": raw_status,
                        "status_flags": status_flags,
                        "job_count": int(info.get("cJobs", 0)),
                        "port": info.get("pPortName", ""),
                        "driver": info.get("pDriverName", ""),
                        "comment": info.get("pComment", ""),
                        "location": info.get("pLocation", ""),
                        "attributes": int(info.get("Attributes", 0)),
                        "server": info.get("pServerName", ""),
                        "share_name": info.get("pShareName", ""),
                    },
                    events=["printer_status_checked"],
                )
            except Exception as exc:
                logger.warning(f"win32print.GetPrinter failed for '{name}': {exc}")
            finally:
                if handle is not None:
                    try:
                        win32print.ClosePrinter(handle)
                    except Exception:
                        pass

        # PowerShell fallback
        try:
            ps_cmd = (
                f"Get-CimInstance -ClassName Win32_Printer -Filter \"Name='{name}'\" | "
                "Select-Object Name, Default, PrinterStatus, WorkOffline, PortName, DriverName | "
                "ConvertTo-Json -Compress"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout.strip())
                is_offline = bool(data.get("WorkOffline", False))
                status_text = "Offline" if is_offline else "Ready"
                raw_st = int(data.get("PrinterStatus", 3))
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={
                        "name": data.get("Name", name),
                        "status": status_text,
                        "status_code": raw_st,
                        "status_flags": [status_text],
                        "job_count": 0,
                        "port": data.get("PortName", ""),
                        "driver": data.get("DriverName", ""),
                    },
                    events=["printer_status_checked"],
                )
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Printer '{name}' not found: {res.stderr.strip()}",
            )
        except Exception as exc:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Failed to get printer status: {exc}",
            )

    def _handle_queue(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        """
        List print jobs in queue for a named printer.
        Uses win32print.OpenPrinter(name) then win32print.EnumJobs(handle, 0, -1, 1).
        """
        name = str(arguments.get("name") or arguments.get("printer_name") or "").strip()
        if not name:
            if _WIN32PRINT_AVAILABLE:
                try:
                    name = win32print.GetDefaultPrinter()
                except Exception:
                    pass
            if not name:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error="Missing required argument: 'name' (printer name).",
                )

        jobs_list: list[dict[str, Any]] = []

        if _WIN32PRINT_AVAILABLE:
            handle = None
            try:
                handle = win32print.OpenPrinter(name)
                raw_jobs = win32print.EnumJobs(handle, 0, -1, 1)

                for j in raw_jobs:
                    if isinstance(j, dict):
                        jid = j.get("JobId", 0)
                        doc = j.get("pDocument", "")
                        raw_st = j.get("Status", 0)
                        owner = j.get("pUserName", "")
                    elif isinstance(j, (tuple, list)):
                        jid = j[0] if len(j) > 0 else 0
                        doc = j[1] if len(j) > 1 else ""
                        raw_st = j[6] if len(j) > 6 else 0
                        owner = j[3] if len(j) > 3 else ""
                    else:
                        continue

                    status_text = _decode_job_status_text(int(raw_st))
                    status_flags = _decode_job_status_flags(int(raw_st))

                    jobs_list.append(
                        {
                            "job_id": jid,
                            "document": doc,
                            "status": status_text,
                            "status_code": raw_st,
                            "status_flags": status_flags,
                            "owner": owner,
                        }
                    )

                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={
                        "printer_name": name,
                        "jobs": jobs_list,
                        "count": len(jobs_list),
                    },
                    events=["printer_queue_enumerated"],
                )
            except Exception as exc:
                logger.warning(f"win32print.EnumJobs failed for '{name}': {exc}")
            finally:
                if handle is not None:
                    try:
                        win32print.ClosePrinter(handle)
                    except Exception:
                        pass

        # PowerShell fallback
        try:
            ps_cmd = (
                f"Get-PrintJob -PrinterName '{name}' | "
                "Select-Object ID, DocumentName, JobStatus, UserName | "
                "ConvertTo-Json -Compress"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode == 0:
                out = res.stdout.strip()
                if out:
                    data = json.loads(out)
                    if isinstance(data, dict):
                        data = [data]
                    for j in data:
                        jobs_list.append(
                            {
                                "job_id": j.get("ID", 0),
                                "document": j.get("DocumentName", ""),
                                "status": str(j.get("JobStatus", "Spooling")),
                                "status_code": 0,
                                "status_flags": [str(j.get("JobStatus", "Spooling"))],
                                "owner": j.get("UserName", ""),
                            }
                        )

                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={
                        "printer_name": name,
                        "jobs": jobs_list,
                        "count": len(jobs_list),
                    },
                    events=["printer_queue_enumerated"],
                )
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Failed to query queue for '{name}': {res.stderr.strip()}",
            )
        except Exception as exc:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Failed to get print queue: {exc}",
            )

    def _handle_print_file(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        """
        Print a file using default or specified printer (HMAC human authorization verified).
        Uses win32api.ShellExecute(0, 'print'/'printto') or os.startfile(path, 'print').
        """
        file_path = str(
            arguments.get("file_path") or arguments.get("path") or arguments.get("file") or ""
        ).strip()
        if not file_path:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="Missing required argument: 'file_path'.",
            )

        path_obj = Path(file_path).resolve()
        if not path_obj.is_file():
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"File not found or not a valid file: '{file_path}'.",
            )

        printer_name = str(
            arguments.get("printer_name") or arguments.get("printer") or ""
        ).strip() or None

        # 1. If specific printer provided and win32api available, use 'printto' verb
        if printer_name and _WIN32API_AVAILABLE:
            try:
                win32api.ShellExecute(
                    0, "printto", str(path_obj), f'"{printer_name}"', ".", 0
                )
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={
                        "file_path": str(path_obj),
                        "printer_name": printer_name,
                        "printed": True,
                        "method": "win32api.ShellExecute(printto)",
                    },
                    events=["printer_job_submitted"],
                )
            except Exception as api_err:
                logger.warning(
                    f"win32api.ShellExecute printto failed for '{printer_name}': {api_err}. Trying default print verb."
                )

        # 2. Print with default print verb via win32api
        if _WIN32API_AVAILABLE:
            try:
                win32api.ShellExecute(0, "print", str(path_obj), None, ".", 0)
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={
                        "file_path": str(path_obj),
                        "printer_name": printer_name or "default",
                        "printed": True,
                        "method": "win32api.ShellExecute(print)",
                    },
                    events=["printer_job_submitted"],
                )
            except Exception as api_err:
                logger.warning(f"win32api.ShellExecute print failed: {api_err}")

        # 3. Fallback to os.startfile(path, 'print')
        try:
            os.startfile(str(path_obj), "print")
            return DesktopResult.create_success(
                goal=goal,
                capability=capability,
                manager=self.name,
                data={
                    "file_path": str(path_obj),
                    "printer_name": printer_name or "default",
                    "printed": True,
                    "method": "os.startfile(print)",
                },
                events=["printer_job_submitted"],
            )
        except Exception as os_err:
            logger.warning(f"os.startfile print failed: {os_err}")

        # 4. Subprocess fallback via PowerShell Start-Process
        try:
            ps_cmd = f"Start-Process -FilePath '{path_obj}' -Verb Print"
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if res.returncode == 0:
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={
                        "file_path": str(path_obj),
                        "printer_name": printer_name or "default",
                        "printed": True,
                        "method": "subprocess.powershell",
                    },
                    events=["printer_job_submitted"],
                )
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"PowerShell print failed: {res.stderr.strip()}",
            )
        except Exception as proc_err:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"All print execution methods failed: {proc_err}",
            )

    def _handle_cancel_job(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        """
        Cancel a print job on a named printer (HMAC human authorization verified).
        Uses win32print.SetJob(handle, job_id, 0, None, win32print.JOB_CONTROL_CANCEL).
        """
        printer_name = str(
            arguments.get("printer_name") or arguments.get("name") or arguments.get("printer") or ""
        ).strip()
        job_id_raw = arguments.get("job_id") if arguments.get("job_id") is not None else arguments.get("id")

        if not printer_name:
            if _WIN32PRINT_AVAILABLE:
                try:
                    printer_name = win32print.GetDefaultPrinter()
                except Exception:
                    pass
            if not printer_name:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error="Missing required argument: 'printer_name'.",
                )

        if job_id_raw is None:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="Missing required argument: 'job_id'.",
            )

        try:
            job_id = int(job_id_raw)
        except (ValueError, TypeError):
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Invalid 'job_id': {job_id_raw}. Must be an integer.",
            )

        if _WIN32PRINT_AVAILABLE:
            handle = None
            try:
                handle = win32print.OpenPrinter(printer_name)
                win32print.SetJob(
                    handle, job_id, 0, None, win32print.JOB_CONTROL_CANCEL
                )
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={
                        "printer_name": printer_name,
                        "job_id": job_id,
                        "cancelled": True,
                        "method": "win32print.SetJob",
                    },
                    events=["print_job_cancelled"],
                )
            except Exception as print_err:
                logger.warning(
                    f"win32print.SetJob failed for printer '{printer_name}' job {job_id}: {print_err}. Trying PowerShell fallback."
                )
            finally:
                if handle is not None:
                    try:
                        win32print.ClosePrinter(handle)
                    except Exception:
                        pass

        # Subprocess fallback via PowerShell
        try:
            ps_cmd = (
                f"Get-PrintJob -PrinterName '{printer_name}' -ID {job_id} | Remove-PrintJob"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode == 0:
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={
                        "printer_name": printer_name,
                        "job_id": job_id,
                        "cancelled": True,
                        "method": "subprocess.powershell",
                    },
                    events=["print_job_cancelled"],
                )
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Failed to cancel job via PowerShell: {res.stderr.strip()}",
            )
        except Exception as sub_err:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Failed to cancel print job: {sub_err}",
            )
