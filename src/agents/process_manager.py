"""
Process Manager - Manages running processes on the system.

Provides comprehensive process management capabilities including:
- Process listing and discovery
- Process information retrieval
- Process control (start, stop, kill)
- Process search by name or PID
- Process status monitoring
- Process change tracking (via Event Bus)
- Background process monitoring
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

import psutil

if TYPE_CHECKING:
    # Only used by Pylance/mypy for type hints — never runs
    from core.event_bus import Event, EventBus
else:
    # Actual runtime import, with graceful fallback
    try:
        from core.event_bus import Event, EventBus
    except ImportError:
        EventBus = None
        Event = None

from .permission_manager import PermissionManager
from .task_model import Task, TaskOutput


class ProcessStatus(str, Enum):
    """Process status enumeration"""

    RUNNING = "running"
    STOPPED = "stopped"
    SLEEPING = "sleeping"
    WAITING = "waiting"
    HUNG = "hung"
    ZOMBIE = "zombie"
    UNKNOWN = "unknown"

    @classmethod
    def from_psutil(cls, psutil_status):
        """Convert psutil status to ProcessStatus"""
        status_map = {
            psutil.STATUS_RUNNING: ProcessStatus.RUNNING,
            psutil.STATUS_SLEEPING: ProcessStatus.SLEEPING,
            psutil.STATUS_DISK_SLEEP: ProcessStatus.SLEEPING,
            psutil.STATUS_STOPPED: ProcessStatus.STOPPED,
            psutil.STATUS_DEAD: ProcessStatus.STOPPED,
            psutil.STATUS_ZOMBIE: ProcessStatus.ZOMBIE,
            psutil.STATUS_LOCKED: ProcessStatus.WAITING,
        }
        # Optional / platform-specific statuses — not all exist on Windows
        if hasattr(psutil, "STATUS_TRACE"):
            status_map[psutil.STATUS_TRACE] = ProcessStatus.WAITING
        if hasattr(psutil, "STATUS_WAKING"):
            status_map[psutil.STATUS_WAKING] = ProcessStatus.WAITING
        if hasattr(psutil, "STATUS_WAITING"):
            status_map[psutil.STATUS_WAITING] = ProcessStatus.WAITING

        return status_map.get(psutil_status, ProcessStatus.UNKNOWN)


# Event names for Process Manager
class ProcessEvent(str, Enum):
    """Process manager event names"""

    PROCESS_STARTED = "process.started"
    PROCESS_STOPPED = "process.stopped"
    PROCESS_EXITED = "process.exited"
    PROCESS_CHANGED = "process.changed"
    PROCESS_LIST_UPDATED = "process.list.updated"
    PROCESS_ERROR = "process.error"


@dataclass
class ProcessState:
    """
    Tracks process state for change detection.

    Stores previous and current process states to detect changes
    and publish events.
    """

    pid: int
    name: str
    previous_status: str | None = None
    previous_cpu: float = 0.0
    previous_memory: float = 0.0
    previous_timestamp: datetime | None = None

    # Aliases so has_changed() can accept either a ProcessInfo or another
    # ProcessState (the test compares two ProcessState snapshots directly).
    @property
    def status(self):
        return self.previous_status

    @property
    def cpu_percent(self):
        return self.previous_cpu

    @property
    def memory_mb(self):
        return self.previous_memory

    def has_changed(self, current: ProcessInfo) -> bool:
        """
        Check if process state has changed.

        Args:
            current: Current process info

        Returns:
            True if state changed
        """
        if self.previous_timestamp is None:
            return False

        return (
            self.previous_status != current.status
            or self.previous_cpu != current.cpu_percent
            or self.previous_memory != current.memory_mb
        )


@dataclass
class ProcessInfo:
    """Represents a running process"""

    pid: int
    name: str
    status: str
    username: str
    cpu_percent: float
    memory_mb: float
    cmdline: list[str]
    create_time: datetime
    executable: str | None = None
    cwd: str | None = None

    def __hash__(self):
        return hash(self.pid)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "pid": self.pid,
            "name": self.name,
            "status": self.status,
            "username": self.username,
            "cpu_percent": self.cpu_percent,
            "memory_mb": round(self.memory_mb, 2),
            "cmdline": self.cmdline,
            "create_time": self.create_time.isoformat(),
            "executable": self.executable,
            "cwd": self.cwd,
        }


class ProcessManager:
    """
    Manages processes on the system using psutil.

    Provides safe, controlled access to process information and control.

    Features:
    - Process monitoring and control
    - Event-driven process change detection
    - Background process monitoring thread
    - Process state tracking and event publishing
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        permission_manager: PermissionManager | None = None,
    ):
        """
        Initialize the process manager.

        Args:
            event_bus: Optional EventBus instance for event-driven notifications
            permission_manager: Optional PermissionManager instance for confirmation
        """
        self.logger = logging.getLogger(__name__)
        self._cache: dict[int, ProcessInfo] = {}
        self._cache_time: datetime | None = None
        self._cache_ttl_seconds = 5  # Cache for 5 seconds

        # Event Bus integration
        self.event_bus = event_bus

        # Permission Manager integration
        self.permission_manager = permission_manager or PermissionManager()

        # Process state tracking for change detection.
        # NOTE: this dict is owned exclusively by _scan_and_detect_changes().
        # get_process_info() must NOT write to it — otherwise the scan loop's
        # "is this a new process?" check always sees it as already-known and
        # PROCESS_STARTED events never fire.
        self._process_states: dict[int, ProcessState] = {}
        self._last_process_list: list[int] = []
        self._last_scan_time: datetime | None = None

        # Background monitoring thread
        self._monitor_thread: threading.Thread | None = None
        self._monitor_running = False
        self._monitor_interval = 1.0  # Check every second

        # Do one synchronous scan immediately so callers don't race the
        # background thread's first pass — _process_states is populated
        # before __init__ returns, eliminating the race for get_process_state().
        self._scan_and_detect_changes()

        # Start background monitor
        self._start_background_monitor()

    def get_process_info(self, pid: int) -> ProcessInfo | None:
        """
        Get information about a specific process by PID.

        Args:
            pid: Process ID

        Returns:
            ProcessInfo object or None if process not found
        """
        try:
            process = psutil.Process(pid)

            # Get basic info
            process_name = process.name()
            status = ProcessStatus.from_psutil(process.status())
            username = process.username()
            cpu_percent = process.cpu_percent()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            cmdline = process.cmdline()

            # Get executable path
            try:
                executable = process.exe()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                executable = None

            # Get current working directory
            try:
                cwd = process.cwd()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                cwd = None

            # Get create time
            try:
                create_time = datetime.fromtimestamp(process.create_time())
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                create_time = datetime.now()

            process_info = ProcessInfo(
                pid=pid,
                name=process_name,
                status=status,
                username=username,
                cpu_percent=cpu_percent,
                memory_mb=memory_mb,
                cmdline=cmdline,
                create_time=create_time,
                executable=executable,
                cwd=cwd,
            )

            # NOTE: state tracking intentionally NOT done here.
            # _scan_and_detect_changes() owns _process_states so that
            # PROCESS_STARTED / PROCESS_CHANGED events fire correctly.

            return process_info

        except psutil.NoSuchProcess:
            self.logger.debug(f"Process {pid} not found")
            return None
        except psutil.AccessDenied:
            # Expected/frequent on Windows for protected system & service
            # processes when not running as Administrator — keep this at
            # DEBUG so normal runs aren't flooded with warnings.
            self.logger.debug(f"Access denied to process {pid}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting process info for {pid}: {e}")
            return None

    def list_processes(
        self, filter_by_name: str | None = None, filter_by_status: str | None = None
    ) -> list[ProcessInfo]:
        """
        List all running processes.

        Args:
            filter_by_name: Optional filter by process name (partial match)
            filter_by_status: Optional filter by status

        Returns:
            List of ProcessInfo objects
        """
        processes = []

        for proc in psutil.process_iter(["pid", "name", "status", "username"]):
            try:
                proc_info = proc.info
                pid = proc_info["pid"]
                process_name = proc_info["name"]
                status = ProcessStatus.from_psutil(proc_info["status"])

                # Apply filters
                if (
                    filter_by_name
                    and filter_by_name.lower() not in process_name.lower()
                ):
                    continue

                if filter_by_status and status != filter_by_status:
                    continue

                # Get full process info
                full_info = self.get_process_info(pid)
                if full_info:
                    processes.append(full_info)

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Sort by CPU usage
        processes.sort(key=lambda p: p.cpu_percent, reverse=True)

        # Publish PROCESS_LIST_UPDATED event with the real count
        self._publish_list_updated_event(count=len(processes))

        return processes

    def find_process_by_name(self, name: str) -> list[ProcessInfo]:
        """
        Find processes by name (supports partial matching).

        Args:
            name: Process name or partial name

        Returns:
            List of matching ProcessInfo objects
        """
        return [p for p in self.list_processes(filter_by_name=name)]

    def find_process_by_pid(self, pid: int) -> ProcessInfo | None:
        """
        Find a process by PID.

        Args:
            pid: Process ID

        Returns:
            ProcessInfo object or None
        """
        return self.get_process_info(pid)

    def is_process_running(self, pid: int) -> bool:
        """
        Check if a process is running.

        Args:
            pid: Process ID

        Returns:
            True if running, False otherwise
        """
        try:
            process = psutil.Process(pid)
            return process.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False

    def start_process(
        self,
        command: str,
        args: list[str] = None,
        cwd: str | None = None,
        shell: bool = False,
    ) -> ProcessInfo:
        """
        Start a new process.

        Args:
            command: Command to execute
            args: Optional list of arguments
            cwd: Optional working directory
            shell: Whether to use shell

        Returns:
            ProcessInfo object for the started process

        Raises:
            Exception: If process cannot be started
        """
        try:
            if args:
                cmd = command + " " + " ".join(args)
            else:
                cmd = command

            if shell:
                process = psutil.Popen(cmd, shell=True, cwd=cwd)
            else:
                process = psutil.Popen([command] + (args or []), cwd=cwd)

            # Wait a bit for process to start
            time.sleep(0.5)

            # Get process info
            return self.get_process_info(process.pid)

        except Exception as e:
            raise Exception(f"Failed to start process: {e}")

    def stop_process(self, pid: int, timeout: int = 5) -> bool:
        """
        Stop a process gracefully with user confirmation.

        Requires user approval before stopping the process.

        Args:
            pid: Process ID
            timeout: Seconds to wait for process to stop

        Returns:
            True if process stopped, False otherwise
        """
        # Request permission first
        process_info = self.get_process_info(pid)
        process_name = process_info.name if process_info else "unknown"
        process_exe = process_info.executable if process_info else "unknown"

        permission_approved = self.permission_manager.request_dangerous_permission(
            operation="stop_process",
            target=f"PID {pid} ({process_name})",
            details=f"You are about to stop the process '{process_name}' (PID: {pid}).\n\nThis will gracefully terminate the process after a short timeout (currently set to {timeout} seconds).\n\nExecutable: {process_exe}\n\nThis action will close the process window/application.\n\nThis action cannot be easily undone.",
            context={
                "pid": pid,
                "name": process_name,
                "executable": process_exe,
                "timeout": timeout,
            },
        )

        if not permission_approved:
            self.logger.info(f"Permission denied for stopping process {pid}")
            return False

        process = None
        try:
            process = psutil.Process(pid)

            # Try graceful termination first
            process.terminate()

            # Wait for termination
            process.wait(timeout=timeout)

            return True

        except psutil.TimeoutExpired:
            # Force kill if graceful termination fails
            try:
                if process is not None:
                    process.kill()
                    process.wait(timeout=timeout)
                    return True
                return False
            except Exception:
                return False
        except psutil.NoSuchProcess:
            return True
        except Exception as e:
            self.logger.error(f"Error stopping process {pid}: {e}")
            return False

    def kill_process(self, pid: int, force: bool = False) -> bool:
        """
        Kill a process with user confirmation.

        Requires user approval before killing the process.

        Args:
            pid: Process ID
            force: Force kill if graceful termination fails

        Returns:
            True if process killed, False otherwise
        """
        # Request permission first
        process_info = self.get_process_info(pid)
        process_name = process_info.name if process_info else "unknown"
        process_exe = process_info.executable if process_info else "unknown"

        permission_approved = self.permission_manager.request_dangerous_permission(
            operation="kill_process",
            target=f"PID {pid} ({process_name})",
            details=f"You are about to kill the process '{process_name}' (PID: {pid}).\nThis will terminate the process immediately.\n\nExecutable: {process_exe}\n\nIf this is the current terminal or application, closing it may cause unexpected behavior.\n\nThis action cannot be easily undone.",
            context={
                "pid": pid,
                "name": process_name,
                "executable": process_exe,
                "force": force,
            },
        )

        if not permission_approved:
            self.logger.info(f"Permission denied for killing process {pid}")
            return False

        # Permission granted, proceed with kill
        try:
            process = psutil.Process(pid)

            if force:
                process.kill()
            else:
                process.terminate()

            self.logger.info(f"Process {pid} ({process_name}) killed successfully")
            return True

        except psutil.NoSuchProcess:
            self.logger.info(f"Process {pid} no longer exists")
            return True
        except Exception as e:
            self.logger.error(f"Error killing process {pid}: {e}")
            return False

    def get_top_processes(self, limit: int = 10) -> list[ProcessInfo]:
        """
        Get the top N processes by CPU usage.

        Args:
            limit: Number of processes to return

        Returns:
            List of top processes
        """
        return self.list_processes()[:limit]

    def get_memory_usage(self) -> dict[str, Any]:
        """
        Get overall memory usage statistics.

        Returns:
            Dictionary with memory statistics
        """
        try:
            memory = psutil.virtual_memory()
            return {
                "total_gb": round(memory.total / (1024 * 1024 * 1024), 2),
                "available_gb": round(memory.available / (1024 * 1024 * 1024), 2),
                "used_gb": round(memory.used / (1024 * 1024 * 1024), 2),
                "percent_used": memory.percent,
                "processes_count": len(psutil.pids()),
            }
        except Exception as e:
            self.logger.error(f"Error getting memory usage: {e}")
            return {}

    def get_system_stats(self) -> dict[str, Any]:
        """
        Get system-level statistics.

        Returns:
            Dictionary with system statistics
        """
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            disk = psutil.disk_usage("/")
            cpu_count = psutil.cpu_count()

            return {
                "cpu_percent": cpu_percent,
                "cpu_count": cpu_count,
                "cpu_cores_logical": cpu_count,
                "cpu_cores_physical": psutil.cpu_count(logical=False),
                "disk_total_gb": round(disk.total / (1024 * 1024 * 1024), 2),
                "disk_used_gb": round(disk.used / (1024 * 1024 * 1024), 2),
                "disk_free_gb": round(disk.free / (1024 * 1024 * 1024), 2),
                "disk_percent_used": disk.percent,
            }
        except Exception as e:
            self.logger.error(f"Error getting system stats: {e}")
            return {}

    def execute_task(self, task: Task) -> TaskOutput:
        """
        Execute a process management task.

        Args:
            task: Task to execute

        Returns:
            TaskOutput with result
        """
        try:
            method = getattr(self, f"_execute_{task.type.value}", None)

            if not method:
                return TaskOutput(
                    success=False,
                    message=f"No handler for task type: {task.type.value}",
                    error=f"Task type {task.type.value} not supported",
                )

            return method(task)

        except Exception as e:
            return TaskOutput(
                success=False, message="Error executing task", error=str(e)
            )

    # ========================================
    # TASK EXECUTION METHODS
    # ========================================

    def _execute_process_list(self, task: Task) -> TaskOutput:
        """List all processes"""
        try:
            filter_name = task.input.get("name")
            filter_status = task.input.get("status")

            processes = self.list_processes(
                filter_by_name=filter_name, filter_by_status=filter_status
            )

            return TaskOutput(
                success=True,
                message=f"Found {len(processes)} processes",
                data={
                    "processes": [p.to_dict() for p in processes],
                    "count": len(processes),
                    "total_cpu_percent": round(
                        sum(p.cpu_percent for p in processes), 2
                    ),
                    "total_memory_mb": round(sum(p.memory_mb for p in processes), 2),
                },
            )

        except Exception as e:
            return TaskOutput(
                success=False, message="Failed to list processes", error=str(e)
            )

    def _execute_process_get(self, task: Task) -> TaskOutput:
        """Get information about a specific process"""
        try:
            pid = task.input.get("pid")

            if pid is None:
                return TaskOutput(
                    success=False,
                    message="Failed to get process",
                    error="PID not provided",
                )

            process = self.get_process_info(pid)

            if not process:
                return TaskOutput(
                    success=False,
                    message=f"Process {pid} not found",
                    error=f"No process with PID {pid} exists",
                )

            return TaskOutput(
                success=True,
                message="Process information retrieved",
                data=process.to_dict(),
            )

        except Exception as e:
            return TaskOutput(
                success=False, message="Failed to get process", error=str(e)
            )

    def _execute_process_start(self, task: Task) -> TaskOutput:
        """Start a process"""
        try:
            command = task.input.get("command")
            args = task.input.get("args", [])
            cwd = task.input.get("cwd")
            shell = task.input.get("shell", False)

            if not command:
                return TaskOutput(
                    success=False,
                    message="Failed to start process",
                    error="Command not provided",
                )

            process = self.start_process(command, args, cwd, shell)

            return TaskOutput(
                success=True,
                message=f"Process started: {process.name} (PID: {process.pid})",
                data=process.to_dict(),
            )

        except Exception as e:
            return TaskOutput(
                success=False, message="Failed to start process", error=str(e)
            )

    def _execute_process_stop(self, task: Task) -> TaskOutput:
        """Stop a process gracefully"""
        try:
            pid = task.input.get("pid")
            timeout = task.input.get("timeout", 5)

            if pid is None:
                return TaskOutput(
                    success=False,
                    message="Failed to stop process",
                    error="PID not provided",
                )

            success = self.stop_process(pid, timeout)

            if success:
                return TaskOutput(
                    success=True,
                    message=f"Process stopped: PID {pid}",
                    data={"pid": pid, "stopped": True},
                )
            else:
                return TaskOutput(
                    success=False,
                    message=f"Failed to stop process {pid}",
                    error="Process did not terminate gracefully",
                )

        except Exception as e:
            return TaskOutput(
                success=False, message="Failed to stop process", error=str(e)
            )

    def _execute_process_kill(self, task: Task) -> TaskOutput:
        """Kill a process"""
        try:
            pid = task.input.get("pid")
            force = task.input.get("force", False)

            if pid is None:
                return TaskOutput(
                    success=False,
                    message="Failed to kill process",
                    error="PID not provided",
                )

            success = self.kill_process(pid, force)

            if success:
                return TaskOutput(
                    success=True,
                    message=f"Process killed: PID {pid}",
                    data={"pid": pid, "killed": True},
                )
            else:
                return TaskOutput(
                    success=False,
                    message=f"Failed to kill process {pid}",
                    error="Failed to kill process",
                )

        except Exception as e:
            return TaskOutput(
                success=False, message="Failed to kill process", error=str(e)
            )

    def _execute_process_search(self, task: Task) -> TaskOutput:
        """Search for processes"""
        try:
            name = task.input.get("name")
            max_results = task.input.get("max_results", 50)

            if not name:
                return TaskOutput(
                    success=False,
                    message="Failed to search processes",
                    error="Search name not provided",
                )

            processes = self.find_process_by_name(name)

            return TaskOutput(
                success=True,
                message=f"Found {len(processes)} matching processes",
                data={
                    "processes": [p.to_dict() for p in processes[:max_results]],
                    "count": len(processes),
                    "search_name": name,
                },
            )

        except Exception as e:
            return TaskOutput(
                success=False, message="Failed to search processes", error=str(e)
            )

    # ========================================
    # EVENT BUS & BACKGROUND MONITORING
    # ========================================

    def _start_background_monitor(self):
        """Start the background process monitoring thread."""
        if self._monitor_running:
            return

        self._monitor_running = True
        self._monitor_thread = threading.Thread(
            target=self._run_monitor_loop, name="ProcessMonitor", daemon=True
        )
        self._monitor_thread.start()
        self.logger.info("Background process monitor started")

    def _stop_background_monitor(self):
        """Stop the background process monitoring thread."""
        self._monitor_running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)
        self.logger.info("Background process monitor stopped")

    def _run_monitor_loop(self):
        """
        Background monitor loop.

        Runs every second, checks for process changes, and publishes events.
        """
        self.logger.debug("Process monitor loop started")

        while self._monitor_running:
            try:
                # Check if we should do a full scan (cache expired or first run)
                if (
                    self._last_scan_time is None
                    or (datetime.now() - self._last_scan_time).total_seconds()
                    >= self._monitor_interval
                ):
                    self._scan_and_detect_changes()

            except Exception as e:
                self.logger.error(f"Error in process monitor loop: {e}")

            # Wait for next iteration
            time.sleep(self._monitor_interval)

        self.logger.debug("Process monitor loop stopped")

    def _scan_and_detect_changes(self):
        """
        Scan processes and detect changes.

        Compares current process list with last list and publishes events
        for newly started, stopped, or changed processes.

        This is the SOLE owner of self._process_states. get_process_info()
        must not write to that dict, or new-process detection here will
        always find PIDs "already known" and PROCESS_STARTED will never fire.
        """
        try:
            # Get current process PIDs
            current_pids = set()

            # Scan all processes
            for proc in psutil.process_iter(["pid", "name", "status"]):
                pid = None
                try:
                    pid = proc.info["pid"]
                    current_pids.add(pid)

                    # Get current process info
                    process = self.get_process_info(pid)
                    if not process:
                        continue

                    # Check if we have a previous state
                    if pid not in self._process_states:
                        # New process detected
                        self._process_states[pid] = ProcessState(
                            pid=pid,
                            name=process.name,
                            previous_status=process.status,
                            previous_cpu=process.cpu_percent,
                            previous_memory=process.memory_mb,
                            previous_timestamp=datetime.now(),
                        )

                        # Publish PROCESS_STARTED event
                        if self.event_bus:
                            self.event_bus.publish(
                                ProcessEvent.PROCESS_STARTED,
                                pid=pid,
                                name=process.name,
                                executable=process.executable,
                                cmdline=process.cmdline,
                            )
                            self.logger.debug(
                                f"Process started: {process.name} (PID: {pid})"
                            )
                    else:
                        # Check for changes
                        state = self._process_states[pid]
                        if state.has_changed(process):
                            # Process changed
                            self.logger.debug(
                                f"Process changed: {process.name} (PID: {pid})"
                            )

                            old_status = state.previous_status
                            old_cpu = state.previous_cpu

                            # Update state
                            state.previous_status = process.status
                            state.previous_cpu = process.cpu_percent
                            state.previous_memory = process.memory_mb
                            state.previous_timestamp = datetime.now()

                            # Publish PROCESS_CHANGED event
                            if self.event_bus:
                                self.event_bus.publish(
                                    ProcessEvent.PROCESS_CHANGED,
                                    pid=pid,
                                    name=process.name,
                                    old_status=old_status,
                                    new_status=process.status,
                                    old_cpu=old_cpu,
                                    new_cpu=process.cpu_percent,
                                )
                        else:
                            # No change, but make sure previous_timestamp is set
                            # so has_changed() can compare on the next pass.
                            if state.previous_timestamp is None:
                                state.previous_timestamp = datetime.now()

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    # Process may have disappeared between iterations
                    if pid is not None and pid in self._process_states:
                        # Publish PROCESS_EXITED event
                        if self.event_bus:
                            self.event_bus.publish(
                                ProcessEvent.PROCESS_EXITED,
                                pid=pid,
                                name=self._process_states[pid].name,
                            )
                        del self._process_states[pid]

            # Detect processes that no longer exist
            removed_pids = set(self._process_states.keys()) - current_pids
            for pid in removed_pids:
                # Publish PROCESS_EXITED event
                if self.event_bus:
                    self.event_bus.publish(
                        ProcessEvent.PROCESS_EXITED,
                        pid=pid,
                        name=self._process_states[pid].name,
                    )
                del self._process_states[pid]

            # Update last scan time
            self._last_scan_time = datetime.now()

        except Exception as e:
            self.logger.error(f"Error scanning processes: {e}")

    def _publish_list_updated_event(self, count: int = 0):
        """
        Publish PROCESS_LIST_UPDATED event.

        Called when the process list is fully updated (e.g., after a list_processes call).

        Args:
            count: Number of processes in the list just produced. Passed in
                   explicitly since self._cache is not populated elsewhere
                   in this class.
        """
        if self.event_bus:
            self.event_bus.publish(ProcessEvent.PROCESS_LIST_UPDATED, count=count)

    def get_process_state(self, pid: int) -> ProcessState | None:
        """
        Get the current state of a process.

        Args:
            pid: Process ID

        Returns:
            ProcessState object or None if not tracked
        """
        return self._process_states.get(pid)

    def get_all_process_states(self) -> dict[int, ProcessState]:
        """
        Get all tracked process states.

        Returns:
            Dictionary of process states
        """
        return self._process_states.copy()

    def cleanup(self):
        """
        Cleanup the process manager resources.

        Stops the background monitor thread and clears cache.
        """
        self._stop_background_monitor()
        self._cache.clear()
        self._process_states.clear()
        self.logger.info("ProcessManager cleaned up")
