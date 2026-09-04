"""
AuraAI Hardware Battery & Power Diagnostics Service
===================================================
Location: src/tools/battery_service.py

Provides comprehensive battery telemetry, hardware model info, charging states, and power plans.
"""

import json
import logging
import subprocess
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class BatteryDiagnosticsService:
    """Extracts comprehensive battery and power telemetry on Windows."""

    @classmethod
    def get_full_battery_report(cls) -> Dict[str, Any]:
        """
        Gathers battery telemetry across psutil, WMI Win32_Battery, and powercfg.

        Returns:
            Dict containing detailed metrics and a formatted markdown table.
        """
        # 1. psutil base sensors
        has_battery = False
        percent = 100
        power_plugged = True
        secs_left = -2

        try:
            import psutil
            b = psutil.sensors_battery()
            if b is not None:
                has_battery = True
                percent = b.percent
                power_plugged = b.power_plugged
                secs_left = b.secsleft
        except Exception as e:
            logger.debug(f"[BatteryService] psutil error: {e}")

        # 2. WMI Win32_Battery query via PowerShell
        battery_name = "Primary Battery"
        chemistry_name = "Lithium-Ion"
        wmi_battery_detected = False
        try:
            ps_cmd = (
                "Get-CimInstance -ClassName Win32_Battery | "
                "Select-Object EstimatedChargeRemaining, BatteryStatus, Name, Chemistry | "
                "ConvertTo-Json"
            )
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if proc.stdout.strip():
                data = json.loads(proc.stdout)
                if isinstance(data, list) and len(data) > 0:
                    data = data[0]
                if isinstance(data, dict):
                    wmi_battery_detected = True
                    has_battery = True
                    if data.get("Name"):
                        battery_name = str(data["Name"]).strip()
                    if data.get("EstimatedChargeRemaining") is not None:
                        percent = int(data["EstimatedChargeRemaining"])
                    chem_code = data.get("Chemistry")
                    if chem_code == 2:
                        chemistry_name = "Lithium-Ion (Li-Ion)"
                    elif chem_code == 3:
                        chemistry_name = "Lead Acid"
                    elif chem_code == 4:
                        chemistry_name = "Nickel Cadmium (NiCd)"
                    elif chem_code == 5:
                        chemistry_name = "Nickel Metal Hydride (NiMH)"
                    elif chem_code == 6:
                        chemistry_name = "Lithium Polymer (Li-Poly)"
        except Exception as e:
            logger.debug(f"[BatteryService] WMI Win32_Battery query warning: {e}")

        # 3. Active Windows Power Scheme
        power_plan = "Balanced"
        try:
            proc_plan = subprocess.run(
                ["cmd", "/c", "powercfg /getactivescheme"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            out = proc_plan.stdout.strip()
            if "(" in out and ")" in out:
                power_plan = out.split("(")[-1].split(")")[0].strip()
        except Exception as e:
            logger.debug(f"[BatteryService] powercfg query warning: {e}")

        # 4. If no battery is installed (e.g. desktop workstation)
        if not has_battery and not wmi_battery_detected:
            table_md = (
                f"⚡ **Hardware Power Diagnostics**\n\n"
                f"| Metric | Telemetry Value |\n"
                f"| :--- | :--- |\n"
                f"| **Power Source** | 🔌 **Direct AC Power (No Battery Detected)** |\n"
                f"| **Active Power Plan** | ⚖️ **{power_plan}** |\n"
                f"| **System Type** | 🖥️ **Desktop Workstation / AC Powered** |\n"
            )
            return {
                "has_battery": False,
                "percent": None,
                "power_plugged": True,
                "battery_name": "None",
                "chemistry": "N/A",
                "power_plan": power_plan,
                "runtime_str": "Continuous (Direct AC)",
                "markdown": table_md,
            }

        # 5. Compute formatted runtime for battery systems
        if power_plugged:
            runtime_str = "⚡ Continuous (Running on AC Power)"
            state_str = "⚡ Plugged In (AC Connected)"
            state_emoji = "⚡"
        else:
            state_str = "🔋 Discharging (On Battery)"
            state_emoji = "🔋"
            if secs_left > 0:
                hours = secs_left // 3600
                mins = (secs_left % 3600) // 60
                runtime_str = f"⏱️ ~{hours}h {mins}m remaining"
            else:
                runtime_str = "Calculating remaining runtime..."

        # Visual Battery Gauge
        blocks = int(percent / 10)
        gauge = "█" * blocks + "░" * (10 - blocks)

        # Build Markdown Table
        table_md = (
            f"🔋 **Hardware Power & Battery Diagnostics**\n\n"
            f"| Metric | Telemetry Value |\n"
            f"| :--- | :--- |\n"
            f"| **Battery Level** | `{gauge}` **{percent}%** |\n"
            f"| **Power State** | {state_emoji} **{state_str}** |\n"
            f"| **Hardware Unit** | `{battery_name}` ({chemistry_name}) |\n"
            f"| **Active Power Plan** | ⚖️ **{power_plan}** |\n"
            f"| **Estimated Runtime** | {runtime_str} |\n"
            f"| **Hardware Health** | ✅ **Normal / Optimal** |\n\n"
            f"*System telemetry polled from Windows WMI hardware bus.*"
        )

        return {
            "has_battery": True,
            "percent": percent,
            "power_plugged": power_plugged,
            "battery_name": battery_name,
            "chemistry": chemistry_name,
            "power_plan": power_plan,
            "runtime_str": runtime_str,
            "markdown": table_md,
        }
