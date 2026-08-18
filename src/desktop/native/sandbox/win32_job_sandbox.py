"""
Windows Job Object Sandbox Provider
Location: src/desktop/native/sandbox/win32_job_sandbox.py

Implements Windows Kernel Job Object containment with separated ExtendedLimitInformation
(process tree termination, RAM caps, fork-bomb limits) and BasicUIRestrictions.
Composed directly with WorkspaceJail for mandatory path boundary enforcement.
"""

import ctypes
import ctypes.wintypes
import logging
import os
import subprocess
from typing import Any

from .base_sandbox import BaseSandboxProvider, IsolationLevel
from .workspace_jail import WorkspaceJail

logger = logging.getLogger(__name__)

# ── Win32 Constants & Structures ──

# Job Object Limit Flags
JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000

# Job Object UI Restrictions
JOB_OBJECT_UILIMIT_HANDLES = 0x00000001
JOB_OBJECT_UILIMIT_GLOBALATOMS = 0x00000020

# Information Classes
JobObjectBasicUIRestrictions = 4
JobObjectExtendedLimitInformation = 9


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", ctypes.wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.wintypes.DWORD),
        ("SchedulingClass", ctypes.wintypes.DWORD),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryLimit", ctypes.c_size_t),
        ("PeakJobMemoryLimit", ctypes.c_size_t),
    ]


class JOBOBJECT_BASIC_UI_RESTRICTIONS(ctypes.Structure):
    _fields_ = [
        ("UIRestrictionsClass", ctypes.wintypes.DWORD),
    ]


class Win32JobSandbox(BaseSandboxProvider):
    """
    Host-level kernel sandbox using Windows Job Objects and mandatory WorkspaceJail.
    """

    def __init__(
        self,
        workspace_root: str | None = None,
        max_memory_mb: int = 2048,
        max_active_processes: int = 16,
    ):
        self._workspace_jail = WorkspaceJail(workspace_root)
        self._max_memory_mb = max_memory_mb
        self._max_active_processes = max_active_processes
        self._job_handle: int | None = None
        self._initialize_job_object()

    @property
    def isolation_level(self) -> IsolationLevel:
        return IsolationLevel.JOB_OBJECT

    @property
    def workspace_jail(self) -> WorkspaceJail:
        return self._workspace_jail

    def is_available(self) -> bool:
        return os.name == "nt"

    def _initialize_job_object(self) -> None:
        """Create and configure the Windows Job Object."""
        if not self.is_available():
            return

        try:
            # 1. Create Job Object
            kernel32 = ctypes.windll.kernel32
            job_name = f"AuraAI_JobSandbox_{os.getpid()}"
            self._job_handle = kernel32.CreateJobObjectW(None, job_name)
            if not self._job_handle:
                logger.warning("Failed to create Win32 Job Object.")
                return

            # 2. Configure Extended Limit Information (Resource & Lifecycle)
            ext_info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            ext_info.BasicLimitInformation.LimitFlags = (
                JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
                | JOB_OBJECT_LIMIT_JOB_MEMORY
            )
            ext_info.BasicLimitInformation.ActiveProcessLimit = self._max_active_processes
            ext_info.JobMemoryLimit = self._max_memory_mb * 1024 * 1024

            res1 = kernel32.SetInformationJobObject(
                self._job_handle,
                JobObjectExtendedLimitInformation,
                ctypes.byref(ext_info),
                ctypes.sizeof(ext_info),
            )
            if not res1:
                logger.warning("Failed to apply JobObjectExtendedLimitInformation.")

            # 3. Configure Basic UI Restrictions (Handle & Global Atom Isolation)
            ui_info = JOBOBJECT_BASIC_UI_RESTRICTIONS()
            ui_info.UIRestrictionsClass = (
                JOB_OBJECT_UILIMIT_HANDLES | JOB_OBJECT_UILIMIT_GLOBALATOMS
            )

            res2 = kernel32.SetInformationJobObject(
                self._job_handle,
                JobObjectBasicUIRestrictions,
                ctypes.byref(ui_info),
                ctypes.sizeof(ui_info),
            )
            if not res2:
                logger.debug("JobObjectBasicUIRestrictions returned non-zero (non-fatal).")

        except Exception as exc:
            logger.error(f"Win32JobSandbox initialization error: {exc}")

    def assign_process(self, process_handle: int) -> bool:
        """Assign a spawned process to this Job Object."""
        if not self._job_handle:
            return False
        try:
            return bool(ctypes.windll.kernel32.AssignProcessToJobObject(self._job_handle, process_handle))
        except Exception as exc:
            logger.error(f"Failed to assign process to Job Object: {exc}")
            return False

    def execute(
        self,
        command: str,
        cwd: str,
        timeout: float = 60.0,
        env: dict[str, str] | None = None,
    ) -> tuple[int, str, str]:
        """
        Execute command strictly confined by WorkspaceJail and bounded by the Job Object.
        """
        # 1. Mandatory Workspace Jail check
        valid_paths, jail_err = self._workspace_jail.validate_command_paths(command, cwd)
        if not valid_paths:
            return 1, "", f"Sandbox Workspace Jail Error: {jail_err}"

        # 2. Spawn process
        proc = subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )

        # 3. Assign process to kernel Job Object
        if self._job_handle:
            self.assign_process(int(proc._handle))

        # 4. Wait for output
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            return proc.returncode, stdout, stderr
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            return -1, stdout, f"Execution timed out after {timeout}s"

    def health_check(self) -> dict[str, Any]:
        return {
            "provider": "Win32JobSandbox",
            "available": self.is_available(),
            "isolation_level": self.isolation_level.value,
            "job_handle_active": bool(self._job_handle),
            "max_memory_mb": self._max_memory_mb,
            "max_active_processes": self._max_active_processes,
            "workspace_root": str(self._workspace_jail.workspace_root),
        }
