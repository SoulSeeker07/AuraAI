"""
Process Manager — Windows Process Enumeration, Inspection, and Control
Location: src/desktop/native/managers/process_manager.py

Provides native Windows process management for AuraAI using psutil and Win32 APIs.
Supports process listing, detailed inspection, process tree exploration, top resource consumers,
process execution, and difflib fuzzy search. Enforces HMAC-SHA256 human approval gates
for mutating and destructive capabilities (process.kill, process.priority).
"""

from __future__ import annotations

import difflib
import logging
import os
import subprocess
from datetime import datetime
from typing import Any

from ..desktop_result import DesktopResult
from ..security.approval_authority import CryptographicApprovalAuthority
from .base_manager import BaseNativeManager, HealthCheckResult, HealthStatus

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

logger = logging.getLogger(__name__)

# Priority mappings for Windows priority classes
PRIORITY_MAP: dict[str, int] = {}
REVERSE_PRIORITY_MAP: dict[int, str] = {}

if PSUTIL_AVAILABLE and psutil is not None:
    PRIORITY_MAP = {
        "realtime": getattr(psutil, "REALTIME_PRIORITY_CLASS", 256),
        "high": getattr(psutil, "HIGH_PRIORITY_CLASS", 128),
        "above_normal": getattr(psutil, "ABOVE_NORMAL_PRIORITY_CLASS", 32768),
        "normal": getattr(psutil, "NORMAL_PRIORITY_CLASS", 32),
        "below_normal": getattr(psutil, "BELOW_NORMAL_PRIORITY_CLASS", 16384),
        "idle": getattr(psutil, "IDLE_PRIORITY_CLASS", 64),
    }
    REVERSE_PRIORITY_MAP = {v: k for k, v in PRIORITY_MAP.items()}


