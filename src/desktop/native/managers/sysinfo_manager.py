"""
System Information Manager — Native Windows System Diagnostics & Metrics
Location: src/desktop/native/managers/sysinfo_manager.py

Provides read-only system telemetry, hardware metrics, and environment diagnostics
including operating system details, CPU topology/utilization, RAM/Swap metrics,
disk partition usage, GPU hardware info via PowerShell CimInstance, system uptime,
and environment variables.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import platform
import socket
import subprocess
from typing import Any

try:
    import psutil
except ImportError:
    psutil = None

from ..desktop_result import DesktopResult
from .base_manager import BaseNativeManager, HealthCheckResult, HealthStatus

logger = logging.getLogger(__name__)


class SystemInfoManager(BaseNativeManager):
    """
    Manages system information, hardware statistics, and environment metrics.

    All capabilities are read-only telemetry operations requiring no HMAC authorization gates.

    Capabilities:
    - sysinfo.os: Operating system metadata, version, architecture, and current user
    - sysinfo.cpu: CPU topology (logical & physical), frequency, processor model, and usage percent
    - sysinfo.ram: Virtual memory and swap statistics (total, available, used, percent)
    - sysinfo.disk: Storage partition enumeration with per-mountpoint disk usage
    - sysinfo.gpu: GPU adapter details (name, driver version, VRAM) via PowerShell CimInstance
    - sysinfo.uptime: System boot timestamp and formatted uptime duration
    - sysinfo.environment_vars: Environment variable listing with optional key filtering
    - sysinfo.summary: Aggregated system overview combining OS, CPU, RAM, disk, and uptime
    """

    NAME = "sysinfo"
    VERSION = "1.0"
    PRIORITY = 25
    DEPENDENCIES: list[str] = ["psutil"]

    def __init__(self) -> None:
        """Initialize SystemInfoManager."""
        super().__init__()
        self._initialized = False

    @property
    def name(self) -> str:
        """Get manager name."""
        return self.NAME

    @property
    def capabilities(self) -> list[str]:
        """Get list of capabilities supported by SystemInfoManager."""
        return [
            "sysinfo.os",
            "sysinfo.cpu",
            "sysinfo.ram",
            "sysinfo.disk",
            "sysinfo.gpu",
            "sysinfo.uptime",
            "sysinfo.environment_vars",
            "sysinfo.summary",
        ]

    def initialize(self) -> bool:
        """Initialize system info manager."""
        self._initialized = True
        return True

    def health_check(self) -> HealthCheckResult:
        """
        Perform health check on SystemInfoManager and dependencies.

        Returns:
            HealthCheckResult indicating healthy or degraded status.
        """
        missing: list[str] = []
        if psutil is None:
            missing.append("psutil")

        status = HealthStatus.HEALTHY if not missing else HealthStatus.DEGRADED
        available_count = len(self.capabilities) if not missing else 2

        return HealthCheckResult(
            manager_name=self.name,
            status=status,
            missing_dependencies=missing,
            available_fallbacks=[],
            total_capabilities=len(self.capabilities),
            available_capabilities=available_count,
            details={
                "initialized": self._initialized,
                "psutil_available": psutil is not None,
            },
        )

    def shutdown(self) -> None:
        """Shutdown manager and clean up resources."""
        self._initialized = False

    def execute(
        self,
        capability: str,
        goal: str = "",
        arguments: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> DesktopResult:
        """
        Dispatch and execute system information capabilities.

        Args:
            capability: Target capability name.
            goal: High-level user goal.
            arguments: Optional operation parameters.
            **kwargs: Additional parameters.

        Returns:
            DesktopResult with system information data or failure details.
        """
        args = arguments or {}
        cap = capability.lower().strip()

        try:
            if cap in ("sysinfo.os", "os"):
                return self._handle_os(goal=goal, capability=capability, arguments=args)
            elif cap in ("sysinfo.cpu", "cpu"):
                return self._handle_cpu(goal=goal, capability=capability, arguments=args)
            elif cap in ("sysinfo.ram", "ram", "memory"):
                return self._handle_ram(goal=goal, capability=capability, arguments=args)
            elif cap in ("sysinfo.disk", "disk", "disks"):
                return self._handle_disk(goal=goal, capability=capability, arguments=args)
            elif cap in ("sysinfo.gpu", "gpu"):
                return self._handle_gpu(goal=goal, capability=capability, arguments=args)
            elif cap in ("sysinfo.uptime", "uptime"):
                return self._handle_uptime(goal=goal, capability=capability, arguments=args)
            elif cap in ("sysinfo.environment_vars", "sysinfo.env", "environment_vars", "env"):
                return self._handle_environment_vars(goal=goal, capability=capability, arguments=args)
            elif cap in ("sysinfo.summary", "sysinfo.overview", "summary", "overview"):
                return self._handle_summary(goal=goal, capability=capability, arguments=args)
            else:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"Unsupported capability: {capability}",
                )
        except Exception as exc:
            logger.error(f"SystemInfoManager.{cap} failed: {exc}", exc_info=True)
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Operation failed: {exc}",
            )

    # ==================== Internal Helpers ====================

    def _get_os_info(self) -> dict[str, Any]:
        """Collect operating system details."""
        username = ""
        try:
            username = os.getlogin()
        except Exception:
            username = os.environ.get("USERNAME") or os.environ.get("USER") or ""

        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "username": username,
            "platform": platform.platform(),
            "architecture": list(platform.architecture()),
            "hostname": socket.gethostname(),
        }

    def _get_cpu_info(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Collect CPU topology, frequency, and load."""
        if psutil is None:
            raise RuntimeError("psutil is not installed")

        interval = float(arguments.get("interval", 0.5))
        physical_cores = psutil.cpu_count(logical=False)
        logical_cores = psutil.cpu_count(logical=True)
        processor = platform.processor()

        freq_data = None
        try:
            freq = psutil.cpu_freq()
            if freq:
                freq_data = {
                    "current_mhz": freq.current,
                    "min_mhz": freq.min,
                    "max_mhz": freq.max,
                }
        except Exception as exc:
            logger.warning(f"Could not retrieve CPU frequency: {exc}")

        usage_percent = None
        try:
            usage_percent = psutil.cpu_percent(interval=interval)
        except Exception as exc:
            logger.warning(f"Could not retrieve CPU percentage: {exc}")

        result: dict[str, Any] = {
            "physical_cores": physical_cores,
            "logical_cores": logical_cores,
            "processor": processor,
            "frequency": freq_data,
            "usage_percent": usage_percent,
        }

        if arguments.get("per_cpu", False):
            try:
                result["per_cpu_percent"] = psutil.cpu_percent(interval=None, percpu=True)
            except Exception as exc:
                logger.warning(f"Could not retrieve per-CPU percentage: {exc}")

        return result

    def _get_ram_info(self) -> dict[str, Any]:
        """Collect virtual and swap memory statistics."""
        if psutil is None:
            raise RuntimeError("psutil is not installed")

        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()

        return {
            "total": vm.total,
            "available": vm.available,
            "used": vm.used,
            "free": vm.free,
            "percent": vm.percent,
            "total_gb": round(vm.total / (1024**3), 2),
            "available_gb": round(vm.available / (1024**3), 2),
            "used_gb": round(vm.used / (1024**3), 2),
            "swap": {
                "total": swap.total,
                "used": swap.used,
                "free": swap.free,
                "percent": swap.percent,
                "sin": getattr(swap, "sin", 0),
                "sout": getattr(swap, "sout", 0),
                "total_gb": round(swap.total / (1024**3), 2),
                "used_gb": round(swap.used / (1024**3), 2),
            },
        }

    def _get_disk_info(self, arguments: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        """Enumerate storage partitions and usage."""
        if psutil is None:
            raise RuntimeError("psutil is not installed")

        include_all = bool(arguments.get("all", False))
        partitions = psutil.disk_partitions(all=include_all)
        partition_list: list[dict[str, Any]] = []
        warnings: list[str] = []

        for part in partitions:
            part_data: dict[str, Any] = {
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "opts": part.opts,
                "usage": None,
            }
            try:
                usage = psutil.disk_usage(part.mountpoint)
                part_data["usage"] = {
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "percent": usage.percent,
                    "total_gb": round(usage.total / (1024**3), 2),
                    "used_gb": round(usage.used / (1024**3), 2),
                    "free_gb": round(usage.free / (1024**3), 2),
                }
            except Exception as exc:
                part_data["error"] = str(exc)
                warnings.append(f"Failed to query disk usage for {part.mountpoint}: {exc}")

            partition_list.append(part_data)

        return {
            "partitions": partition_list,
            "partition_count": len(partition_list),
        }, warnings

    def _get_gpu_info(self) -> tuple[list[dict[str, Any]], list[str]]:
        """Query GPU adapters via PowerShell Win32_VideoController."""
        gpus: list[dict[str, Any]] = []
        warnings: list[str] = []
        cmd = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, AdapterRAM | ConvertTo-Json -Compress",
        ]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode != 0:
                err_msg = proc.stderr.strip() or f"PowerShell exited with code {proc.returncode}"
                logger.warning(f"GPU detection command failed: {err_msg}")
                warnings.append(f"GPU query warning: {err_msg}")
                return [], warnings

            stdout = proc.stdout.strip()
            if not stdout:
                return [], warnings

            parsed = json.loads(stdout)
            raw_list = [parsed] if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])

            for item in raw_list:
                if not isinstance(item, dict):
                    continue
                name = item.get("Name") or "Unknown GPU"
                driver = item.get("DriverVersion") or "Unknown"
                adapter_ram = item.get("AdapterRAM")
                ram_mb = None
                ram_gb = None
                if isinstance(adapter_ram, (int, float)) and adapter_ram > 0:
                    ram_mb = round(adapter_ram / (1024**2), 2)
                    ram_gb = round(adapter_ram / (1024**3), 2)

                gpus.append({
                    "name": name,
                    "driver_version": driver,
                    "adapter_ram": adapter_ram,
                    "adapter_ram_mb": ram_mb,
                    "adapter_ram_gb": ram_gb,
                })
        except subprocess.TimeoutExpired:
            msg = "PowerShell GPU detection query timed out after 10s"
            logger.warning(msg)
            warnings.append(msg)
        except Exception as exc:
            msg = f"Failed to detect GPU: {exc}"
            logger.warning(msg)
            warnings.append(msg)

        return gpus, warnings

    def _get_uptime_info(self) -> dict[str, Any]:
        """Calculate system uptime from boot time."""
        if psutil is None:
            raise RuntimeError("psutil is not installed")

        boot_time = psutil.boot_time()
        now = datetime.datetime.now().timestamp()
        uptime_seconds = max(0.0, now - boot_time)
        boot_dt = datetime.datetime.fromtimestamp(boot_time)

        uptime_delta = datetime.timedelta(seconds=int(uptime_seconds))
        days = uptime_delta.days
        hours, rem = divmod(uptime_delta.seconds, 3600)
        minutes, seconds = divmod(rem, 60)

        return {
            "boot_time": boot_time,
            "boot_time_iso": boot_dt.isoformat(),
            "uptime_seconds": round(uptime_seconds, 2),
            "uptime_days": days,
            "uptime_hours": hours,
            "uptime_minutes": minutes,
            "uptime_formatted": f"{days} days, {hours:02d}:{minutes:02d}:{seconds:02d}",
        }

    # ==================== Capability Handlers ====================

    def _handle_os(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        """Handle sysinfo.os capability."""
        data = self._get_os_info()
        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data=data,
            events=["sysinfo_os_retrieved"],
        )

    def _handle_cpu(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        """Handle sysinfo.cpu capability."""
        if psutil is None:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="psutil dependency is not installed",
            )

        data = self._get_cpu_info(arguments)
        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data=data,
            events=["sysinfo_cpu_retrieved"],
        )

    def _handle_ram(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        """Handle sysinfo.ram capability."""
        if psutil is None:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="psutil dependency is not installed",
            )

        data = self._get_ram_info()
        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data=data,
            events=["sysinfo_ram_retrieved"],
        )

    def _handle_disk(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        """Handle sysinfo.disk capability."""
        if psutil is None:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="psutil dependency is not installed",
            )

        data, warnings = self._get_disk_info(arguments)
        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data=data,
            events=["sysinfo_disk_retrieved"],
            warnings=warnings if warnings else None,
        )

    def _handle_gpu(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        """Handle sysinfo.gpu capability."""
        gpus, warnings = self._get_gpu_info()
        data = {
            "gpus": gpus,
            "count": len(gpus),
        }
        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data=data,
            events=["sysinfo_gpu_retrieved"],
            warnings=warnings if warnings else None,
        )

    def _handle_uptime(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        """Handle sysinfo.uptime capability."""
        if psutil is None:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="psutil dependency is not installed",
            )

        data = self._get_uptime_info()
        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data=data,
            events=["sysinfo_uptime_retrieved"],
        )

    def _handle_environment_vars(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        """Handle sysinfo.environment_vars capability."""
        filter_str = arguments.get("filter")
        all_vars = dict(os.environ)

        if filter_str:
            filter_lower = str(filter_str).lower()
            filtered = {
                k: v for k, v in all_vars.items()
                if filter_lower in k.lower()
            }
            data = {
                "environment_variables": filtered,
                "count": len(filtered),
                "total_count": len(all_vars),
                "filter": filter_str,
            }
        else:
            data = {
                "environment_variables": all_vars,
                "count": len(all_vars),
            }

        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data=data,
            events=["sysinfo_environment_vars_retrieved"],
        )

    def _handle_summary(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        """Handle sysinfo.summary capability combining OS, CPU, RAM, disk, and uptime."""
        summary: dict[str, Any] = {}
        warnings: list[str] = []

        # 1. OS info
        try:
            summary["os"] = self._get_os_info()
        except Exception as exc:
            logger.warning(f"OS info query failed in summary: {exc}")
            summary["os"] = {"error": str(exc)}
            warnings.append(f"OS info failed: {exc}")

        # 2. CPU info
        if psutil:
            try:
                cpu_interval = float(arguments.get("cpu_interval", 0.2))
                summary["cpu"] = self._get_cpu_info({"interval": cpu_interval})
            except Exception as exc:
                logger.warning(f"CPU info query failed in summary: {exc}")
                summary["cpu"] = {"error": str(exc)}
                warnings.append(f"CPU info failed: {exc}")
        else:
            summary["cpu"] = {"error": "psutil not available"}

        # 3. RAM info
        if psutil:
            try:
                summary["ram"] = self._get_ram_info()
            except Exception as exc:
                logger.warning(f"RAM info query failed in summary: {exc}")
                summary["ram"] = {"error": str(exc)}
                warnings.append(f"RAM info failed: {exc}")
        else:
            summary["ram"] = {"error": "psutil not available"}

        # 4. Disk info
        if psutil:
            try:
                disk_data, disk_warn = self._get_disk_info(arguments)
                summary["disk"] = disk_data
                warnings.extend(disk_warn)
            except Exception as exc:
                logger.warning(f"Disk info query failed in summary: {exc}")
                summary["disk"] = {"error": str(exc)}
                warnings.append(f"Disk info failed: {exc}")
        else:
            summary["disk"] = {"error": "psutil not available"}

        # 5. Uptime info
        if psutil:
            try:
                summary["uptime"] = self._get_uptime_info()
            except Exception as exc:
                logger.warning(f"Uptime info query failed in summary: {exc}")
                summary["uptime"] = {"error": str(exc)}
                warnings.append(f"Uptime info failed: {exc}")
        else:
            summary["uptime"] = {"error": "psutil not available"}

        # Optional GPU info if requested
        if arguments.get("include_gpu", False):
            try:
                gpus, gpu_warn = self._get_gpu_info()
                summary["gpu"] = {"gpus": gpus, "count": len(gpus)}
                warnings.extend(gpu_warn)
            except Exception as exc:
                logger.warning(f"GPU info query failed in summary: {exc}")
                summary["gpu"] = {"error": str(exc)}
                warnings.append(f"GPU info failed: {exc}")

        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data=summary,
            events=["sysinfo_summary_retrieved"],
            warnings=warnings if warnings else None,
        )
