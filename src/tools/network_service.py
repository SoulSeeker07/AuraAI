"""
AuraAI Native Wi-Fi & Network Diagnostics Service
=================================================
Location: src/tools/network_service.py

Provides genuine real-time Wi-Fi telemetry, connected SSID/signal strength,
active network adapter information (IPv4/IPv6, Gateway, DNS), and radio control on Windows.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class NetworkDiagnosticsService:
    """Extracts genuine live Wi-Fi and network telemetry on Windows."""

    @classmethod
    def get_wifi_radio_state(cls) -> str:
        """
        Queries Windows Runtime (WinRT) for the live Wi-Fi Radio state.
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
            "$wifiRadio = $radios | Where-Object { $_.Kind -eq [Windows.Devices.Radios.RadioKind]::WiFi } | Select-Object -First 1; "
            "if ($wifiRadio) { Write-Output $wifiRadio.State.ToString(); exit }; "
            "} catch {}; "
            "$wlan = netsh wlan show interfaces; "
            "if ($wlan -match 'State\\s*:\\s*connected|State\\s*:\\s*disconnected') { Write-Output 'On' } else { Write-Output 'Off' }"
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
            logger.debug(f"[NetworkService] Wi-Fi radio query warning: {e}")
        return "Unknown"

    @classmethod
    def get_wifi_interface_info(cls) -> Dict[str, Any]:
        """
        Extracts genuine Wi-Fi connection info: SSID, Signal %, Radio type, State.
        """
        info: Dict[str, Any] = {
            "connected": False,
            "ssid": "",
            "signal": "",
            "state": "disconnected",
            "radio_type": "",
        }
        try:
            proc = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            for line in proc.stdout.splitlines():
                line = line.strip()
                if line.startswith("SSID") and not line.startswith("BSSID"):
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        info["ssid"] = parts[1].strip()
                elif line.startswith("Signal"):
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        info["signal"] = parts[1].strip()
                elif line.startswith("State"):
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        st = parts[1].strip().lower()
                        info["state"] = st
                        if st == "connected":
                            info["connected"] = True
                elif line.startswith("Radio type"):
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        info["radio_type"] = parts[1].strip()
        except Exception as e:
            logger.debug(f"[NetworkService] netsh wlan query warning: {e}")

        return info

    @classmethod
    def get_active_ip_adapters(cls) -> List[Dict[str, Any]]:
        """
        Extracts genuine active network adapters (IPv4, Gateway, DNS).
        """
        ps = (
            "$ErrorActionPreference = 'SilentlyContinue'; "
            "$adapters = @(); "
            "try { "
            "  $net = Get-NetIPConfiguration | Where-Object { $_.IPv4Address -and $_.NetAdapter.Status -eq 'Up' }; "
            "  foreach ($n in $net) { "
            "    $adapters += [PSCustomObject]@{ "
            "      InterfaceAlias = $n.InterfaceAlias; "
            "      IPv4Address = $n.IPv4Address.IPAddress; "
            "      IPv4DefaultGateway = if ($n.IPv4DefaultGateway) { $n.IPv4DefaultGateway.NextHop } else { 'N/A' }; "
            "      DNSServer = ($n.DNSServer.ServerAddresses -join ', ') "
            "    }; "
            "  } "
            "} catch {}; "
            "$adapters | ConvertTo-Json -Depth 2"
        )
        adapters: List[Dict[str, Any]] = []
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                capture_output=True,
                text=True,
                timeout=5,
            )
            out = proc.stdout.strip()
            if out:
                parsed = json.loads(out)
                if isinstance(parsed, dict):
                    parsed = [parsed]
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and item.get("InterfaceAlias"):
                            adapters.append({
                                "alias": str(item["InterfaceAlias"]).strip(),
                                "ipv4": str(item.get("IPv4Address", "")).strip(),
                                "gateway": str(item.get("IPv4DefaultGateway", "N/A")).strip(),
                                "dns": str(item.get("DNSServer", "")).strip(),
                            })
        except Exception as e:
            logger.debug(f"[NetworkService] NetIPConfiguration query warning: {e}")

        return adapters

    @classmethod
    def get_full_network_report(cls, wifi_only: bool = False) -> Dict[str, Any]:
        """
        Compiles genuine Wi-Fi and network configuration report in Markdown format.
        """
        wifi_state = cls.get_wifi_radio_state()
        wifi_info = cls.get_wifi_interface_info()
        adapters = cls.get_active_ip_adapters()

        lines: List[str] = []

        if wifi_only or wifi_info.get("connected"):
            lines.append("📶 **Wi-Fi Network Status**")
            lines.append(f"- **Radio State:** {'Enabled (On)' if wifi_state == 'On' else wifi_state}")
            if wifi_info.get("connected") and wifi_info.get("ssid"):
                lines.append(f"- **Connected SSID:** **{wifi_info['ssid']}**")
                if wifi_info.get("signal"):
                    lines.append(f"- **Signal Strength:** {wifi_info['signal']}")
                if wifi_info.get("radio_type"):
                    lines.append(f"- **Protocol / Radio:** {wifi_info['radio_type']}")
            else:
                lines.append("- **Connection:** *(Not connected to any Wi-Fi network)*")

        if not wifi_only:
            if not lines:
                lines.append("🌐 **Network & IP Configuration**")
            else:
                lines.append("\n🌐 **Active Network Adapters:**")

            if adapters:
                for a in adapters:
                    gw_str = f" | Gateway: `{a['gateway']}`" if a['gateway'] != "N/A" else ""
                    lines.append(f"- **{a['alias']}:** IP `{a['ipv4']}`{gw_str}")
            else:
                lines.append("- *(No active IP adapters detected)*")

        report_md = "\n".join(lines)

        return {
            "wifi_state": wifi_state,
            "wifi_info": wifi_info,
            "adapters": adapters,
            "markdown": report_md,
        }

    @classmethod
    def set_wifi_state(cls, enable: bool) -> Dict[str, Any]:
        """
        Enables or disables Wi-Fi radio using Windows Runtime (WinRT) APIs.
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
            "$radio=(&$getRadios)|?{$_.Kind -eq [Windows.Devices.Radios.RadioKind]::WiFi}|Select-Object -First 1; "
            "if($null -eq $radio){Write-Output 'NO_RADIO'; exit}; "
            "$setStatus={$asTask.MakeGenericMethod([Windows.Devices.Radios.RadioAccessStatus]).Invoke($null,@($radio.SetStateAsync($args[0]))).Result}; "
            f"$status = &$setStatus ([Windows.Devices.Radios.RadioState]::{target_state}); "
            "Start-Sleep -Milliseconds 1000; "
            "$radio2=(&$getRadios)|?{$_.Kind -eq [Windows.Devices.Radios.RadioKind]::WiFi}|Select-Object -First 1; "
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
                    "message": f"📶 Wi-Fi {action_word} successfully.",
                }
            elif "NO_RADIO" in out:
                return {
                    "success": False,
                    "state": "Not Found",
                    "message": "⚠️ No Wi-Fi adapter detected on this system.",
                }
            else:
                return {
                    "success": False,
                    "state": "Error",
                    "message": f"⚠️ Could not set Wi-Fi state: {out}",
                }
        except Exception as e:
            return {
                "success": False,
                "state": "Error",
                "message": f"⚠️ Wi-Fi control error: {e}",
            }