class ProcessManager(BaseNativeManager):
    """
    Native Windows Process Manager for AuraAI.

    Manages process enumeration, inspection, resource monitoring, lifecycle control,
    and priority scheduling. Enforces HMAC-SHA256 cryptographic human approval gates
    for mutating and destructive operations (process termination and priority adjustment).
    """

    NAME = "process"
    VERSION = "1.0"
    PRIORITY = 18
    DEPENDENCIES: list[str] = ["psutil"]

    MUTATING_CAPABILITIES: set[str] = {
        "process.kill",
        "process.priority",
    }

    def __init__(self, auth: CryptographicApprovalAuthority | None = None) -> None:
        """Initialize ProcessManager with optional cryptographic approval authority."""
        super().__init__()
        self._auth: CryptographicApprovalAuthority = (
            auth or CryptographicApprovalAuthority.get_instance()
        )
        self._initialized = False

    @property
    def name(self) -> str:
        """Get manager name."""
        return self.NAME

    @property
    def auth(self) -> CryptographicApprovalAuthority:
        """Get cryptographic approval authority."""
        return self._auth

    @property
    def capabilities(self) -> list[str]:
        """Get list of capabilities supported by ProcessManager."""
        return [
            "process.list",
            "process.info",
            "process.kill",
            "process.priority",
            "process.top",
            "process.tree",
            "process.start",
            "process.search",
        ]

    def initialize(self) -> bool:
        """Initialize manager resources."""
        self._initialized = True
        return True

    def health_check(self) -> HealthCheckResult:
        """
        Perform health check on ProcessManager and psutil dependency.

        Returns:
            HealthCheckResult with dependency status and capability metrics.
        """
        status = HealthStatus.HEALTHY if PSUTIL_AVAILABLE else HealthStatus.UNAVAILABLE
        missing = [] if PSUTIL_AVAILABLE else ["psutil"]

        return HealthCheckResult(
            manager_name=self.name,
            status=status,
            missing_dependencies=missing,
            available_fallbacks=[],
            total_capabilities=len(self.capabilities),
            available_capabilities=len(self.capabilities) if PSUTIL_AVAILABLE else 0,
            details={
                "initialized": self._initialized,
                "psutil_available": PSUTIL_AVAILABLE,
                "current_pid": os.getpid(),
                "security_model": "cryptographic_hmac_human_approval_gate",
            },
        )

    def shutdown(self) -> None:
        """Shutdown manager and release resources."""
        self._initialized = False

    @staticmethod
    def _safe_proc_call(proc: Any, method_name: str, default: Any = None) -> Any:
        """Safely invoke a psutil.Process method handling access and lifecycle errors."""
        try:
            method = getattr(proc, method_name, None)
            if callable(method):
                return method()
            return method if method is not None else default
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
            return default
        except Exception:
            return default

    def execute(
        self,
        capability: str,
        goal: str = "",
        arguments: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> DesktopResult:
        """
        Execute a process management capability.

        Args:
            capability: Name of the capability to execute.
            goal: Natural language goal or user instruction.
            arguments: Dictionary of arguments for the capability.
            **kwargs: Extra parameters passed by caller.

        Returns:
            DesktopResult indicating success or failure.
        """
        args = arguments or {}
        cap = capability.lower().strip()

        try:
            # 1. HMAC Gate for Mutating Capabilities
            if cap in self.MUTATING_CAPABILITIES:
                # Validate arguments & construct deterministic action payload
                if cap == "process.kill":
                    pid = args.get("pid")
                    name = args.get("name")
                    force = bool(args.get("force", False))
                    if pid is None and not name:
                        return DesktopResult.create_failure(
                            goal=goal,
                            capability=capability,
                            manager=self.name,
                            error="Either 'pid' or 'name' argument is required for process.kill.",
                        )
                    target = f"pid:{pid}" if pid is not None else f"name:{name}"
                    action_params = {"capability": cap, "pid": pid, "name": name, "force": force}
                elif cap == "process.priority":
                    pid = args.get("pid")
                    priority = args.get("priority")
                    if pid is None or priority is None:
                        return DesktopResult.create_failure(
                            goal=goal,
                            capability=capability,
                            manager=self.name,
                            error="Both 'pid' and 'priority' arguments are required for process.priority.",
                        )
                    target = f"pid:{pid}:priority:{priority}"
                    action_params = {"capability": cap, "pid": pid, "priority": str(priority)}
                else:
                    target = goal or cap
                    action_params = {"capability": cap, "args": args}

                ticket_id = args.get("approval_ticket_id") or args.get("ticket_id")
                signature = args.get("approval_signature") or args.get("signature")

                if not ticket_id or not signature:
                    # Issue un-signed approval ticket
                    issued_ticket_id = self._auth.create_ticket(
                        action_type=cap,
                        target=target,
                        parameters=action_params,
                        description=f"Human authorization required for process control: {cap} on '{target}'",
                    )
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Process operation '{cap}' is mutating/destructive and requires human cryptographic approval.",
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

            # 2. Dependency Check (process.start only needs subprocess and os)
            if not PSUTIL_AVAILABLE and cap != "process.start":
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error="Required dependency 'psutil' is not installed or available.",
                )

            # 3. Dispatch to Handlers
            if cap == "process.list":
                return self._handle_list(goal=goal, capability=capability, arguments=args)
            elif cap == "process.info":
                return self._handle_info(goal=goal, capability=capability, arguments=args)
            elif cap == "process.kill":
                return self._handle_kill(goal=goal, capability=capability, arguments=args)
            elif cap == "process.priority":
                return self._handle_priority(goal=goal, capability=capability, arguments=args)
            elif cap == "process.top":
                return self._handle_top(goal=goal, capability=capability, arguments=args)
            elif cap == "process.tree":
                return self._handle_tree(goal=goal, capability=capability, arguments=args)
            elif cap == "process.start":
                return self._handle_start(goal=goal, capability=capability, arguments=args)
            elif cap == "process.search":
                return self._handle_search(goal=goal, capability=capability, arguments=args)
            else:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"Unsupported capability: {capability}",
                )

        except Exception as exc:
            logger.error(f"ProcessManager.{cap} failed: {exc}", exc_info=True)
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Operation failed: {exc}",
            )

    def _handle_list(
        self,
        goal: str,
        capability: str,
        arguments: dict[str, Any],
    ) -> DesktopResult:
        """
        List all running processes with name, pid, cpu_percent, memory_percent, status.

        Uses psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']).
        """
        processes: list[dict[str, Any]] = []

        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
            try:
                info = proc.info
                processes.append({
                    "pid": info.get("pid"),
                    "name": info.get("name") or "",
                    "cpu_percent": info.get("cpu_percent") or 0.0,
                    "memory_percent": round(info.get("memory_percent") or 0.0, 2),
                    "status": str(info.get("status") or "unknown"),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # Optional limit if requested
        limit = arguments.get("limit") or arguments.get("count")
        if limit is not None:
            try:
                limit_val = int(limit)
                if limit_val > 0:
                    processes = processes[:limit_val]
            except (ValueError, TypeError):
                pass

        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={"processes": processes, "count": len(processes)},
            events=["processes_listed"],
        )

    def _handle_info(
        self,
        goal: str,
        capability: str,
        arguments: dict[str, Any],
    ) -> DesktopResult:
        """
        Get detailed info for a specific process by PID or name.

        Includes: pid, name, exe, cmdline, status, create_time, cpu_percent,
        memory_info, num_threads, username.
        """
        pid_arg = arguments.get("pid")
        name_arg = arguments.get("name")

        if pid_arg is None and not name_arg:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="Either 'pid' or 'name' argument must be provided.",
            )

        target_proc: Any = None
        all_matching_pids: list[int] = []

        if pid_arg is not None:
            try:
                pid = int(pid_arg)
            except (ValueError, TypeError):
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"Invalid PID value: {pid_arg}",
                )
            try:
                target_proc = psutil.Process(pid)
            except psutil.NoSuchProcess:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"Process with PID {pid} not found or no longer running.",
                )
        else:
            target_name = str(name_arg).strip().lower()
            target_stem = target_name[:-4] if target_name.endswith(".exe") else target_name

            candidates: list[psutil.Process] = []
            for p in psutil.process_iter(["pid", "name"]):
                try:
                    pname = (p.info.get("name") or "").lower()
                    pname_stem = pname[:-4] if pname.endswith(".exe") else pname
                    if pname == target_name or pname_stem == target_stem or pname == f"{target_name}.exe":
                        candidates.append(p)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

            if not candidates:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"No running process found matching name: '{name_arg}'",
                )
            target_proc = candidates[0]
            all_matching_pids = [c.pid for c in candidates]

        try:
            pid = target_proc.pid
            name = self._safe_proc_call(target_proc, "name", "")
            exe = self._safe_proc_call(target_proc, "exe", "")
            cmdline = self._safe_proc_call(target_proc, "cmdline", [])
            status = str(self._safe_proc_call(target_proc, "status", "unknown"))

            # create_time
            ctime = self._safe_proc_call(target_proc, "create_time", 0.0)
            create_time_dict = {
                "timestamp": ctime,
                "iso": datetime.fromtimestamp(ctime).isoformat() if ctime else "",
            }

            cpu_percent = self._safe_proc_call(target_proc, "cpu_percent", 0.0)

            # memory_info
            mem_info = self._safe_proc_call(target_proc, "memory_info")
            memory_dict: dict[str, Any] = {}
            if mem_info and hasattr(mem_info, "_asdict"):
                memory_dict = mem_info._asdict()
            elif mem_info and isinstance(mem_info, tuple):
                memory_dict = {"rss": mem_info[0], "vms": mem_info[1]}

            num_threads = self._safe_proc_call(target_proc, "num_threads", 0)
            username = self._safe_proc_call(target_proc, "username", "")

            data: dict[str, Any] = {
                "pid": pid,
                "name": name,
                "exe": exe,
                "cmdline": cmdline,
                "status": status,
                "create_time": create_time_dict,
                "cpu_percent": cpu_percent,
                "memory_info": memory_dict,
                "num_threads": num_threads,
                "username": username,
            }
            if len(all_matching_pids) > 1:
                data["all_matching_pids"] = all_matching_pids

            return DesktopResult.create_success(
                goal=goal,
                capability=capability,
                manager=self.name,
                data=data,
                events=["process_info_retrieved"],
            )
        except psutil.NoSuchProcess:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Process {target_proc.pid} terminated while retrieving info.",
            )

    def _handle_kill(
        self,
        goal: str,
        capability: str,
        arguments: dict[str, Any],
    ) -> DesktopResult:
        """
        Kill a process by PID or name.

        Args:
            pid: Optional target process ID.
            name: Optional target process name.
            force: Whether to forcefully terminate (SIGKILL) or gracefully terminate (SIGTERM).
        """
        pid_arg = arguments.get("pid")
        name_arg = arguments.get("name")
        force = bool(arguments.get("force", False))

        if pid_arg is None and not name_arg:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="Either 'pid' or 'name' argument must be provided.",
            )

        current_pid = os.getpid()
        procs_to_kill: list[psutil.Process] = []

        if pid_arg is not None:
            try:
                pid = int(pid_arg)
            except (ValueError, TypeError):
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"Invalid PID value: {pid_arg}",
                )

            # Safety Guardrails
            if pid == current_pid:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error="CRITICAL SAFETY GUARDRAIL: Terminating the AuraAI host process is strictly prohibited.",
                    data={"security_alert": "self_termination_blocked"},
                )
            if pid in (0, 4):
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error="CRITICAL SAFETY GUARDRAIL: Terminating Windows core system process is strictly prohibited.",
                    data={"security_alert": "system_process_termination_blocked"},
                )

            try:
                procs_to_kill.append(psutil.Process(pid))
            except psutil.NoSuchProcess:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"Process with PID {pid} not found or no longer running.",
                )
        else:
            target_name = str(name_arg).strip().lower()
            target_stem = target_name[:-4] if target_name.endswith(".exe") else target_name

            for p in psutil.process_iter(["pid", "name"]):
                try:
                    pname = (p.info.get("name") or "").lower()
                    pname_stem = pname[:-4] if pname.endswith(".exe") else pname
                    if pname == target_name or pname_stem == target_stem or pname == f"{target_name}.exe":
                        # Guard against self and core system processes
                        if p.pid != current_pid and p.pid not in (0, 4):
                            procs_to_kill.append(p)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

            if not procs_to_kill:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"No killable running process found matching name: '{name_arg}'",
                )

        killed_records: list[dict[str, Any]] = []
        errors: list[str] = []

        for proc in procs_to_kill:
            proc_pid = proc.pid
            proc_name = self._safe_proc_call(proc, "name", f"PID_{proc_pid}")
            try:
                if force:
                    proc.kill()
                else:
                    proc.terminate()

                killed_records.append({
                    "pid": proc_pid,
                    "name": proc_name,
                    "method": "kill" if force else "terminate",
                })
            except (psutil.NoSuchProcess, psutil.ZombieProcess):
                killed_records.append({
                    "pid": proc_pid,
                    "name": proc_name,
                    "status": "already_exited",
                })
            except psutil.AccessDenied as exc:
                errors.append(f"Access denied terminating PID {proc_pid} ({proc_name}): {exc}")
            except Exception as exc:
                errors.append(f"Failed to terminate PID {proc_pid} ({proc_name}): {exc}")

        # Wait briefly for termination
        gone, alive = psutil.wait_procs(procs_to_kill, timeout=2.0)

        if not killed_records and errors:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="; ".join(errors),
                data={"errors": errors},
            )

        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={
                "killed": killed_records,
                "count": len(killed_records),
                "force": force,
                "still_alive": [p.pid for p in alive],
                "errors": errors if errors else None,
            },
            events=["process_killed"],
        )

    def _handle_priority(
        self,
        goal: str,
        capability: str,
        arguments: dict[str, Any],
    ) -> DesktopResult:
        """
        Set process priority.

        Args:
            pid: Target process ID.
            priority: Priority string ('realtime', 'high', 'above_normal', 'normal', 'below_normal', 'idle').
        """
        pid_arg = arguments.get("pid")
        priority_arg = arguments.get("priority")

        if pid_arg is None or priority_arg is None:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="Both 'pid' and 'priority' arguments are required.",
            )

        try:
            pid = int(pid_arg)
        except (ValueError, TypeError):
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Invalid PID value: {pid_arg}",
            )

        # Normalize priority name
        pri_raw = str(priority_arg).lower().strip().replace(" ", "_").replace("-", "_")
        alias_map = {
            "abovenormal": "above_normal",
            "belownormal": "below_normal",
            "real_time": "realtime",
            "low": "below_normal",
        }
        pri_normalized = alias_map.get(pri_raw, pri_raw)

        if pri_normalized not in PRIORITY_MAP:
            valid_options = ", ".join(PRIORITY_MAP.keys())
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Invalid priority '{priority_arg}'. Must be one of: {valid_options}",
            )

        target_priority_class = PRIORITY_MAP[pri_normalized]

        try:
            proc = psutil.Process(pid)
        except psutil.NoSuchProcess:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Process with PID {pid} not found or no longer running.",
            )

        try:
            old_nice = proc.nice()
            proc.nice(target_priority_class)
            new_nice = proc.nice()

            old_pri_name = REVERSE_PRIORITY_MAP.get(old_nice, str(old_nice))
            new_pri_name = REVERSE_PRIORITY_MAP.get(new_nice, pri_normalized)

            return DesktopResult.create_success(
                goal=goal,
                capability=capability,
                manager=self.name,
                data={
                    "pid": pid,
                    "name": self._safe_proc_call(proc, "name", ""),
                    "previous_priority": old_pri_name,
                    "previous_priority_class": old_nice,
                    "new_priority": new_pri_name,
                    "new_priority_class": new_nice,
                },
                events=["process_priority_changed"],
            )
        except psutil.AccessDenied as exc:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Access denied changing priority for PID {pid}: {exc}",
            )
        except psutil.NoSuchProcess:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Process with PID {pid} exited before priority could be changed.",
            )

    def _handle_top(
        self,
        goal: str,
        capability: str,
        arguments: dict[str, Any],
    ) -> DesktopResult:
        """
        Top N processes by CPU or memory.

        Args:
            sort_by: Metric to sort by ('cpu' or 'memory', default 'cpu').
            count: Number of processes to return (default 10).
        """
        sort_by = str(arguments.get("sort_by", "cpu")).strip().lower()
        count_arg = arguments.get("count", 10)

        try:
            count = int(count_arg)
            if count <= 0:
                count = 10
        except (ValueError, TypeError):
            count = 10

        sort_field = "memory_percent" if sort_by in ("memory", "mem", "ram") else "cpu_percent"

        procs_data: list[dict[str, Any]] = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status", "username"]):
            try:
                info = proc.info
                procs_data.append({
                    "pid": info.get("pid"),
                    "name": info.get("name") or "",
                    "cpu_percent": info.get("cpu_percent") or 0.0,
                    "memory_percent": round(info.get("memory_percent") or 0.0, 2),
                    "status": str(info.get("status") or "unknown"),
                    "username": info.get("username") or "",
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        procs_data.sort(key=lambda x: x.get(sort_field, 0.0), reverse=True)
        top_n = procs_data[:count]

        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={
                "processes": top_n,
                "sorted_by": sort_field,
                "count": len(top_n),
                "requested_count": count,
            },
            events=["process_top_retrieved"],
        )

    def _handle_tree(
        self,
        goal: str,
        capability: str,
        arguments: dict[str, Any],
    ) -> DesktopResult:
        """
        Get process tree for a PID.

        Args:
            pid: Process ID whose children will be recursively discovered.
        """
        pid_arg = arguments.get("pid")
        if pid_arg is None:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="Argument 'pid' is required for process.tree.",
            )

        try:
            pid = int(pid_arg)
        except (ValueError, TypeError):
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Invalid PID value: {pid_arg}",
            )

        try:
            proc = psutil.Process(pid)
        except psutil.NoSuchProcess:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Process with PID {pid} not found or no longer running.",
            )

        try:
            root_info = {
                "pid": proc.pid,
                "name": self._safe_proc_call(proc, "name", ""),
                "status": str(self._safe_proc_call(proc, "status", "unknown")),
                "cpu_percent": self._safe_proc_call(proc, "cpu_percent", 0.0),
                "memory_percent": round(self._safe_proc_call(proc, "memory_percent", 0.0) or 0.0, 2),
            }

            children = proc.children(recursive=True)
            children_list: list[dict[str, Any]] = []

            for child in children:
                try:
                    children_list.append({
                        "pid": child.pid,
                        "ppid": self._safe_proc_call(child, "ppid", proc.pid),
                        "name": self._safe_proc_call(child, "name", ""),
                        "status": str(self._safe_proc_call(child, "status", "unknown")),
                        "cpu_percent": self._safe_proc_call(child, "cpu_percent", 0.0),
                        "memory_percent": round(self._safe_proc_call(child, "memory_percent", 0.0) or 0.0, 2),
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

            return DesktopResult.create_success(
                goal=goal,
                capability=capability,
                manager=self.name,
                data={
                    "parent": root_info,
                    "children": children_list,
                    "total_children": len(children_list),
                },
                events=["process_tree_retrieved"],
            )
        except psutil.NoSuchProcess:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Process with PID {pid} exited while building tree.",
            )

    def _handle_start(
        self,
        goal: str,
        capability: str,
        arguments: dict[str, Any],
    ) -> DesktopResult:
        """
        Start a new process.

        Args:
            command: Command string or list of command arguments.
            cwd: Optional working directory for the spawned process.
        """
        command = arguments.get("command") or arguments.get("cmd") or goal
        if not command:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="Argument 'command' is required to start a process.",
            )

        cwd = arguments.get("cwd")
        if cwd and not os.path.exists(cwd):
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Working directory does not exist: {cwd}",
            )

        try:
            if isinstance(command, str):
                proc = subprocess.Popen(command, shell=True, cwd=cwd)
            elif isinstance(command, (list, tuple)):
                proc = subprocess.Popen(command, cwd=cwd)
            else:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"Invalid command type: {type(command).__name__}. Must be string or list.",
                )

            return DesktopResult.create_success(
                goal=goal,
                capability=capability,
                manager=self.name,
                data={
                    "pid": proc.pid,
                    "command": command,
                    "cwd": cwd or os.getcwd(),
                },
                events=["process_started"],
            )
        except Exception as exc:
            logger.error(f"ProcessManager.process.start failed: {exc}", exc_info=True)
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Failed to start process: {exc}",
            )

    def _handle_search(
        self,
        goal: str,
        capability: str,
        arguments: dict[str, Any],
    ) -> DesktopResult:
        """
        Find processes matching a name pattern using difflib fuzzy matching.

        Args:
            name: Pattern or name to match against running processes.
            threshold: Minimum similarity score (0.0 to 1.0, default 0.4).
            limit: Maximum number of results to return (default 50).
        """
        name_arg = arguments.get("name") or arguments.get("pattern") or arguments.get("query")
        if not name_arg:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="Argument 'name' is required for process.search.",
            )

        query = str(name_arg).strip()
        query_lower = query.lower()
        query_stem = query_lower[:-4] if query_lower.endswith(".exe") else query_lower

        threshold = float(arguments.get("threshold", 0.4))
        limit = arguments.get("limit") or arguments.get("count") or 50

        try:
            limit_val = int(limit)
        except (ValueError, TypeError):
            limit_val = 50

        all_procs: list[dict[str, Any]] = []
        for proc in psutil.process_iter(["pid", "name", "status", "cpu_percent", "memory_percent", "username"]):
            try:
                all_procs.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        matches: list[dict[str, Any]] = []
        for p in all_procs:
            pname = (p.get("name") or "").strip()
            if not pname:
                continue

            pname_lower = pname.lower()
            pname_stem = pname_lower[:-4] if pname_lower.endswith(".exe") else pname_lower

            ratio_full = difflib.SequenceMatcher(None, query_lower, pname_lower).ratio()
            ratio_stem = difflib.SequenceMatcher(None, query_stem, pname_stem).ratio()
            best_ratio = max(ratio_full, ratio_stem)

            is_exact = query_lower == pname_lower or query_stem == pname_stem
            is_substring = query_lower in pname_lower or query_stem in pname_stem

            score = best_ratio
            if is_exact:
                score = 1.0
            elif is_substring:
                score = max(score, 0.75)

            if score >= threshold or is_substring:
                matches.append({
                    "pid": p.get("pid"),
                    "name": pname,
                    "status": str(p.get("status") or "unknown"),
                    "cpu_percent": p.get("cpu_percent") or 0.0,
                    "memory_percent": round(p.get("memory_percent") or 0.0, 2),
                    "username": p.get("username") or "",
                    "similarity": round(score, 3),
                })

        matches.sort(key=lambda x: (x["similarity"], x["cpu_percent"]), reverse=True)

        if limit_val > 0:
            matches = matches[:limit_val]

        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={
                "matches": matches,
                "query": query,
                "count": len(matches),
            },
            events=["processes_searched"],
        )
