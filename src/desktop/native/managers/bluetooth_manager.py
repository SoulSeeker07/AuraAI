"""
Bluetooth Manager — Windows Bluetooth Radio & Device Management
Location: src/desktop/native/managers/bluetooth_manager.py

Provides native Windows Bluetooth radio state interrogation, peripheral enumeration,
HMAC-gated radio toggling via PowerShell PnP cmdlets, and best-effort pairing/connection
assists via ms-settings:bluetooth.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from typing import Any

from ..desktop_result import DesktopResult
from ..sandbox.sandbox_manager import SandboxManager
from ..security.approval_authority import CryptographicApprovalAuthority
from .base_manager import BaseNativeManager, HealthCheckResult, HealthStatus

logger = logging.getLogger(__name__)

# Strict validation regex for Windows PnP Device Instance IDs to protect against command injection
SAFE_INSTANCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\\{}&\.\-\:\@]+$")


class BluetoothManager(BaseNativeManager):
    """
    Manages Bluetooth radio and peripheral devices on Windows desktop via PowerShell and Win32.

    Capabilities:
    - bluetooth.status: Query Bluetooth radio status, adapter info, and peripheral statistics.
    - bluetooth.toggle: Enable or disable Bluetooth radio hardware (HMAC-gated).
    - bluetooth.list_devices: List paired, discovered, and connected Bluetooth devices.
    - bluetooth.connect: Assist connecting to a Bluetooth device (launches Settings UI).
    - bluetooth.disconnect: Assist disconnecting a Bluetooth device (launches Settings UI).
    """

    NAME = "bluetooth"
    VERSION = "1.0"
    PRIORITY = 22
    DEPENDENCIES: list[str] = []

    MUTATING_CAPABILITIES = {
        "bluetooth.toggle",
    }

    def __init__(
        self,
        auth: CryptographicApprovalAuthority | None = None,
        sandbox: SandboxManager | None = None,
    ):
        """Initialize BluetoothManager with optional security authority and sandbox."""
        super().__init__()
        self._auth: CryptographicApprovalAuthority = (
            auth or CryptographicApprovalAuthority.get_instance()
        )
        self._sandbox: SandboxManager = sandbox or SandboxManager.get_instance()
        self._initialized = False

    @property
    def name(self) -> str:
        """Return canonical manager name."""
        return self.NAME

    @property
    def auth(self) -> CryptographicApprovalAuthority:
        """Return cryptographic approval authority."""
        return self._auth

    @property
    def capabilities(self) -> list[str]:
        """Return list of supported capabilities."""
        return [
            "bluetooth.status",
            "bluetooth.toggle",
            "bluetooth.list_devices",
            "bluetooth.connect",
            "bluetooth.disconnect",
        ]

    def initialize(self) -> bool:
        """Initialize manager resources and verify host execution environment."""
        self._initialized = True
        return True

    def health_check(self) -> HealthCheckResult:
        """
        Verify Bluetooth subsystem health and query radio presence.

        Returns:
            HealthCheckResult with detailed status and available capabilities.
        """
        sandbox_provider = None
        try:
            sandbox_hc = self._sandbox.health_check()
            sandbox_provider = sandbox_hc.get("active_provider")
        except Exception as exc:
            logger.debug(f"Could not query sandbox health check: {exc}")

        devices = []
        radio_found = False
        try:
            devices = self._get_pnp_devices()
            radio = self._find_radio_adapter(devices)
            radio_found = radio is not None
        except Exception as exc:
            logger.warning(f"Health check Bluetooth device probe failed: {exc}")

        status = HealthStatus.HEALTHY if self._initialized else HealthStatus.INITIALIZING

        return HealthCheckResult(
            manager_name=self.name,
            status=status,
            total_capabilities=len(self.capabilities),
            available_capabilities=len(self.capabilities),
            details={
                "initialized": self._initialized,
                "security_model": "cryptographic_hmac_human_approval_gate",
                "sandbox_provider": sandbox_provider,
                "hardware_detected": radio_found,
                "total_bluetooth_entries": len(devices),
            },
        )

    def shutdown(self) -> None:
        """Release manager resources on shutdown."""
        self._initialized = False

    # ── Internal PowerShell Execution Helpers ──

    def _run_powershell(self, script: str, timeout: float = 15.0) -> tuple[int, str, str]:
        """
        Execute a PowerShell script via subprocess on the Windows host.

        Args:
            script: The PowerShell script/command string to run.
            timeout: Command timeout in seconds.

        Returns:
            tuple of (returncode, stdout, stderr)
        """
        cmd = [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
            return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
        except subprocess.TimeoutExpired:
            logger.warning(f"PowerShell command timed out after {timeout}s: {script[:100]}...")
            return -1, "", f"Command timed out after {timeout}s"
        except Exception as exc:
            logger.error(f"Failed to execute PowerShell command: {exc}")
            return -1, "", str(exc)

    def _get_pnp_devices(self) -> list[dict[str, Any]]:
        """
        Retrieve all Bluetooth PnP devices via PowerShell Get-PnpDevice -Class Bluetooth.

        Returns:
            List of device dictionaries with Status, Name, InstanceId, Present, Service.
        """
        ps_cmd = (
            "Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | "
            "Select-Object Status, Name, InstanceId, Present, Service, Class | "
            "ConvertTo-Json -Compress"
        )
        code, out, _ = self._run_powershell(ps_cmd, timeout=12.0)
        if code != 0 or not out:
            # Fallback attempt querying BluetoothDevice class
            alt_cmd = (
                "Get-PnpDevice -Class BluetoothDevice -ErrorAction SilentlyContinue | "
                "Select-Object Status, Name, InstanceId, Present, Service, Class | "
                "ConvertTo-Json -Compress"
            )
            code, out, _ = self._run_powershell(alt_cmd, timeout=12.0)
            if code != 0 or not out:
                return []

        try:
            parsed = json.loads(out)
            if isinstance(parsed, dict):
                return [parsed]
            elif isinstance(parsed, list):
                return parsed
            return []
        except json.JSONDecodeError:
            return self._parse_pnp_fallback(out)

    def _parse_pnp_fallback(self, raw_output: str) -> list[dict[str, Any]]:
        """
        Regex fallback to extract device records from raw PowerShell output.
        """
        devices = []
        matches = re.findall(
            r'{\s*"Status":\s*"([^"]*)".*?"Name":\s*"([^"]*)".*?"InstanceId":\s*"([^"]*)"',
            raw_output,
            re.DOTALL,
        )
        for status, name, inst_id in matches:
            devices.append({
                "Status": status,
                "Name": name,
                "InstanceId": inst_id,
                "Present": True,
            })
        return devices

    def _classify_device(self, dev: dict[str, Any]) -> str:
        """
        Categorize a PnP Bluetooth item into peripheral, radio_adapter, service, or system_enumerator.
        """
        inst_id = str(dev.get("InstanceId") or "").upper()
        name = str(dev.get("Name") or "").lower()
        svc = str(dev.get("Service") or "").upper()

        if svc in {"BTHUSB", "BTHMINI"} or inst_id.startswith(("USB\\", "PCI\\")):
            return "radio_adapter"
        if "enumerator" in name or inst_id.startswith("BTH\\MS_") or svc in {"BTHENUM", "BTHLEENUM"}:
            return "system_enumerator"
        if any(
            w in name
            for w in [
                "avrcp transport",
                "generic attribute",
                "information service",
                "identification service",
                "rfcomm protocol",
            ]
        ):
            return "service"
        if inst_id.startswith(("BTHENUM\\DEV_", "BTHLE\\DEV_", "BTHLEDEVICE\\")):
            return "peripheral"
        return "peripheral"

    def _find_radio_adapter(self, devices: list[dict[str, Any]]) -> dict[str, Any] | None:
        """
        Identify the physical Bluetooth radio controller from the device list.
        """
        # 1. Primary check: Driver service matches known radio controllers or InstanceId starts with USB/PCI
        for dev in devices:
            svc = str(dev.get("Service") or "").upper()
            inst_id = str(dev.get("InstanceId") or "").upper()
            if svc in {"BTHUSB", "BTHMINI"} or inst_id.startswith(("USB\\", "PCI\\")):
                return dev

        # 2. Secondary check: Name contains radio keywords without transport/enumerator terms
        for dev in devices:
            name = str(dev.get("Name") or "").lower()
            if (
                any(kw in name for kw in ["bluetooth adapter", "wireless bluetooth", "bluetooth radio"])
                and not any(bad in name for bad in ["enumerator", "transport", "protocol", "service"])
            ):
                return dev

        # 3. Tertiary fallback: First non-enumerated/non-peripheral device
        for dev in devices:
            inst_id = str(dev.get("InstanceId") or "").upper()
            if not inst_id.startswith(("BTHENUM\\", "BTHLE\\", "BTHLEDEVICE\\", "BTH\\MS_")):
                return dev

        return devices[0] if devices else None

    def _find_device_by_name(self, name: str) -> dict[str, Any] | None:
        """Search for a known device matching the given name using case-insensitive regex."""
        if not name:
            return None
        devices = self._get_pnp_devices()
        pattern = re.compile(re.escape(name), re.IGNORECASE)

        # First pass: Prioritize actual peripheral devices over services/transports
        for dev in devices:
            dev_name = dev.get("Name") or ""
            if pattern.search(dev_name) and self._classify_device(dev) == "peripheral":
                return {
                    "name": dev.get("Name"),
                    "status": dev.get("Status"),
                    "instance_id": dev.get("InstanceId"),
                    "present": bool(dev.get("Present", False)),
                    "device_type": "peripheral",
                }

        # Second pass: Match any device entry
        for dev in devices:
            dev_name = dev.get("Name") or ""
            if pattern.search(dev_name):
                return {
                    "name": dev.get("Name"),
                    "status": dev.get("Status"),
                    "instance_id": dev.get("InstanceId"),
                    "present": bool(dev.get("Present", False)),
                    "device_type": self._classify_device(dev),
                }
        return None

    def _open_bluetooth_settings(self) -> tuple[bool, str]:
        """Open the Windows Settings app to the Bluetooth page."""
        try:
            os.startfile("ms-settings:bluetooth")
            return True, ""
        except Exception as e1:
            try:
                subprocess.Popen(["cmd.exe", "/c", "start", "ms-settings:bluetooth"], shell=False)
                return True, ""
            except Exception as e2:
                logger.error(f"Failed to open ms-settings:bluetooth: {e1} / {e2}")
                return False, f"{e1} / {e2}"

    # ── Capability Handlers ──

    def _handle_status(self, goal: str, capability: str, arguments: dict[str, Any]) -> DesktopResult:
        """Check Bluetooth radio status via Get-PnpDevice -Class Bluetooth."""
        devices = self._get_pnp_devices()
        radio = self._find_radio_adapter(devices)

        radio_enabled = False
        radio_status = "Unknown"
        adapter_name = None
        adapter_id = None

        if radio:
            adapter_name = radio.get("Name")
            adapter_id = radio.get("InstanceId")
            radio_status = radio.get("Status", "Unknown")
            radio_enabled = (radio_status == "OK" and bool(radio.get("Present", True)))

        paired_peripherals = [d for d in devices if self._classify_device(d) == "peripheral"]
        connected_peripherals = [d for d in paired_peripherals if d.get("Present")]

        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={
                "radio_enabled": radio_enabled,
                "radio_status": radio_status,
                "adapter_name": adapter_name,
                "adapter_instance_id": adapter_id,
                "hardware_detected": radio is not None,
                "total_bluetooth_entries": len(devices),
                "paired_devices_count": len(paired_peripherals),
                "connected_devices_count": len(connected_peripherals),
                "summary": (
                    f"Bluetooth radio is {'enabled' if radio_enabled else 'disabled or unavailable'} "
                    f"({adapter_name or 'No adapter found'}). "
                    f"{len(paired_peripherals)} paired device(s) ({len(connected_peripherals)} connected)."
                ),
            },
            events=["bluetooth_status_checked"],
        )

    def _handle_toggle(self, goal: str, capability: str, arguments: dict[str, Any]) -> DesktopResult:
        """Enable or disable Bluetooth radio hardware via Enable-PnpDevice / Disable-PnpDevice."""
        enable_val = arguments.get("enable")
        if enable_val is None:
            txt = f"{arguments.get('state', '')} {arguments.get('action', '')} {goal}".lower()
            enable = False if any(w in txt for w in ["disable", "off", "stop", "false"]) else True
        else:
            enable = bool(enable_val)

        # 1. Resolve target adapter instance ID
        instance_id = arguments.get("instance_id")
        adapter_name = "Bluetooth Radio"
        devices = self._get_pnp_devices()
        radio = self._find_radio_adapter(devices)

        if not instance_id:
            if not radio:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error="No Bluetooth radio adapter found on this system to toggle.",
                )
            instance_id = radio.get("InstanceId")
            adapter_name = radio.get("Name", "Bluetooth Radio")
        elif radio:
            adapter_name = radio.get("Name", "Bluetooth Radio")

        if not instance_id or not SAFE_INSTANCE_ID_PATTERN.match(str(instance_id)):
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Invalid or unsafe Bluetooth instance ID format: {instance_id}",
            )

        # 2. Build and execute PowerShell command
        action_verb = "Enable-PnpDevice" if enable else "Disable-PnpDevice"
        ps_cmd = f"{action_verb} -InstanceId '{instance_id}' -Confirm:$false"

        code, out, err = self._run_powershell(ps_cmd, timeout=15.0)

        # Audit log execution
        try:
            from ..security.audit_logger import SecurityAuditLogger

            SecurityAuditLogger.get_instance().log_event(
                event_type="BLUETOOTH_RADIO_TOGGLE",
                action_type="bluetooth.toggle",
                target=str(instance_id),
                status="SUCCESS" if code == 0 else "FAILURE",
                details={
                    "enable": enable,
                    "adapter_name": adapter_name,
                    "exit_code": code,
                    "error": err,
                },
            )
        except Exception as audit_err:
            logger.warning(f"Audit log failed on bluetooth toggle: {audit_err}")

        if code != 0 or err:
            err_msg = err or out or "PnP device toggle command failed."
            if "Access is denied" in err_msg or "CM_PROB" in err_msg or "0x5" in err_msg:
                err_msg = (
                    f"{err_msg} (Elevated Administrator privileges are required to enable/disable "
                    f"hardware PnP devices in Windows)."
                )
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Failed to {'enable' if enable else 'disable'} Bluetooth adapter: {err_msg}",
                data={
                    "adapter_name": adapter_name,
                    "instance_id": instance_id,
                    "enable": enable,
                    "exit_code": code,
                    "error_output": err,
                },
            )

        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={
                "enabled": enable,
                "action": "enabled" if enable else "disabled",
                "adapter_name": adapter_name,
                "instance_id": instance_id,
                "message": f"Successfully {'enabled' if enable else 'disabled'} Bluetooth radio ({adapter_name}).",
            },
            events=["bluetooth_enabled" if enable else "bluetooth_disabled"],
        )

    def _handle_list_devices(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        """List paired, discovered, and connected Bluetooth devices."""
        devices = self._get_pnp_devices()

        paired_peripherals = []
        all_formatted = []

        for d in devices:
            cat = self._classify_device(d)
            item = {
                "name": d.get("Name"),
                "status": d.get("Status"),
                "instance_id": d.get("InstanceId"),
                "present": bool(d.get("Present", False)),
                "device_type": cat,
            }
            all_formatted.append(item)
            if cat == "peripheral":
                paired_peripherals.append(item)

        only_paired = arguments.get("only_paired", False)
        result_devices = paired_peripherals if only_paired else all_formatted

        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={
                "devices": result_devices,
                "paired_devices": paired_peripherals,
                "total_entries": len(all_formatted),
                "paired_count": len(paired_peripherals),
                "connected_count": sum(1 for d in paired_peripherals if d.get("present")),
            },
            events=["bluetooth_devices_listed"],
        )

    def _handle_connect(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        """Assist connecting to a Bluetooth device by launching ms-settings:bluetooth."""
        device_name = str(
            arguments.get("device_name")
            or arguments.get("name")
            or arguments.get("device")
            or ""
        ).strip()

        if not device_name and goal:
            m = re.search(r"connect(?:\s+to)?\s+([A-Za-z0-9_\s\-\'\"]+)", goal, re.I)
            if m:
                device_name = m.group(1).strip().strip("'\"")

        matched_device = self._find_device_by_name(device_name) if device_name else None

        launched, launch_err = self._open_bluetooth_settings()
        if not launched:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Failed to open Bluetooth Settings: {launch_err}",
                data={"device_name": device_name},
            )

        msg = (
            f"Opened Windows Bluetooth Settings. Direct Bluetooth connection cannot be triggered "
            f"via Windows CLI without user prompt; please select '{device_name or 'your device'}' "
            f"in the settings window to connect."
        )

        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={
                "device_name": device_name,
                "matched_device": matched_device,
                "is_known_device": matched_device is not None,
                "settings_launched": True,
                "settings_uri": "ms-settings:bluetooth",
                "message": msg,
            },
            events=["bluetooth_connect_requested", "bluetooth_settings_opened"],
        )

    def _handle_disconnect(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        """Assist disconnecting a Bluetooth device by launching ms-settings:bluetooth."""
        device_name = str(
            arguments.get("device_name")
            or arguments.get("name")
            or arguments.get("device")
            or ""
        ).strip()

        if not device_name and goal:
            m = re.search(r"disconnect(?:\s+from)?\s+([A-Za-z0-9_\s\-\'\"]+)", goal, re.I)
            if m:
                device_name = m.group(1).strip().strip("'\"")

        matched_device = self._find_device_by_name(device_name) if device_name else None

        launched, launch_err = self._open_bluetooth_settings()
        if not launched:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Failed to open Bluetooth Settings: {launch_err}",
                data={"device_name": device_name},
            )

        msg = (
            f"Opened Windows Bluetooth Settings. Direct Bluetooth disconnection cannot be triggered "
            f"via Windows CLI without user confirmation; please select '{device_name or 'your device'}' "
            f"and choose Disconnect in the settings window."
        )

        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={
                "device_name": device_name,
                "matched_device": matched_device,
                "is_known_device": matched_device is not None,
                "settings_launched": True,
                "settings_uri": "ms-settings:bluetooth",
                "message": msg,
            },
            events=["bluetooth_disconnect_requested", "bluetooth_settings_opened"],
        )

    # ── Dispatch Engine ──

    def execute(
        self,
        capability: str,
        goal: str = "",
        arguments: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> DesktopResult:
        """
        Execute requested capability on the Windows Bluetooth subsystem.

        Args:
            capability: Capability name (e.g., 'bluetooth.status', 'bluetooth.toggle').
            goal: Natural language goal description.
            arguments: Operation arguments.
            **kwargs: Extra argument overrides.

        Returns:
            DesktopResult indicating success or failure.
        """
        args = arguments.copy() if arguments else {}
        args.update(kwargs)
        cap = capability.lower().strip()

        try:
            # 1. Handle HMAC-gated mutating capabilities
            if cap in self.MUTATING_CAPABILITIES:
                enable_val = args.get("enable")
                if enable_val is None:
                    txt = f"{args.get('state', '')} {args.get('action', '')} {goal}".lower()
                    enable = False if any(w in txt for w in ["disable", "off", "stop", "false"]) else True
                else:
                    enable = bool(enable_val)

                target = f"bluetooth_radio_enable={enable}"
                action_params = {"capability": cap, "enable": enable, "target": target}

                ticket_id = args.get("approval_ticket_id")
                signature = args.get("approval_signature")

                if not ticket_id or not signature:
                    issued_ticket_id = self._auth.create_ticket(
                        action_type=cap,
                        target=target,
                        parameters=action_params,
                        description=f"Human authorization required to {'enable' if enable else 'disable'} Bluetooth radio.",
                    )
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Bluetooth operation '{cap}' modifies system hardware radio state and requires human approval.",
                        data={
                            "requires_confirmation": True,
                            "approval_ticket_id": issued_ticket_id,
                            "action_type": cap,
                            "target": target,
                            "risk_tier": "confirmation_required",
                        },
                    )

                # Verify cryptographic signature
                valid_sig, auth_err = self._auth.verify_and_redeem(
                    ticket_id, signature, action_type=cap, target=target, parameters=action_params
                )
                if not valid_sig:
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Human authorization failed: {auth_err}",
                        data={"security_alert": "unauthorized_or_forged_approval"},
                    )

                return self._handle_toggle(goal=goal, capability=capability, arguments=args)

            # 2. Read-only and assist capabilities
            if cap in ("bluetooth.status", "bluetooth.state", "bluetooth.get_status"):
                return self._handle_status(goal=goal, capability=capability, arguments=args)
            elif cap in ("bluetooth.list_devices", "bluetooth.devices", "bluetooth.list"):
                return self._handle_list_devices(goal=goal, capability=capability, arguments=args)
            elif cap == "bluetooth.connect":
                return self._handle_connect(goal=goal, capability=capability, arguments=args)
            elif cap == "bluetooth.disconnect":
                return self._handle_disconnect(goal=goal, capability=capability, arguments=args)
            else:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"Unsupported capability: {capability}",
                )

        except Exception as exc:
            logger.error(f"BluetoothManager.{cap} failed: {exc}", exc_info=True)
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Operation failed: {exc}",
            )
