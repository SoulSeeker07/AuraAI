"""
Restricted User Sandbox Provider (Path B)
Location: src/desktop/native/sandbox/restricted_user_sandbox.py

Executes untrusted CLI commands under the security context of a dedicated
low-privilege local user (AuraSandboxUser) using Win32 CreateProcessWithLogonW
and binds child processes to kernel Job Objects.
"""

import ctypes
import ctypes.wintypes
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from .account_provisioner import AccountProvisioner, SANDBOX_USER_NAME
from .base_sandbox import BaseSandboxProvider, IsolationLevel
from .win32_job_sandbox import Win32JobSandbox

logger = logging.getLogger(__name__)

# Win32 Logon Constants
LOGON_WITH_PROFILE = 0x00000001
LOGON_NETCREDENTIALS_ONLY = 0x00000002
CREATE_NO_WINDOW = 0x08000000
STARTF_USESTDHANDLES = 0x00000100
HANDLE_FLAG_INHERIT = 0x00000001


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.wintypes.DWORD),
        ("lpReserved", ctypes.wintypes.LPWSTR),
        ("lpDesktop", ctypes.wintypes.LPWSTR),
        ("lpTitle", ctypes.wintypes.LPWSTR),
        ("dwX", ctypes.wintypes.DWORD),
        ("dwY", ctypes.wintypes.DWORD),
        ("dwXSize", ctypes.wintypes.DWORD),
        ("dwYSize", ctypes.wintypes.DWORD),
        ("dwXCountChars", ctypes.wintypes.DWORD),
        ("dwYCountChars", ctypes.wintypes.DWORD),
        ("dwFillAttribute", ctypes.wintypes.DWORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("wShowWindow", ctypes.wintypes.WORD),
        ("cbReserved2", ctypes.wintypes.WORD),
        ("lpReserved2", ctypes.c_char_p),
        ("hStdInput", ctypes.wintypes.HANDLE),
        ("hStdOutput", ctypes.wintypes.HANDLE),
        ("hStdError", ctypes.wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", ctypes.wintypes.HANDLE),
        ("hThread", ctypes.wintypes.HANDLE),
        ("dwProcessId", ctypes.wintypes.DWORD),
        ("dwThreadId", ctypes.wintypes.DWORD),
    ]


class RestrictedUserSandbox(BaseSandboxProvider):
    """
    Spawns processes under a dedicated unprivileged user token with OS NTFS DACL isolation.
    """

    def __init__(
        self,
        username: str = SANDBOX_USER_NAME,
        password: str | None = None,
        workspace_root: str | None = None,
    ):
        self._username = username
        self._password = password or os.environ.get("AURA_SANDBOX_PASSWORD", "AuraSandboxPass123!")
        self._workspace_root = Path(workspace_root or os.getcwd()).resolve()
        self._provisioner = AccountProvisioner(self._username)
        self._job_sandbox = Win32JobSandbox(workspace_root=str(self._workspace_root))


    @property
    def isolation_level(self) -> IsolationLevel:
        return IsolationLevel.RESTRICTED_USER

    def is_available(self) -> bool:
        """Available on Windows when the sandbox user account exists and a password is provided."""
        if os.name != "nt":
            return False
        return self._provisioner.account_exists() and bool(self._password)

    def set_password(self, password: str) -> None:
        """Set ephemeral session password."""
        self._password = password

    def execute(
        self,
        command: str,
        cwd: str,
        timeout: float = 60.0,
        env: dict[str, str] | None = None,
    ) -> tuple[int, str, str]:
        """
        Execute command as AuraSandboxUser via CreateProcessWithLogonW inside Job Object.
        """
        if not self.is_available():
            raise RuntimeError(
                "Fail-Closed Security Invariant: RestrictedUserSandbox is unavailable (AuraSandboxUser account missing or password unconfigured)."
            )

        advapi32 = ctypes.windll.advapi32
        kernel32 = ctypes.windll.kernel32

        # Create pipes for stdout/stderr redirection
        h_read_out, h_write_out = ctypes.wintypes.HANDLE(), ctypes.wintypes.HANDLE()
        h_read_err, h_write_err = ctypes.wintypes.HANDLE(), ctypes.wintypes.HANDLE()

        kernel32.CreatePipe(ctypes.byref(h_read_out), ctypes.byref(h_write_out), None, 0)
        kernel32.CreatePipe(ctypes.byref(h_read_err), ctypes.byref(h_write_err), None, 0)

        kernel32.SetHandleInformation(h_write_out, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT)
        kernel32.SetHandleInformation(h_write_err, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT)

        si = STARTUPINFOW()
        si.cb = ctypes.sizeof(STARTUPINFOW)
        si.dwFlags = STARTF_USESTDHANDLES
        si.hStdOutput = h_write_out
        si.hStdError = h_write_err

        import base64

        exec_cwd = str(Path(cwd).resolve())
        wrapped_command = f'Set-Location "{exec_cwd}"; {command}'
        encoded_cmd = base64.b64encode(wrapped_command.encode("utf-16le")).decode("ascii")
        cmd_line = f"powershell.exe -NoProfile -NonInteractive -EncodedCommand {encoded_cmd}"

        pi = PROCESS_INFORMATION()

        success = advapi32.CreateProcessWithLogonW(
            self._username,
            ".",
            self._password,
            LOGON_WITH_PROFILE,
            None,
            cmd_line,
            CREATE_NO_WINDOW,
            None,
            exec_cwd,
            ctypes.byref(si),
            ctypes.byref(pi),
        )

        # Close write ends in parent
        kernel32.CloseHandle(h_write_out)
        kernel32.CloseHandle(h_write_err)

        if not success:
            err_code = kernel32.GetLastError()
            kernel32.CloseHandle(h_read_out)
            kernel32.CloseHandle(h_read_err)
            return 1, "", f"CreateProcessWithLogonW failed with Win32 Error: {err_code}"

        # Assign spawned process to kernel Job Object
        self._job_sandbox.assign_process(int(pi.hProcess))

        # Wait for process completion
        timeout_ms = int(timeout * 1000)
        wait_res = kernel32.WaitForSingleObject(pi.hProcess, timeout_ms)

        exit_code = ctypes.wintypes.DWORD()
        kernel32.GetExitCodeProcess(pi.hProcess, ctypes.byref(exit_code))

        # Read captured pipes
        stdout = self._read_pipe(kernel32, h_read_out)
        stderr = self._read_pipe(kernel32, h_read_err)

        # Cleanup handles
        kernel32.CloseHandle(pi.hProcess)
        kernel32.CloseHandle(pi.hThread)
        kernel32.CloseHandle(h_read_out)
        kernel32.CloseHandle(h_read_err)

        if wait_res == 0x00000102:  # WAIT_TIMEOUT
            return -1, stdout, f"Execution timed out after {timeout}s"

        return int(exit_code.value), stdout, stderr

    def _read_pipe(self, kernel32: Any, handle: ctypes.wintypes.HANDLE) -> str:
        """Read all available bytes from pipe handle."""
        chunks = []
        buf = (ctypes.c_char * 4096)()
        bytes_read = ctypes.wintypes.DWORD()

        while True:
            res = kernel32.ReadFile(handle, buf, 4096, ctypes.byref(bytes_read), None)
            if not res or bytes_read.value == 0:
                break
            chunks.append(buf.raw[:bytes_read.value])

        raw_text = b"".join(chunks).decode("utf-8", errors="replace")
        if "#< CLIXML" in raw_text:
            import re
            lines = re.findall(r'<S S="(?:Error|Warning|verbose|debug)">([^<]+)</S>', raw_text, re.IGNORECASE)
            if lines:
                return "\n".join(lines).replace("_x000D__x000A_", "\n")
            cleaned = re.sub(r"<[^>]+>", "", raw_text).replace("#< CLIXML", "").strip()
            if cleaned:
                return cleaned
            if '<Obj S="progress"' in raw_text:
                return ""
        return raw_text


    def health_check(self) -> dict[str, Any]:
        return {
            "provider": "RestrictedUserSandbox",
            "available": self.is_available(),
            "isolation_level": self.isolation_level.value,
            "username": self._username,
            "account_exists": self._provisioner.account_exists(),
            "workspace_root": str(self._workspace_root),
        }
