"""
Staging Sandbox Environment
Location: src/codeact/staging_sandbox.py

Encapsulates ephemeral staging directories, minimal environment isolation,
and OS-level containment via Windows Job Objects for CodeAct scripts.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from .models import CodeActRequest

logger = logging.getLogger(__name__)


def _find_venv_python() -> str:
    """Resolve the active virtual environment Python executable."""
    # Check if currently running within venv
    if hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    ):
        venv_exe = Path(sys.prefix) / "Scripts" / "python.exe"
        if venv_exe.exists():
            return str(venv_exe)

    # Check project root default .venv location
    cur = Path(__file__).resolve()
    for parent in cur.parents:
        cand = parent / ".venv" / "Scripts" / "python.exe"
        if cand.exists():
            return str(cand)

    return sys.executable


class StagingSandbox:
    """
    Hermetic staging workspace for CodeAct script execution.
    Creates an isolated ephemeral directory under .staging/, sets un-elevated NTFS DACLs,
    and executes untrusted scripts via RestrictedUserSandbox under AuraSandboxUser with Job Objects.
    """

    def __init__(self, request: CodeActRequest | None = None, base_dir: str | Path | None = None):
        self.request = request
        if base_dir:
            self._base_dir = Path(base_dir).resolve()
        else:
            self._base_dir = (Path.cwd() / ".staging").resolve()
        self.staging_dir: Path | None = None
        self._python_exe: str = _find_venv_python()
        self._restricted_sandbox: Any = None

    def __enter__(self) -> "StagingSandbox":
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self.staging_dir = Path(
            tempfile.mkdtemp(prefix="aura_run_", dir=self._base_dir)
        ).resolve()

        # Copy any input files into staging as read-only copies
        if self.request and self.request.input_files:
            for src_file in self.request.input_files:
                src_path = Path(src_file).resolve()
                if src_path.exists() and src_path.is_file():
                    dest_file = self.staging_dir / src_path.name
                    shutil.copy2(src_path, dest_file)
                    try:
                        os.chmod(dest_file, 0o444)
                    except Exception:
                        pass

        # Grant un-elevated Modify access to AuraSandboxUser on the ephemeral staging directory
        try:
            from src.desktop.native.sandbox.account_provisioner import grant_staging_access
            grant_staging_access(self.staging_dir)
        except Exception as exc:
            logger.warning(f"Failed to apply staging DACL grant: {exc}")

        # Initialize RestrictedUserSandbox (Fail-Closed on Windows)
        if os.name == "nt":
            try:
                from src.desktop.native.sandbox.restricted_user_sandbox import RestrictedUserSandbox

                self._restricted_sandbox = RestrictedUserSandbox(
                    workspace_root=str(self.staging_dir)
                )
                if not self._restricted_sandbox.is_available():
                    raise RuntimeError(
                        "Fail-Closed Security Invariant: RestrictedUserSandbox (AuraSandboxUser) is unavailable on this host."
                    )
            except Exception as exc:
                logger.error(f"FATAL: Failed to initialize RestrictedUserSandbox: {exc}")
                raise RuntimeError(
                    f"Fail-Closed Security Invariant: RestrictedUserSandbox failed to initialize for staging dir: {exc}"
                ) from exc

        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.staging_dir and self.staging_dir.exists():
            try:
                # Reset permissions on any read-only input files before rmtree
                for root, dirs, files in os.walk(self.staging_dir):
                    for f in files:
                        p = Path(root) / f
                        try:
                            os.chmod(p, 0o666)
                        except Exception:
                            pass
                shutil.rmtree(self.staging_dir, ignore_errors=True)
            except Exception as exc:
                logger.warning(f"Error cleaning up staging dir '{self.staging_dir}': {exc}")

    def write_script(self, code: str, filename: str = "script.py") -> Path:
        """Write Python code to a file inside the staging directory."""
        if not self.staging_dir:
            raise RuntimeError("StagingSandbox is not entered.")
        target = self.staging_dir / filename
        target.write_text(code, encoding="utf-8")
        return target

    def _build_minimal_env(self) -> dict[str, str]:
        """
        Construct a minimal environment dictionary free of API keys or host credentials.
        """
        system_root = os.environ.get("SYSTEMROOT", r"C:\Windows")
        system32 = os.path.join(system_root, "System32")
        venv_scripts = str(Path(self._python_exe).parent)

        env: dict[str, str] = {
            "SYSTEMROOT": system_root,
            "SYSTEMDRIVE": os.environ.get("SYSTEMDRIVE", "C:"),
            "PATH": f"{venv_scripts};{system32};{system_root}",
            "TEMP": str(self.staging_dir) if self.staging_dir else tempfile.gettempdir(),
            "TMP": str(self.staging_dir) if self.staging_dir else tempfile.gettempdir(),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        }
        return env

    def execute(
        self, script_path: str | Path, timeout: float = 30.0
    ) -> tuple[int, str, str, int]:
        """
        Execute a script inside the staging sandbox under the RestrictedUserSandbox with Job Object.

        Returns:
            (exit_code, stdout, stderr, duration_ms)
        """
        if not self.staging_dir:
            raise RuntimeError("StagingSandbox is not entered.")

        script_full_path = str(Path(script_path).resolve())

        if os.name == "nt":
            if not self._restricted_sandbox:
                raise RuntimeError("Fail-Closed Security Invariant: No active RestrictedUserSandbox instance found.")

            cmd = f'& "{self._python_exe}" "{script_full_path}"'
            start_time = time.perf_counter()
            exit_code, stdout, stderr = self._restricted_sandbox.execute(
                command=cmd,
                cwd=str(self.staging_dir),
                timeout=timeout,
            )
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return exit_code, stdout, stderr, duration_ms

        else:
            # POSIX fallback
            env = self._build_minimal_env()
            start_time = time.perf_counter()
            proc = subprocess.Popen(
                [self._python_exe, script_full_path],
                cwd=str(self.staging_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                exit_code = -1
                stderr = f"Execution exceeded wall-clock timeout of {timeout}s"

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return exit_code, stdout, stderr, duration_ms
