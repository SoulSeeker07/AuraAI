"""
AuraAI Native Bluetooth Diagnostics & Control Service
=====================================================
Location: src/tools/bluetooth_service.py

Provides genuine real-time Bluetooth telemetry, radio state querying,
paired & connected peripheral status inspection, and radio control on Windows.
"""

from __future__ import annotations

import json
import logging
import subprocess
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class BluetoothDiagnosticsService:
    """Extracts genuine live Bluetooth radio telemetry and paired device states on Windows."""

    @classmethod
    def get_radio_state(cls) -> str:
        """
        Queries Windows Runtime (WinRT) for the live Bluetooth Radio state.
        Returns: 'On', 'Off', 'Disabled', or 'Not Present'.
        """
        ps = (
            "$ErrorActionPreference = 'SilentlyContinue'; "
            "try { "
            "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
            "$null = [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime]; "
            "$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]; "
            "$getRadios = { $asTask.MakeGenericMethod([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]]).Invoke($null, @([Windows.Devices.Radios.Radio]::GetRadiosAsync())).Result }; "
            "$radios = &$getRadios; "
            "$btRadio = $radios | Where-Object { $_.Kind -eq [Windows.Devices.Radios.RadioKind]::Bluetooth } | Select-Object -First 1; "
            "if ($btRadio) { Write-Output $btRadio.State.ToString(); exit }; "
            "} catch {}; "
            "# Fallback to checking bthserv service "
            "$svc = Get-Service bthserv -ErrorAction SilentlyContinue; "
            "if ($svc -and $svc.Status -eq 'Running') { Write-Output 'On' } else { Write-Output 'Off' }"
        )
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                capture_output=True,
                text=True,
                timeout=5,
            )
            out = proc.stdout.strip()
            if out in ("On", "Off", "Disabled"):
                return out
        except Exception as e:
            logger.debug(f"[BluetoothService] Radio query warning: {e}")
        return "Unknown"

    @classmethod
    def get_paired_devices(cls) -> List[Dict[str, Any]]:
        """
        Queries Windows PnP subsystem for real paired Bluetooth peripherals
        and determines their live connection state and device properties.
        """
        ps = (
            "$ErrorActionPreference = 'SilentlyContinue'; "
            "$devices = @(); "
            "try { "
            "  $pnp = Get-PnpDevice -Class Bluetooth | Where-Object { "
            "    $_.FriendlyName -and "
            "    $_.FriendlyName -notmatch 'Enumerator|Protocol|Service|Attribute|Transport|Adapter|Intel\\(R\\)|Microsoft|Generic' "
            "  }; "
            "  $seen = @{}; "
            "  foreach ($d in $pnp) { "
            "    $name = $d.FriendlyName.Trim(); "
            "    if ($seen.ContainsKey($name)) { continue }; "
            "    $seen[$name] = $true; "
            "    $isConnected = $false; "
            "    try { "
            "      $prop = Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName '{83da6326-97a6-4088-9453-a1923f573b29} 15' -ErrorAction SilentlyContinue; "
            "      if ($prop -and $prop.Data -eq $true) { $isConnected = $true } "
            "    } catch {}; "
            "    $devices += [PSCustomObject]@{ "
            "      Name = $name; "
            "      Status = $d.Status; "
            "      Present = $d.Present; "
            "      Connected = $isConnected "
            "    }; "
            "  } "
            "} catch {}; "
            "$devices | ConvertTo-Json -Depth 2"
        )
        devices: List[Dict[str, Any]] = []
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                capture_output=True,
                text=True,
                timeout=6,
            )
            out = proc.stdout.strip()
            if out:
                parsed = json.loads(out)
                if isinstance(parsed, dict):
                    parsed = [parsed]
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and item.get("Name"):
                            devices.append({
                                "name": str(item["Name"]).strip(),
                                "status": str(item.get("Status", "OK")),
                                "present": bool(item.get("Present", True)),
                                "connected": bool(item.get("Connected", False)),
                            })
        except Exception as e:
            logger.debug(f"[BluetoothService] Device query warning: {e}")

        return devices

    @classmethod
    def get_full_bluetooth_report(cls) -> Dict[str, Any]:
        """
        Compiles genuine Bluetooth radio state and paired/connected devices list
        into a structured result with a clean Markdown formatted summary.
        """
        radio_state = cls.get_radio_state()
        devices = cls.get_paired_devices()

        connected_devices = [d for d in devices if d.get("connected")]
        paired_devices = [d for d in devices if not d.get("connected")]

        if radio_state == "On":
            state_str = "Enabled (On)"
            state_icon = "🔵"
        elif radio_state == "Off":
            state_str = "Disabled (Off)"
            state_icon = "⚪"
        else:
            state_str = f"Status: {radio_state}"
            state_icon = "⚠️"

        lines = [
            f"{state_icon} **Bluetooth Status**",
            f"- **State:** {state_str}",
            f"- **Connected Devices:** {len(connected_devices)}",
        ]

        if connected_devices:
            for idx, dev in enumerate(connected_devices, 1):
                lines.append(f"  - **Device {idx}:** {dev['name']} *(Connected)*")
        else:
            lines.append("  - *(No devices currently connected)*")

        if paired_devices:
            lines.append(f"- **Paired Devices ({len(paired_devices)}):**")
            for dev in paired_devices[:6]:
                lines.append(f"  - • {dev['name']} *(Paired / Idle)*")
            if len(paired_devices) > 6:
                lines.append(f"  - • ...and {len(paired_devices) - 6} more paired devices.")

        report_md = "\n".join(lines)

        return {
            "radio_state": radio_state,
            "connected_count": len(connected_devices),
            "connected_devices": connected_devices,
            "paired_devices": paired_devices,
            "total_paired": len(devices),
            "markdown": report_md,
        }

    @classmethod
    def set_radio_state(cls, enable: bool) -> Dict[str, Any]:
        """
        Enables or disables Bluetooth radio using Windows Runtime (WinRT) APIs.
        """
        target_state = "On" if enable else "Off"
        ps = (
            "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
            "[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime]|Out-Null; "
            "[Windows.Devices.Radios.RadioAccessStatus,Windows.System.Devices,ContentType=WindowsRuntime]|Out-Null; "
            "$asTask=([System.WindowsRuntimeSystemExtensions].GetMethods()|"
            "?{$_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and "
            "$_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'})[0]; "
            "$getRadios={$asTask.MakeGenericMethod([System.Collections.Generic.IReadOnlyList"
            "[Windows.Devices.Radios.Radio]]).Invoke($null,@([Windows.Devices.Radios.Radio]"
            "::GetRadiosAsync())).Result}; "
            "$radio=(&$getRadios)|?{$_.Kind -eq [Windows.Devices.Radios.RadioKind]::Bluetooth}|Select-Object -First 1; "
            "if($null -eq $radio){Write-Output 'NO_RADIO'; exit}; "
            "$setStatus={$asTask.MakeGenericMethod([Windows.Devices.Radios.RadioAccessStatus]).Invoke($null,@($radio.SetStateAsync($args[0]))).Result}; "
            f"$status = &$setStatus ([Windows.Devices.Radios.RadioState]::{target_state}); "
            "Start-Sleep -Milliseconds 1000; "
            "$radio2=(&$getRadios)|?{$_.Kind -eq [Windows.Devices.Radios.RadioKind]::Bluetooth}|Select-Object -First 1; "
            f"if($status -eq [Windows.Devices.Radios.RadioAccessStatus]::Allowed -and $radio2.State -eq [Windows.Devices.Radios.RadioState]::{target_state}){{"
            "Write-Output 'OK'}else{Write-Output ('ERR:Status='+$status.ToString()+' State='+$radio2.State.ToString())}"
        )
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                capture_output=True,
                text=True,
                timeout=12,
            )
            out = (proc.stdout or "").strip()
            success = "OK" in out
            action_word = "enabled" if enable else "disabled"
            if success:
                return {
                    "success": True,
                    "state": target_state,
                    "message": f"🔵 Bluetooth {action_word} successfully.",
                }
            elif "NO_RADIO" in out:
                return {
                    "success": False,
                    "state": "Not Found",
                    "message": "⚠️ No Bluetooth adapter detected on this system.",
                }
            else:
                return {
                    "success": False,
                    "state": "Error",
                    "message": f"⚠️ Could not set Bluetooth state: {out}",
                }
        except Exception as e:
            return {
                "success": False,
                "state": "Error",
                "message": f"⚠️ Bluetooth control error: {e}",
            }
