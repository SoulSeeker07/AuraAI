"""
AuraAI Native Hardware & System Diagnostics Service
===================================================
Location: src/tools/system_diagnostics_service.py

Provides genuine live CPU utilization, RAM usage, storage volume breakdown,
OS build info, and machine uptime on Windows.
"""

from __future__ import annotations

import datetime
import logging
import platform
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class SystemDiagnosticsService:
    """Extracts genuine hardware and system telemetry on Windows."""

    @classmethod
    def get_full_system_report(cls) -> Dict[str, Any]:
        """
        Compiles genuine hardware telemetry (CPU, RAM, Disks, OS, Uptime)
        into a structured result with a clean Markdown formatted summary.
        """
        import psutil

        # 1. CPU
        cpu_percent = psutil.cpu_percent(interval=0.15)
        cpu_logical = psutil.cpu_count(logical=True) or 1
        cpu_physical = psutil.cpu_count(logical=False) or 1

        cpu_name = platform.processor() or "Multi-Core Processor"
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            )
            val, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            if val:
                cpu_name = str(val).strip()
        except Exception:
            pass

        # 2. RAM
        mem = psutil.virtual_memory()
        ram_total_gb = round(mem.total / (1024**3), 1)
        ram_used_gb = round(mem.used / (1024**3), 1)
        ram_free_gb = round(mem.available / (1024**3), 1)
        ram_percent = mem.percent

        # 3. Disks
        disks: List[Dict[str, Any]] = []
        for part in psutil.disk_partitions(all=False):
            if "cdrom" in part.opts or part.fstype == "":
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
                total_gb = round(usage.total / (1024**3), 1)
                free_gb = round(usage.free / (1024**3), 1)
                used_gb = round(usage.used / (1024**3), 1)
                disks.append({
                    "mount": part.mountpoint,
                    "total_gb": total_gb,
                    "used_gb": used_gb,
                    "free_gb": free_gb,
                    "percent": usage.percent,
                })
            except Exception:
                pass

        # 4. OS & Uptime
        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.datetime.now() - boot_time
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)
        uptime_str = f"{hours}h {minutes}m"

        os_str = f"{platform.system()} {platform.release()} (Build {platform.version()})"

        # Visual CPU and RAM Gauges
        def make_gauge(pct: float) -> str:
            blocks = int(pct / 10)
            return "█" * blocks + "░" * (10 - blocks)

        cpu_gauge = make_gauge(cpu_percent)
        ram_gauge = make_gauge(ram_percent)

        # Markdown formatting
        lines = [
            "⚡ **System Hardware Diagnostics & Telemetry**\n",
            "| Metric | Telemetry Value |",
            "| :--- | :--- |",
            f"| **CPU Model** | `{cpu_name}` |",
            f"| **CPU Cores** | {cpu_physical} Physical / {cpu_logical} Logical |",
            f"| **CPU Utilization** | `{cpu_gauge}` **{cpu_percent}%** |",
            f"| **RAM Memory** | `{ram_gauge}` **{ram_percent}%** ({ram_used_gb} GB / {ram_total_gb} GB) |",
            f"| **Operating System** | {os_str} |",
            f"| **System Uptime** | ⏱️ **{uptime_str}** |",
        ]

        if disks:
            lines.append("\n💾 **Storage Volumes:**")
            for d in disks:
                d_gauge = make_gauge(d["percent"])
                lines.append(
                    f"- **Drive {d['mount']}** `{d_gauge}` **{d['percent']}%** "
                    f"({d['free_gb']} GB free of {d['total_gb']} GB)"
                )

        report_md = "\n".join(lines)

        return {
            "cpu": {
                "name": cpu_name,
                "usage_percent": cpu_percent,
                "cores_physical": cpu_physical,
                "cores_logical": cpu_logical,
            },
            "ram": {
                "total_gb": ram_total_gb,
                "used_gb": ram_used_gb,
                "free_gb": ram_free_gb,
                "usage_percent": ram_percent,
            },
            "disks": disks,
            "uptime": uptime_str,
            "os": os_str,
            "markdown": report_md,
        }
